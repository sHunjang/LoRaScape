# licenser_tool/keygen_gui.py
"""
LoRaScape 라이선스 발급 도구임. 본체(LoRaScape.exe)와 완전히 독립적으로
실행/패키징되는 사내 전용 프로그램임 - lorascape 패키지 전체를 import하지 않고,
issuer_core.py/normalize.py만 동기화해서 쓰기 때문에 rasterio/sklearn 같은
무거운 본체 의존성이 이 도구에 전혀 안 들어감.

기능:
  - 신규 비밀키 생성 + 파일로 저장 (keys/{회사명}_license.key)
  - 기존 비밀키 파일 불러오기
  - 회사명으로 인증코드 발급 (클립보드 복사)
  - 발급 이력 기록 (issue_history.json, 로컬 전용)
"""
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QGroupBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import Qt

from issuer_core import generate_secret_key, generate_auth_code

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"

STYLE = f"""
    QWidget {{ background:{DARK}; color:{TEXT}; }}
    QLabel {{ color:{TEXT}; }}
    QLineEdit {{
        background:{PANEL}; color:{TEXT};
        border:1px solid {BORDER}; border-radius:4px;
        padding:4px 6px; min-height:26px;
    }}
    QGroupBox {{
        color:{MUTED}; border:1px solid {BORDER};
        border-radius:6px; margin-top:8px; padding-top:8px;
    }}
    QGroupBox::title {{ subcontrol-origin:margin; left:8px; }}
    QPushButton {{
        background:#253a5a; color:{TEXT};
        border:1px solid #3a5a8a; border-radius:5px;
        padding:6px 16px; font-size:12px;
    }}
    QPushButton:hover {{ background:#2e4a7a; }}
    QTableWidget {{
        background:{PANEL}; color:{TEXT}; gridline-color:{BORDER};
    }}
    QHeaderView::section {{ background:{DARK}; color:{MUTED}; border:none; padding:4px; }}
"""

KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")
HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issue_history.json")

HISTORY_COLS = ["발급일시", "회사명", "인증코드", "키 파일"]


def _load_history() -> list:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(history: list):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


class KeygenWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoRaScape 라이선스 발급 도구")
        self.setStyleSheet(STYLE)
        self.resize(720, 560)

        self._current_key_path = ""
        self._current_secret_key: bytes = b""

        self._build()
        self._load_history_table()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        grp_key = QGroupBox("비밀키")
        fl_key = QFormLayout(grp_key)

        self.e_key_path = QLineEdit("")
        self.e_key_path.setReadOnly(True)
        row_key = QHBoxLayout()
        row_key.addWidget(self.e_key_path, 1)
        btn_new_key = QPushButton("신규 생성")
        btn_new_key.clicked.connect(self._on_generate_new_key)
        btn_load_key = QPushButton("불러오기")
        btn_load_key.clicked.connect(self._on_load_key)
        row_key.addWidget(btn_new_key)
        row_key.addWidget(btn_load_key)
        fl_key.addRow("키 파일", row_key)
        lay.addWidget(grp_key)

        grp_issue = QGroupBox("인증코드 발급")
        fl_issue = QFormLayout(grp_issue)
        self.e_company = QLineEdit("")
        self.e_company.setPlaceholderText("고객사명")
        fl_issue.addRow("회사명", self.e_company)

        row_issue = QHBoxLayout()
        self.e_code = QLineEdit("")
        self.e_code.setReadOnly(True)
        self.e_code.setPlaceholderText("발급된 인증코드가 여기 표시됩니다")
        btn_issue = QPushButton("발급")
        btn_issue.clicked.connect(self._on_issue_code)
        btn_copy = QPushButton("복사")
        btn_copy.clicked.connect(self._on_copy_code)
        row_issue.addWidget(self.e_code, 1)
        row_issue.addWidget(btn_issue)
        row_issue.addWidget(btn_copy)
        fl_issue.addRow("인증코드", row_issue)
        lay.addWidget(grp_issue)

        self.lbl_msg = QLabel("")
        self.lbl_msg.setStyleSheet("color:#e87a7a;font-size:10px;")
        self.lbl_msg.setWordWrap(True)
        lay.addWidget(self.lbl_msg)

        lay.addWidget(QLabel("발급 이력"))
        self.tbl_history = QTableWidget(0, len(HISTORY_COLS))
        self.tbl_history.setHorizontalHeaderLabels(HISTORY_COLS)
        self.tbl_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_history.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_history.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lay.addWidget(self.tbl_history)

    # ── 비밀키 ───────────────────────────────────────────────

    def _on_generate_new_key(self):
        company = self.e_company.text().strip()
        if not company:
            self.lbl_msg.setText("먼저 회사명을 입력하세요 (키 파일명에 사용됩니다).")
            return

        os.makedirs(KEYS_DIR, exist_ok=True)
        safe_name = "".join(c for c in company if c.isalnum() or c in "-_") or "unnamed"
        default_path = os.path.join(KEYS_DIR, f"{safe_name}_license.key")

        path, _ = QFileDialog.getSaveFileName(self, "비밀키 파일 저장 위치", default_path, "License Key (*.key)")
        if not path:
            return

        secret_hex = generate_secret_key()
        with open(path, "w", encoding="utf-8") as f:
            f.write(secret_hex)

        self._current_key_path = path
        self._current_secret_key = secret_hex.encode("utf-8")
        self.e_key_path.setText(path)
        self.lbl_msg.setText("")

    def _on_load_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "비밀키 파일 선택", KEYS_DIR, "License Key (*.key)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read().strip()
            if not content:
                self.lbl_msg.setText("키 파일이 비어있습니다.")
                return
            self._current_key_path = path
            self._current_secret_key = content.encode("utf-8")
            self.e_key_path.setText(path)
            self.lbl_msg.setText("")
        except OSError as e:
            self.lbl_msg.setText(f"키 파일을 읽을 수 없습니다: {e}")

    # ── 발급 ─────────────────────────────────────────────────

    def _on_issue_code(self):
        company = self.e_company.text().strip()
        if not company:
            self.lbl_msg.setText("회사명을 입력하세요.")
            return
        if not self._current_secret_key:
            self.lbl_msg.setText("먼저 비밀키를 생성하거나 불러오세요.")
            return

        code = generate_auth_code(self._current_secret_key, company)
        self.e_code.setText(code)
        self.lbl_msg.setText("")

        history = _load_history()
        history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company": company,
            "code": code,
            "key_path": self._current_key_path,
        })
        _save_history(history)
        self._load_history_table()

    def _on_copy_code(self):
        code = self.e_code.text()
        if code:
            QApplication.clipboard().setText(code)
            self.lbl_msg.setText("클립보드에 복사되었습니다.")
            self.lbl_msg.setStyleSheet("color:#7ae87a;font-size:10px;")
        else:
            self.lbl_msg.setStyleSheet("color:#e87a7a;font-size:10px;")

    def _load_history_table(self):
        history = _load_history()
        self.tbl_history.setRowCount(0)
        for entry in reversed(history):  # 최신 발급이 위로 오게 함
            r = self.tbl_history.rowCount()
            self.tbl_history.insertRow(r)
            values = [entry.get("timestamp", ""), entry.get("company", ""),
                      entry.get("code", ""), entry.get("key_path", "")]
            for c, v in enumerate(values):
                self.tbl_history.setItem(r, c, QTableWidgetItem(v))


def main():
    import sys
    app = QApplication(sys.argv)
    window = KeygenWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()