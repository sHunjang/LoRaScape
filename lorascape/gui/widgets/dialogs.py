# lorascape/gui/widgets/dialogs.py
"""
GW/Node 개별 파라미터 편집 다이얼로그임. 원본 참고 파일(dialogs.py)의
GWParamDialog/NodeParamDialog와 같은 역할이되, 우리 스키마(GatewaySite/NodeSite)의
필드명(tx_power_dbm, antenna_gain_dbi 등)에 맞춰 새로 만듦.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QDoubleSpinBox, QPushButton, QLabel, QGroupBox,
)

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"

STYLE_DLG = f"""
    QDialog {{ background:{DARK}; color:{TEXT}; }}
    QLabel {{ color:{TEXT}; }}
    QLineEdit, QDoubleSpinBox {{
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


def _dspin(lo, hi, val, dec=2, suffix="", step=0.1):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    s.setDecimals(dec)
    s.setSuffix(suffix)
    s.setSingleStep(step)
    return s


class GWParamDialog(QDialog):
    """GW 무선 파라미터 편집 다이얼로그임."""

    def __init__(self, gw, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"GW 파라미터 — {gw.gw_id}")
        self.setStyleSheet(STYLE_DLG)
        self.setMinimumWidth(380)
        self._build(gw)

    def _build(self, gw):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        grp = QGroupBox("GW 파라미터")
        fl = QFormLayout(grp)
        fl.setSpacing(8)

        self.e_id = QLineEdit(gw.gw_id)
        self.e_lon = QLineEdit(f"{gw.lon:.6f}")
        self.e_lat = QLineEdit(f"{gw.lat:.6f}")
        self.sp_pt = _dspin(-30, 50, gw.tx_power_dbm, 1, " dBm")
        self.sp_gt = _dspin(0, 30, gw.antenna_gain_dbi, 2, " dBi")
        self.sp_lt = _dspin(0, 20, gw.cable_loss_db, 2, " dB")
        self.sp_hb = _dspin(0.5, 200, gw.antenna_height_m, 1, " m")

        fl.addRow("GW ID", self.e_id)
        fl.addRow("경도", self.e_lon)
        fl.addRow("위도", self.e_lat)
        fl.addRow("송신 출력 Pt", self.sp_pt)
        fl.addRow("안테나 이득 Gt", self.sp_gt)
        fl.addRow("케이블 손실 Lt", self.sp_lt)
        fl.addRow("안테나 높이", self.sp_hb)
        lay.addWidget(grp)

        btn_l = QHBoxLayout()
        ok = QPushButton("확인")
        ok.setProperty("role", "ok")
        cxl = QPushButton("취소")
        cxl.setProperty("role", "cancel")
        ok.clicked.connect(self.accept)
        cxl.clicked.connect(self.reject)
        btn_l.addStretch()
        btn_l.addWidget(cxl)
        btn_l.addWidget(ok)
        lay.addLayout(btn_l)

    def apply_to(self, gw):
        """다이얼로그에서 편집한 값을 gw 객체에 그대로 반영함 (in-place 수정)."""
        gw.gw_id = self.e_id.text()
        gw.lon = float(self.e_lon.text())
        gw.lat = float(self.e_lat.text())
        gw.tx_power_dbm = self.sp_pt.value()
        gw.antenna_gain_dbi = self.sp_gt.value()
        gw.cable_loss_db = self.sp_lt.value()
        gw.antenna_height_m = self.sp_hb.value()


class NodeParamDialog(QDialog):
    """Node 무선 파라미터 편집 다이얼로그임."""

    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Node 파라미터 — {node.node_id}")
        self.setStyleSheet(STYLE_DLG)
        self.setMinimumWidth(380)
        self._build(node)

    def _build(self, node):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        grp = QGroupBox("단말(Node) 파라미터")
        fl = QFormLayout(grp)
        fl.setSpacing(8)

        self.e_id = QLineEdit(node.node_id)
        self.e_lon = QLineEdit(f"{node.lon:.6f}")
        self.e_lat = QLineEdit(f"{node.lat:.6f}")
        self.sp_min_rx = _dspin(-150, -50, node.min_rx_dbm, 1, " dBm")
        self.sp_gr = _dspin(0, 30, node.antenna_gain_dbi, 2, " dBi")
        self.sp_lr = _dspin(0, 20, node.cable_loss_db, 2, " dB")
        self.sp_hm = _dspin(0.1, 50, node.antenna_height_m, 1, " m")
        self.sp_indoor = _dspin(0, 30, node.indoor_loss_db, 1, " dB")

        fl.addRow("Node ID", self.e_id)
        fl.addRow("경도", self.e_lon)
        fl.addRow("위도", self.e_lat)
        fl.addRow("최소 수신 레벨", self.sp_min_rx)
        fl.addRow("수신 이득 Gr", self.sp_gr)
        fl.addRow("수신 손실 Lr", self.sp_lr)
        fl.addRow("안테나 높이", self.sp_hm)
        fl.addRow("실내 투과 손실", self.sp_indoor)
        lay.addWidget(grp)

        note = QLabel("실내 투과 손실: 실외=0dB, 목조=5~10dB, 콘크리트=10~25dB")
        note.setStyleSheet(f"color:{MUTED};font-size:10px;")
        lay.addWidget(note)

        btn_l = QHBoxLayout()
        ok = QPushButton("확인")
        ok.setProperty("role", "ok")
        cxl = QPushButton("취소")
        cxl.setProperty("role", "cancel")
        ok.clicked.connect(self.accept)
        cxl.clicked.connect(self.reject)
        btn_l.addStretch()
        btn_l.addWidget(cxl)
        btn_l.addWidget(ok)
        lay.addLayout(btn_l)

    def apply_to(self, node):
        node.node_id = self.e_id.text()
        node.lon = float(self.e_lon.text())
        node.lat = float(self.e_lat.text())
        node.min_rx_dbm = self.sp_min_rx.value()
        node.antenna_gain_dbi = self.sp_gr.value()
        node.cable_loss_db = self.sp_lr.value()
        node.antenna_height_m = self.sp_hm.value()
        node.indoor_loss_db = self.sp_indoor.value()