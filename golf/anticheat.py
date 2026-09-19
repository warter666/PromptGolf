"""反作弊：静态 AST 扫描 + 运行时文件访问守卫 + 资产完整性。

三层各自的边界（已知局限，README 有说明）：
- 静态层抓"针对公开测试字面量特判"，抓不到语义等价的改写；
- 守卫层抓"运行时读私有测试文件"，抓不到对 sys.modules 的内省；
- 完整性层抓"改测试/改提供资产"，按字节哈希比对。
"""
import ast
from pathlib import Path

from . import core

SUSPICIOUS_READ = ("test", "canar", "hidden")


def static_scan(rd: Path, task: dict) -> list[dict]:
    """扫描入口文件：禁用导入、与公开测试字面量的比较、可疑文件读取。"""
    pub_literals = set()
    for f in (rd / "tests").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                v = node.value
                if isinstance(v, str) and len(v) >= 4:
                    pub_literals.add(v)
                elif isinstance(v, float):
                    pub_literals.add(v)

    findings = []
    for name in task["entry"]:
        f = rd / name
        if not f.exists():
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for m in mods:
                    if m.split(".")[0] in {"pytest", "unittest", "test", "tests", "conftest"}:
                        findings.append({
                            "kind": "导入禁用模块",
                            "detail": f"{name} 第 {node.lineno} 行导入了 {m}",
                            "line": node.lineno,
                        })
            if isinstance(node, ast.Compare):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and sub.value in pub_literals:
                        findings.append({
                            "kind": "疑似特判已知用例",
                            "detail": f"{name} 第 {node.lineno} 行在比较中使用了公开测试的样例值 {sub.value!r}",
                            "line": node.lineno,
                        })
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"exec", "eval", "compile"}:
                    findings.append({
                        "kind": "动态执行",
                        "detail": f"{name} 第 {node.lineno} 行使用了 {node.func.id}()",
                        "line": node.lineno,
                    })
                elif node.func.id == "open":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if any(k in arg.value.lower() for k in SUSPICIOUS_READ):
                                findings.append({
                                    "kind": "读取测试文件",
                                    "detail": f"{name} 第 {node.lineno} 行 open 了 {arg.value!r}",
                                    "line": node.lineno,
                                })

    # 去重
    seen, out = set(), []
    for x in findings:
        key = (x["kind"], x["detail"])
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def guard_findings(guard_log: list[str]) -> list[dict]:
    """运行时守卫日志：被测代码在测试期间打开了私有测试文件（按路径去重）。"""
    out, seen = [], set()
    for p in guard_log:
        if p in seen:
            continue
        seen.add(p)
        out.append({
            "kind": "运行时访问私有测试",
            "detail": f"测试执行期间被测代码读取了私有测试文件: {p}",
            "line": 0,
        })
    return out


def integrity(rd: Path, task: dict) -> list[dict]:
    """公开测试与任务提供资产是否被改动。"""
    findings = []
    state = core.load_run(rd)
    if core.file_hashes(rd / "tests") != state.get("public_hashes"):
        findings.append({
            "kind": "公开测试被改动",
            "detail": "tests/ 目录与初始时不一致——公开测试是需求的一部分，不许改",
            "line": 0,
        })
    for name in task.get("provided", []):
        cur = rd / name
        orig = task["dir"] / "starter" / name
        if not cur.exists() or core.file_hash(cur) != core.file_hash(orig):
            findings.append({
                "kind": "改动提供的资产",
                "detail": f"{name} 与原始文件不一致——数据/工具以原始文件为准，应适配而不是改它",
                "line": 0,
            })
    return findings
