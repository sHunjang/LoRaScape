"""splash_screen.py 검증 테스트임. QApplication 필요함. 렌더링(paintEvent) 자체보다는
상태 전환 로직(set_loading, update_progress, finish_loading)이 의도대로 동작하는지 확인함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.splash_screen import SplashScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_splash_screen_creates_without_error(qapp):
    splash = SplashScreen()
    assert splash is not None
    assert splash.btn_start.isVisible() or not splash.isVisible()  # 아직 show() 안 했으니 실제 가시성보단 존재 확인


def test_set_loading_true_hides_start_button_shows_progress(qapp):
    splash = SplashScreen()
    splash.set_loading(True)
    assert splash.btn_start.isHidden()
    assert not splash.prog.isHidden()


def test_set_loading_false_shows_start_button_hides_progress(qapp):
    splash = SplashScreen()
    splash.set_loading(True)
    splash.set_loading(False)
    assert not splash.btn_start.isHidden()
    assert splash.prog.isHidden()


def test_update_progress_sets_value_and_text(qapp):
    splash = SplashScreen()
    splash.set_loading(True)
    splash.update_progress(42, "테스트 중...")
    assert splash.prog.value() == 42
    assert splash.lbl_status.text() == "테스트 중..."
    assert splash.lbl_pct.text() == "42%"


def test_update_progress_clamps_out_of_range_values(qapp):
    splash = SplashScreen()
    splash.set_loading(True)
    splash.update_progress(150)
    assert splash.prog.value() == 100
    splash.update_progress(-10)
    assert splash.prog.value() == 0


def test_start_button_click_emits_sig_start_and_disables_button(qapp):
    splash = SplashScreen()
    received = []
    splash.sig_start.connect(lambda: received.append(True))
    splash.btn_start.click()
    assert received == [True]
    assert not splash.btn_start.isEnabled()