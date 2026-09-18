# lorascape/gui/widgets/license_dialog.py
"""
라이선스 인증 다이얼로그임. license.key 파일 경로를 찾고(고정 경로 우선, 없으면
직접 선택), 회사명/사용자명/인증코드를 입력받아 core.license.verifier로 검증함.

인증 성공 시 회사명/사용자명/코드를 app_config에 저장해서, 다음 실행부터는
main_window 시작 전에 이 저장된 값으로 조용히 재검증만 하고 다이얼로그를
안 띄우게 함 (매번 재입력하는 번거로움을 없애려는 목적 - _try_silent_login 참고).
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QGroupBox, QFileDialog,
)
from PyQt5.QtCore import Qt

from lorascape.gui.app_config import load_config, save_config
from lorascape.license.verifier import load_secret_key, verify_auth_code

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"

STYLE = f"""
    QDialog {{ background:{DARK}; color:{TEXT}; }}
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
        padding:6px 18px; font-size:12px;
    }}
    QPushButton:hover {{ background:#2e4a7a; }}
    QPushButton[role="ok"] {{ background:#1d4a1d; border-color:#2a6a2a; }}
    QPushButton[role="cancel"] {{ background:#3a1a1a; border-color:#6a2a2a; }}
"""


def find_license_key_path() -> str:
    """
    exe와 같은 폴더에서 license.key를 찾음. 실행 파일 기준 경로를 찾는 게
    맞지만, 개발 중(python 스크립트 실행)에는 sys.executable이 python.exe를
    가리켜서 의미가 없으니, 현재 작업 디렉터리도 같이 확인함.
    못 찾으면 빈 문자열 반환 (호출부가 파일 선택창을 띄우게 함).
    """
    import sys
    candidates = [
        os.path.join(os.path.dirname(sys.executable), "license.key"),
        os.path.join(os.getcwd(), "license.key"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def try_silent_login() -> bool:
    """
    app_config에 저장된 회사명/사용자명/코드로 license.key 기준 조용히
    재검증을 시도함. 성공하면 True - 이 경우 LicenseDialog를 아예 안 띄움.
    실패(파일 없음, 저장된 값 없음, 코드 안 맞음 등 어떤 이유든)하면 False -
    이 경우 호출부가 LicenseDialog를 띄워야 함.
    """
    cfg = load_config()
    company = cfg.get("license_company", "")
    code = cfg.get("license_code", "")
    if not company or not code:
        return False

    key_path = find_license_key_path()
    if not key_path:
        return False

    try:
        secret_key = load_secret_key(key_path)
    except (FileNotFoundError, ValueError):
        return False

    result = verify_auth_code(secret_key, company, code, debug_mode=False)
    return result.is_valid


class LicenseDialog(QDialog):
    """라이선스 인증 - 회사명/사용자명/인증코드 입력 창임."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("라이선스 인증")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(520)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._cfg = load_config()
        self._key_path = find_license_key_path()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        info = QLabel(
            "LoRaScape 라이선스 인증이 필요합니다.\n"
            "발급받은 인증 코드를 입력하세요."
        )
        info.setStyleSheet(f"color:{MUTED};font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        key_group = QGroupBox("라이선스 키 파일")
        key_row = QHBoxLayout(key_group)
        self.e_key_path = QLineEdit(self._key_path)
        self.e_key_path.setReadOnly(True)
        btn_browse = QPushButton("찾아보기")
        btn_browse.clicked.connect(self._browse_key_file)
        key_row.addWidget(self.e_key_path, 1)
        key_row.addWidget(btn_browse)
        lay.addWidget(key_group)

        grp = QGroupBox("인증 정보")
        fl = QFormLayout(grp)
        fl.setSpacing(8)
        self.e_company = QLineEdit(self._cfg.get("license_company", ""))
        self.e_company.setPlaceholderText("회사명")
        self.e_user = QLineEdit(self._cfg.get("license_user", ""))
        self.e_user.setPlaceholderText("사용자명")
        self.e_code = QLineEdit("")
        self.e_code.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        fl.addRow("회사명", self.e_company)
        fl.addRow("사용자명", self.e_user)
        fl.addRow("인증 코드", self.e_code)
        lay.addWidget(grp)

        self.lbl_msg = QLabel("")
        self.lbl_msg.setStyleSheet("color:#e87a7a;font-size:10px;")
        self.lbl_msg.setWordWrap(True)
        lay.addWidget(self.lbl_msg)

        bot = QHBoxLayout()
        btn_cancel = QPushButton("취소")
        btn_cancel.setProperty("role", "cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("✔  인증")
        btn_ok.setProperty("role", "ok")
        btn_ok.clicked.connect(self._verify)
        bot.addStretch()
        bot.addWidget(btn_cancel)
        bot.addWidget(btn_ok)
        lay.addLayout(bot)

    def _browse_key_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "라이선스 키 파일 선택", "", "License Key (*.key)")
        if path:
            self._key_path = path
            self.e_key_path.setText(path)

    def _verify(self):
        company = self.e_company.text().strip()
        user = self.e_user.text().strip()
        code = self.e_code.text().strip()

        if not self._key_path:
            self.lbl_msg.setText("라이선스 키 파일을 선택하세요.")
            return
        if not (company and user and code):
            self.lbl_msg.setText("모든 항목을 입력하세요.")
            return

        try:
            secret_key = load_secret_key(self._key_path)
        except FileNotFoundError:
            self.lbl_msg.setText("라이선스 키 파일을 찾을 수 없습니다.")
            return
        except ValueError as e:
            self.lbl_msg.setText(str(e))
            return

        # ★ debug_mode는 항상 False로 고정함 - 배포판에서 회사명/코드 정규화
        # 내부 비교값이 화면에 노출되면 안 됨.
        result = verify_auth_code(secret_key, company, code, debug_mode=False)

        if result.is_valid:
            self._cfg["license_company"] = company
            self._cfg["license_user"] = user
            self._cfg["license_code"] = code
            save_config(self._cfg)
            self.accept()
        else:
            self.lbl_msg.setText(
                "✗ 인증 코드가 올바르지 않습니다. 회사명·사용자명·코드를 확인하세요."
            )