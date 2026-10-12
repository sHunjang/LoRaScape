"""프로젝트 파일(SQLite) 저장 계층 검증 테스트임 (Qt 불필요)."""
import os
import sqlite3

import pytest

from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.data.project_db import (
    ProjectDB, ProjectFormatError, ProjectTooNewError, SCHEMA_VERSION,
    KIND_GATEWAY, KIND_NODE, SOURCE_USER, SOURCE_IMPORT,
)


def gw(gw_id, lat=37.40, lon=127.10, **kw):
    return GatewaySite(gw_id=gw_id, region="탄천", location_desc=f"{gw_id} 위치", lat=lat, lon=lon,
                       install_type="스마트폴", power_source="상시전원", **kw)


def nd(node_id, lat=37.41, lon=127.11, **kw):
    return NodeSite(node_id=node_id, region="탄천", location_desc="", lat=lat, lon=lon,
                    device_type="악취감지센서", install_type="벽부", **kw)


@pytest.fixture
def db(tmp_path):
    with ProjectDB.create(str(tmp_path / "site.lsproj"), name="성남") as d:
        yield d


# ── 생성/열기 ──

def test_create_open_roundtrip_keeps_name(tmp_path):
    path = str(tmp_path / "a.lsproj")
    ProjectDB.create(path, name="성남시", app_version="1.5.0").close()
    with ProjectDB.open(path) as d:
        assert d.name == "성남시" and d.get_meta("created_with") == "1.5.0"


def test_create_refuses_to_overwrite_existing_file(tmp_path):
    path = tmp_path / "a.lsproj"
    path.write_text("소중한 파일")
    with pytest.raises(FileExistsError):
        ProjectDB.create(str(path))
    assert path.read_text() == "소중한 파일"


def test_open_rejects_non_project_files(tmp_path):
    bad = tmp_path / "x.lsproj"
    bad.write_text("이건 SQLite가 아님")
    with pytest.raises(ProjectFormatError):
        ProjectDB.open(str(bad))
    other = tmp_path / "other.db"
    c = sqlite3.connect(str(other)); c.execute("CREATE TABLE t (a)"); c.commit(); c.close()
    with pytest.raises(ProjectFormatError):
        ProjectDB.open(str(other))


def test_open_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        ProjectDB.open(str(tmp_path / "없음.lsproj"))


def test_open_rejects_project_from_newer_version(tmp_path):
    path = str(tmp_path / "new.lsproj")
    ProjectDB.create(path).close()
    c = sqlite3.connect(path); c.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}"); c.commit(); c.close()
    with pytest.raises(ProjectTooNewError):
        ProjectDB.open(path)


# ── 기본값 ──

def test_factory_default_gw_height_is_1_5_from_schema(db):
    assert db.get_defaults(KIND_GATEWAY)["antenna_height_m"] == 1.5
    assert db.factory_defaults(KIND_GATEWAY)["antenna_height_m"] == GatewaySite.__dataclass_fields__["antenna_height_m"].default


def test_sync_with_default_values_stores_no_explicit_rows(db):
    db.sync_gateways([gw("G1"), gw("G2")])
    fid = db.data_fidelity(KIND_GATEWAY)
    assert fid["total"] == 2
    assert all(v["explicit"] == 0 and v["default"] == 2 for v in fid["params"].values())


def test_user_edit_is_stored_as_explicit_and_others_stay_default(db):
    gws = [gw("G1"), gw("G2"), gw("G3")]
    db.sync_gateways(gws)
    gws[1].antenna_height_m = 5.0                       # 목록창에서 G2 높이를 고침
    db.sync_gateways(gws)
    loaded = {g.gw_id: g for g in db.load_gateways()}
    assert loaded["G2"].antenna_height_m == 5.0 and loaded["G1"].antenna_height_m == 1.5
    assert db.data_fidelity(KIND_GATEWAY)["params"]["antenna_height_m"] == {"explicit": 1, "default": 2}
    src = db._conn.execute("SELECT source FROM device_params WHERE id='G2'").fetchone()[0]
    assert src == SOURCE_USER


def test_changing_default_applies_to_non_overridden_devices_only(db):
    gws = [gw("G1"), gw("G2")]
    db.sync_gateways(gws)
    gws[1].antenna_height_m = 5.0
    db.sync_gateways(gws)
    db.set_default(KIND_GATEWAY, "antenna_height_m", 3.0)
    heights = {g.gw_id: g.antenna_height_m for g in db.load_gateways()}
    assert heights == {"G1": 3.0, "G2": 5.0}            # 직접 입력한 G2는 그대로
    db.set_default(KIND_GATEWAY, "antenna_height_m", 1.5)   # 공장 기본값으로 되돌리면 덮어쓰기 삭제
    assert db._conn.execute("SELECT COUNT(*) FROM defaults").fetchone()[0] == 0
    assert {g.gw_id: g.antenna_height_m for g in db.load_gateways()} == {"G1": 1.5, "G2": 5.0}


