"""result_panel.py 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.result_panel import ResultPanel
from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.core.optimization.gw_placement import optimize_gw_placement


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeFlatDem:
    """평지 지형(장애물 없음)을 흉내 내는 가짜 DEM임."""

    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=20):
        from lorascape.data.coord_transform import distance_m
        total = distance_m(lat1, lon1, lat2, lon2)
        return [(total * i / n_samples, 50.0) for i in range(n_samples + 1)]

    def is_installable(self, lat, lon):
        return True


def _make_node(node_id, lat, lon):
    return NodeSite(
        node_id=node_id, region="테스트", location_desc="",
        lat=lat, lon=lon, device_type="테스트", install_type="테스트",
    )


def test_result_panel_creates_without_error(qapp):
    panel = ResultPanel()
    assert panel is not None


def test_show_result_updates_coverage_card(qapp):
    nodes = [
        _make_node("N1", 37.4000, 127.1200),
        _make_node("N2", 37.4001, 127.1201),
    ]
    dem = FakeFlatDem()
    result = optimize_gw_placement(nodes, dem, initial_k=1, max_k=3, coverage_target=1.0)

    panel = ResultPanel()
    panel.show_result(result, total_nodes=len(nodes))

    assert "%" in panel.card_coverage._value_lbl.text()
    assert panel.card_gw_count._value_lbl.text() == str(result.k)
    assert panel.card_node_count._value_lbl.text() == "2"


def test_show_result_populates_sf_distribution(qapp):
    nodes = [_make_node("N1", 37.4000, 127.1200)]
    dem = FakeFlatDem()
    result = optimize_gw_placement(nodes, dem, initial_k=1, max_k=3, coverage_target=1.0)

    panel = ResultPanel()
    panel.show_result(result, total_nodes=len(nodes))

    # 연결된 Node의 sf 값에 해당하는 막대에 1개가 잡혀야 함
    conn = next(c for c in result.connections.values() if c is not None)
    assert panel._sf_rows[conn.sf]._value_lbl.text() == "1개"


def test_show_result_computes_overlap_percentage(qapp):
    # Node들이 여러 GW에 동시에 잡히도록 서로 아주 가까이 배치함
    nodes = [
        _make_node("N1", 37.4000, 127.1200),
        _make_node("N2", 37.4000, 127.1200),
    ]
    dem = FakeFlatDem()
    result = optimize_gw_placement(nodes, dem, initial_k=1, max_k=3, coverage_target=1.0)

    panel = ResultPanel()
    panel.show_result(result, total_nodes=len(nodes))
    assert "%" in panel.card_overlap._value_lbl.text()


def test_show_loading_resets_cards(qapp):
    panel = ResultPanel()
    panel.show_loading()
    assert panel.card_status._value_lbl.text() == "계산 중..."
    assert panel.card_overlap._value_lbl.text() == "─"


def test_show_error_sets_status_card(qapp):
    panel = ResultPanel()
    panel.show_error("문제 발생")
    assert panel.card_status._value_lbl.text() == "오류"