"""
linkbudget 3개 모듈(link_budget, toa, diversity) 검증 테스트임.
"""
import math
import pytest
from lorascape.core.linkbudget.link_budget import (
    rx_power_dbm,
    thermal_noise_dbm,
    snr_db,
    select_sf,
    SF_SNR_THRESHOLDS_DB,
)
from lorascape.core.linkbudget.toa import time_on_air_s, symbol_duration_s
from lorascape.core.linkbudget.diversity import macro_diversity_combine, aloha_pdr


# --- link_budget.py ---

def test_rx_power_dbm_basic_formula():
    # Pr = Pt + Gt - Lt - PL + Gr - Lr - 실내손실
    result = rx_power_dbm(
        tx_power_dbm=14, gw_antenna_gain_dbi=6, gw_cable_loss_db=1,
        path_loss_db=130, node_antenna_gain_dbi=0, node_cable_loss_db=0,
    )
    expected = 14 + 6 - 1 - 130 + 0 - 0 - 0
    assert result == pytest.approx(expected)


def test_rx_power_decreases_with_higher_path_loss():
    base = rx_power_dbm(14, 6, 1, 120, 0, 0)
    worse = rx_power_dbm(14, 6, 1, 140, 0, 0)
    assert worse < base


def test_thermal_noise_known_value():
    # 125kHz 대역폭(LoRa 흔한 설정) 기준 값 확인
    bw = 125_000
    expected = -174 + 10 * math.log10(bw)
    assert thermal_noise_dbm(bw) == pytest.approx(expected)


def test_snr_db_basic():
    rx = -110
    bw = 125_000
    nf = 6
    result = snr_db(rx, bw, nf)
    expected = rx - (thermal_noise_dbm(bw) + nf)
    assert result == pytest.approx(expected)


def test_select_sf_picks_lowest_sf_meeting_threshold():
    # SF7 임계값(-7.5dB)을 넉넉히 만족하는 아주 좋은 SNR -> SF7 나와야 함
    assert select_sf(0.0) == 7


def test_select_sf_falls_back_to_higher_sf_for_weak_signal():
    # SF7 임계값(-7.5)은 못 만족하지만 SF10 임계값(-15)은 만족하는 경우
    assert select_sf(-14.0) == 10


def test_select_sf_returns_none_when_unreachable():
    # SF12 임계값(-20)보다도 낮으면 연결 불가
    assert select_sf(-25.0) is None


def test_sf_thresholds_are_monotonically_decreasing():
    # SF가 커질수록 임계값이 더 낮아져야 함(더 관대해져야 함) - 상식 체크
    values = [SF_SNR_THRESHOLDS_DB[sf] for sf in sorted(SF_SNR_THRESHOLDS_DB)]
    assert values == sorted(values, reverse=True)


# --- toa.py ---

def test_symbol_duration_known_value():
    # SF7, BW=125kHz 기준
    assert symbol_duration_s(7, 125_000) == pytest.approx((2 ** 7) / 125_000)


def test_time_on_air_increases_with_higher_sf():
    # SF가 높아질수록(느려질수록) ToA도 늘어나야 함
    toa_sf7 = time_on_air_s(payload_bytes=20, sf=7, bandwidth_hz=125_000)
    toa_sf10 = time_on_air_s(payload_bytes=20, sf=10, bandwidth_hz=125_000)
    assert toa_sf10 > toa_sf7


def test_time_on_air_increases_with_payload_size():
    toa_small = time_on_air_s(payload_bytes=10, sf=7, bandwidth_hz=125_000)
    toa_large = time_on_air_s(payload_bytes=50, sf=7, bandwidth_hz=125_000)
    assert toa_large > toa_small


def test_time_on_air_positive():
    toa = time_on_air_s(payload_bytes=1, sf=7, bandwidth_hz=125_000)
    assert toa > 0


# --- diversity.py ---

def test_macro_diversity_single_gw_returns_same_value():
    # GW 하나만 있으면 그냥 그 값 그대로 나와야 함 (합산 이득 없음)
    result = macro_diversity_combine([-100.0])
    assert result == pytest.approx(-100.0)


def test_macro_diversity_two_equal_gws_gives_3db_gain():
    # 동일한 세기의 신호 2개를 선형 합산하면 이론적으로 약 +3dB 이득이 나와야 함
    result = macro_diversity_combine([-100.0, -100.0])
    assert result == pytest.approx(-97.0, abs=0.1)


def test_macro_diversity_raises_on_empty_list():
    with pytest.raises(ValueError):
        macro_diversity_combine([])


def test_aloha_pdr_zero_load_is_perfect():
    # 트래픽 부하가 0이면 충돌이 없으니 PDR=1(100%)이어야 함
    assert aloha_pdr(0.0) == pytest.approx(1.0)


def test_aloha_pdr_decreases_with_load():
    pdr_low = aloha_pdr(0.1)
    pdr_high = aloha_pdr(1.0)
    assert pdr_high < pdr_low


def test_aloha_pdr_known_value_at_g_half():
    # G=0.5일 때 PDR = e^(-1) ≈ 0.3679 (ALOHA 최대 처리량 지점 - 유명한 기준값)
    assert aloha_pdr(0.5) == pytest.approx(math.exp(-1))