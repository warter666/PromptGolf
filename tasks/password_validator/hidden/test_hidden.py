from solution import validate


def test_七位违规():
    assert validate("Abcdef1")


def test_二十一位违规():
    assert validate("Abcdefghij1234567890ab")


def test_只有小写不行():
    assert validate("abcdefgh1")


def test_只有大写不行():
    assert validate("ABCDEFGH1")


def test_纯数字不行():
    assert validate("12345678")


def test_错误逐条返回():
    # "abc" 违反：长度 / 无大写 / 无数字，应恰好 3 条
    assert len(validate("abc")) == 3


def test_错误信息类型():
    for msg in validate("abc"):
        assert isinstance(msg, str) and msg
