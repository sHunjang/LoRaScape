"""initial_setup_dialog.py 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.initial_setup_dialog import InitialSetupDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dialog_ok_button_disabled_when_paths_empty(qapp):
    dlg = InitialSetupDialog()
    dlg.e_shp.setText("")
    dlg.e_dem.setText("")
    assert dlg.btn_ok.isEnabled() is False


def test_dialog_ok_button_disabled_when_paths_do_not_exist(qapp):
    dlg = InitialSetupDialog()
    dlg.e_shp.setText("nonexistent.shp")
    dlg.e_dem.setText("nonexistent.img")
    assert dlg.btn_ok.isEnabled() is False


def test_dialog_ok_button_enabled_when_required_paths_exist(qapp, tmp_path):
    shp = tmp_path / "region.shp"
    dem = tmp_path / "dem.img"
    for f in (shp, dem):
        f.write_text("dummy")

    dlg = InitialSetupDialog()
    dlg.e_shp.setText(str(shp))
    dlg.e_dem.setText(str(dem))
    assert dlg.btn_ok.isEnabled() is True


def test_dialog_optional_dsm_blank_does_not_block_ok(qapp, tmp_path):
    shp = tmp_path / "region.shp"
    dem = tmp_path / "dem.img"
    for f in (shp, dem):
        f.write_text("dummy")

    dlg = InitialSetupDialog()
    dlg.e_shp.setText(str(shp))
    dlg.e_dem.setText(str(dem))
    dlg.e_dsm.setText("")  # DSM 비워둠 - 그래도 OK 버튼 활성화돼야 함
    assert dlg.btn_ok.isEnabled() is True


def test_dialog_invalid_dsm_path_blocks_ok(qapp, tmp_path):
    shp = tmp_path / "region.shp"
    dem = tmp_path / "dem.img"
    for f in (shp, dem):
        f.write_text("dummy")

    dlg = InitialSetupDialog()
    dlg.e_shp.setText(str(shp))
    dlg.e_dem.setText(str(dem))
    dlg.e_dsm.setText("nonexistent_dsm.img")  # 존재 안 하는 DSM 경로 -> 막혀야 함
    assert dlg.btn_ok.isEnabled() is False


def test_accept_preserves_license_and_other_settings(qapp, tmp_path, monkeypatch):
    import lorascape.gui.app_config as app_config
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app_config.save_config({**app_config.load_config(),
                            "license_company": "회사", "license_code": "CODE", "fc_mhz": 915.0})
    shp, dem = tmp_path / "a.shp", tmp_path / "b.img"
    shp.write_text("x")
    dem.write_text("x")

    dlg = InitialSetupDialog()
    dlg.e_shp.setText(str(shp))
    dlg.e_dem.setText(str(dem))
    dlg._accept()

    saved = app_config.load_config()
    assert saved["license_company"] == "회사" and saved["license_code"] == "CODE"
    assert saved["fc_mhz"] == 915.0
    assert saved["shp_path"] == str(shp)