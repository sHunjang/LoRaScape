"""DemLoader의 값 없는 칸(nodata) 처리 검증 - 실제 DEM 없이 가짜 래스터를 만들어서 씀."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform as _tf

from lorascape.core.diffraction.deygout import deygout_recursive
from lorascape.data.dem_loader import DemLoader

CENTER_LAT, CENTER_LON = 37.40, 127.12
NODATA = -9999.0
RES = 5.0        # 5m 해상도
SIZE = 1200      # 6km x 6km


def _write_dem(path, data, nodata=NODATA):
    cx, cy = _tf("EPSG:4326", "EPSG:3857", [CENTER_LON], [CENTER_LAT])
    h, w = data.shape
    kwargs = dict(driver="GTiff", height=h, width=w, count=1, dtype="float32", crs="EPSG:3857",
                  transform=from_origin(cx[0] - w * RES / 2, cy[0] + h * RES / 2, RES, RES))
    if nodata is not None:
        kwargs["nodata"] = nodata
    with rasterio.open(path, "w", **kwargs) as dst:
        dst.write(data.astype("float32"), 1)
    return str(path)


def _latlon(dem, row, col):
    x, y = dem.dataset.xy(row, col)
    lons, lats = _tf(dem.crs, "EPSG:4326", [x], [y])
    return lats[0], lons[0]


@pytest.fixture
def plateau_with_pond(tmp_path):
    """전 구간 고도 100m 평지, 중심(=GW 자리)에 값 없는 웅덩이와 동쪽에 값 없는 하천 띠."""
    data = np.full((SIZE, SIZE), 100.0)
    data[SIZE // 2 - 3:SIZE // 2 + 3, SIZE // 2 - 3:SIZE // 2 + 3] = NODATA
    data[:, SIZE // 2 + 120:SIZE // 2 + 130] = NODATA
    return _write_dem(tmp_path / "pond.tif", data)


def test_profile_across_holes_has_no_zero_elevation_by_default(plateau_with_pond):
    with DemLoader(plateau_with_pond) as dem:
        prof = dem.get_elevation_profile(CENTER_LAT, CENTER_LON, CENTER_LAT, CENTER_LON + 0.0035, 20)
    assert all(e == pytest.approx(100.0) for _, e in prof)


def test_flat_terrain_with_holes_gives_no_false_diffraction_loss(plateau_with_pond):
    """값 없는 칸을 0m로 채우던 시절에는 이 경로가 80dB 손실로 계산됐음."""
    with DemLoader(plateau_with_pond) as dem:
        prof = dem.get_elevation_profile(CENTER_LAT, CENTER_LON, CENTER_LAT, CENTER_LON + 0.0035, 20)
    assert deygout_recursive(prof, 920.0, 1.5, 1.5) == 0.0


def test_fill_holes_false_keeps_legacy_zero_fill(plateau_with_pond):
    with DemLoader(plateau_with_pond, fill_holes=False) as dem:
        prof = dem.get_elevation_profile(CENTER_LAT, CENTER_LON, CENTER_LAT, CENTER_LON + 0.0035, 20)
    assert prof[0][1] == 0.0
    assert deygout_recursive(prof, 920.0, 1.5, 1.5) > 0.0


def test_get_elevation_and_is_installable_still_report_the_hole(plateau_with_pond):
    """구멍을 메우는 건 전파 계산용 프로파일만이고, 설치 가능 판정에는 영향이 없어야 함."""
    with DemLoader(plateau_with_pond) as dem:
        assert dem.get_elevation(CENTER_LAT, CENTER_LON) is None
        assert dem.is_installable(CENTER_LAT, CENTER_LON) is False
        assert dem.is_installable(CENTER_LAT + 0.003, CENTER_LON) is True


def test_hole_is_filled_with_nearest_valid_value(tmp_path):
    data = np.full((SIZE, SIZE), 50.0)
    data[:, SIZE // 2 + 10:] = 150.0
    data[:, SIZE // 2 - 5:SIZE // 2 + 10] = NODATA          # 왼쪽(50m)~오른쪽(150m) 사이 15칸 띠
    path = _write_dem(tmp_path / "strip.tif", data)
    with DemLoader(path) as dem:
        near_left = _latlon(dem, SIZE // 2, SIZE // 2 - 4)
        near_right = _latlon(dem, SIZE // 2, SIZE // 2 + 8)
        got = dem.get_elevations_batch(np.array([near_left[0], near_right[0]]),
                                       np.array([near_left[1], near_right[1]]))
    assert got[0] == pytest.approx(50.0) and got[1] == pytest.approx(150.0)


def test_outside_the_raster_is_still_zero(plateau_with_pond):
    with DemLoader(plateau_with_pond) as dem:
        assert dem.get_elevations_batch(np.array([10.0]), np.array([10.0]))[0] == 0.0


def test_raster_without_nodata_value_is_unchanged(tmp_path):
    data = np.full((SIZE, SIZE), 80.0)
    path = _write_dem(tmp_path / "nonodata.tif", data, nodata=None)
    with DemLoader(path) as dem:
        assert dem.get_elevations_batch(np.array([CENTER_LAT]), np.array([CENTER_LON]))[0] == 80.0


def test_all_nodata_raster_does_not_crash(tmp_path):
    path = _write_dem(tmp_path / "empty.tif", np.full((200, 200), NODATA))
    with DemLoader(path) as dem:
        assert dem.get_elevations_batch(np.array([CENTER_LAT]), np.array([CENTER_LON]))[0] == 0.0
