# lorascape/gui/widgets/initial_setup_dialog.py
"""
프로그램 최초 실행(또는 다른 지역 데이터로 바꿀 때) Shapefile/DEM/DSM을 선택하는 창임.
GW/Node 엑셀 인벤토리는 여기서 안 받고, GW목록/단말목록 창에서 직접 불러오게 함
(지역 경계·지형 데이터와 인벤토리 데이터는 갱신 주기가 달라서 - DEM은 지역
바꿀 때만 바뀌지만, 엑셀 인벤토리는 현장에 GW/Node 늘어날 때마다 자주 갱신될 수 있어서
목록창에서 바로 다시 불러올 수 있는 게 실무적으로 편함).
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit,
    QPushButton, QLabel, QFileDialog,
)
from PyQt5.QtCore import Qt

from lorascape.gui.app_config import load_config, save_config

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"
GREEN = "#00C94A"
RED = "#FF4444"

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
        padding:6px 14px; font-size:12px;
    }}
    QPushButton:hover {{ background:#2e4a7a; }}
    QPushButton[role="ok"] {{ background:#1d4a1d; border-color:#2a6a2a; }}
    QPushButton[role="cancel"] {{ background:#3a1a1a; border-color:#6a2a2a; }}
"""


class InitialSetupDialog(QDialog):
    """분석에 사용할 Shapefile/DEM/DSM을 선택하는 창임."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터 파일 선택")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(620)
        self._cfg = load_config()
        self._build()
        self._validate()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        info = QLabel(
            "분석에 사용할 지역 경계(Shapefile)와 수치 표면 모델(DEM/DSM) 파일을 선택하세요.\n"
            "GW/Node 데이터는 프로그램 실행 후 'GW 목록' 또는 '단말 목록' 창에서 엑셀로 불러올 수 있습니다."
        )
        info.setStyleSheet(f"color:{MUTED};font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        self.e_shp = self._add_path_row(lay, "지역 경계 파일 (Shapefile *.shp)", self._cfg["shp_path"], self._browse_shp)
        self.e_dem = self._add_path_row(lay, "수치 표면 모델 파일 (DEM/DSM *.img / *.tif)", self._cfg["dem_path"], self._browse_dem)

        dsm_group = QGroupBox("추가 DSM 파일 (선택사항 *.img / *.tif)")
        dsm_lay = QHBoxLayout(dsm_group)
        self.e_dsm = QLineEdit(self._cfg["dsm_path"])
        self.e_dsm.setPlaceholderText("DSM 파일 (없으면 DEM을 DSM으로 사용)")
        self.e_dsm.textChanged.connect(self._validate)
        btn_dsm = QPushButton("찾아보기")
        btn_dsm.clicked.connect(self._browse_dsm)
        btn_dsm_clear = QPushButton("초기화")
        btn_dsm_clear.clicked.connect(lambda: self.e_dsm.setText(""))
        dsm_lay.addWidget(self.e_dsm, 1)
        dsm_lay.addWidget(btn_dsm)
        dsm_lay.addWidget(btn_dsm_clear)
        lay.addWidget(dsm_group)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size:11px;")
        lay.addWidget(self.lbl_status)

        bot = QHBoxLayout()
        btn_cancel = QPushButton("취소")
        btn_cancel.setProperty("role", "cancel")
        btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("확인 — 분석 시작")
        self.btn_ok.setProperty("role", "ok")
        self.btn_ok.clicked.connect(self._accept)
        bot.addStretch()
        bot.addWidget(btn_cancel)
        bot.addWidget(self.btn_ok)
        lay.addLayout(bot)

    def _add_path_row(self, parent_layout, label_text, initial_value, browse_slot):
        group = QGroupBox(label_text)
        row = QHBoxLayout(group)
        edit = QLineEdit(initial_value)
        edit.textChanged.connect(self._validate)
        btn = QPushButton("찾아보기")
        btn.clicked.connect(browse_slot)
        row.addWidget(edit, 1)
        row.addWidget(btn)
        parent_layout.addWidget(group)
        return edit

    def _browse_shp(self):
        path, _ = QFileDialog.getOpenFileName(self, "지역 경계 Shapefile 선택", self.e_shp.text(), "Shapefile (*.shp)")
        if path:
            self.e_shp.setText(path)

    def _browse_dem(self):
        path, _ = QFileDialog.getOpenFileName(self, "DEM 파일 선택", self.e_dem.text(), "DEM/DSM (*.img *.tif)")
        if path:
            self.e_dem.setText(path)

    def _browse_dsm(self):
        path, _ = QFileDialog.getOpenFileName(self, "DSM 파일 선택", self.e_dsm.text(), "DEM/DSM (*.img *.tif)")
        if path:
            self.e_dsm.setText(path)

    def _validate(self):
        """필수 파일 2개(Shapefile, DEM)가 전부 존재하는 경로인지 확인함."""
        checks = [
            ("SHP", self.e_shp.text()),
            ("DEM", self.e_dem.text()),
        ]
        lines = []
        all_ok = True
        for label, path in checks:
            exists = bool(path) and os.path.exists(path)
            all_ok = all_ok and exists
            mark = "✓" if exists else "✗"
            color = GREEN if exists else RED
            name = os.path.basename(path) if path else "(미선택)"
            lines.append(f'<span style="color:{color};">{mark} {label}: {name}</span>')

        dsm_text = self.e_dsm.text()
        if dsm_text:
            dsm_ok = os.path.exists(dsm_text)
            lines.append(f'<span style="color:{GREEN if dsm_ok else RED};">'
                         f'{"✓" if dsm_ok else "✗"} DSM: {os.path.basename(dsm_text)}</span>')
            all_ok = all_ok and dsm_ok
        else:
            lines.append(f'<span style="color:{MUTED};">— DSM: DEM 사용</span>')

        self.lbl_status.setText(" | ".join(lines))
        self.btn_ok.setEnabled(all_ok)
        return all_ok

    def _accept(self):
        if not self._validate():
            return
        config = {
            "shp_path": self.e_shp.text(),
            "dem_path": self.e_dem.text(),
            "dsm_path": self.e_dsm.text(),
            "xlsx_path": self._cfg.get("xlsx_path", ""),  # 목록창에서 마지막으로 불러온 엑셀 경로를 그대로 보존함
        }
        save_config(config)
        self._result_config = config
        self.accept()

    def get_paths(self) -> dict:
        return dict(self._result_config)