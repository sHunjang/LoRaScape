"""MainWindow의 프로젝트 파일 연결 검증 (가짜 지도 위젯 사용)."""
import os

import pytest
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

import lorascape.gui.app_config as app_config
from lorascape.data.project_db import ProjectDB, KIND_GATEWAY, KIND_NODE
from lorascape.data.schema import GatewaySite, NodeSite
import lorascape.gui.main_window as mw
from lorascape.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    popups = []
    monkeypatch.setattr(mw, "_styled_message_box",
                        lambda *a, **k: type("_M", (), {"exec_": lambda self: popups.append(a[3])})())
    w = MainWindow()
    w.popups = popups
    yield w
    w.close()


def gw(gw_id, lat=37.40, lon=127.10, **kw):
    return GatewaySite(gw_id=gw_id, region="", location_desc="", lat=lat, lon=lon,
                       install_type="t", power_source="t", **kw)


def nd(node_id, lat=37.41, lon=127.11, **kw):
    return NodeSite(node_id=node_id, region="", location_desc="", lat=lat, lon=lon,
                    device_type="악취감지센서", install_type="t", **kw)


def pick_save(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))


def pick_open(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))


def read_back(path):
    with ProjectDB.open(str(path)) as p:
        return p.load_gateways(), p.load_nodes()


# ── 프로젝트 만들기/열기 ──

def test_new_project_stores_current_devices_and_sets_title(window, tmp_path, monkeypatch):
    window.gateways, window.nodes = [gw("G1"), gw("G2")], [nd("N1")]
    path = tmp_path / "성남.lsproj"
    pick_save(monkeypatch, path)
    window._on_new_project_clicked()
    assert window.project is not None and "성남" in window.windowTitle()
    assert [g.gw_id for g in window.project.load_gateways()] == ["G1", "G2"]
    assert [n.node_id for n in window.project.load_nodes()] == ["N1"]


def test_new_project_adds_extension_and_persists(window, tmp_path, monkeypatch):
    window.gateways, window.nodes = [gw("G1")], [nd("N1"), nd("N2")]
    pick_save(monkeypatch, tmp_path / "site")                       # 확장자를 안 적어도 .lsproj가 붙음
    window._on_new_project_clicked()
    assert os.path.exists(tmp_path / "site.lsproj")
    window.project.close(); window.project = None
    gws, nds = read_back(tmp_path / "site.lsproj")
    assert [g.gw_id for g in gws] == ["G1"] and [n.node_id for n in nds] == ["N1", "N2"]


def test_new_project_refuses_existing_file(window, tmp_path, monkeypatch):
    existing = tmp_path / "x.lsproj"
    existing.write_text("기존 내용")
    pick_save(monkeypatch, existing)
    window._on_new_project_clicked()
    assert window.project is None and existing.read_text() == "기존 내용" and window.popups


def test_open_project_replaces_screen_with_project_devices(window, tmp_path, monkeypatch):
    path = str(tmp_path / "p.lsproj")
    with ProjectDB.create(path, name="현장A") as p:
        p.sync_gateways([gw("A1", antenna_height_m=4.0)])
        p.sync_nodes([nd("AN1")])
    window.gateways = [gw("OLD")]
    window._open_project(path)
    assert [g.gw_id for g in window.gateways] == ["A1"] and window.gateways[0].antenna_height_m == 4.0
    assert [n.node_id for n in window.nodes] == ["AN1"]
    assert window.last_result is None and "현장A" in window.windowTitle()


def test_open_bad_file_shows_error_and_keeps_screen(window, tmp_path):
    bad = tmp_path / "bad.lsproj"
    bad.write_text("SQLite 아님")
    window.gateways = [gw("KEEP")]
    assert window._open_project(str(bad)) is False
    assert [g.gw_id for g in window.gateways] == ["KEEP"] and window.project is None and window.popups


def test_opening_another_project_closes_previous_one(window, tmp_path):
    for n in ("a", "b"):
        ProjectDB.create(str(tmp_path / f"{n}.lsproj"), name=n).close()
    window._open_project(str(tmp_path / "a.lsproj"))
    first = window.project
    window._open_project(str(tmp_path / "b.lsproj"))
    assert window.project is not first and first._conn is None


# ── 자동 저장 ──

