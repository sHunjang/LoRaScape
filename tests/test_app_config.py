"""app_config.py 검증 테스트임. 실제 홈 폴더를 건드리지 않게 CONFIG_PATH를 임시로 바꿔서 테스트함."""
import json
import lorascape.gui.app_config as app_config


def test_load_config_returns_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "nonexistent.json"))
    cfg = app_config.load_config()
    assert cfg == app_config.DEFAULT_CONFIG


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "config.json"))

    saved = {"shp_path": "a.shp", "dem_path": "b.img", "dsm_path": "", "xlsx_path": "c.xlsx"}
    app_config.save_config(saved)
    loaded = app_config.load_config()
    assert loaded == saved


def test_load_config_handles_corrupted_json(tmp_path, monkeypatch):
    bad_file = tmp_path / "config.json"
    bad_file.write_text("{ this is not valid json", encoding="utf-8")
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(bad_file))
    cfg = app_config.load_config()
    assert cfg == app_config.DEFAULT_CONFIG


def test_load_config_merges_partial_saved_data(tmp_path, monkeypatch):
    """예전 버전 설정 파일에 필드가 일부만 있어도 기본값과 합쳐져서 KeyError가 안 나야 함."""
    partial = tmp_path / "config.json"
    partial.write_text(json.dumps({"xlsx_path": "only_this.xlsx"}), encoding="utf-8")
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(partial))
    cfg = app_config.load_config()
    assert cfg["xlsx_path"] == "only_this.xlsx"
    assert cfg["shp_path"] == ""  # 기본값으로 채워짐