"""
site_inventory.py의 _clean() 함수 검증 테스트임.
이번에 NaN 좌표가 안 걸러져서 K-means까지 흘러들어간 버그가 있었어서,
이 함수는 반드시 회귀 테스트로 잡아둬야 함.
"""
import math
import pytest
from lorascape.data.site_inventory import _clean


def test_clean_none_stays_none():
    assert _clean(None) is None


def test_clean_nan_float_becomes_none():
    """이번에 잡은 버그의 핵심 케이스임 - float NaN이 None으로 바뀌어야 함."""
    assert _clean(float("nan")) is None


def test_clean_dash_string_becomes_none():
    assert _clean("-") is None


def test_clean_empty_string_becomes_none():
    assert _clean("") is None
    assert _clean("   ") is None


def test_clean_tbd_and_na_become_none():
    assert _clean("TBD") is None
    assert _clean("n/a") is None


def test_clean_valid_number_passes_through():
    assert _clean(37.4217346) == 37.4217346


def test_clean_valid_string_passes_through():
    assert _clean("탄천") == "탄천"


def test_clean_zero_is_not_treated_as_empty():
    """0은 유효한 값인데 falsy라서 실수로 None 처리되면 안 됨 - 방어적으로 확인."""
    assert _clean(0) == 0
    assert _clean(0.0) == 0.0