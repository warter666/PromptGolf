"""缝隙探针：每个 test_G 开头的函数对应 task.json 里一条留白（G01-G06）。"""
from solution import validate


def test_G01_空输入不抛异常():
    r = validate(None)
    assert isinstance(r, list) and len(r) >= 1
    r2 = validate("")
    assert isinstance(r2, list) and len(r2) >= 1


def test_G02_非字符串不抛异常():
    for bad in (123, 3.14, ["abc"], {"pw": 1}):
        r = validate(bad)
        assert isinstance(r, list) and len(r) >= 1


def test_G03_全角字符不算字母数字():
    # 全角大写 + 全角小写 + 全角数字：按 ASCII 判定应至少违反大小写/数字规则
    r = validate("Ａｂｃｄｅｆｇ１")
    assert len(r) >= 1
    # 仅末位换成全角数字：不得视为已包含数字
    assert len(validate("Abcdefg１")) >= 1


def test_G04_连续相同区分大小写():
    # AaA 不是"连续 3 个相同的字符"
    assert not validate("AaAbcdef1")


def test_G05_长度边界包含():
    assert not validate("Abcdefg1")               # 8 位
    assert not validate("Abcdefghij1234567890")   # 20 位
    assert len(validate("Abcdefghij12345678901")) >= 1  # 21 位


def test_G06_合规时返回空列表():
    assert validate("Abcdefg1") == []
