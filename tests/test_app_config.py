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

    # load_config()는 저장된 값에 DEFAULT_CONFIG를 병합해서 반환하는 게 정상 동작임
    # (부분 저장 파일도 안전하게 로드하기 위한 설계) - 그래서 저장한 값 4개가
    # 다시 로드한 결과에 '포함'되어 있는지만 확인하고, 전체가 정확히 일치하는지는
    # 확인하지 않음 (analysis 설정 등 DEFAULT_CONFIG의 다른 필드가 자동으로 채워지니까).
    saved = {"shp_path": "a.shp", "dem_path": "b.img", "dsm_path": "", "xlsx_path": "c.xlsx"}
    app_config.save_config(saved)
    loaded = app_config.load_config()

    for key, value in saved.items():
        assert loaded[key] == value


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
    

def test_default_config_includes_analysis_settings():
    """분석 설정 기본값들이 DEFAULT_CONFIG에 다 들어있는지 확인함 (누락 방지용 회귀 테스트)."""
    required_keys = {
        "fc_mhz", "bandwidth_hz", "receiver_noise_figure_db",
        "environment", "coverage_target", "max_additional",
    }
    assert required_keys.issubset(app_config.DEFAULT_CONFIG.keys())
    

def test_default_config_includes_heatmap_opacity():
    assert "heatmap_opacity" in app_config.DEFAULT_CONFIG
    assert 0.0 < app_config.DEFAULT_CONFIG["heatmap_opacity"] <= 1.0