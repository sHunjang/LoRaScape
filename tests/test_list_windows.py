"""
gw_list_window.py / node_list_window.py 검증 테스트임. QApplication 필요함.
"""
import pytest

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog

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
    

def test_gw_list_window_add_appends_and_emits(qapp, monkeypatch):
    from lorascape.gui.widgets.dialogs import GWParamDialog
    win = GWListWindow([])

    # GWParamDialog가 실제로 뜨는 걸 막고 바로 accept된 것처럼 동작하게 함
    monkeypatch.setattr(GWParamDialog, "exec_", lambda self: QDialog.Accepted)
    monkeypatch.setattr(GWParamDialog, "apply_to", lambda self, gw: None)

    changed = []
    win.sig_gws_changed.connect(lambda: changed.append(True))
    win._on_add_gw()

    assert len(win.gateways) == 1
    assert changed == [True]


def test_gw_list_window_delete_selected_removes_rows(qapp):
    win = GWListWindow([_make_gw("GW1", 37.4, 127.1), _make_gw("GW2", 37.5, 127.2)])
    win.tbl.selectRow(0)
    win._on_delete_selected()
    assert len(win.gateways) == 1
    assert win.gateways[0].gw_id == "GW2"


def test_gw_list_window_delete_all_clears_list(qapp, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    win = GWListWindow([_make_gw("GW1", 37.4, 127.1)])
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    win._on_delete_all()
    assert len(win.gateways) == 0


def test_gw_list_window_selected_coverage_emits_ids(qapp):
    win = GWListWindow([_make_gw("GW1", 37.4, 127.1), _make_gw("GW2", 37.5, 127.2)])
    win.tbl.selectRow(1)
    received = []
    win.sig_selected_coverage_requested.connect(lambda ids: received.append(ids))
    win._on_show_selected_coverage()
    assert received == [["GW2"]]


def test_gw_list_window_csv_roundtrip(qapp, tmp_path):
    win = GWListWindow([_make_gw("GW1", 37.4, 127.1)])
    csv_path = tmp_path / "gws.csv"

    from PyQt5.QtWidgets import QFileDialog
    import lorascape.gui.widgets.gw_list_window as mod
    win._on_export_csv.__globals__  # no-op to reference module context

    # QFileDialog 팝업 없이 바로 경로를 리턴하게 monkeypatch
    orig_save = QFileDialog.getSaveFileName
    orig_open = QFileDialog.getOpenFileName
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(csv_path), ""))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(csv_path), ""))
    try:
        win._on_export_csv()
        win2 = GWListWindow([])
        win2._on_import_csv()
        assert len(win2.gateways) == 1
        assert win2.gateways[0].gw_id == "GW1"
    finally:
        QFileDialog.getSaveFileName = orig_save
        QFileDialog.getOpenFileName = orig_open


def test_node_list_window_random_placement_adds_requested_count(qapp, monkeypatch):
    from PyQt5.QtWidgets import QInputDialog
    win = NodeListWindow([_make_node("N1", 37.4, 127.1)])
    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (5, True))
    win._on_random_placement()
    assert len(win.nodes) == 6  # 기존 1개 + 랜덤 5개


def test_node_list_window_delete_selected_removes_rows(qapp):
    win = NodeListWindow([_make_node("N1", 37.4, 127.1), _make_node("N2", 37.5, 127.2)])
    win.tbl.selectRow(0)
    win._on_delete_selected()
    assert len(win.nodes) == 1
    assert win.nodes[0].node_id == "N2"