def test_set_default_rejects_unknown_param(db):
    with pytest.raises(ValueError):
        db.set_default(KIND_GATEWAY, "region", 1.0)


def test_new_device_created_in_app_with_custom_value_is_marked_user(db):
    db.sync_gateways([gw("G1", antenna_height_m=8.0)])
    assert db.load_gateways()[0].antenna_height_m == 8.0
    assert db.data_fidelity(KIND_GATEWAY)["params"]["antenna_height_m"]["explicit"] == 1


def test_setting_value_back_to_default_after_default_changed(db):
    """기본값을 3.0으로 바꾼 뒤 한 장비를 1.5로 직접 입력하면 그 장비는 1.5를 유지해야 함."""
    gws = [gw("G1"), gw("G2")]
    db.sync_gateways(gws)
    db.set_default(KIND_GATEWAY, "antenna_height_m", 3.0)
    gws = db.load_gateways()
    gws[0].antenna_height_m = 1.5
    db.sync_gateways(gws)
    assert {g.gw_id: g.antenna_height_m for g in db.load_gateways()} == {"G1": 1.5, "G2": 3.0}


# ── 목록 동기화 ──

def test_attributes_order_and_enabled_flag_survive_reload(tmp_path):
    path = str(tmp_path / "p.lsproj")
    with ProjectDB.create(path) as d:
        g2 = gw("G2"); g2.enabled = False
        d.sync_gateways([gw("G3"), g2, gw("G1")])
    with ProjectDB.open(path) as d:
        loaded = d.load_gateways()
    assert [g.gw_id for g in loaded] == ["G3", "G2", "G1"]
    assert loaded[1].enabled is False and loaded[0].install_type == "스마트폴" and loaded[0].region == "탄천"


def test_sync_deletes_missing_by_default_and_can_keep(db):
    db.sync_gateways([gw("G1"), gw("G2")])
    db.sync_gateways([gw("G1")])
    assert [g.gw_id for g in db.load_gateways()] == ["G1"]
    db.sync_gateways([gw("G1"), gw("G9")])
    db.sync_gateways([gw("G1")], delete_missing=False)
    assert {g.gw_id for g in db.load_gateways()} == {"G1", "G9"}


def test_deleting_device_also_removes_its_explicit_params(db):
    db.sync_gateways([gw("G1", antenna_height_m=9.0)])
    db.sync_gateways([])
    assert db._conn.execute("SELECT COUNT(*) FROM device_params").fetchone()[0] == 0


def test_moved_position_is_saved(db):
    gws = [gw("G1")]
    db.sync_gateways(gws)
    gws[0].lat, gws[0].lon = 37.55, 127.22
    db.sync_gateways(gws)
    g = db.load_gateways()[0]
    assert (g.lat, g.lon) == (37.55, 127.22)


def test_duplicate_ids_are_rejected_and_database_is_untouched(db):
    db.sync_gateways([gw("G1")])
    with pytest.raises(ValueError, match="중복"):
        db.sync_gateways([gw("G1"), gw("G2"), gw("G2")])
    assert [g.gw_id for g in db.load_gateways()] == ["G1"]


def test_numpy_values_in_attributes_are_stored(db):
    import numpy as np
    g = gw("G1")
    g.power_w = np.float64(12.5)
    db.sync_gateways([g])
    assert db.load_gateways()[0].power_w == 12.5


def test_node_params_work_like_gateway_params(db):
    nodes = [nd("N1"), nd("N2", min_rx_dbm=-75.0)]
    db.sync_nodes(nodes)
    loaded = {n.node_id: n for n in db.load_nodes()}
    assert loaded["N2"].min_rx_dbm == -75.0 and loaded["N1"].min_rx_dbm == -100.0
    assert db.data_fidelity(KIND_NODE)["params"]["min_rx_dbm"] == {"explicit": 1, "default": 1}


def test_gateways_and_nodes_with_same_id_do_not_collide(db):
    db.sync_gateways([gw("X1")])
    db.sync_nodes([nd("X1")])
    assert len(db.load_gateways()) == 1 and len(db.load_nodes()) == 1


# ── 개별 값 직접 조작 ──

def test_set_and_clear_param(db):
    db.sync_gateways([gw("G1")])
    db.set_param(KIND_GATEWAY, "G1", "antenna_gain_dbi", 9.0)
    assert db.load_gateways()[0].antenna_gain_dbi == 9.0
    db.clear_param(KIND_GATEWAY, "G1", "antenna_gain_dbi")
    assert db.load_gateways()[0].antenna_gain_dbi == 6.0


