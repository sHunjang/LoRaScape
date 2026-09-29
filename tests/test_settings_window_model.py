"""설정창의 전파 모델 선택 검증 테스트임 (기존 test_settings_window.py와 fixture 이름을 맞춤)."""
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


# ── 전파 모델 선택 ──

def test_settings_window_model_combo_lists_all_models_and_defaults_to_song(qapp, isolated_config):
    from lorascape.core.propagation.models import PROPAGATION_MODELS
    win = SettingsWindow()
    keys = [win.cb_model.itemData(i) for i in range(win.cb_model.count())]
    assert keys == [k for k, _ in PROPAGATION_MODELS]
    assert win.cb_model.currentData() == "song"


def test_settings_window_model_is_collected_and_saved(qapp, isolated_config):
    win = SettingsWindow()
    win.cb_model.setCurrentIndex(win.cb_model.findData("cost231"))

    received = []
    win.sig_settings_changed.connect(lambda s: received.append(s))
    win._accept()

    assert received[0]["propagation_model"] == "cost231"
    assert app_config.load_config()["propagation_model"] == "cost231"


def test_settings_window_reopens_with_saved_model(qapp, isolated_config):
    app_config.save_config({**app_config.load_config(), "propagation_model": "cost231"})
    assert SettingsWindow().cb_model.currentData() == "cost231"


def test_settings_window_reset_restores_song_model(qapp, isolated_config):
    win = SettingsWindow()
    win.cb_model.setCurrentIndex(win.cb_model.findData("cost231"))
    win._reset_defaults()
    assert win.cb_model.currentData() == "song"


def test_settings_window_model_note_visible_only_for_cost231(qapp, isolated_config):
    win = SettingsWindow()
    assert win.lbl_model_note.isHidden() is True
    win.cb_model.setCurrentIndex(win.cb_model.findData("cost231"))
    assert win.lbl_model_note.isHidden() is False
    win.cb_model.setCurrentIndex(win.cb_model.findData("song"))
    assert win.lbl_model_note.isHidden() is True


def test_settings_window_unknown_saved_model_falls_back_without_crashing(qapp, isolated_config):
    """config.json에 모르는 모델 이름이 들어 있어도 창은 열려야 하고, 적용하면 목록의 값으로 저장됨."""
    app_config.save_config({**app_config.load_config(), "propagation_model": "okumura"})
    win = SettingsWindow()
    assert win.cb_model.currentData() in ("song", "cost231")
    win._accept()
    assert app_config.load_config()["propagation_model"] in ("song", "cost231")