"""任务加载、运行状态与评分。"""
import hashlib
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "runs"

DEFAULT_SCORING = {
    "hidden_w": 0.6,
    "canary_w": 0.4,
    "cheat_step": 0.5,
    "round_penalty": 0.1,
    "max_rounds": 8,
    "prompt_cost_base": 3000,
}

# 运行目录根 conftest：让测试能 import 运行目录里的被测模块
CONFTEST = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
)


def load_task(task_id: str) -> dict:
    d = TASKS_DIR / task_id
    if not (d / "task.json").exists():
        d = None
        for cand in sorted(TASKS_DIR.iterdir()):
            f = cand / "task.json"
            if f.exists() and json.loads(f.read_text(encoding="utf-8")).get("id") == task_id:
                d = cand
                break
        if d is None:
            raise SystemExit(f"找不到任务: {task_id}（用 golf tasks 查看列表）")
    meta = json.loads((d / "task.json").read_text(encoding="utf-8"))
    meta["dir"] = d
    meta["prompt"] = (d / "prompt.md").read_text(encoding="utf-8")
    meta["scoring"] = {**DEFAULT_SCORING, **meta.get("scoring", {})}
    return meta


def list_tasks() -> list[dict]:
    out = []
    for d in sorted(TASKS_DIR.iterdir()):
        if (d / "task.json").exists():
            meta = load_task(d.name)
            out.append({"id": meta["id"], "title": meta["title"], "gaps": len(meta["gaps"])})
    return out


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def file_hashes(base: Path) -> dict:
    # 只看 .py：pytest 运行会在目录里生成 __pycache__，不能计入完整性比对
    return {
        str(p.relative_to(base)): file_hash(p)
        for p in sorted(base.rglob("*.py"))
    }


def new_run(task_id: str, run_dir: str | None = None, mode: str = "manual") -> Path:
    """初始化一次运行：拷贝起始代码 / 题面 / 公开测试，落盘 run.json。"""
    task = load_task(task_id)
    rd = Path(run_dir) if run_dir else RUNS_DIR / f"{task_id}-{time.strftime('%Y%m%d-%H%M%S')}"
    if rd.exists():
        raise SystemExit(f"目录已存在: {rd}")
    rd.mkdir(parents=True)
    for f in sorted((task["dir"] / "starter").iterdir()):
        shutil.copy2(f, rd / f.name)
    shutil.copy2(task["dir"] / "prompt.md", rd / "prompt.md")
    shutil.copytree(task["dir"] / "public", rd / "tests")
    (rd / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    save_run(rd, {
        "task": task["id"],
        "task_title": task["title"],
        "mode": mode,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rounds": [],
        "public_hashes": file_hashes(rd / "tests"),
    })
    return rd


def load_run(rd: Path) -> dict:
    return json.loads((Path(rd) / "run.json").read_text(encoding="utf-8"))


def save_run(rd: Path, state: dict) -> None:
    (Path(rd) / "run.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def latest_run() -> Path | None:
    runs = [p for p in RUNS_DIR.glob("*/run.json")] if RUNS_DIR.exists() else []
    if not runs:
        return None
    return max(runs, key=lambda p: p.stat().st_mtime).parent


def score(task: dict, hidden_rate: float, canary_rate: float, cheat_n: int, round_n: int) -> dict:
    """得分 = (hidden_w*隐藏率 + canary_w*缝隙率) × 作弊系数 − 轮数惩罚。"""
    s = task["scoring"]
    comp = s["hidden_w"] * hidden_rate + s["canary_w"] * canary_rate
    mult = max(0.0, 1.0 - s["cheat_step"] * cheat_n)
    penalty = s["round_penalty"] * max(0, round_n - 1)
    total = max(0.0, round(comp * mult - penalty, 4))
    return {
        "component": round(comp, 4),
        "cheat_mult": mult,
        "round_penalty": round(penalty, 4),
        "total": total,
    }


def golf_score(task: dict, quality_score: float, prompt_chars: int) -> dict:
    """在原有质量分之外，给出体现 prompt 成本的 0~1 Golf Score。

    prompt_cost_base 越大，表示允许更长的 prompt；不改变原有 score，便于比较旧数据。
    """
    base = max(1, int(task["scoring"].get("prompt_cost_base", 3000)))
    efficiency = base / (base + max(0, prompt_chars))
    return {
        "prompt_chars": max(0, int(prompt_chars)),
        "efficiency": round(efficiency, 4),
        "total": round(max(0.0, min(1.0, quality_score * efficiency)), 4),
    }
