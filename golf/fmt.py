"""终端输出辅助。"""
import sys
from pathlib import Path

from . import core

MARK = {"stable": "一直稳", "fixed": "已堵住", "open": "仍敞开"}


def setup():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def resolve_dir(args_dir: str | None) -> Path:
    if args_dir:
        return Path(args_dir)
    latest = core.latest_run()
    if latest is None:
        raise SystemExit("找不到运行目录，请先 golf init <task_id> 创建")
    return latest


def feedback(rec: dict, prev: dict | None) -> None:
    print(f"\n—— 第 {rec['n']} 轮 ——")
    p, h = rec["public"], rec["hidden"]
    print(f"公开测试  {p['passed']}/{p['total']}")
    for f in p["failures"][:8]:
        print(f"  失败: {f['name']}")
    if len(p["failures"]) > 8:
        print(f"  ...另有 {len(p['failures']) - 8} 条失败")
    print(f"隐藏测试  {h['passed']}/{h['total']}   （计分，不给看细节）")
    gaps = rec["gaps"]
    closed = sum(1 for v in gaps.values() if v["passed"])
    line = f"缝隙地图  {closed}/{len(gaps)} 已堵"
    if prev and prev.get("gaps"):
        newly = sum(1 for gid, v in gaps.items() if v["passed"] and not prev["gaps"].get(gid, {}).get("passed"))
        if newly:
            line += f"（本轮新堵 {newly} 条）"
    print(line)
    if rec["cheat"]:
        print(f"作弊扫描  发现 {len(rec['cheat'])} 处异常：")
        for c in rec["cheat"]:
            print(f"  [{c['kind']}] {c['detail']}")
    else:
        print("作弊扫描  未发现异常")
    if rec.get("prompt_chars_total") is not None:
        print(f"Prompt 成本  {rec["prompt_chars"]} 字符（累计 {rec["prompt_chars_total"]}）")
    if rec.get("golf_score"):
        gs = rec["golf_score"]
        print(f"Golf Score  {gs["total"]:.2f}   效率系数 {gs["efficiency"]:.2f}")
    b = rec["breakdown"]
    print(
        f"本轮得分  {b['total']:.2f}  "
        f"= 基础 {b['component']:.2f} × 作弊系数 {b['cheat_mult']:.2f} − 轮数罚 {b['round_penalty']:.1f}"
    )


def gap_states(state: dict, task: dict) -> dict:
    """每条缝隙的跨轮状态: stable / fixed / open。"""
    out = {}
    for g in task["gaps"]:
        hist = [
            bool(r["gaps"][g["id"]]["passed"])
            for r in state["rounds"]
            if r.get("gaps") and g["id"] in r["gaps"]
        ]
        if not hist:
            st, fixed_at = "open", None
        elif all(hist):
            st, fixed_at = "stable", None
        elif hist[-1]:
            st, fixed_at = "fixed", hist.index(True) + 1
        else:
            st, fixed_at = "open", None
        out[g["id"]] = {"state": st, "hist": hist, "fixed_at": fixed_at, "title": g["title"]}
    return out
