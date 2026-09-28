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
from scipy.ndimage import zoom

from lorascape.core.optimization.heatmap import HeatmapGrid

# dBm 구간별 색상임. ATDI 류 도구처럼 강함=빨강, 약함=파랑/투명 계열로 감.
# (threshold, RGBA) 순서로 위에서 아래로 검사함 - pr_to_color(map_layers.py)와
# 다른 이유는, 여기는 히트맵 '면' 색상이라 좀 더 세분화된 5단계+알파값이 필요해서임.
DEFAULT_COLOR_LEVELS = [
    (-80,  (255, 0, 0, 220)),      # 매우 강함 - 빨강 (기존 180 -> 220)
    (-90,  (255, 100, 0, 195)),    # 강함 - 주황 (기존 160 -> 195)
    (-100, (255, 220, 0, 165)),    # 보통 - 노랑 (기존 140 -> 165)
    (-110, (0, 200, 80, 140)),     # 약함 - 초록 (기존 120 -> 140)
    (-999, (0, 0, 0, 0)),          # 범위 밖 - 완전 투명
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


def _pr_to_alpha(pr: float, opacity: float = 1.0) -> int:
    """
    수신전력을 투명도(alpha)로 변환함. opacity(0.0~1.0)를 알파 최대값에 직접
    곱해서 반영함 - 예전엔 이 함수가 만든 알파값에 folium ImageOverlay의
    opacity 파라미터가 또 곱해지는 구조라, GW가 많아 레이어가 여러 장 겹칠
    때 이중으로 옅어지는 문제가 있었음. 이제는 여기서 opacity를 직접 반영해서
    최종 알파를 계산하고, ImageOverlay opacity는 1.0으로 고정해서 이중 감쇠를 없앰.
    """
    if pr >= -80:
        base = 235
    elif pr >= -90:
        base = 200
    elif pr >= -100:
        base = 160
    elif pr >= -110:
        base = 115
    elif pr >= -120:
        base = 65
    else:
        return 0  # 커버리지 없음 - 완전 투명 (opacity와 무관하게 항상 투명)

    return int(base * max(0.0, min(1.0, opacity)))


def render_heatmap_image(
    grid: HeatmapGrid, color_levels=None, base_color: tuple = None,
    smooth_factor: int = 4, opacity: float = 1.0,
) -> np.ndarray:
    """
    HeatmapGrid를 (H, W, 4) uint8 RGBA numpy 배열로 변환함.

    opacity: 0.0~1.0. base_color 모드(다중 GW)에서는 _pr_to_alpha에 직접 전달되고,
    단일 GW 그라데이션 모드에서는 각 레벨의 알파값에 곱해서 적용함. 두 모드 다
    여기서 최종 알파까지 확정하고, 호출부(map_layers)는 ImageOverlay opacity를
    1.0으로 고정해서 이중 감쇠를 방지함.
    """
    pr_grid = grid.pr_grid
    if smooth_factor > 1:
        clipped = np.clip(pr_grid, -140, None)
        pr_grid = zoom(clipped, smooth_factor, order=3)

    rows, cols = pr_grid.shape
    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)

    levels = color_levels or DEFAULT_COLOR_LEVELS
    scaled_levels = [
        (threshold, (r, g, b, int(a * max(0.0, min(1.0, opacity)))))
        for threshold, (r, g, b, a) in levels
    ]

    for i in range(rows):
        for j in range(cols):
            pr = pr_grid[i, j]
            if base_color is not None:
                alpha = _pr_to_alpha(pr, opacity)
                rgba[i, j] = (*base_color, alpha)
            else:
                rgba[i, j] = _pr_to_rgba(pr, scaled_levels)

    return np.flipud(rgba)


def build_heatmap_layer_dict(
    grid: HeatmapGrid, color_levels=None, base_color: tuple = None,
    smooth_factor: int = 4, opacity: float = 1.0,
) -> dict:
    """map_layers.add_heatmap_layers()가 기대하는 형태로 조립함. opacity를 그대로 전달함."""
    rgba = render_heatmap_image(grid, color_levels, base_color, smooth_factor, opacity)
    data_uri = to_data_uri(rgba)

    lat_min, lat_max, lon_min, lon_max = grid.bounds
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    return {
        "gw_id": grid.gw_id,
        "url": data_uri,
        "bounds": bounds,
    }
    


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