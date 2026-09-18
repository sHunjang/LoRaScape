"""hillshade.py 검증 테스트임. 순수 numpy 함수라 Qt 없이도 테스트 가능함."""
import numpy as np
from lorascape.gui.widgets.hillshade import compute_hillshade


def test_hillshade_output_shape_matches_input():
    elev = np.random.rand(50, 60) * 100
    result = compute_hillshade(elev)
    assert result.shape == (50, 60)


def test_hillshade_output_is_uint8_range():
    elev = np.random.rand(30, 30) * 500
    result = compute_hillshade(elev)
    assert result.dtype == np.uint8
    assert result.min() >= 0 and result.max() <= 255


def test_hillshade_flat_terrain_is_uniform():
    # 완전 평지면 어느 지점이나 명암이 똑같아야 함 (경사가 없으니까)
    elev = np.full((20, 20), 50.0)
    result = compute_hillshade(elev)
    assert result.std() == 0


def test_hillshade_handles_nan_without_crashing():
    elev = np.full((10, 10), 50.0)
    elev[3, 3] = np.nan
    result = compute_hillshade(elev)
    assert not np.isnan(result).any()
    assert result[3, 3] == 128  # NaN 자리는 중간 회색으로 채워져야 함


def test_hillshade_varied_terrain_differs_from_flat():
    # 언덕 모양(중앙이 높고 가장자리로 갈수록 낮아지는 지형)을 만듦.
    # 이러면 지점마다 경사 방향/크기가 달라져서 명암도 지점마다 달라져야 함.
    # (앞서 실패했던 균일 경사면 테스트는 잘못된 가정이었음 - 균일 경사면은
    #  전부 같은 방향으로 기울어져 있어서 명암도 균일하게 나오는 게 정상 동작임)
    flat = np.full((20, 20), 50.0)

    y, x = np.mgrid[0:20, 0:20]
    center = 10
    hill = 100 - ((x - center) ** 2 + (y - center) ** 2) * 0.5  # 중앙이 볼록한 언덕

    result_flat = compute_hillshade(flat)
    result_hill = compute_hillshade(hill)

    assert result_hill.std() > result_flat.std()