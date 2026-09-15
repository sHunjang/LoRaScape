# lorascape/gui/widgets/node_list_window.py
"""Node 목록 창임. GWListWindow와 구조/역할이 거의 동일함 (엑셀 불러오기 버튼 포함)."""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLabel, QFileDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal

from lorascape.gui.widgets.dialogs import NodeParamDialog, STYLE_DLG, DARK, PANEL, TEXT, MUTED, BORDER

COLS = ["Node ID", "지역", "설치물 유형", "위도", "경도", "Gr(dBi)", "높이(m)"]


class NodeListWindow(QDialog):
    """Node 목록 창임."""
    sig_nodes_changed = pyqtSignal()
    sig_load_excel_requested = pyqtSignal(str)

    def __init__(self, nodes: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단말(Node) 목록")
        self.setStyleSheet(STYLE_DLG)
        self.resize(800, 520)
        self.setWindowFlag(Qt.Window)

        self.nodes = nodes
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
        for node in self.nodes:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            values = [node.node_id, node.region, node.device_type,
                      f"{node.lat:.6f}", f"{node.lon:.6f}",
                      f"{node.antenna_gain_dbi:.1f}", f"{node.antenna_height_m:.1f}"]
            for c, v in enumerate(values):
                self.tbl.setItem(r, c, QTableWidgetItem(v))

        self.lbl_summary.setText(f"총 Node {len(self.nodes)}개")

    def _on_row_double_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self.nodes):
            return
        node = self.nodes[row]
        dlg = NodeParamDialog(node, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to(node)
            self._fill()
            self.sig_nodes_changed.emit()

    def set_nodes(self, nodes: list):
        self.nodes = nodes
        self._fill()