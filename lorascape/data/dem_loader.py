# lorascape/data/dem_loader.py
"""
DEM(수치표면모델) 래스터 파일을 읽어서 특정 좌표의 고도값을 뽑아내는 모듈임.
Deygout 회절 계산에서 GW-Node 사이 지형 프로파일을 뽑을 때, 그리고
K-means 후보지 보정(저지대/수면 등 설치 불가 지역 판정)할 때 둘 다 이 모듈을 씀.

rasterio 라이브러리를 씀 - GIS 래스터(.img, .tif 등) 표준 처리 라이브러리임.
"""
import numpy as np
import rasterio

from rasterio import warp as rio_warp
from rasterio.warp import transform as rio_transform


class DemLoader:
    """
    DEM 파일 하나를 감싸는 클래스임. 파일을 매번 열고 닫는 게 아니라
    한 번 열어두고 여러 번 좌표 조회하는 구조로 만듦 (성능 때문 - I/O 반복 줄이려고).

    ★ 성능 수정: 예전엔 get_elevation()이 호출될 때마다 self.dataset.read(1)로
    DEM 전체 밴드를 디스크에서 매번 다시 읽었음. 지형 프로파일 하나 뽑는 데만
    (20샘플) DEM 전체를 20번 읽는 꼴이었고, GW-Node 조합이 수백~수천 개면
    이게 그대로 곱해져서 심각한 병목이었음.
    지금은 __init__ 시점에 밴드 전체를 딱 한 번 numpy 배열로 캐싱해두고,
    이후 조회는 전부 메모리 인덱싱만 함.
    """

    def __init__(self, dem_path: str):
        self.dem_path = dem_path
        self.dataset = rasterio.open(dem_path)
        self.crs = self.dataset.crs

        # ★ 캐싱: 여기서 딱 한 번만 전체 밴드를 메모리에 올림.
        # DEM이 아주 크면(수 GB) 이것도 부담일 수 있는데, 지금 성남시 DEM은
        # 수십MB 수준이라 문제없음. 더 큰 DEM을 쓸 경우엔 필요한 영역만
        # 캐싱하는 방식(타일 캐시)으로 확장이 필요할 수 있음 - 지금은 오버엔지니어링이라 안 함.
        self._band = self.dataset.read(1)
        self._nodata = self.dataset.nodata

    def get_elevation(self, lat: float, lon: float) -> float:
        """
        위경도(WGS84) 좌표 하나 받아서 그 지점의 고도값(m)을 반환함.
        캐싱된 배열(self._band)에서 인덱싱만 하니까 디스크 I/O가 전혀 없음.
        """
        xs, ys = rio_transform("EPSG:4326", self.crs, [lon], [lat])
        x, y = xs[0], ys[0]

        row, col = self.dataset.index(x, y)

        if row < 0 or row >= self._band.shape[0] or col < 0 or col >= self._band.shape[1]:
            return None

        value = self._band[row, col]

        if self._nodata is not None and value == self._nodata:
            return None

        return float(value)

    def get_elevation_profile(self, lat1: float, lon1: float, lat2: float, lon2: float, n_samples: int = 50) -> list:
        """
        두 지점 사이를 n_samples개 구간으로 나눠 고도를 샘플링함.
        반환값: [(거리_m, 고도_m), ...] (deygout_recursive의 profile 인자 형태).

        샘플 좌표를 한꺼번에 get_elevations_batch로 조회함. 예전엔 샘플마다 get_elevation을
        불러서 지점당 rasterio 환경 진입/좌표변환 비용이 반복됐음 (히트맵 프로파일링에서 확인).
        DEM 범위 밖/nodata는 예전과 같이 0.0으로 채워짐.
        """
        from lorascape.data.coord_transform import distance_m

        total_dist = distance_m(lat1, lon1, lat2, lon2)
        t = np.linspace(0.0, 1.0, n_samples + 1)
        elevs = self.get_elevations_batch(lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t)
        return [(float(total_dist * ti), float(e)) for ti, e in zip(t, elevs)]


    def get_elevations_batch(self, lats, lons) -> np.ndarray:
        """
        여러 지점의 고도를 한 번에 조회함. lats/lons는 같은 shape의 배열이고 같은 shape로 반환함.
        get_elevation()과 동일한 규칙(DEM 범위 밖/nodata는 0.0)을 씀 - get_elevation_profile이
        구멍을 0.0으로 채우는 것과 결과가 같아야 히트맵이 예전 계산과 일치함.
        좌표변환을 지점마다 부르지 않고 배열로 한 번에 처리하는 게 핵심임.
        """
        lats = np.asarray(lats, dtype=float)
        lons = np.asarray(lons, dtype=float)
        xs, ys = rio_transform("EPSG:4326", self.crs, lons.ravel().tolist(), lats.ravel().tolist())
        cols_f, rows_f = ~self.dataset.transform * (np.asarray(xs), np.asarray(ys))
        rows = np.floor(rows_f).astype(int)
        cols = np.floor(cols_f).astype(int)

        h, w = self._band.shape
        valid = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)

        out = np.zeros(rows.shape, dtype=float)
        vals = self._band[rows[valid], cols[valid]].astype(float)
        if self._nodata is not None:
            vals[vals == self._nodata] = 0.0
        out[valid] = vals
        return out.reshape(lats.shape)


    def is_installable(self, lat: float, lon: float, min_elevation_diff: float = -5.0) -> bool:
        """
        K-means 후보지 보정용 함수임 (문서 3번 요구사항: '저지대/수면 등 설치 불가 지역'이면
        군집 내 가장 가까운 유효 지점으로 이동해야 함 - 그 판정을 이 함수가 담당함).

        지금은 아주 단순하게 '고도값이 없거나(수면/구멍) 비정상적으로 낮으면 설치 불가'로만 판정함.
        TODO: 실제로는 하천 범람 구역, 경사도, 접근성 등 조건이 더 필요할 수 있음 -
              일단 뼈대만 만들어두고 나중에 조건 추가하는 구조로 감.
        """
        elevation = self.get_elevation(lat, lon)
        if elevation is None:
            return False  # DEM 범위 밖이거나 nodata면 설치 불가로 간주
        return True  # 지금은 고도값만 있으면 일단 설치 가능으로 판정 (추후 조건 강화 필요)


    def read_elevation_grid(
        self, lat_min: float, lat_max: float, lon_min: float, lon_max: float,
        max_pixels: int = 800,
    ):
        """
        지정한 위경도 범위(bounding box)의 고도 격자를 numpy 배열로 읽어옴.
        지도 배경(음영기복도) 렌더링용으로 씀 - get_elevation처럼 점 하나씩이 아니라
        영역 전체를 한 번에 읽어야 해서 별도 메서드로 분리함.

        max_pixels: 너무 큰 DEM을 그대로 읽으면 화면에 다 못 보여주고 느려지기만 하니까
                    긴 변 기준으로 이 픽셀 수 이내로 다운샘플링함.

        반환값: (elevation_2d_array, (lon_min, lon_max, lat_min, lat_max)) 튜플임.
                두 번째 값은 나중에 화면에 그릴 때 좌표축 맞추는 용도(extent)로 씀.
        """
        from rasterio.warp import transform as rio_transform
        from rasterio.windows import from_bounds

        xs, ys = rio_transform("EPSG:4326", self.crs, [lon_min, lon_max], [lat_min, lat_max])
        window = from_bounds(xs[0], ys[0], xs[1], ys[1], transform=self.dataset.transform)

        # 원본 해상도로 읽으면 너무 클 수 있으니, out_shape으로 다운샘플링하며 읽음
        win_height = max(1, int(window.height))
        win_width = max(1, int(window.width))
        scale = min(1.0, max_pixels / max(win_height, win_width))
        out_h = max(1, int(win_height * scale))
        out_w = max(1, int(win_width * scale))

        data = self.dataset.read(1, window=window, out_shape=(out_h, out_w))

        if self.dataset.nodata is not None:
            data = np.where(data == self.dataset.nodata, np.nan, data)

        return data, (lon_min, lon_max, lat_min, lat_max)


    def close(self):
        """파일 핸들 정리함. with문으로 안 쓸 경우 명시적으로 호출 필요."""
        self.dataset.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_dem_latlon_bounds(dem_path: str) -> tuple:
    """
    DEM 파일의 지리적 범위를 위경도(EPSG:4326)로 반환하는 가벼운 함수임.
    (lon_min, lat_min, lon_max, lat_max) 순서로 반환함.

    DemLoader 클래스를 안 쓰고 별도 함수로 만든 이유: DemLoader.__init__은
    성능을 위해 밴드 전체를 메모리에 캐싱하는데, 여기선 "지리적 범위"라는
    메타데이터 하나만 필요해서 그 무거운 로딩을 할 필요가 없음 - 앱 시작
    시점에 빠르게 호출되어야 하는 함수라 가볍게 만듦.
    """
    with rasterio.open(dem_path) as dataset:
        bounds = dataset.bounds  # (left, bottom, right, top) - DEM 파일 자체 좌표계 기준
        lon_min, lat_min, lon_max, lat_max = rio_warp.transform_bounds(
            dataset.crs, "EPSG:4326", *bounds
        )
    return (lon_min, lat_min, lon_max, lat_max)