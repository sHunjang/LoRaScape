# lorascape/core/optimization/heatmap.py
"""
GW 하나의 커버리지를 격자(grid) 형태로 계산하는 모듈임. Qt/이미지 렌더링에는
전혀 의존 안 함 - "위경도 격자 각 지점의 수신전력(dBm)"만 순수하게 계산함.
이미지로 그리는 건 별도 모듈(heatmap_render.py, 다음 단계)이 담당함.

ATDI 같은 상용 도구가 보여주는 "면적형 커버리지"를 만들려면, GW 주변을
촘촘한 격자로 나눠서 각 셀마다 Song's Model + Deygout으로 경로손실을 계산해야 함.
Node 개수(143개)만 계산하던 것과 달리 격자 셀 수는 훨씬 많아질 수 있어서
(60x60=3600개), 계산 비용이 무겁다는 걸 염두에 둬야 함 - 그래서 grid_size를
인자로 노출해서 속도/정밀도를 조절할 수 있게 함.
"""
from dataclasses import dataclass
import numpy as np

from lorascape.data.coord_transform import distance_m
from lorascape.core.propagation.song_model import path_loss as song_path_loss
from lorascape.core.diffraction.deygout import deygout_recursive
from lorascape.core.linkbudget.link_budget import rx_power_dbm

DEYGOUT_LOSS_CAP_DB = 30.0


@dataclass
class HeatmapGrid:
    """GW 하나의 커버리지 격자 계산 결과임."""
    gw_id: str
    pr_grid: np.ndarray          # (rows, cols) 형태, 각 셀의 수신전력(dBm)
    lat_grid: np.ndarray         # 같은 shape, 각 셀의 위도
    lon_grid: np.ndarray         # 같은 shape, 각 셀의 경도
    bounds: tuple                # (lat_min, lat_max, lon_min, lon_max)


def compute_gw_heatmap_grid(
    gw,
    dem,
    node_antenna_height_m: float = 1.5,
    radius_km: float = 2.0,
    grid_size: int = 40,
    fc_mhz: float = 920.0,
    environment: str = "urban",
    n_profile_samples: int = 10,
) -> HeatmapGrid:
    """
    GW 하나를 중심으로 radius_km 반경의 정사각형 영역을 grid_size x grid_size
    격자로 나눠서 각 지점의 수신전력(dBm)을 계산함.

    grid_size가 커질수록 화질은 좋아지지만 계산 시간이 제곱으로 늘어남
    (40x40=1600셀, 각 셀마다 DEM 프로파일 10샘플 조회 -> 1600*10=16000회 DEM 조회).
    실시간성이 필요하면 grid_size를 줄이고, 정밀도가 필요하면 늘리면 됨.

    n_profile_samples를 gw_placement.py의 기본값(20)보다 낮춰둔 이유: 격자 셀 수가
    Node 개수보다 훨씬 많아서, 프로파일 샘플 수까지 기본값 그대로 쓰면 너무 느려짐 -
    히트맵은 "대략적인 면적 형태"를 보여주는 목적이라 약간의 정밀도 손실은 감수함.
    """
    # 위도 1도 ≈ 111km 고정 근사, 경도는 위도에 따라 보정 (간단한 근사면 충분 - 격자 범위 계산용)
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * max(np.cos(np.radians(gw.lat)), 0.01))

    lat_min, lat_max = gw.lat - lat_delta, gw.lat + lat_delta
    lon_min, lon_max = gw.lon - lon_delta, gw.lon + lon_delta

    lats = np.linspace(lat_min, lat_max, grid_size)
    lons = np.linspace(lon_min, lon_max, grid_size)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    pr_grid = np.full((grid_size, grid_size), -999.0)

    for i in range(grid_size):
        for j in range(grid_size):
            lat, lon = lat_grid[i, j], lon_grid[i, j]
            d_km = distance_m(gw.lat, gw.lon, lat, lon) / 1000.0

            if d_km < 0.01:
                d_km = 0.01  # GW 바로 위 지점(거리 0)은 log10(0) 방지용 최소값

            base_pl = song_path_loss(fc_mhz, gw.antenna_height_m, node_antenna_height_m, d_km, environment)

            profile = dem.get_elevation_profile(gw.lat, gw.lon, lat, lon, n_profile_samples)
            diffraction_loss = deygout_recursive(
                profile, fc_mhz, tx_height=gw.antenna_height_m, rx_height=node_antenna_height_m
            )
            diffraction_loss_capped = min(diffraction_loss, DEYGOUT_LOSS_CAP_DB)

            total_pl = base_pl + diffraction_loss_capped

            pr = rx_power_dbm(
                gw.tx_power_dbm, gw.antenna_gain_dbi, gw.cable_loss_db,
                total_pl, 0.0, 0.0,
            )
            pr_grid[i, j] = pr

    return HeatmapGrid(
        gw_id=gw.gw_id,
        pr_grid=pr_grid,
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        bounds=(lat_min, lat_max, lon_min, lon_max),
    )