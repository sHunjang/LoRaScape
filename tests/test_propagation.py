"""
song_model.py 검증용 테스트임.
core 로직은 GUI 없이도 이 테스트만으로 정확성 검증 가능해야 하는 구조로 짠 거임.
"""
import math
import pytest
from lorascape.core.propagation.song_model import (
    basic_path_loss,
    ahm_correction,
    path_loss,
    ENV_DENSE_URBAN,
    ENV_URBAN,
    ENV_SUBURBAN,
    ENV_OPEN,
)


def test_basic_path_loss_known_value():
    # 수식을 그대로 다시 풀어서 계산한 값이랑 함수 리턴값이 일치하는지 확인하는 테스트임.
    # (수식 자체를 검증하는 게 아니라, "코드가 수식을 있는 그대로 옮겼는지"를 확인하는 거)
    fc, hb, d = 920, 20, 1.0
    expected = (
        39.25
        + 35.15 * math.log10(fc)
        - 19.21 * math.log10(hb)
        + (42.5 - 5.2 * math.log10(hb)) * math.log10(d)
    )
    assert basic_path_loss(fc, hb, d) == pytest.approx(expected, rel=1e-9)


def test_basic_path_loss_increases_with_distance():
    # 거리 멀어지면 손실도 커져야 정상임. 방향성만 체크하는 간단한 테스트.
    fc, hb = 920, 20
    pl_near = basic_path_loss(fc, hb, 0.5)
    pl_far = basic_path_loss(fc, hb, 2.0)
    assert pl_far > pl_near


@pytest.mark.parametrize("env", [ENV_DENSE_URBAN, ENV_URBAN, ENV_SUBURBAN, ENV_OPEN])
def test_ahm_correction_runs_for_all_envs(env):
    # 4개 환경 전부 에러 없이 계산 잘 되는지만 확인하는 스모크 테스트임.
    result = ahm_correction(env, hm_m=1.5, fc_mhz=920)
    assert isinstance(result, float)


def test_ahm_correction_invalid_env_raises():
    # 잘못된 환경 문자열 넣으면 ValueError 터지는 게 맞음 (조용히 넘어가면 안 됨).
    with pytest.raises(ValueError):
        ahm_correction("invalid_env", hm_m=1.5, fc_mhz=920)


def test_path_loss_equals_bpl_minus_ahm():
    # path_loss가 실제로 BPL - ahm 공식대로 동작하는지 확인함.
    fc, hb, hm, d, env = 920, 20, 1.5, 1.0, ENV_URBAN
    bpl = basic_path_loss(fc, hb, d)
    ahm = ahm_correction(env, hm, fc)
    assert path_loss(fc, hb, hm, d, env) == pytest.approx(bpl - ahm)


def test_dense_urban_has_higher_loss_than_open():
    # 도심(Dense Urban)이 개활지(Open)보다 전파 손실이 더 커야 상식적으로 맞음.
    # 수식 부호가 뒤바뀌는 실수 같은 걸 잡아내기 위한 테스트임.
    fc, hb, hm, d = 920, 20, 1.5, 1.0
    pl_dense = path_loss(fc, hb, hm, d, ENV_DENSE_URBAN)
    pl_open = path_loss(fc, hb, hm, d, ENV_OPEN)
    assert pl_dense > pl_open