"""Deygout 2차 회절 계산 검증 테스트임 - 경로 방향 대칭성과 1차 손실 독립 검증."""
import random
import pytest

from lorascape.core.diffraction.deygout import (
    deygout_recursive, fresnel_v, diffraction_loss_j, _rebase_distances,
)

FC = 920.0
D, N = 1500.0, 20


def make_profile(peaks, base=50.0):
    """N+1개 샘플, 지정한 (샘플번호, 높이) 위치에 봉우리를 얹은 프로파일."""
    return [(D * i / N, base + sum(h for pos, h in peaks if pos == i)) for i in range(N + 1)]


def reverse(profile):
    total = profile[-1][0]
    return [(total - d, e) for d, e in reversed(profile)]


@pytest.mark.parametrize("peaks", [
    [(5, 45), (14, 30)],
    [(14, 45), (5, 30)],
    [(8, 40), (3, 25)],
    [(8, 40), (17, 25)],
    [(4, 30), (10, 45), (16, 20)],
])
def test_loss_is_same_when_path_direction_is_reversed(peaks):
    """같은 지형에서 GW와 Node를 맞바꿔도 회절손실은 같아야 함 (수정 전에는 수십 dB씩 달랐음)."""
    p = make_profile(peaks)
    assert deygout_recursive(p, FC, 1.5, 1.5) == pytest.approx(deygout_recursive(reverse(p), FC, 1.5, 1.5), abs=1e-9)


def test_symmetry_holds_with_different_antenna_heights_swapped():
    rnd = random.Random(7)
    for _ in range(200):
        p = [(D * i / N, 50 + max(0.0, rnd.gauss(0, 18))) for i in range(N + 1)]
        ha, hb = rnd.choice([1.5, 5.0, 15.0]), rnd.choice([1.5, 0.25])
        fwd = deygout_recursive(p, FC, ha, hb)
        rev = deygout_recursive(reverse(p), FC, hb, ha)      # 반대로 가면 높이도 서로 바뀜
        assert fwd == pytest.approx(rev, abs=1e-9)


def test_single_peak_matches_first_order_formula_independently():
    """봉우리 하나면 2차가 없으므로 J(v)+13과 같아야 함 - 기하를 손으로 계산해서 독립 검증함."""
    p = make_profile([(10, 40)])                      # 샘플 10 = 정확히 중간(750m), 고도 90m
    los = 50.0 + 1.5                                  # 양 끝이 50m 평지, 안테나 1.5m
    v = fresnel_v(90.0 - los, 750.0, 750.0, FC)
    assert deygout_recursive(p, FC, 1.5, 1.5) == pytest.approx(diffraction_loss_j(v) + 13.0)


def test_second_order_never_reduces_loss():
    p = make_profile([(5, 45), (14, 30)])
    assert deygout_recursive(p, FC, 1.5, 1.5, max_order=2) >= deygout_recursive(p, FC, 1.5, 1.5, max_order=1)


def test_flat_terrain_has_no_diffraction_loss():
    assert deygout_recursive(make_profile([]), FC, 1.5, 1.5) == 0.0


def test_rebase_distances_starts_at_zero_and_keeps_original():
    sub = [(300.0, 60.0), (450.0, 70.0), (600.0, 65.0)]
    out = _rebase_distances(sub)
    assert [d for d, _ in out] == [0.0, 150.0, 300.0]
    assert sub[0][0] == 300.0                          # 원본은 그대로
