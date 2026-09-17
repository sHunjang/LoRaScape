"""
dem_loader.py 검증용 테스트임.
실제 DEM 파일이 있어야 하는 테스트는 pytest.mark.skipif로 표시해서
DEM 파일 없는 환경(예: CI 서버)에서는 자동으로 건너뛰게 만듦.
"""
import os
import pytest
from lorascape.data.dem_loader import DemLoader

DEM_PATH = "sample_data/seongnam/dem_build_seongnam_3857-2.img"
DEM_EXISTS = os.path.exists(DEM_PATH)


@pytest.mark.skipif(not DEM_EXISTS, reason="성남시 DEM 샘플 파일이 없어서 건너뜀")
def test_dem_loads_and_returns_crs():
    with DemLoader(DEM_PATH) as dem:
        assert dem.crs is not None


@pytest.mark.skipif(not DEM_EXISTS, reason="성남시 DEM 샘플 파일이 없어서 건너뜀")
def test_get_elevation_within_seongnam():
    # 성남시청 근처 좌표로 테스트함 (대략적인 좌표 - DEM 범위 안에 있어야 함)
    with DemLoader(DEM_PATH) as dem:
        elevation = dem.get_elevation(37.4201, 127.1265)
        assert elevation is not None
        assert -10 < elevation < 500  # 성남시 고도 범위 상식선 체크 (음수/터무니없이 큰 값 방지)


@pytest.mark.skipif(not DEM_EXISTS, reason="성남시 DEM 샘플 파일이 없어서 건너뜀")
def test_elevation_profile_between_two_points():
    # 여수대교 GW <-> 방아교 센서 구간으로 프로파일 뽑아봄 (앞서 검증한 실제 좌표 재사용)
    with DemLoader(DEM_PATH) as dem:
        profile = dem.get_elevation_profile(
            37.4217346, 127.1171853,
            37.3992061, 127.1245804,
            n_samples=20,
        )
        assert len(profile) == 21  # n_samples+1개 포인트여야 함
        # 거리는 0부터 시작해서 끝까지 단조증가해야 함
        distances = [d for d, _ in profile]
        assert distances == sorted(distances)
        

def test_get_elevation_does_not_reread_dataset_after_init():
    """
    캐싱이 실제로 되고 있는지 확인하는 테스트임.
    dataset.read를 감시해서, __init__ 이후 get_elevation을 여러 번 불러도
    dataset.read가 추가로 호출되지 않아야 함 (캐싱 안 되면 매번 호출될 것).
    """
    if not DEM_EXISTS:
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    with DemLoader(DEM_PATH) as dem:
        original_read = dem.dataset.read
        call_count = {"n": 0}

        def counting_read(*args, **kwargs):
            call_count["n"] += 1
            return original_read(*args, **kwargs)

        dem.dataset.read = counting_read

        for _ in range(10):
            dem.get_elevation(37.4201, 127.1265)

        assert call_count["n"] == 0  # __init__ 이후로는 read가 한 번도 더 호출되면 안 됨


def test_get_dem_latlon_bounds_returns_valid_seongnam_range():
    """성남시 DEM 파일의 지리적 범위가 상식적인 위경도 범위로 나오는지 확인함."""
    if not DEM_EXISTS:
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    from lorascape.data.dem_loader import get_dem_latlon_bounds
    lon_min, lat_min, lon_max, lat_max = get_dem_latlon_bounds(DEM_PATH)

    # 성남시는 대략 위도 37.3~37.5, 경도 127.0~127.2 부근임 - 그 근방인지 대략 확인
    assert 30 < lat_min < lat_max < 45
    assert 120 < lon_min < lon_max < 135


def test_get_dem_latlon_bounds_does_not_load_full_band():
    """
    get_dem_latlon_bounds가 DemLoader처럼 밴드 전체를 메모리에 올리지 않고
    가볍게 동작하는지 확인함 (rasterio.open을 with문으로 바로 닫는지).
    """
    if not DEM_EXISTS:
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    import time
    from lorascape.data.dem_loader import get_dem_latlon_bounds

    start = time.time()
    get_dem_latlon_bounds(DEM_PATH)
    elapsed = time.time() - start

    assert elapsed < 1.0  # 메타데이터만 읽는 거라 1초 안에 끝나야 함 (밴드 전체 읽으면 더 걸림)