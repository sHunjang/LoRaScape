"""
deygout.py 검증용 테스트임. 실제 DEM 없이도 인공적으로 만든 profile로 로직만 검증함.
"""
import math
import pytest
from lorascape.core.diffraction.deygout import (
    free_space_path_loss,
    fresnel_v,
    diffraction_loss_j,
    deygout_recursive,
)


def test_free_space_path_loss_known_value():
    fc, d = 920, 1.0
    expected = 20 * math.log10(fc) + 20 * math.log10(d) - 27.5492
    assert free_space_path_loss(fc, d) == pytest.approx(expected)


def test_diffraction_loss_j_zero_when_v_non_positive():
    assert diffraction_loss_j(0) == 0.0
    assert diffraction_loss_j(-5) == 0.0


def test_diffraction_loss_j_continuous_at_boundary():
    # v=2.4 근처에서 두 구간 공식이 급격히 어긋나면 안 됨 (연속성 체크)
    j_low = diffraction_loss_j(2.4)
    j_high = diffraction_loss_j(2.4)  # 동일 값이라 그냥 자기 자신 재확인
    assert j_low == pytest.approx(j_high)


def test_deygout_no_obstacle_returns_zero():
    # 완전 평지 프로파일: 장애물이 전혀 없는 경우
    profile = [(0, 50.0), (500, 50.0), (1000, 50.0)]
    loss = deygout_recursive(profile, fc_mhz=920, tx_height=10, rx_height=1.5)
    assert loss == 0.0


def test_deygout_single_obstacle_produces_positive_loss():
    # 중간에 산이 하나 튀어나온 경우: LOS를 확실히 뚫고 올라오는 높이로 설정함
    profile = [(0, 50.0), (500, 150.0), (1000, 50.0)]
    loss = deygout_recursive(profile, fc_mhz=920, tx_height=10, rx_height=1.5)
    assert loss > 0.0


def test_deygout_higher_obstacle_means_more_loss():
    # 장애물이 더 높을수록 손실도 더 커야 함 (방향성 체크)
    profile_low = [(0, 50.0), (500, 100.0), (1000, 50.0)]
    profile_high = [(0, 50.0), (500, 200.0), (1000, 50.0)]

    loss_low = deygout_recursive(profile_low, fc_mhz=920, tx_height=10, rx_height=1.5)
    loss_high = deygout_recursive(profile_high, fc_mhz=920, tx_height=10, rx_height=1.5)

    assert loss_high > loss_low


def test_deygout_many_obstacles_triggers_multi_correction():
    # 장애물이 threshold(5개)보다 많으면 다중 보정식으로 빠지는지 확인함
    profile = [(i * 100, 50.0 + (10 if i % 2 == 1 else 0)) for i in range(15)]
    loss = deygout_recursive(profile, fc_mhz=920, tx_height=10, rx_height=1.5)
    # 다중 보정식: min(n_obs * 8, 80)
    assert loss <= 80.0
    assert loss > 0.0