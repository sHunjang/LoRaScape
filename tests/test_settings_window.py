"""settings_window.py 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.settings_window import SettingsWindow
import lorascape.gui.app_config as app_config


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """실제 홈 폴더 설정을 건드리지 않게 격리함."""
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    return tmp_path


def test_settings_window_loads_defaults(qapp, isolated_config):
    win = SettingsWindow()
    assert win.sp_fc.value() == 920.0
    assert win.sp_bw.value() == 125000.0
    assert win.sp_target.value() == 0.9
    assert win.sp_max_add.value() == 15


def test_settings_window_accept_saves_and_emits(qapp, isolated_config):
    win = SettingsWindow()
    win.sp_fc.setValue(915.0)
    win.sp_target.setValue(0.95)

    received = []
    win.sig_settings_changed.connect(lambda s: received.append(s))
    win._accept()

    assert received[0]["fc_mhz"] == 915.0
    assert received[0]["coverage_target"] == 0.95

    reloaded = app_config.load_config()
    assert reloaded["fc_mhz"] == 915.0


def test_settings_window_reset_defaults_restores_values(qapp, isolated_config):
    win = SettingsWindow()
    win.sp_fc.setValue(800.0)
    win.sp_max_add.setValue(5)

    win._reset_defaults()

    assert win.sp_fc.value() == app_config.DEFAULT_CONFIG["fc_mhz"]
    assert win.sp_max_add.value() == app_config.DEFAULT_CONFIG["max_additional"]


def test_settings_window_environment_combo_has_all_options(qapp, isolated_config):
    win = SettingsWindow()
    assert win.cb_env.count() == 4
    keys = [win.cb_env.itemData(i) for i in range(win.cb_env.count())]
    assert set(keys) == {"dense_urban", "urban", "suburban", "open"}
    

def test_settings_window_heatmap_opacity_slider_defaults(qapp, isolated_config):
    win = SettingsWindow()
    assert win.sl_heatmap_opacity.value() == int(app_config.DEFAULT_CONFIG["heatmap_opacity"] * 100)


def test_settings_window_heatmap_opacity_collected_and_saved(qapp, isolated_config):
    win = SettingsWindow()
    win.sl_heatmap_opacity.setValue(50)

    received = []
    win.sig_settings_changed.connect(lambda s: received.append(s))
    win._accept()

    assert received[0]["heatmap_opacity"] == pytest.approx(0.5)
    reloaded = app_config.load_config()
    assert reloaded["heatmap_opacity"] == pytest.approx(0.5)


def test_settings_window_grid_size_combo_has_all_presets(qapp, isolated_config):
    from lorascape.gui.app_config import HEATMAP_GRID_SIZE_PRESETS
    win = SettingsWindow()
    assert win.cb_grid_size.count() == len(HEATMAP_GRID_SIZE_PRESETS)


def test_settings_window_grid_size_defaults_to_60(qapp, isolated_config):
    win = SettingsWindow()
    assert win.cb_grid_size.currentData() == 60


def test_settings_window_grid_size_collected_and_saved(qapp, isolated_config):
    win = SettingsWindow()
    idx = win.cb_grid_size.findData(80)
    win.cb_grid_size.setCurrentIndex(idx)

    received = []
    win.sig_settings_changed.connect(lambda s: received.append(s))
    win._accept()

    assert received[0]["heatmap_grid_size"] == 80
    reloaded = app_config.load_config()
    assert reloaded["heatmap_grid_size"] == 80


def test_settings_window_reset_restores_grid_size_default(qapp, isolated_config):
    win = SettingsWindow()
    idx = win.cb_grid_size.findData(80)
    win.cb_grid_size.setCurrentIndex(idx)

    win._reset_defaults()

    assert win.cb_grid_size.currentData() == app_config.DEFAULT_CONFIG["heatmap_grid_size"]