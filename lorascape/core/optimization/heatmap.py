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
    progress_callback=None,
) -> HeatmapGrid:
    """
    GW 하나를 중심으로 radius_km 반경 정사각형을 grid_size x grid_size 격자로 나눠
    각 지점의 수신전력(dBm)을 계산함.

    DEM이 get_elevations_batch를 지원하면 모든 셀의 지형 단면을 한 번에 조회함
    (프로파일링 결과 셀마다 조회하는 방식이 전체 시간의 99%였음). 지원하지 않는
    DEM(테스트용 가짜 DEM 등)은 기존처럼 셀마다 get_elevation_profile을 씀.
    """
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * max(np.cos(np.radians(gw.lat)), 0.01))

    lat_min, lat_max = gw.lat - lat_delta, gw.lat + lat_delta
    lon_min, lon_max = gw.lon - lon_delta, gw.lon + lon_delta

    lats = np.linspace(lat_min, lat_max, grid_size)
    lons = np.linspace(lon_min, lon_max, grid_size)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    pr_grid = np.full((grid_size, grid_size), -999.0)
    total_cells = grid_size * grid_size

    use_batch = hasattr(dem, "get_elevations_batch")
    if use_batch:
        t = np.linspace(0.0, 1.0, n_profile_samples + 1)
        flat_lat = lat_grid.ravel()[:, None]
        flat_lon = lon_grid.ravel()[:, None]
        elev_all = dem.get_elevations_batch(
            gw.lat + (flat_lat - gw.lat) * t[None, :],
            gw.lon + (flat_lon - gw.lon) * t[None, :],
        )  # (셀 수, 샘플 수+1)

    for i in range(grid_size):
        for j in range(grid_size):
            lat, lon = lat_grid[i, j], lon_grid[i, j]
            d_km_raw = distance_m(gw.lat, gw.lon, lat, lon) / 1000.0
            d_km = max(d_km_raw, 0.01)  # GW 바로 위 지점의 log10(0) 방지

            base_pl = song_path_loss(fc_mhz, gw.antenna_height_m, node_antenna_height_m, d_km, environment)

            if use_batch:
                total = d_km_raw * 1000.0  # 기존 get_elevation_profile과 같은 실제 거리 기준
                profile = [(total * tt, float(e)) for tt, e in zip(t, elev_all[i * grid_size + j])]
            else:
                profile = dem.get_elevation_profile(gw.lat, gw.lon, lat, lon, n_profile_samples)

            diffraction_loss = deygout_recursive(
                profile, fc_mhz, tx_height=gw.antenna_height_m, rx_height=node_antenna_height_m
            )
            total_pl = base_pl + min(diffraction_loss, DEYGOUT_LOSS_CAP_DB)

            pr_grid[i, j] = rx_power_dbm(
                gw.tx_power_dbm, gw.antenna_gain_dbi, gw.cable_loss_db,
                total_pl, 0.0, 0.0,
            )

            if progress_callback is not None:
                done = i * grid_size + j + 1
                if done % 10 == 0 or done == total_cells:
                    progress_callback(done, total_cells)

    return HeatmapGrid(
        gw_id=gw.gw_id,
        pr_grid=pr_grid,
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        bounds=(lat_min, lat_max, lon_min, lon_max),
    )