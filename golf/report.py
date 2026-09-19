"""生成自包含 HTML 可视化报告：缝隙地图 + 逐轮曲线 + 轮次日志。

纯手写 SVG/CSS，无第三方依赖，单文件可直接发给别人看。
"""
import html
import time
from pathlib import Path

from . import core, fmt

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--tx:#1f2328;--sub:#656d76;--line:#e4e7ec;
--green:#16a34a;--blue:#2563eb;--red:#dc2626;--amber:#d97706}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.65 "Segoe UI",system-ui,"Microsoft YaHei",sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:32px 20px 60px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:30px 0 8px;border-left:4px solid var(--blue);padding-left:8px}
.sub{color:var(--sub);font-size:12.5px;margin:0 0 12px}
.meta{color:var(--sub);font-size:13px}
.top{display:flex;gap:14px;margin-top:20px;flex-wrap:wrap;align-items:stretch}
.donut{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 18px;text-align:center}
.donut .label{font-size:12px;color:var(--sub);margin-top:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;flex:1;min-width:320px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.card .v{font-size:22px;font-weight:600}
.card .k{font-size:12px;color:var(--sub)}
.replay{display:grid;gap:14px}.replay-round{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.replay-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.round-tag{font-weight:700}.replay-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.replay-box{border:1px solid var(--line);border-radius:8px;padding:10px}.replay-box .k{font-size:11px;color:var(--sub);text-transform:uppercase;letter-spacing:.4px}.replay-box pre{white-space:pre-wrap;max-height:180px;overflow:auto;margin:6px 0 0;background:#f6f8fa;padding:8px;border-radius:6px;font-size:11.5px}.metric-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.metric{padding:4px 9px;border-radius:99px;background:#f0f2f5;font-size:12px}@media(max-width:700px){.replay-grid{grid-template-columns:1fr}}\n.map{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-left-width:4px;border-radius:8px;padding:12px 14px}
.tile.stable{border-left-color:var(--green)}
.tile.fixed{border-left-color:var(--blue)}
.tile.open{border-left-color:var(--red)}
.gid{font-weight:700;font-size:12px;color:var(--sub);letter-spacing:.5px}
.gtitle{margin:1px 0 7px;font-size:15px;font-weight:600}
.badge{display:inline-block;font-size:11px;padding:1px 9px;border-radius:99px;color:#fff}
.stable .badge{background:var(--green)}
.fixed .badge{background:var(--blue)}
.open .badge{background:var(--red)}
.hist{margin:9px 0 2px}
.hist span{display:inline-block;min-width:34px;height:20px;line-height:20px;text-align:center;font-size:11px;color:#fff;border-radius:4px;margin-right:4px}
.hist .p{background:var(--green)}
.hist .f{background:var(--red)}
.tile details{margin-top:6px;font-size:12.5px;color:var(--sub)}
.tile summary{cursor:pointer;color:var(--blue)}
.tile p{margin:6px 0}
.tile pre{background:#0d1117;color:#c9d1d9;padding:8px 10px;border-radius:6px;overflow:auto;font-size:11px;max-height:190px;white-space:pre-wrap}
.legend{display:flex;gap:16px;font-size:12px;color:var(--sub);margin:4px 0 8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden;font-size:13px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f0f2f5;font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:none}
td details summary{cursor:pointer;color:var(--blue);font-size:12px}
td pre{white-space:pre-wrap;font-size:11.5px;background:#f6f8fa;padding:6px 8px;border-radius:6px;max-width:540px;margin:6px 0 0}
.note{background:#ecfdf3;border:1px solid #bbf7d0;color:#166534;border-radius:8px;padding:10px 14px;font-size:13px}
.warnbox{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;border-radius:8px;padding:10px 14px;font-size:13px}
.warnbox ul{margin:6px 0 0;padding-left:18px}
.warnbox li{margin:4px 0}
footer{margin-top:40px;color:var(--sub);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
code{background:#eef0f3;border-radius:4px;padding:0 5px;font-size:12.5px}
"""

COLORS = {"score": "#2563eb", "hidden": "#16a34a", "canary": "#d97706"}


def _chart(series: dict, n: int) -> str:
    W, H, P = 680, 220, 36
    out = [f'<svg viewBox="0 0 {W} {H}" style="width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px">']
    for fy in (0, 0.25, 0.5, 0.75, 1.0):
        y = H - P - fy * (H - 2 * P)
        out.append(f'<line x1="{P}" y1="{y:.0f}" x2="{W - P}" y2="{y:.0f}" stroke="#eef0f3"/>')
        out.append(f'<text x="{P - 7}" y="{y + 4:.0f}" font-size="10" fill="#9aa1ab" text-anchor="end">{fy:.2f}</text>')
    for i in range(n):
        x = P + (i * (W - 2 * P) / (n - 1) if n > 1 else 0)
        out.append(f'<text x="{x:.0f}" y="{H - 12}" font-size="10" fill="#9aa1ab" text-anchor="middle">R{i + 1}</text>')
    for key, vals in series.items():
        c = COLORS[key]
        pts = []
        for i, v in enumerate(vals):
            x = P + (i * (W - 2 * P) / (n - 1) if n > 1 else 0)
            y = H - P - min(max(v, 0.0), 1.0) * (H - 2 * P)
            pts.append((x, y))
        if n > 1:
            pl = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            out.append(f'<polyline points="{pl}" fill="none" stroke="{c}" stroke-width="2"/>')
        for x, y in pts:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3.5" fill="{c}"/>')
    out.append("</svg>")
    return "".join(out)


def _donut(score: float) -> str:
    pct = max(0.0, min(score, 1.0))
    r = 38
    c = 2 * 3.14159265 * r
    dash = pct * c
    color = "#16a34a" if score >= 0.8 else "#d97706" if score >= 0.5 else "#dc2626"
    return (
        f'<svg viewBox="0 0 110 110" style="width:132px">'
        f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="#e8ebef" stroke-width="11"/>'
        f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="{color}" stroke-width="11" '
        f'stroke-dasharray="{dash:.1f} {c - dash:.1f}" transform="rotate(-90 55 55)" stroke-linecap="round"/>'
        f'<text x="55" y="53" text-anchor="middle" font-size="20" font-weight="600" fill="#1f2328">{score:.2f}</text>'
        f'<text x="55" y="69" text-anchor="middle" font-size="9" fill="#656d76">满分 1.0</text></svg>'
    )


def _norm(r: dict) -> dict:
    raw_gaps = r.get("gaps") or {}
    gp = sum(1 for v in raw_gaps.values() if v.get("passed"))
    gt = len(raw_gaps)
    return {
        "n": r.get("n", "?"),
        "prompt": r.get("prompt", ""),
        "cheat": r.get("cheat", []),
        "score": r.get("score", 0.0),
        "golf_score": r.get("golf_score") or {},
        "prompt_chars": r.get("prompt_chars", len(r.get("prompt", ""))),
        "prompt_chars_total": r.get("prompt_chars_total", 0),
        "public": r.get("public") or {"passed": 0, "total": 0, "failures": []},
        "hidden": r.get("hidden") or {"passed": 0, "total": 0, "failures": []},
        # gaps 统一成汇总 + 明细两份，图表用汇总，地图明细用 detail
        "gaps": {"passed": gp, "total": gt, "detail": raw_gaps},
    }


def build(rd: Path) -> Path:
    rd = Path(rd)
    state = core.load_run(rd)
    task = core.load_task(state["task"])
    rounds = [_norm(r) for r in state["rounds"]]
    states = fmt.gap_states(state, task)
    final = rounds[-1] if rounds else None

    e = html.escape
    parts = []
    parts.append(f'<!doctype html><html lang="zh"><head><meta charset="utf-8">')
    parts.append(f'<title>{e(state["task_title"])} · PromptGolf 报告</title><style>{CSS}</style></head><body><div class="wrap">')
    parts.append(f'<h1>{e(state["task_title"])} <span style="font-weight:400;color:var(--sub)">· 评测报告</span></h1>')
    parts.append(
        f'<div class="meta">任务 <code>{e(state["task"])}</code> · 模式 {e(state.get("mode", "manual"))} · '
        f'{len(rounds)} 轮 · {e(state.get("created", ""))}</div>'
    )

    # 顶部：得分环 + 统计卡
    score = final["score"] if final else 0.0
    closed = sum(1 for s in states.values() if s["state"] != "open")
    parts.append('<div class="top">')
    parts.append(f'<div class="donut">{_donut(score)}<div class="label">最终质量分</div></div>')
    parts.append('<div class="cards">')
    if final:
        parts.append(f'<div class="card"><div class="v">{final["hidden"]["passed"]}/{final["hidden"]["total"]}</div><div class="k">隐藏测试（最后一轮）</div></div>')
    parts.append(f'<div class="card"><div class="v">{closed}/{len(states)}</div><div class="k">缝隙已堵住</div></div>')
    cheat_n = sum(len(r["cheat"]) for r in rounds)
    parts.append(f'<div class="card"><div class="v" style="color:{"var(--red)" if cheat_n else "var(--green)"}">{cheat_n}</div><div class="k">作弊发现</div></div>')
    parts.append(f'<div class="card"><div class="v">{len(rounds)}</div><div class="k">使用轮数</div></div>')
    if final and final["golf_score"]:
        parts.append(f'<div class="card"><div class="v">{final["golf_score"].get("total", 0):.2f}</div><div class="k">最终 Golf Score</div></div>')
    parts.append('</div></div>')

    # 缝隙地图
    parts.append('<h2>缝隙地图</h2>')
    parts.append('<p class="sub">每格是题面里刻意留白的一条缝。模型在留白处做了未声明的假设，就会在对应格留下记录；绿=从第一轮就稳，蓝=中途掉出去又爬回来，红=直到最后仍敞开。点开看每格的留白点、出题人认定的解释与失败详情。</p>')
    parts.append('<div class="map">')
    for g in task["gaps"]:
        s = states[g["id"]]
        badge = {"stable": "一直稳", "fixed": f"第 {s['fixed_at']} 轮堵住", "open": "仍敞开"}[s["state"]]
        hist = "".join(
            f'<span class="{"p" if ok else "f"}" title="第 {i + 1} 轮">R{i + 1}</span>'
            for i, ok in enumerate(s["hist"])
        ) or '<span style="color:var(--sub)">尚无记录</span>'
        last_fail = ""
        for r in reversed(rounds):
            ginfo = r["gaps"]["detail"].get(g["id"])
            if ginfo and not ginfo["passed"] and ginfo.get("text"):
                last_fail = ginfo["text"]
                break
        fail_html = f"<pre>{e(last_fail)}</pre>" if last_fail else ""
        parts.append(
            f'<div class="tile {s["state"]}"><div class="gid">{e(g["id"])}</div>'
            f'<div class="gtitle">{e(g["title"])}</div><span class="badge">{badge}</span>'
            f'<div class="hist">{hist}</div><details><summary>这条缝是什么</summary>'
            f'<p><b>留白:</b> {e(g["hint"])}</p><p><b>认定:</b> {e(g["intent"])}</p>{fail_html}</details></div>'
        )
    parts.append('</div>')

    # Prompt Replay：把每一轮的 prompt → 评测结果串成一条可回放轨迹
    parts.append('<h2>Prompt Replay</h2>')
    parts.append('<p class="sub">从第一轮开始回放：你给了模型什么上下文、模型经过评测后暴露了哪些问题，以及下一轮 prompt 的成本。这个视图强调“prompt → 反馈 → 下一次 prompt”的闭环。</p>')
    parts.append('<div class="replay">')
    for i, r in enumerate(rounds):
        gs = r["golf_score"]
        g = r["gaps"]
        parts.append(
            f'<div class="replay-round"><div class="replay-head"><span class="round-tag">R{r["n"]}</span>'
            f'<span class="metric">质量分 {r["score"]:.2f}</span></div>'
            f'<div class="replay-grid">'
            f'<div class="replay-box"><div class="k">Prompt</div><pre>{e(r["prompt"])}</pre></div>'
            f'<div class="replay-box"><div class="k">评测结果</div>'
            f'<div class="metric-row"><span class="metric">公开 {r["public"]["passed"]}/{r["public"]["total"]}</span>'
            f'<span class="metric">隐藏 {r["hidden"]["passed"]}/{r["hidden"]["total"]}</span>'
            f'<span class="metric">缝隙 {g["passed"]}/{g["total"]}</span>'
            f'<span class="metric">作弊 {len(r["cheat"])}</span></div>'
            f'<p class="sub">Prompt 成本 {r["prompt_chars"]} 字符 · 累计 {r["prompt_chars_total"]} 字符'
            + (f' · Golf Score {gs.get("total", 0):.2f} · 效率 {gs.get("efficiency", 0):.2f}' if gs else '')
            + '</p></div></div></div>'
        )
        if i < len(rounds) - 1:
            parts.append('<div style="text-align:center;color:var(--sub);font-size:12px">↓ 下一轮 prompt</div>')
    parts.append('</div>')

    # 逐轮曲线
    parts.append('<h2>逐轮曲线</h2>')
    parts.append(
        '<div class="legend">'
        '<span><i style="background:#2563eb"></i>总得分</span>'
        '<span><i style="background:#16a34a"></i>隐藏测试通过率</span>'
        '<span><i style="background:#d97706"></i>缝隙堵住率</span></div>'
    )
    if rounds:
        n = len(rounds)
        series = {
            "score": [r["score"] for r in rounds],
            "hidden": [r["hidden"]["passed"] / r["hidden"]["total"] if r["hidden"]["total"] else 0 for r in rounds],
            "canary": [r["gaps"]["passed"] / r["gaps"]["total"] if r["gaps"]["total"] else 0 for r in rounds],
        }
        parts.append(_chart(series, n))
    else:
        parts.append('<p class="sub">尚无轮次记录</p>')

    # 轮次日志
    parts.append('<h2>轮次日志</h2>')
    parts.append('<table><tr><th>轮</th><th>引导 prompt</th><th>公开</th><th>隐藏</th><th>缝隙</th><th>作弊</th><th>得分</th></tr>')
    for r in rounds:
        prompt = e(r["prompt"])
        short = e(r["prompt"][:46] + ("…" if len(r["prompt"]) > 46 else ""))
        g = r.get("gaps") or {}
        parts.append(
            f'<tr><td>{r["n"]}</td>'
            f'<td><details><summary>{short}</summary><pre>{prompt}</pre></details></td>'
            f'<td>{r["public"]["passed"]}/{r["public"]["total"]}</td>'
            f'<td>{r["hidden"]["passed"]}/{r["hidden"]["total"]}</td>'
            f'<td>{g.get("passed", 0)}/{g.get("total", 0)}</td>'
            f'<td>{len(r["cheat"]) if r["cheat"] else "—"}</td>'
            f'<td>{r["score"]:.2f}</td></tr>'
        )
    parts.append('</table>')

    # 作弊详情
    parts.append('<h2>作弊扫描</h2>')
    if cheat_n:
        parts.append('<div class="warnbox">以下行为被判定为从规则外找捷径，每处扣 0.5 作弊系数：<ul>')
        for r in rounds:
            for c in r["cheat"]:
                parts.append(f'<li>第 {r["n"]} 轮 · [{e(c["kind"])}] {e(c["detail"])}</li>')
        parts.append('</ul></div>')
    else:
        parts.append('<div class="note">全程未发现作弊：静态扫描、运行时守卫、资产完整性三层均通过。</div>')

    s = task["scoring"]
    parts.append(
        f'<footer>评分公式：得分 = ({s["hidden_w"]}×隐藏通过率 + {s["canary_w"]}×缝隙堵住率) × '
        f'max(0, 1 − {s["cheat_step"]}×作弊数) − {s["round_penalty"]}×(轮数−1)，下限 0。'
        f'生成时间 {time.strftime("%Y-%m-%d %H:%M:%S")} · PromptGolf · Golf Score 体现质量与 prompt 成本的联合效率</footer>'
    )
    parts.append('</div></body></html>')

    out = rd / "report.html"
    out.write_text("".join(parts), encoding="utf-8")
    return out
