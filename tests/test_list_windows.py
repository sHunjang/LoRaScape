"""
gw_list_window.py / node_list_window.py 검증 테스트임. QApplication 필요함.
"""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.gw_list_window import GWListWindow
from lorascape.gui.widgets.node_list_window import NodeListWindow
from lorascape.data.schema import GatewaySite, NodeSite


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


def test_gw_list_window_fills_table_rows(qapp):
    gws = [_make_gw("GW1", 37.40, 127.12), _make_gw("GW2", 37.41, 127.13)]
    win = GWListWindow(gws)
    assert win.tbl.rowCount() == 2
    assert win.tbl.item(0, 1).text() == "GW1"  # GW ID 컬럼


def test_gw_list_window_set_gateways_updates_table(qapp):
    win = GWListWindow([_make_gw("GW1", 37.40, 127.12)])
    new_gws = [_make_gw("GWA", 37.4, 127.1), _make_gw("GWB", 37.5, 127.2), _make_gw("GWC", 37.6, 127.3)]
    win.set_gateways(new_gws)
    assert win.tbl.rowCount() == 3


def test_node_list_window_fills_table_rows(qapp):
    nodes = [_make_node("N1", 37.40, 127.12), _make_node("N2", 37.41, 127.13)]
    win = NodeListWindow(nodes)
    assert win.tbl.rowCount() == 2
    assert win.tbl.item(0, 0).text() == "N1"


def test_node_list_window_set_nodes_updates_table(qapp):
    win = NodeListWindow([_make_node("N1", 37.40, 127.12)])
    win.set_nodes([_make_node("NX", 37.4, 127.1), _make_node("NY", 37.5, 127.2)])
    assert win.tbl.rowCount() == 2
    
    
def test_gw_list_window_emits_load_excel_signal(qapp, tmp_path):
    """엑셀 불러오기 버튼 -> QFileDialog를 거치는 부분은 실제 파일 다이얼로그라 자동테스트가
    까다로우니, 시그널 자체가 존재하고 emit 가능한지만 확인함 (실제 클릭 흐름은 수동 확인)."""
    win = GWListWindow([_make_gw("GW1", 37.40, 127.12)])
    received = []
    win.sig_load_excel_requested.connect(lambda path: received.append(path))
    win.sig_load_excel_requested.emit("dummy.xlsx")
    assert received == ["dummy.xlsx"]


def test_node_list_window_emits_load_excel_signal(qapp):
    win = NodeListWindow([_make_node("N1", 37.40, 127.12)])
    received = []
    win.sig_load_excel_requested.connect(lambda path: received.append(path))
    win.sig_load_excel_requested.emit("dummy.xlsx")
    assert received == ["dummy.xlsx"]