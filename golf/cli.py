"""PromptGolf 命令行入口。"""
import argparse
import time
from pathlib import Path

from . import core, fmt, report


def cmd_tasks(_args):
    rows = core.list_tasks()
    if not rows:
        print("tasks/ 下还没有任务")
        return
    for t in rows:
        print(f"{t['id']:<22} {t['title']}（{t['gaps']} 条缝隙）")


def cmd_init(args):
    rd = core.new_run(args.task, args.dir, mode=args.mode)
    task = core.load_task(args.task)
    print(f"任务: {task['title']}（{len(task['gaps'])} 条缝隙）")
    print(f"运行目录: {rd}")
    print("""
下一步:
  1. 阅读运行目录里的 prompt.md —— 这就是你手里的全部需求（它故意有留白）
  2. 用你顺手的任意 AI agent 修改入口文件，你只能通过 prompt 引导它
  3. 每引导一轮，记录一次: golf round "你这一轮给出的 prompt"
  4. 结束后生成可视化报告: golf report --dir <运行目录>

规则: 公开测试只是引导线，评分看隐藏测试与缝隙；不许改 tests/ 与任务提供的资产。""")


def cmd_round(args):
    fmt.setup()
    rd = fmt.resolve_dir(args.dir)
    state = core.load_run(rd)
    task = core.load_task(state["task"])
    s = task["scoring"]
    if len(state["rounds"]) >= s["max_rounds"]:
        raise SystemExit(f"已达最大轮数 {s['max_rounds']}，请 golf report 收尾")
    n = len(state["rounds"]) + 1

    # 快照本轮提交的入口文件
    hist = rd / "history" / f"round-{n}"
    hist.mkdir(parents=True, exist_ok=True)
    for name in task["entry"]:
        src = rd / name
        if src.exists():
            (hist / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    from . import evaluate
    rec = evaluate.evaluate_round(rd, task, n)
    rec["n"] = n
    rec["prompt"] = args.prompt
    rec["prompt_chars"] = len(args.prompt)
    previous_chars = sum(int(r.get("prompt_chars", len(r.get("prompt", "")))) for r in state["rounds"])
    rec["prompt_chars_total"] = previous_chars + rec["prompt_chars"]
    rec["golf_score"] = core.golf_score(task, rec["score"], rec["prompt_chars_total"])
    rec["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["rounds"].append(rec)
    core.save_run(rd, state)
    fmt.feedback(rec, state["rounds"][n - 2] if n >= 2 else None)
    print("\n继续引导，或 golf report 生成可视化报告")


def cmd_status(args):
    fmt.setup()
    rd = fmt.resolve_dir(args.dir)
    state = core.load_run(rd)
    task = core.load_task(state["task"])
    print(f"任务: {state['task_title']} · 模式 {state['mode']} · 已用 {len(state['rounds'])} 轮")
    if not state["rounds"]:
        print("还没有轮次记录")
        return
    rec = state["rounds"][-1]
    fmt.feedback(rec, state["rounds"][-2] if len(state["rounds"]) >= 2 else None)
    if args.reveal:
        print("\n缝隙明细（练习模式）:")
        for gid, info in fmt.gap_states(state, task).items():
            mark = fmt.MARK[info["state"]]
            if info["state"] == "fixed":
                mark += f"（第 {info['fixed_at']} 轮）"
            print(f"  {gid} {info['title']}: {mark}")


def cmd_report(args):
    fmt.setup()
    rd = fmt.resolve_dir(args.dir)
    out = report.build(rd)
    print(f"报告已生成: {out.resolve()}")
    print("用浏览器打开即可（单文件，可直接发给别人）")


def cmd_auto(args):
    fmt.setup()
    from . import auto
    auto.run(args.task, rounds=args.rounds, run_dir=args.dir, model=args.model, base=args.base, benchmark=args.benchmark)


def main():
    ap = argparse.ArgumentParser(
        prog="golf",
        description="PromptGolf —— 用 prompt 引导模型完成任务的可视化评测场",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tasks", help="列出任务").set_defaults(fn=cmd_tasks)

    p = sub.add_parser("init", help="初始化一次运行")
    p.add_argument("task", help="任务 id（见 golf tasks）")
    p.add_argument("--dir", help="运行目录（默认 runs/<task>-<时间戳>）")
    p.add_argument("--mode", default="manual", choices=["manual", "auto", "benchmark"], help="运行模式：manual/auto/benchmark")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("round", help="记录一轮：快照 + 评测 + 反馈")
    p.add_argument("prompt", help="你这一轮给模型的引导 prompt")
    p.add_argument("--dir", help="运行目录（默认最近一次）")
    p.set_defaults(fn=cmd_round)

    p = sub.add_parser("status", help="查看当前状态")
    p.add_argument("--dir", help="运行目录（默认最近一次）")
    p.add_argument("--reveal", action="store_true", help="练习模式：显示每条缝隙的明细")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("report", help="生成 HTML 可视化报告")
    p.add_argument("--dir", help="运行目录（默认最近一次）")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("auto", help="自动模式：LLM 只靠公开测试反馈迭代作答")
    p.add_argument("task", help="任务 id")
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--benchmark", action="store_true", help="公开测试全过后仍继续到指定轮数，用于基准评测")
    p.add_argument("--dir", help="运行目录")
    p.add_argument("--model", help="模型名（默认取 GOLF_MODEL）")
    p.add_argument("--base", help="OpenAI 兼容接口地址（默认取 GOLF_API_BASE）")
    p.set_defaults(fn=cmd_auto)

    args = ap.parse_args()
    args.fn(args)
