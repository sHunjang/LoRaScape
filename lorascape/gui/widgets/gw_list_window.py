# lorascape/gui/widgets/gw_list_window.py
"""
GW 목록 창임. 테이블로 GW를 나열하고, 더블클릭하면 파라미터 편집 다이얼로그가 뜸.
'엑셀 불러오기' 버튼으로 GW/Node 인벤토리 엑셀을 직접 선택할 수 있음 - 실제 로딩은
main_window가 담당함(GW/Node 둘 다 한 엑셀에서 나오니, 이 창은 경로만 골라서
시그널로 알려주고 main_window가 양쪽 목록을 다 갱신함).
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QCheckBox, QLabel, QFileDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal

from lorascape.gui.widgets.dialogs import GWParamDialog, STYLE_DLG, DARK, PANEL, TEXT, MUTED, BORDER

COLS = ["활성", "GW ID", "지역", "위도", "경도", "Pt(dBm)", "Gt(dBi)", "높이(m)"]


class GWListWindow(QDialog):
    """GW 목록 창임."""
    sig_gws_changed = pyqtSignal()          # 파라미터 편집 시 발생 (지도 갱신 트리거용)
    sig_load_excel_requested = pyqtSignal(str)  # 엑셀 불러오기 버튼 클릭 시 경로와 함께 발생

    def __init__(self, gateways: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GW 목록")
        self.setStyleSheet(STYLE_DLG)
        self.resize(760, 480)
        self.setWindowFlag(Qt.Window)

        self.gateways = gateways
        self._build()
        self._fill()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet(f"color:{MUTED};font-size:11px;")
        top.addWidget(self.lbl_summary)
        top.addStretch()

        btn_load = QPushButton("엑셀 불러오기")
        btn_load.setStyleSheet(
            f"QPushButton{{background:#1c2a3a;color:#7ab8e8;"
            f"border:1px solid #2a4a6a;border-radius:4px;"
            f"padding:5px 14px;font-size:11px;}}"
            f"QPushButton:hover{{background:#254d78;}}"
        )
        btn_load.clicked.connect(self._on_load_excel_clicked)
        top.addWidget(btn_load)
        lay.addLayout(top)

        self.tbl = QTableWidget(0, len(COLS))
        self.tbl.setHorizontalHeaderLabels(COLS)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setStyleSheet(
            f"QTableWidget{{background:{PANEL};color:{TEXT};"
            f"gridline-color:{BORDER};alternate-background-color:#1a1d28;"
            f"selection-background-color:#253a5a;}}"
            f"QHeaderView::section{{background:{DARK};color:{MUTED};border:none;padding:4px;}}"
        )
        self.tbl.doubleClicked.connect(self._on_row_double_clicked)
        lay.addWidget(self.tbl)

        hint = QLabel("행을 더블클릭하면 파라미터를 편집할 수 있습니다.")
        hint.setStyleSheet(f"color:{MUTED};font-size:10px;")
        lay.addWidget(hint)

    def _on_load_excel_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "GW/Node 인벤토리 엑셀 선택", "", "Excel Files (*.xlsx)")
        if path:
            self.sig_load_excel_requested.emit(path)

    def _fill(self):
        self.tbl.setRowCount(0)
        for gw in self.gateways:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            chk = QCheckBox()
            chk.setChecked(gw.enabled)
            chk.stateChanged.connect(lambda state, g=gw: self._on_enabled_toggled(g, state))
            self.tbl.setCellWidget(r, 0, chk)

            values = [gw.gw_id, gw.region, f"{gw.lat:.6f}", f"{gw.lon:.6f}",
                      f"{gw.tx_power_dbm:.1f}", f"{gw.antenna_gain_dbi:.1f}", f"{gw.antenna_height_m:.1f}"]
            for c, v in enumerate(values, start=1):
                self.tbl.setItem(r, c, QTableWidgetItem(v))

        self.lbl_summary.setText(f"총 GW {len(self.gateways)}개 (활성 {sum(1 for g in self.gateways if g.enabled)}개)")

    def _on_enabled_toggled(self, gw, state):
        gw.enabled = bool(state)
        self.sig_gws_changed.emit()

    def _on_row_double_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self.gateways):
            return
        gw = self.gateways[row]
        dlg = GWParamDialog(gw, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to(gw)
            self._fill()
            self.sig_gws_changed.emit()

    def set_gateways(self, gateways: list):
        """외부(main_window)에서 GW 목록이 새로 로드됐을 때 갱신용."""
        self.gateways = gateways
        self._fill()