"""suggestion_window.py 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication, QDialog
from lorascape.gui.widgets.suggestion_window import SuggestionWindow
from lorascape.data.schema import GatewaySite


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


def test_suggestion_window_fills_table(qapp):
    suggested = [_make_gw("OPT_GW_001", 37.4, 127.1), _make_gw("OPT_GW_002", 37.5, 127.2)]
    node_gw_ids = {"N1": ["OPT_GW_001"], "N2": ["OPT_GW_001", "OPT_GW_002"]}
    win = SuggestionWindow("테스트 제안", suggested, node_gw_ids)
    assert win.tbl.rowCount() == 2


def test_suggestion_window_computes_newly_covered_count(qapp):
    suggested = [_make_gw("OPT_GW_001", 37.4, 127.1)]
    node_gw_ids = {"N1": ["OPT_GW_001"], "N2": ["OPT_GW_001"], "N3": []}
    win = SuggestionWindow("테스트 제안", suggested, node_gw_ids)
    assert win.tbl.item(0, 4).text() == "2"


def test_suggestion_window_apply_emits_only_checked(qapp):
    suggested = [_make_gw("OPT_GW_001", 37.4, 127.1), _make_gw("OPT_GW_002", 37.5, 127.2)]
    win = SuggestionWindow("테스트 제안", suggested, {})

    # 두 번째 행 체크 해제
    win.tbl.cellWidget(1, 0).setChecked(False)

    received = []
    win.sig_apply_requested.connect(lambda gws: received.append(gws))
    win._on_apply()

    assert len(received[0]) == 1
    assert received[0][0].gw_id == "OPT_GW_001"


def test_suggestion_window_select_all_checks_everything(qapp):
    suggested = [_make_gw("A", 37.4, 127.1), _make_gw("B", 37.5, 127.2)]
    win = SuggestionWindow("테스트", suggested, {})
    win._set_all_checked(False)
    win._set_all_checked(True)
    for r in range(win.tbl.rowCount()):
        assert win.tbl.cellWidget(r, 0).isChecked()


def test_suggestion_window_apply_with_nothing_checked_rejects(qapp):
    suggested = [_make_gw("A", 37.4, 127.1)]
    win = SuggestionWindow("테스트", suggested, {})
    win._set_all_checked(False)

    received = []
    win.sig_apply_requested.connect(lambda gws: received.append(gws))
    win._on_apply()

    assert received == []  # 아무것도 체크 안 했으면 emit 안 되고 그냥 닫혀야 함