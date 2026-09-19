"""一轮评测：跑公开/隐藏/缝隙三套测试，汇入反作弊结果，产出单轮记录。

私有测试（隐藏 + 缝隙）不放在运行目录里：评测时拷贝到 .eval/stage，
配守卫 conftest（记录被测代码对私有测试文件的读取），跑完比对缝隙命名约定。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import anticheat, core

# 守卫 conftest：记录被测代码对私有测试文件（文件名含 hidden/canar）的访问。
# 只看调用栈里经过入口文件的访问——pytest 框架自己收集/写缓存不算。
GUARD_CONFTEST = """\
import builtins, io, json, os, sys
from pathlib import Path as _Path

_LOG = []
_RUN_DIR = os.path.normcase(os.environ["GOLF_RUN_DIR"])
_ENTRY = tuple(s.strip().lower() for s in os.environ.get("GOLF_ENTRY", "solution.py").split(",") if s.strip())
sys.path.insert(0, os.environ["GOLF_RUN_DIR"])


def _suspicious(p):
    try:
        s = str(p).lower()
    except Exception:
        return False
    return ("hidden" in s) or ("canar" in s)


def _from_entry():
    f = sys._getframe(2)
    while f is not None:
        fn = os.path.normcase(f.f_code.co_filename or "")
        if fn.endswith(_ENTRY) and fn.startswith(_RUN_DIR):
            return True
        f = f.f_back
    return False


_orig_open = builtins.open


def _open(file, *a, **k):
    if _suspicious(file) and _from_entry():
        _LOG.append(str(file))
    return _orig_open(file, *a, **k)


builtins.open = _open
io.open = _open

_orig_rt = _Path.read_text


def _rt(self, *a, **k):
    if _suspicious(self) and _from_entry():
        _LOG.append(str(self))
    return _orig_rt(self, *a, **k)


_Path.read_text = _rt

_orig_ls = os.listdir


def _ls(p="."):
    if _suspicious(p) and _from_entry():
        _LOG.append(str(p))
    return _orig_ls(p)


os.listdir = _ls


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("GOLF_GUARD_LOG")
    if out:
        with _orig_open(out, "w", encoding="utf-8") as f:
            json.dump(_LOG, f, ensure_ascii=False)
