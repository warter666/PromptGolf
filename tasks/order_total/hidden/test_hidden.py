import pytest

from solution import convert


def test_美元兑人民币含小数():
    assert convert(3.45, "USD", "CNY") == pytest.approx(24.84, abs=0.01)


def test_美元兑日元经人民币():
    assert convert(100, "USD", "JPY") == pytest.approx(15000.0, abs=0.5)


def test_日元兑美元():
    assert convert(144, "JPY", "USD") == pytest.approx(0.96, abs=0.01)


def test_卢比兑人民币():
    assert convert(100, "INR", "CNY") == pytest.approx(8.60, abs=0.01)
