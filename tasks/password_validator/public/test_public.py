from solution import validate


def test_类型契约():
    r = validate("Abcdefg1")
    assert isinstance(r, list)


def test_合规密码_通过():
    assert not validate("Abcdefg1")


def test_过短():
    assert validate("Ab1!")


def test_缺大写():
    assert validate("abcdefg1")


def test_缺数字():
    assert validate("Abcdefghi")


def test_连续相同():
    assert validate("Abcddddefg1")
