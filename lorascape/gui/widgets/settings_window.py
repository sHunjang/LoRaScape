# lorascape/gui/widgets/settings_window.py
"""
분석 설정 창임. GW/Node 개별 무선 파라미터(Pt, Gt 등)는 다루지 않음 - 그건
GW/Node 목록창에서 개체별로 편집함. 여기는 "분석 전체에 적용되는" 값만 다룸:
주파수, 대역폭, 수신기 잡음지수, 환경분류, 커버리지 목표치, 최대 추가배치 GW 수.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDoubleSpinBox, QSpinBox, QComboBox, QPushButton, QGroupBox, QLabel, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal

from lorascape.gui.app_config import load_config, save_config

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"

STYLE = f"""
    QDialog {{ background:{DARK}; color:{TEXT}; }}
    QLabel {{ color:{TEXT}; }}
    QDoubleSpinBox, QSpinBox, QComboBox {{
        background:{PANEL}; color:{TEXT};
        border:1px solid {BORDER}; border-radius:4px;
        padding:4px 6px; min-height:26px;
    }}
    QComboBox QAbstractItemView {{
        background:{PANEL}; color:{TEXT};
        selection-background-color:#253a5a;
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

ENVIRONMENTS = [
    ("dense_urban", "Dense Urban (고밀도 도심)"),
    ("urban", "Urban (도심)"),
    ("suburban", "Suburban (교외)"),
    ("open", "Open (개활지)"),
]


class SettingsWindow(QDialog):
    """분석 설정 창임."""
    sig_settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("분석 설정")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(420)
        self._cfg = load_config()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        note = QLabel(
            "여기 설정은 전체 분석에 공통 적용됩니다.\n"
            "개별 GW/Node의 무선 파라미터(송신출력, 안테나 이득 등)는 "
            "'GW 목록' / '단말 목록' 창에서 각각 편집하세요."
        )
        note.setStyleSheet(f"color:{MUTED};font-size:10px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        grp1 = QGroupBox("전파 계산 파라미터")
        fl1 = QFormLayout(grp1)
        fl1.setSpacing(8)

        self.sp_fc = QDoubleSpinBox()
        self.sp_fc.setRange(100, 2000)
        self.sp_fc.setValue(self._cfg["fc_mhz"])
        self.sp_fc.setSuffix(" MHz")
        self.sp_fc.setDecimals(1)

        self.sp_bw = QDoubleSpinBox()
        self.sp_bw.setRange(1000, 500000)
        self.sp_bw.setValue(self._cfg["bandwidth_hz"])
        self.sp_bw.setSuffix(" Hz")
        self.sp_bw.setDecimals(0)

        self.sp_nf = QDoubleSpinBox()
        self.sp_nf.setRange(0, 20)
        self.sp_nf.setValue(self._cfg["receiver_noise_figure_db"])
        self.sp_nf.setSuffix(" dB")
        self.sp_nf.setDecimals(1)

        self.cb_env = QComboBox()
        for key, label in ENVIRONMENTS:
            self.cb_env.addItem(label, userData=key)
        idx = self.cb_env.findData(self._cfg["environment"])
        if idx >= 0:
            self.cb_env.setCurrentIndex(idx)

        fl1.addRow("반송 주파수", self.sp_fc)
        fl1.addRow("대역폭", self.sp_bw)
        fl1.addRow("수신기 잡음지수", self.sp_nf)
        fl1.addRow("환경 분류 (Song's Model)", self.cb_env)
        lay.addWidget(grp1)

        grp2 = QGroupBox("GW 배치 검증/보강 파라미터")
        fl2 = QFormLayout(grp2)
        fl2.setSpacing(8)

        self.sp_target = QDoubleSpinBox()
        self.sp_target.setRange(0.5, 1.0)
        self.sp_target.setValue(self._cfg["coverage_target"])
        self.sp_target.setSingleStep(0.05)
        self.sp_target.setDecimals(2)

        self.sp_max_add = QSpinBox()
        self.sp_max_add.setRange(1, 50)
        self.sp_max_add.setValue(self._cfg["max_additional"])

        fl2.addRow("목표 커버리지", self.sp_target)
        fl2.addRow("최대 추가 배치 GW 수", self.sp_max_add)
        lay.addWidget(grp2)

        grp3 = QGroupBox("지도 표시")
        fl3 = QFormLayout(grp3)
        fl3.setSpacing(8)

        opacity_row = QHBoxLayout()
        self.sl_heatmap_opacity = QSlider(Qt.Horizontal)
        self.sl_heatmap_opacity.setRange(10, 100)  # 10%~100%
        self.sl_heatmap_opacity.setValue(int(self._cfg["heatmap_opacity"] * 100))
        self.lbl_heatmap_opacity_val = QLabel(f"{self.sl_heatmap_opacity.value()}%")
        self.sl_heatmap_opacity.valueChanged.connect(
            lambda v: self.lbl_heatmap_opacity_val.setText(f"{v}%")
        )
        opacity_row.addWidget(self.sl_heatmap_opacity)
        opacity_row.addWidget(self.lbl_heatmap_opacity_val)

        fl3.addRow("히트맵 진하기", opacity_row)
        lay.addWidget(grp3)

        btn_l = QHBoxLayout()
        btn_reset = QPushButton("기본값 복원")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_cancel = QPushButton("취소")
        btn_cancel.setProperty("role", "cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("적용")
        btn_ok.setProperty("role", "ok")
        btn_ok.clicked.connect(self._accept)
        btn_l.addWidget(btn_reset)
        btn_l.addStretch()
        btn_l.addWidget(btn_cancel)
        btn_l.addWidget(btn_ok)
        lay.addLayout(btn_l)

    def _reset_defaults(self):
        from lorascape.gui.app_config import DEFAULT_CONFIG
        self.sp_fc.setValue(DEFAULT_CONFIG["fc_mhz"])
        self.sp_bw.setValue(DEFAULT_CONFIG["bandwidth_hz"])
        self.sp_nf.setValue(DEFAULT_CONFIG["receiver_noise_figure_db"])
        self.sl_heatmap_opacity.setValue(int(DEFAULT_CONFIG["heatmap_opacity"] * 100))
        idx = self.cb_env.findData(DEFAULT_CONFIG["environment"])
        if idx >= 0:
            self.cb_env.setCurrentIndex(idx)
        self.sp_target.setValue(DEFAULT_CONFIG["coverage_target"])
        self.sp_max_add.setValue(DEFAULT_CONFIG["max_additional"])

    def _collect(self) -> dict:
        return {
            "fc_mhz": self.sp_fc.value(),
            "bandwidth_hz": self.sp_bw.value(),
            "receiver_noise_figure_db": self.sp_nf.value(),
            "environment": self.cb_env.currentData(),
            "coverage_target": self.sp_target.value(),
            "max_additional": self.sp_max_add.value(),
            "heatmap_opacity": self.sl_heatmap_opacity.value() / 100.0,
        }

    def _accept(self):
        new_settings = self._collect()
        self._cfg.update(new_settings)
        save_config(self._cfg)
        self.sig_settings_changed.emit(new_settings)
        self.accept()