def test_set_param_validates_input(db):
    db.sync_gateways([gw("G1")])
    with pytest.raises(ValueError):
        db.set_param(KIND_GATEWAY, "G1", "lat", 1.0)
    with pytest.raises(KeyError):
        db.set_param(KIND_GATEWAY, "없는ID", "antenna_gain_dbi", 1.0)


# ── 가져오기 병합 ──

def test_import_adds_new_devices_with_defaults_only(db):
    rep = db.import_gateways([gw("G1"), gw("G2")])
    assert (rep.added, rep.updated, rep.unchanged) == (2, 0, 0)
    assert db.data_fidelity(KIND_GATEWAY)["params"]["antenna_height_m"]["explicit"] == 0


def test_import_twice_is_idempotent(db):
    db.import_nodes([nd("N1"), nd("N2", min_rx_dbm=-75.0)])
    rep = db.import_nodes([nd("N1"), nd("N2", min_rx_dbm=-75.0)])
    assert (rep.added, rep.updated, rep.unchanged) == (0, 0, 2)


def test_import_records_non_default_values_as_import_source(db):
    db.import_nodes([nd("N1", min_rx_dbm=-75.0)])
    src = db._conn.execute("SELECT source FROM device_params WHERE id='N1'").fetchone()[0]
    assert src == SOURCE_IMPORT


def test_reimport_updates_position_but_keeps_user_values_and_enabled(db):
    gws = [gw("G1"), gw("G2")]
    db.sync_gateways(gws)
    gws[0].antenna_height_m = 6.0
    gws[0].enabled = False
    db.sync_gateways(gws)                                        # 사용자가 높이를 고치고 G1을 껐음
    rep = db.import_gateways([gw("G1", lat=37.99, lon=127.99), gw("G2")])   # 위치만 바뀐 새 파일
    g = {x.gw_id: x for x in db.load_gateways()}
    assert (g["G1"].lat, g["G1"].lon) == (37.99, 127.99)
    assert g["G1"].antenna_height_m == 6.0 and g["G1"].enabled is False
    assert rep.updated == 1 and rep.unchanged == 1 and rep.protected == []


def test_reimport_does_not_override_user_value_with_different_file_value(db):
    gws = [gw("G1")]
    db.sync_gateways(gws)
    gws[0].antenna_height_m = 6.0
    db.sync_gateways(gws)
    rep = db.import_gateways([gw("G1", antenna_height_m=12.0)])      # 파일은 12m라고 주장
    assert db.load_gateways()[0].antenna_height_m == 6.0              # 사용자 입력이 우선
    assert rep.protected == [("G1", "antenna_height_m")]


def test_reimport_can_update_previous_import_values(db):
    db.import_nodes([nd("N1", min_rx_dbm=-75.0)])
    db.import_nodes([nd("N1", min_rx_dbm=-80.0)])
    assert db.load_nodes()[0].min_rx_dbm == -80.0


def test_import_reports_missing_ids_without_deleting_them(db):
    db.import_gateways([gw("G1"), gw("G2")])
    rep = db.import_gateways([gw("G1")])
    assert rep.missing_ids == ["G2"] and {g.gw_id for g in db.load_gateways()} == {"G1", "G2"}


def test_import_appends_new_devices_after_existing_in_order(db):
    db.import_gateways([gw("G1"), gw("G2")])
    db.import_gateways([gw("G9"), gw("G1")])
    assert [g.gw_id for g in db.load_gateways()] == ["G1", "G2", "G9"]


def test_import_rejects_duplicate_ids_without_partial_write(db):
    with pytest.raises(ValueError):
        db.import_gateways([gw("G1"), gw("G1")])
    assert db.load_gateways() == []


# ── 백업/지속성 ──

def test_backup_creates_readable_copy_and_refuses_overwrite(tmp_path):
    src = str(tmp_path / "s.lsproj")
    with ProjectDB.create(src, name="원본") as d:
        d.sync_gateways([gw("G1", antenna_height_m=4.0)])
        dest = str(tmp_path / "backup.lsproj")
        d.backup_to(dest)
        with pytest.raises(FileExistsError):
            d.backup_to(dest)
        d.backup_to(dest, overwrite=True)
    with ProjectDB.open(dest) as b:
        assert b.name == "원본" and b.load_gateways()[0].antenna_height_m == 4.0


def test_data_persists_after_close_and_reopen(tmp_path):
    path = str(tmp_path / "p.lsproj")
    with ProjectDB.create(path) as d:
        d.sync_gateways([gw("G1", antenna_height_m=7.0)])
        d.set_default(KIND_NODE, "min_rx_dbm", -90.0)
    with ProjectDB.open(path) as d:
        assert d.load_gateways()[0].antenna_height_m == 7.0
        assert d.get_defaults(KIND_NODE)["min_rx_dbm"] == -90.0
