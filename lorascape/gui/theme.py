# lorascape/gui/theme.py
"""
앱 전체에 적용하는 팝업 공통 스타일임. 개별 창마다 QMessageBox 스타일을 따로 주면
빠지는 곳이 생기므로(부모 창의 어두운 배경만 물려받고 글자는 검정이 되는 문제),
QApplication 스타일시트로 한 번에 적용함.
"""
DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
BORDER = "#2a2f3b"

POPUP_STYLE = f"""
QMessageBox, QInputDialog {{ background:{DARK}; }}
QMessageBox QLabel, QInputDialog QLabel {{ color:{TEXT}; font-size:12px; }}
QMessageBox QPushButton, QInputDialog QPushButton {{
    background:#253a5a; color:{TEXT};
    border:1px solid #3a5a8a; border-radius:5px;
    padding:6px 18px; min-width:60px;
}}
QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {{ background:#2e4a7a; }}
QInputDialog QLineEdit, QInputDialog QSpinBox, QInputDialog QDoubleSpinBox, QInputDialog QComboBox {{
    background:{PANEL}; color:{TEXT};
    border:1px solid {BORDER}; border-radius:4px; padding:4px 6px; min-height:24px;
}}
"""