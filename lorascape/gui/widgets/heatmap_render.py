# lorascape/gui/widgets/heatmap_render.py
"""
HeatmapGrid(dBm 격자 데이터)를 실제 색상 PNG 이미지로 변환하는 모듈임.
folium.raster_layers.ImageOverlay가 요구하는 형태(base64 data URI 또는 파일 경로)로
만들어서 map_layers.py의 add_heatmap_layers()가 그대로 쓸 수 있게 함.

dBm -> 색상 매핑은 legend_window.py 참고 파일의 기본 구간(PR_COLOR_LEVELS)과
동일한 기준을 씀 - 나중에 사용자가 legend_window에서 커스터마이즈하면 그 값을
여기 넘겨받아 쓰면 됨 (지금은 기본값 하드코딩).
"""
import base64
import io
import numpy as np
from PIL import Image

from lorascape.core.optimization.heatmap import HeatmapGrid

# dBm 구간별 색상임. ATDI 류 도구처럼 강함=빨강, 약함=파랑/투명 계열로 감.
# (threshold, RGBA) 순서로 위에서 아래로 검사함 - pr_to_color(map_layers.py)와
# 다른 이유는, 여기는 히트맵 '면' 색상이라 좀 더 세분화된 5단계+알파값이 필요해서임.
DEFAULT_COLOR_LEVELS = [
    (-80,  (255, 0, 0, 180)),      # 매우 강함 - 빨강
    (-90,  (255, 100, 0, 160)),    # 강함 - 주황
    (-100, (255, 220, 0, 140)),    # 보통 - 노랑
    (-110, (0, 200, 80, 120)),     # 약함 - 초록
    (-999, (0, 0, 0, 0)),          # 범위 밖 - 완전 투명 (커버리지 없다는 뜻)
]


def _pr_to_rgba(pr: float, color_levels=None) -> tuple:
    levels = color_levels or DEFAULT_COLOR_LEVELS
    for threshold, rgba in levels:
        if pr >= threshold:
            return rgba
    return (0, 0, 0, 0)


def render_heatmap_image(grid: HeatmapGrid, color_levels=None) -> np.ndarray:
    """
    HeatmapGrid를 (H, W, 4) uint8 RGBA numpy 배열로 변환함.
    folium ImageOverlay는 이미지의 (0,0)이 왼쪽 위(북서쪽)라고 가정하는데,
    우리 pr_grid는 lat_grid를 오름차순(남->북)으로 만들었으니 위아래를 뒤집어야
    실제 지도 방향과 맞음 (이 뒤집기를 빼먹으면 히트맵이 위아래가 뒤집혀서 나타남).
    """
    rows, cols = grid.pr_grid.shape
    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)

    for i in range(rows):
        for j in range(cols):
            rgba[i, j] = _pr_to_rgba(grid.pr_grid[i, j], color_levels)

    return np.flipud(rgba)  # 남->북 순서 배열을 이미지 좌표계(북이 위)로 뒤집음


def to_data_uri(rgba_image: np.ndarray) -> str:
    """
    RGBA numpy 배열을 PNG base64 data URI 문자열로 변환함. folium의
    ImageOverlay(image=...)에 파일 경로 대신 이 문자열을 바로 넣을 수 있음 -
    임시파일을 따로 관리 안 해도 되는 장점이 있음.
    """
    img = Image.fromarray(rgba_image, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_heatmap_layer_dict(grid: HeatmapGrid, color_levels=None) -> dict:
    """
    map_layers.add_heatmap_layers()가 기대하는 형태({'gw_id', 'url', 'bounds'})로
    조립해서 반환함. main_window가 이 함수 결과를 그대로 refresh(heatmaps=[...])에
    넘기면 됨.
    """
    rgba = render_heatmap_image(grid, color_levels)
    data_uri = to_data_uri(rgba)

    lat_min, lat_max, lon_min, lon_max = grid.bounds
    # folium ImageOverlay의 bounds는 [[lat_min, lon_min], [lat_max, lon_max]] 형태임
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    return {
        "gw_id": grid.gw_id,
        "url": data_uri,
        "bounds": bounds,
    }