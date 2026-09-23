"""map_widget.py의 refresh()가 layers 함수들에 올바른 인자를 전달하는지 확인함.
실제 지도 렌더링(QWebEngineView)보다는 호출 인자 정합성에 집중함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.map_widget import MapWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_refresh_passes_show_pr_layer_false_when_heatmaps_present(qapp, monkeypatch):
    """히트맵이 있으면 add_coverage_layers에 show_pr_layer=False가 전달되는지 확인함."""
    import lorascape.gui.widgets.map_widget as mod

    captured = {}
    original = mod.layers.add_coverage_layers

    def _spy(m, nodes, result, selected_gws, cov_opacity, show_pr_layer=True):
        captured["show_pr_layer"] = show_pr_layer

    monkeypatch.setattr(mod.layers, "add_coverage_layers", _spy)

    widget = MapWidget()
    widget.refresh(heatmaps=[{"gw_id": "GW1", "url": "data:image/png;base64,", "bounds": [[0, 0], [1, 1]]}])

    assert captured["show_pr_layer"] is False


def test_refresh_passes_show_pr_layer_true_when_no_heatmaps(qapp, monkeypatch):
    import lorascape.gui.widgets.map_widget as mod

    captured = {}

    def _spy(m, nodes, result, selected_gws, cov_opacity, show_pr_layer=True):
        captured["show_pr_layer"] = show_pr_layer

    monkeypatch.setattr(mod.layers, "add_coverage_layers", _spy)

    widget = MapWidget()
    widget.refresh(heatmaps=None)

    assert captured["show_pr_layer"] is True