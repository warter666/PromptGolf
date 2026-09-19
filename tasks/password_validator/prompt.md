# 任务：密码强度校验器

实现 `solution.py` 中的 `validate(password)`。

签名：`validate(password: str) -> list[str]`

对不满足以下规则的密码，返回所有违反项的错误信息（每条错误对应一条规则，用中文描述）；全部满足时同样返回一个值。

规则：

1. 长度必须在 8 到 20 之间
2. 必须同时包含大写字母和小写字母
3. 必须包含数字
4. 不能出现连续 3 个相同的字符

`tests/` 目录下是公开测试，可用 `python -m pytest tests -q` 运行。
