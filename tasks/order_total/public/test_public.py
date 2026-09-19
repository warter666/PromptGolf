import pytest

from solution import convert


def test_人民币兑美元():
    assert convert(72, "CNY", "USD") == pytest.approx(10.0, abs=0.01)


def test_美元兑人民币():
    assert convert(10, "USD", "CNY") == pytest.approx(72.0, abs=0.01)


def test_日元兑人民币():
    assert convert(1000, "JPY", "CNY") == pytest.approx(48.0, abs=0.01)


def test_同币种原样返回():
    assert convert(5, "USD", "USD") == pytest.approx(5.0, abs=0.001)
