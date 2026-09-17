"""heatmap.py 검증 테스트임. 가짜 평지 DEM으로 로직만 검증함 (실제 DEM 없이도 빠르게)."""
import numpy as np
import pytest
from lorascape.data.schema import GatewaySite
from lorascape.data.coord_transform import distance_m
from lorascape.core.optimization.heatmap import compute_gw_heatmap_grid


class FakeFlatDem:
    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=10):
        total = distance_m(lat1, lon1, lat2, lon2)
        return [(total * i / n_samples, 50.0) for i in range(n_samples + 1)]

    def is_installable(self, lat, lon):
        return True


def _make_gw(gw_id, lat, lon):
    return GatewaySite(
        gw_id=gw_id, region="테스트", location_desc="",
        lat=lat, lon=lon, install_type="테스트", power_source="테스트",
    )


def test_heatmap_grid_has_correct_shape():
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    grid = compute_gw_heatmap_grid(gw, dem, radius_km=1.0, grid_size=10)

    assert grid.pr_grid.shape == (10, 10)
    assert grid.lat_grid.shape == (10, 10)
    assert grid.lon_grid.shape == (10, 10)


def test_heatmap_grid_center_has_strongest_signal():
    """GW 위치(격자 중앙)의 수신전력이 가장자리보다 강해야 함 (거리 가까울수록 신호 셈)."""
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    grid = compute_gw_heatmap_grid(gw, dem, radius_km=1.0, grid_size=11)  # 홀수라 정확한 중앙 셀 있음

    center = grid.pr_grid[5, 5]
    corner = grid.pr_grid[0, 0]
    assert center > corner


def test_heatmap_grid_bounds_contain_gw_location():
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    grid = compute_gw_heatmap_grid(gw, dem, radius_km=1.0, grid_size=10)

    lat_min, lat_max, lon_min, lon_max = grid.bounds
    assert lat_min < gw.lat < lat_max
    assert lon_min < gw.lon < lon_max


def test_heatmap_grid_larger_radius_covers_more_area():
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    grid_small = compute_gw_heatmap_grid(gw, dem, radius_km=1.0, grid_size=10)
    grid_large = compute_gw_heatmap_grid(gw, dem, radius_km=5.0, grid_size=10)

    span_small = grid_small.bounds[1] - grid_small.bounds[0]
    span_large = grid_large.bounds[1] - grid_large.bounds[0]
    assert span_large > span_small


def test_heatmap_grid_signal_decreases_with_distance_monotonically_along_axis():
    """중심에서 한쪽 방향으로 갈수록 신호가 단조 감소해야 함 (평지 조건에서)."""
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    grid = compute_gw_heatmap_grid(gw, dem, radius_km=1.0, grid_size=11)

    center_row = grid.pr_grid[5, 5:]  # 중앙에서 오른쪽 끝까지
    diffs = np.diff(center_row)
    assert (diffs <= 1e-6).all()  # 갈수록 값이 커지면 안 됨(강해지면 안 됨) - 단조 감소(또는 동일) 확인
    
    
def test_heatmap_grid_progress_callback_called_with_final_completion():
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    calls = []

    compute_gw_heatmap_grid(
        gw, dem, radius_km=1.0, grid_size=10,
        progress_callback=lambda done, total: calls.append((done, total)),
    )

    assert calls  # 최소 한 번은 호출돼야 함
    assert calls[-1] == (100, 100)  # 마지막 호출은 반드시 (전체, 전체)여야 함 (100% 도달 보장)


def test_heatmap_grid_progress_callback_not_called_when_none():
    gw = _make_gw("GW1", 37.40, 127.12)
    dem = FakeFlatDem()
    # progress_callback=None이 기본값이라, 그냥 호출해서 에러 안 나는지만 확인함
    grid = compute_gw_heatmap_grid(gw, dem, radius_km=1.0, grid_size=10)
    assert grid is not None