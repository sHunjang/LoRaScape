"""heatmap_render.py 검증 테스트임. Qt 없이 numpy/PIL만으로 테스트 가능함."""
import numpy as np
import base64
from lorascape.core.optimization.heatmap import HeatmapGrid
from lorascape.gui.widgets.heatmap_render import (
    _pr_to_rgba, render_heatmap_image, to_data_uri, build_heatmap_layer_dict,
    DEFAULT_COLOR_LEVELS,
)


def _make_grid(pr_values: np.ndarray) -> HeatmapGrid:
    rows, cols = pr_values.shape
    lat_grid = np.linspace(37.39, 37.41, rows).reshape(-1, 1).repeat(cols, axis=1)
    lon_grid = np.linspace(127.11, 127.13, cols).reshape(1, -1).repeat(rows, axis=0)
    return HeatmapGrid(
        gw_id="GW1", pr_grid=pr_values, lat_grid=lat_grid, lon_grid=lon_grid,
        bounds=(37.39, 37.41, 127.11, 127.13),
    )


def test_pr_to_rgba_strong_signal_is_red():
    assert _pr_to_rgba(-70) == DEFAULT_COLOR_LEVELS[0][1]


def test_pr_to_rgba_out_of_range_is_transparent():
    assert _pr_to_rgba(-500) == (0, 0, 0, 0)


def test_render_heatmap_image_shape_matches_grid():
    """
    smooth_factor=1(보간 없음)일 때는 원본 격자 크기와 이미지 크기가 그대로 일치해야 함.
    기본값(smooth_factor=4)으로는 업샘플링되므로 크기가 달라지는 게 정상 동작임
    - 그건 test_render_heatmap_image_smooth_factor_upsamples_dimensions에서 별도로 검증함.
    """
    pr_values = np.full((10, 8), -85.0)
    grid = _make_grid(pr_values)
    rgba = render_heatmap_image(grid, smooth_factor=1)
    assert rgba.shape == (10, 8, 4)


def test_render_heatmap_image_flips_vertically():
    """남->북 순서 배열이 이미지 좌표계(북이 위)로 뒤집혀야 함을 확인함."""
    pr_values = np.zeros((4, 4))
    pr_values[0, :] = -70   # 남쪽(배열 첫 행) - 강한 신호(빨강)
    pr_values[-1, :] = -999  # 북쪽(배열 마지막 행) - 신호 없음(투명)

    grid = _make_grid(pr_values)
    rgba = render_heatmap_image(grid)

    # 뒤집었으니 이미지의 첫 행(위쪽, 북쪽)이 투명이어야 하고, 마지막 행(아래쪽, 남쪽)이 빨강이어야 함
    assert tuple(rgba[0, 0]) == (0, 0, 0, 0)
    assert tuple(rgba[-1, 0]) == DEFAULT_COLOR_LEVELS[0][1]


def test_to_data_uri_produces_valid_base64_png_header():
    rgba = np.zeros((5, 5, 4), dtype=np.uint8)
    uri = to_data_uri(rgba)
    assert uri.startswith("data:image/png;base64,")

    b64_part = uri.split(",", 1)[1]
    decoded = base64.b64decode(b64_part)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 파일 매직 넘버 확인


def test_build_heatmap_layer_dict_has_expected_keys():
    pr_values = np.full((5, 5), -90.0)
    grid = _make_grid(pr_values)
    layer = build_heatmap_layer_dict(grid)

    assert layer["gw_id"] == "GW1"
    assert layer["url"].startswith("data:image/png;base64,")
    assert layer["bounds"] == [[37.39, 127.11], [37.41, 127.13]]
    

def test_pr_to_alpha_strong_signal_has_higher_alpha_than_weak():
    from lorascape.gui.widgets.heatmap_render import _pr_to_alpha
    assert _pr_to_alpha(-75) > _pr_to_alpha(-105)


def test_pr_to_alpha_out_of_range_is_fully_transparent():
    from lorascape.gui.widgets.heatmap_render import _pr_to_alpha
    assert _pr_to_alpha(-500) == 0


def test_render_heatmap_image_smooth_factor_upsamples_dimensions():
    pr_values = np.full((10, 10), -90.0)
    grid = _make_grid(pr_values)

    rgba_smooth = render_heatmap_image(grid, smooth_factor=4)
    rgba_raw = render_heatmap_image(grid, smooth_factor=1)

    assert rgba_smooth.shape[0] == rgba_raw.shape[0] * 4
    assert rgba_smooth.shape[1] == rgba_raw.shape[1] * 4


def test_build_heatmap_layer_dict_accepts_smooth_factor():
    pr_values = np.full((8, 8), -95.0)
    grid = _make_grid(pr_values)
    layer = build_heatmap_layer_dict(grid, smooth_factor=2)
    assert layer["url"].startswith("data:image/png;base64,")