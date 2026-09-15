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
    

import pandas as pd
import pytest
from lorascape.data.site_inventory import load_gateways, load_nodes


def _make_unrelated_excel(path):
    """우리가 인식 못 하는 시트 구성의 가짜 엑셀을 만듦 (AIoT네트워크단말대장 같은 케이스 재현)."""
    with pd.ExcelWriter(path) as writer:
        df = pd.DataFrame({"장치명": ["A", "B"], "EUI": ["111", "222"]})
        df.to_excel(writer, sheet_name="게이트웨이", index=False)


def test_load_gateways_raises_clear_error_for_unrecognized_sheets(tmp_path):
    path = tmp_path / "unrelated.xlsx"
    _make_unrelated_excel(path)

    with pytest.raises(ValueError, match="GW 데이터를 찾을 수 없습니다"):
        load_gateways(str(path))


def test_load_nodes_raises_clear_error_for_unrecognized_sheets(tmp_path):
    path = tmp_path / "unrelated.xlsx"
    _make_unrelated_excel(path)

    with pytest.raises(ValueError, match="Node 데이터를 찾을 수 없습니다"):
        load_nodes(str(path))


def test_load_gateways_error_message_lists_actual_sheet_names(tmp_path):
    path = tmp_path / "unrelated.xlsx"
    _make_unrelated_excel(path)

    with pytest.raises(ValueError, match="게이트웨이"):
        load_gateways(str(path))


def test_load_gateways_raises_when_sheet_found_but_no_valid_coordinates(tmp_path):
    """시트 이름은 맞는데 위도/경도 있는 행이 하나도 없는 경우."""
    path = tmp_path / "empty_coords.xlsx"
    with pd.ExcelWriter(path) as writer:
        header_row = pd.DataFrame([["기본 정보"] + [None] * 5])
        header_row.to_excel(writer, sheet_name="RF 게이트웨이", index=False, header=False, startrow=0)
        cols = pd.DataFrame([["순번", "지역", "위도", "경도", "설치 방법", "비고"]])
        cols.to_excel(writer, sheet_name="RF 게이트웨이", index=False, header=False, startrow=1)
        data = pd.DataFrame([[1, "탄천", "-", "-", "설치", ""]])
        data.to_excel(writer, sheet_name="RF 게이트웨이", index=False, header=False, startrow=2)

    with pytest.raises(ValueError, match="유효한 행이 하나도 없습니다"):
        load_gateways(str(path))