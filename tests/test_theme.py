"""팝업 공통 스타일 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QLabel
from PyQt5.QtGui import QPalette
from lorascape.gui.theme import POPUP_STYLE, TEXT


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.setStyleSheet("")   # 다른 테스트에 스타일이 남지 않게 정리함


def test_popup_style_covers_message_box_and_input_dialog():
    assert "QMessageBox QLabel" in POPUP_STYLE
    assert "QInputDialog QLabel" in POPUP_STYLE


def test_message_box_label_text_is_light_with_app_stylesheet(qapp):
    qapp.setStyleSheet(POPUP_STYLE)
    box = QMessageBox(QMessageBox.Information, "제목", "본문 텍스트")
    box.ensurePolished()
    label = box.findChild(QLabel, "qt_msgbox_label")
    label.ensurePolished()
    assert label.palette().color(QPalette.WindowText).name().lower() == TEXT.lower()