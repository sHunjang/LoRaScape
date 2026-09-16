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


# 다중 GW 선택 시 각 GW에 배정할 색조(hue) 팔레트임. 색상환에서 서로 최대한
# 멀리 떨어지게 골라서, 겹치는 지역도 시각적으로 구분되게 함.
# (dBm 강도는 알파값으로, GW 구분은 색상으로 표현하는 방식 - ATDI 참고사례와
# 유사하게 GW별로 톤을 다르게 가져감)
GW_HUE_PALETTE = [
    (255, 60, 60),    # 빨강
    (60, 140, 255),   # 파랑
    (60, 220, 100),   # 초록
    (255, 180, 40),   # 주황
    (200, 80, 255),   # 보라
    (40, 220, 220),   # 청록
    (255, 100, 180),  # 분홍
    (180, 220, 40),   # 연두
]


def get_gw_color(index: int) -> tuple:
    """GW 인덱스에 따라 팔레트에서 색상을 순환 배정함."""
    return GW_HUE_PALETTE[index % len(GW_HUE_PALETTE)]


def _pr_to_rgba(pr: float, color_levels=None) -> tuple:
    levels = color_levels or DEFAULT_COLOR_LEVELS
    for threshold, rgba in levels:
        if pr >= threshold:
            return rgba
    return (0, 0, 0, 0)


def _pr_to_alpha(pr: float) -> int:
    """
    수신전력을 투명도(alpha)로 변환함. 신호가 강할수록 진하게, 약할수록 옅게
    보이도록 함 - 다중 GW 색상 구분 모드에서는 색상 자체가 GW를 구분하는
    용도라서, 강도는 알파(투명도)로 표현하는 방식으로 바꿈.
    """
    if pr >= -80:
        return 200
    elif pr >= -90:
        return 170
    elif pr >= -100:
        return 130
    elif pr >= -110:
        return 90
    elif pr >= -120:
        return 50
    else:
        return 0  # 커버리지 없음 - 완전 투명


def render_heatmap_image(grid: HeatmapGrid, color_levels=None, base_color: tuple = None) -> np.ndarray:
    """
    HeatmapGrid를 (H, W, 4) uint8 RGBA numpy 배열로 변환함.

    base_color가 주어지면(다중 GW 모드): 그 색상 고정 + pr값에 따라 알파(투명도)만
    다르게 해서, GW별로 색조가 구분되게 함.
    base_color가 None이면(단일 GW 모드): 기존처럼 dBm 구간별 5색 그라데이션(빨강~파랑)을 씀.
    """
    rows, cols = grid.pr_grid.shape
    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)

    for i in range(rows):
        for j in range(cols):
            pr = grid.pr_grid[i, j]
            if base_color is not None:
                alpha = _pr_to_alpha(pr)
                rgba[i, j] = (*base_color, alpha)
            else:
                rgba[i, j] = _pr_to_rgba(pr, color_levels)

    return np.flipud(rgba)


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


def build_heatmap_layer_dict(grid: HeatmapGrid, color_levels=None, base_color: tuple = None) -> dict:
    """
    map_layers.add_heatmap_layers()가 기대하는 형태({'gw_id', 'url', 'bounds'})로
    조립해서 반환함. main_window가 이 함수 결과를 그대로 refresh(heatmaps=[...])에
    넘기면 됨.

    base_color가 주어지면(다중 GW 모드): render_heatmap_image에 그대로 전달해서
    GW별로 색조가 구분되게 함.
    """
    rgba = render_heatmap_image(grid, color_levels, base_color)
    data_uri = to_data_uri(rgba)

    lat_min, lat_max, lon_min, lon_max = grid.bounds
    # folium ImageOverlay의 bounds는 [[lat_min, lon_min], [lat_max, lon_max]] 형태임
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    return {
        "gw_id": grid.gw_id,
        "url": data_uri,
        "bounds": bounds,
    }