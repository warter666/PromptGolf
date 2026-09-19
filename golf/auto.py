"""自动模式：调 OpenAI 兼容接口，让模型只靠公开测试反馈迭代作答。

模型每一轮只能看到：题面、当前代码、上一轮公开测试失败摘要——
和真人考生手里的信息一致。隐藏测试与缝隙探针只用于评分。
"""
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import core, evaluate, fmt


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _check_base(base: str) -> str:
    """接口地址只认 https；明文 http 仅限本机推理服务。"""
    u = urlparse(base if "://" in base else "https://" + base)
    if u.scheme not in ("http", "https"):
        raise SystemExit(f"不支持的接口协议: {u.scheme or '(空)'}，只支持 http/https")
    if u.scheme == "http" and u.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit("明文 http 仅允许本机地址（localhost/127.0.0.1），外部接口请用 https")
    if u.username or u.password:
        raise SystemExit("接口地址不应内嵌凭据，请改用 GOLF_API_KEY")
    return u.geturl()


def _chat(base: str, key: str, model: str, messages: list, timeout: int = 180) -> str:
    url = _check_base(base).rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with _opener.open(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def extract_code(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n"


def run(task_id: str, rounds: int = 5, run_dir: str | None = None,
        model: str | None = None, base: str | None = None) -> Path:
    base = base or os.environ.get("GOLF_API_BASE", "https://api.openai.com/v1")
    key = os.environ.get("GOLF_API_KEY", "")
    model = model or os.environ.get("GOLF_MODEL", "")
    if not key or not model:
        raise SystemExit("请设置环境变量 GOLF_API_KEY 与 GOLF_MODEL（也可用 --model / --base 覆盖）")
    _check_base(base)

    task = core.load_task(task_id)
    rd = core.new_run(task_id, run_dir, mode="auto")
    entry = task["entry"][0]
    print(f"自动模式: {model} @ {_check_base(base)} · 运行目录 {rd}")

    sysmsg = "你是参赛程序员。只输出一个完整的代码文件内容（用 ```python 代码块包裹），不要输出其他解释。"
    last_public = ""
    for k in range(1, rounds + 1):
        cur = (rd / entry).read_text(encoding="utf-8")
        user = f"# 任务\n\n{task['prompt']}\n\n# 当前 {entry}\n\n```python\n{cur}```\n"
        if last_public:
            user += f"\n# 上一轮公开测试未通过的用例\n\n{last_public}\n"
        user += f"\n这是第 {k}/{rounds} 轮。直接输出完整的 {entry}。"

        try:
            text = _chat(base, key, model, [
                {"role": "system", "content": sysmsg},
                {"role": "user", "content": user},
            ])
            code = extract_code(text)
        except Exception as ex:
            print(f"第 {k} 轮调用失败: {ex}")
            break
        if not re.search(rf"def {task['function']}\s*\(", code):
            print(f"第 {k} 轮: 模型输出里没有 {task['function']} 函数，跳过写入")
            continue
        (rd / entry).write_text(code, encoding="utf-8")

        rec = evaluate.evaluate_round(rd, task, k)
        rec["n"] = k
        rec["prompt"] = f"(auto) {model} 第 {k} 轮"
        rec["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        state = core.load_run(rd)
        state["rounds"].append(rec)
        core.save_run(rd, state)
        fmt.feedback(rec, state["rounds"][k - 2] if k >= 2 else None)

        fails = rec["public"]["failures"]
        last_public = "\n".join(f"- {f['name']}: {f['text'][:200]}" for f in fails)
        if not fails:
            print("\n公开测试全部通过，自动模式提前结束（隐藏测试与缝隙只用于评分）")
            break

    from . import report
    out = report.build(rd)
    print(f"\n报告: {out.resolve()}")
    return rd