def _with_project(window, tmp_path, monkeypatch, gws=None, nds=None):
    window.gateways, window.nodes = gws or [gw("G1"), gw("G2")], nds or [nd("N1")]
    pick_save(monkeypatch, tmp_path / "p.lsproj")
    window._on_new_project_clicked()
    return str(tmp_path / "p.lsproj")


def test_list_window_edit_is_saved_to_project(window, tmp_path, monkeypatch):
    path = _with_project(window, tmp_path, monkeypatch)
    window.gateways[0].antenna_height_m = 7.5          # 목록창에서 G1 높이를 고침
    window._on_gws_changed_from_list()
    assert window.project.load_gateways()[0].antenna_height_m == 7.5
    assert window.project.data_fidelity(KIND_GATEWAY)["params"]["antenna_height_m"]["explicit"] == 1


def test_list_window_delete_is_saved_to_project(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    del window.gateways[1]
    window._on_gws_changed_from_list()
    assert [g.gw_id for g in window.project.load_gateways()] == ["G1"]


def test_gw_and_node_drag_are_saved(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window._on_gw_dragged("G1", 127.5, 37.5)
    window._on_node_dragged("N1", 127.6, 37.6)
    assert (window.project.load_gateways()[0].lat, window.project.load_gateways()[0].lon) == (37.5, 127.5)
    assert (window.project.load_nodes()[0].lat, window.project.load_nodes()[0].lon) == (37.6, 127.6)


def test_context_menu_adds_are_saved_with_unique_ids_even_after_deletion(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch, gws=[gw("RCLICK_GW_1"), gw("RCLICK_GW_2")])
    del window.gateways[0]                              # 1번을 지운 뒤 새로 추가하면 예전엔 2번과 ID가 겹쳤음
    window._add_gw_at(37.45, 127.15)
    ids = [g.gw_id for g in window.gateways]
    assert len(set(ids)) == len(ids) == 2
    assert {g.gw_id for g in window.project.load_gateways()} == set(ids)
    window._add_node_at(37.46, 127.16)
    assert len(window.project.load_nodes()) == 2 and not window.popups


def test_applied_suggestions_are_saved(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window._on_suggestions_applied([gw("OPT_1")])
    assert "OPT_1" in [g.gw_id for g in window.project.load_gateways()]


def test_duplicate_ids_show_error_instead_of_crashing(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window.gateways.append(gw("G1"))                    # 목록창 CSV 가져오기 등으로 ID가 겹친 경우
    window._on_gws_changed_from_list()
    assert window.popups and "중복" in window.status_label.text()
    assert [g.gw_id for g in window.project.load_gateways()] == ["G1", "G2"]   # DB는 그대로


def test_without_project_nothing_is_persisted_and_nothing_breaks(window):
    window.gateways = [gw("G1")]
    window._on_gws_changed_from_list()
    window._on_gw_dragged("G1", 127.5, 37.5)
    window._add_gw_at(37.5, 127.5)
    assert window.project is None and not window.popups


# ── 엑셀 가져오기 병합 ──

def test_reimport_keeps_user_values_but_updates_positions(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window.gateways[0].antenna_height_m = 9.0
    window._on_gws_changed_from_list()
    window._on_data_loaded([gw("G1", lat=37.9, lon=127.9), gw("G2"), gw("G3")], None, target="gw")
    got = {g.gw_id: g for g in window.gateways}
    assert got["G1"].antenna_height_m == 9.0 and got["G1"].lat == 37.9 and "G3" in got
    assert "추가 1" in window.status_label.text()


def test_reimport_keeps_devices_missing_from_file(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window._on_data_loaded([gw("G1")], None, target="gw")
    assert {g.gw_id for g in window.gateways} == {"G1", "G2"}
    assert "파일에 없는 기존 1개 유지" in window.status_label.text()


def test_import_without_project_keeps_old_behavior(window):
    window._on_data_loaded([gw("X1")], [nd("Y1")], target="both")
    assert [g.gw_id for g in window.gateways] == ["X1"] and [n.node_id for n in window.nodes] == ["Y1"]


# ── 장비 기본값 ──

def test_changing_default_gw_height_reaches_project_and_non_overridden_gateways(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window.gateways[1].antenna_height_m = 8.0
    window._on_gws_changed_from_list()
    window._on_defaults_applied({KIND_GATEWAY: {"antenna_height_m": 3.0}})
    heights = {g.gw_id: g.antenna_height_m for g in window.gateways}
    assert heights == {"G1": 3.0, "G2": 8.0}
    assert window.project.get_defaults(KIND_GATEWAY)["antenna_height_m"] == 3.0
    assert "다시 실행" in window.status_label.text()


def test_default_change_survives_closing_and_reopening(window, tmp_path, monkeypatch):
    path = _with_project(window, tmp_path, monkeypatch)
    window._on_defaults_applied({KIND_GATEWAY: {"antenna_height_m": 3.0}})
    window.project.close(); window.project = None
    window._open_project(path)
    assert [g.antenna_height_m for g in window.gateways] == [3.0, 3.0]


def test_defaults_dialog_without_project_offers_to_create_one(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    window._open_defaults_dialog()
    assert window.project is None


# ── 마지막 프로젝트 / 백업 / 종료 ──

def test_reopen_last_project(window, tmp_path):
    path = str(tmp_path / "last.lsproj")
    with ProjectDB.create(path, name="마지막") as p:
        p.sync_gateways([gw("L1")])
    window._open_project(path)
    window.project.close(); window.project = None
    window.gateways = []
    window._settings = app_config.load_config()
    assert window.reopen_last_project() is True
    assert [g.gw_id for g in window.gateways] == ["L1"]


def test_reopen_last_project_missing_file_is_quiet(window, tmp_path):
    window._settings["last_project_path"] = str(tmp_path / "사라짐.lsproj")
    assert window.reopen_last_project() is False
    assert "찾을 수 없습니다" in window.status_label.text() and not window.popups


def test_backup_creates_valid_copy(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    window.gateways[0].antenna_height_m = 5.5
    window._on_gws_changed_from_list()
    pick_save(monkeypatch, tmp_path / "백업")
    window._on_backup_project_clicked()
    gws, _ = read_back(tmp_path / "백업.lsproj")
    assert gws[0].antenna_height_m == 5.5


def test_backup_without_project_shows_notice(window):
    window._on_backup_project_clicked()
    assert window.popups


def test_close_event_closes_project(window, tmp_path, monkeypatch):
    _with_project(window, tmp_path, monkeypatch)
    proj = window.project
    window.close()
    assert window.project is None and proj._conn is None


def test_toolbar_has_project_and_defaults_actions(window):
    from PyQt5.QtWidgets import QToolBar, QToolButton
    tb = window.findChild(QToolBar)
    labels = [a.text() for a in tb.actions()]
    assert "프로젝트" in labels and "장비 기본값" in labels
    btn = tb.widgetForAction([a for a in tb.actions() if a.text() == "프로젝트"][0])
    assert btn.popupMode() == QToolButton.InstantPopup


# ── 시작 시 자동 열기 ──

def _saved_project(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    path = str(tmp_path / "auto.lsproj")
    with ProjectDB.create(path, name="자동") as p:
        p.sync_gateways([gw("A1")])
    app_config.update_config(last_project_path=path)
    return path


def test_window_does_not_reopen_project_by_default(qapp, tmp_path, monkeypatch):
    _saved_project(tmp_path, monkeypatch)
    w = MainWindow()
    assert w.project is None and w.gateways == []
    w.close()


def test_auto_open_project_reopens_last_one(qapp, tmp_path, monkeypatch):
    _saved_project(tmp_path, monkeypatch)
    w = MainWindow(auto_open_project=True)
    assert w.project is not None and [g.gw_id for g in w.gateways] == ["A1"]
    w.close()


def test_startup_excel_autoload_is_skipped_when_project_opened(qapp, tmp_path, monkeypatch):
    """프로젝트가 있으면 지난 세션의 엑셀 자동 로딩이 지워 둔 장비를 되살리면 안 됨."""
    _saved_project(tmp_path, monkeypatch)
    loads = []
    monkeypatch.setattr(MainWindow, "_load_data", lambda self, silent=False: loads.append(silent))
    w = MainWindow(xlsx_path="지난번.xlsx", auto_open_project=True)
    assert loads == []
    w.close()


def test_startup_excel_autoload_still_runs_without_project(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    loads = []
    monkeypatch.setattr(MainWindow, "_load_data", lambda self, silent=False: loads.append(silent))
    w = MainWindow(xlsx_path="지난번.xlsx", auto_open_project=True)     # 저장된 프로젝트 없음
    assert loads == [True]
    w.close()
