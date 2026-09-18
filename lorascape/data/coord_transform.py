# lorascape/data/coord_transform.py
"""
위경도(WGS84) <-> 평면좌표 변환 모듈임.
K-means는 유클리드 거리를 쓰기 때문에 위경도(도 단위) 그대로 넣으면 왜곡됨
(위도 1도랑 경도 1도가 실제 거리로 다름) - 그래서 평면좌표로 변환하고 나서 클러스터링해야 함.

성남시는 EPSG:5186(GRS80 중부원점, 미터 단위계) 좌표계를 씀 - 국내 지자체 사업에서 표준적으로 쓰는 좌표계임.
"""
from pyproj import Transformer

# WGS84(위경도) -> EPSG:5186(성남시 등 중부원점 좌표계, 단위: m)
_to_planar = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
_to_latlon = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)


def latlon_to_xy(lat: float, lon: float) -> tuple[float, float]:
    """위경도 -> 평면좌표(m) 변환. always_xy=True라서 입력 순서는 (lon, lat)인 거 주의."""
    x, y = _to_planar.transform(lon, lat)
    return x, y


def xy_to_latlon(x: float, y: float) -> tuple[float, float]:
    """평면좌표(m) -> 위경도 변환. K-means centroid를 다시 지도에 표시할 때 씀."""
    lon, lat = _to_latlon.transform(x, y)
    return lat, lon


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 지점 사이의 평면거리(m)임. path_loss 계산할 때 d_km 구하는 용도로 씀."""
    x1, y1 = latlon_to_xy(lat1, lon1)
    x2, y2 = latlon_to_xy(lat2, lon2)
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5