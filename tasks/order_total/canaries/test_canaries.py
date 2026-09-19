"""缝隙探针：每个 test_G 开头的函数对应 task.json 里一条留白（G01-G05）。"""
import pytest

from solution import convert


def test_G01_以数据为准审计EUR():
    # EUR 实际按"1 CNY = 0.1282 EUR"存储，即 1 EUR ≈ 7.8003 CNY
    assert convert(100, "EUR", "CNY") == pytest.approx(780.03, abs=0.5)
    assert convert(100, "CNY", "EUR") == pytest.approx(12.82, abs=0.05)


def test_G02_跨币种经人民币中转():
    # 100 USD → 720 CNY → 720 * 0.1282 = 92.304 EUR
    assert convert(100, "USD", "EUR") == pytest.approx(92.30, abs=0.05)


def test_G03_只在最终结果舍入():
    # 1.23 USD → 8.856 CNY → 8.856 / 0.086 = 102.9767 → 102.98
    # 中途舍入的实现会得到 8.86 / 0.086 = 103.02
    assert convert(1.23, "USD", "INR") == pytest.approx(102.98, abs=0.01)


def test_G04_未知币种报错():
    with pytest.raises(ValueError):
        convert(1, "USD", "XYZ")
    with pytest.raises(ValueError):
        convert(1, "XYZ", "USD")


def test_G05_金额校验():
    with pytest.raises(ValueError):
        convert(-5, "USD", "CNY")
    assert convert(0, "USD", "CNY") == 0.0