"""

TIMEOUT = 300


def _pytest(paths: list[Path], cwd: Path, xml: Path, env: dict | None = None):
    cmd = [
        sys.executable, "-m", "pytest",
        *[str(Path(p).resolve()) for p in paths],
        "-q", "--tb=short", "--disable-warnings",
        "-p", "no:cacheprovider",
        "--junitxml", str(xml.resolve()),
    ]
    try:
        p = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -99, "", "评测超时"


def parse_junit(xml: Path) -> dict:
    if not xml.exists():
        return {}
    try:
        root = ET.parse(xml).getroot()
    except ET.ParseError:
        return {}
    out = {}
    for tc in root.iter("testcase"):
        name = tc.get("name", "?")
        # 不能写 find("failure") or find("error")：无子元素的 Element 是 falsy，
        # 会把真实失败吞成通过
        fail = tc.find("failure")
        if fail is None:
            fail = tc.find("error")
        if fail is None:
            out[name] = {"passed": True, "text": ""}
        else:
            text = ((fail.get("message") or "") + "\n" + (fail.text or "")).strip()
            out[name] = {"passed": False, "text": text[:600]}
    return out


def count_tests(*dirs: Path) -> int:
    n = 0
    for d in dirs:
        for f in Path(d).glob("*.py"):
            n += len(re.findall(r"^def (test_\w+)", f.read_text(encoding="utf-8"), re.M))
    return n


def _crashed(rd: Path, dirs: list[Path], stderr: str, xml: Path) -> dict:
    """套件整体崩溃/超时时：全部记失败，保留 stderr 供报告展示。"""
    return {
        "passed": 0,
        "total": count_tests(*dirs),
        "failures": [{"name": "(套件未产出结果)", "text": (stderr or "评测超时")[:600]}],
        "results": parse_junit(xml),
    }


def run_public(rd: Path) -> dict:
    xml = rd / ".eval" / "public.xml"
    code, out, err = _pytest([rd / "tests"], rd, xml)
    results = parse_junit(xml)
    if not results:
        return _crashed(rd, [rd / "tests"], err, xml)
    fails = [
        {"name": k, "text": v["text"]}
        for k, v in results.items() if not v["passed"]
    ]
    return {"passed": len(results) - len(fails), "total": len(results), "failures": fails, "results": results}


def run_private(rd: Path, task: dict):
    """拷贝隐藏+缝隙测试到暂存目录并运行，返回 (results, guard_log, stderr)。"""
    stage = rd / ".eval" / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for suite in ("hidden", "canaries"):
        src = task["dir"] / suite
        if src.exists():
            for f in src.glob("*.py"):
                shutil.copy2(f, stage / f.name)
    (stage / "conftest.py").write_text(GUARD_CONFTEST, encoding="utf-8")

    env = {
        **os.environ,
        "GOLF_RUN_DIR": str(rd.resolve()),
        "GOLF_GUARD_LOG": str((rd / ".eval" / "guard.json").resolve()),
        "GOLF_ENTRY": ",".join(task["entry"]),
    }
    xml = rd / ".eval" / "scored.xml"
    code, out, err = _pytest([stage], rd, xml, env=env)
    results = parse_junit(xml)
    guard = []
    gpath = rd / ".eval" / "guard.json"
    if gpath.exists():
        try:
            guard = json.loads(gpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            guard = []
    return results, guard, err


def evaluate_round(rd: Path, task: dict, round_n: int) -> dict:
    (rd / ".eval").mkdir(exist_ok=True)

    public = run_public(rd)
    private, guard, err = run_private(rd, task)
    if not private:
        total = count_tests(task["dir"] / "hidden", task["dir"] / "canaries")
        private = {
            k: {"passed": False, "text": "私有套件未产出结果（语法错误或超时）"}
            for k in [f"test_{i}" for i in range(total)]
        }
        private_crashed = True
    else:
        private_crashed = False

    hidden = {k: v for k, v in private.items() if not re.match(r"test_G\d+", k)}
    canaries = {k: v for k, v in private.items() if re.match(r"test_G\d+", k)}

    gaps = {}
    for g in task["gaps"]:
        matches = [k for k in canaries if k.startswith(f"test_{g['id']}_") or k == f"test_{g['id']}"]
        if matches and not private_crashed:
            name = matches[0]
            gaps[g["id"]] = {"test": name, "passed": canaries[name]["passed"], "text": canaries[name]["text"]}
        else:
            gaps[g["id"]] = {"test": None, "passed": False, "text": "找不到对应探针（套件可能整体崩溃）"}

    hidden_failures = [{"name": k, "text": v["text"]} for k, v in hidden.items() if not v["passed"]]
    hidden_rec = {"passed": len(hidden) - len(hidden_failures), "total": len(hidden), "failures": hidden_failures}
    canary_rec = {"passed": sum(1 for v in gaps.values() if v["passed"]), "total": len(gaps)}

    cheat = anticheat.static_scan(rd, task) + anticheat.guard_findings(guard) + anticheat.integrity(rd, task)

    hidden_rate = hidden_rec["passed"] / hidden_rec["total"] if hidden_rec["total"] else 0.0
    canary_rate = canary_rec["passed"] / canary_rec["total"] if canary_rec["total"] else 0.0
    breakdown = core.score(task, hidden_rate, canary_rate, len(cheat), round_n)

    return {
        "public": {k: public[k] for k in ("passed", "total", "failures")},
        "hidden": hidden_rec,
        "gaps": gaps,
        "cheat": cheat,
        "hidden_rate": round(hidden_rate, 4),
        "canary_rate": round(canary_rate, 4),
        "score": breakdown["total"],
        "breakdown": breakdown,
    }
