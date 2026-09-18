"""distance_window.py 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.distance_window import DistanceWindow, bearing
from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.core.optimization.gw_placement import ConnectionResult


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_gw(gw_id, lat, lon):
    return GatewaySite(
        gw_id=gw_id, region="테스트", location_desc="",
        lat=lat, lon=lon, install_type="테스트", power_source="테스트",
    )


def _make_node(node_id, lat, lon):
    return NodeSite(
        node_id=node_id, region="테스트", location_desc="",
        lat=lat, lon=lon, device_type="테스트", install_type="테스트",
    )


class FakeResult:
    """OptimizationResult 흉내 - connections만 있으면 됨."""
    def __init__(self, connections):
        self.connections = connections


def test_bearing_due_north_is_zero():
    # 같은 경도, 위도만 북쪽으로 이동 -> 방위각 0
    b = bearing(37.40, 127.10, 37.50, 127.10)
    assert b == pytest.approx(0.0, abs=0.5)


def test_bearing_due_east_is_90():
    b = bearing(37.40, 127.10, 37.40, 127.20)
    assert b == pytest.approx(90.0, abs=0.5)


def test_distance_window_fills_table_for_selected_gw(qapp):
    gws = [_make_gw("GW1", 37.40, 127.10)]
    nodes = [_make_node("N1", 37.41, 127.11), _make_node("N2", 37.42, 127.12)]
    win = DistanceWindow(gws, nodes)
    assert win.tbl.rowCount() == 2


def test_distance_window_marks_connected_node_status(qapp):
    gws = [_make_gw("GW1", 37.40, 127.10)]
    nodes = [_make_node("N1", 37.41, 127.11)]
    conn = ConnectionResult(gw_id="GW1", node_id="N1", path_loss_db=100, rx_power_dbm=-90, snr_db=5, sf=7)
    result = FakeResult({"N1": conn})

    win = DistanceWindow(gws, nodes, result=result)
    status_text = win.tbl.item(0, 4).text()
    assert "이 GW에 연결" in status_text


def test_distance_window_marks_unconnected_node_status(qapp):
    gws = [_make_gw("GW1", 37.40, 127.10)]
    nodes = [_make_node("N1", 37.41, 127.11)]
    result = FakeResult({"N1": None})

    win = DistanceWindow(gws, nodes, result=result)
    status_text = win.tbl.item(0, 4).text()
    assert "미연결" in status_text


def test_distance_window_set_data_updates_combo_and_table(qapp):
    win = DistanceWindow([_make_gw("GW1", 37.4, 127.1)], [_make_node("N1", 37.41, 127.11)])
    new_gws = [_make_gw("GWA", 37.4, 127.1), _make_gw("GWB", 37.5, 127.2)]
    new_nodes = [_make_node("NX", 37.41, 127.11), _make_node("NY", 37.42, 127.12)]
    win.set_data(new_gws, new_nodes)
    assert win.cb_gw.count() == 2
    assert win.tbl.rowCount() == 2


def test_distance_window_empty_gateways_shows_no_rows(qapp):
    win = DistanceWindow([], [_make_node("N1", 37.4, 127.1)])
    assert win.tbl.rowCount() == 0