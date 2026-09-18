# lorascape/gui/widgets/suggestion_window.py
"""
GW 배치 제안 검토 창임. '추가 설치 위치 제안'과 '신규 배치 추천' 두 기능이
공유하는 공통 UI임 - 제안된 GW 후보들을 목록으로 보여주고, 사용자가 체크박스로
선택해서 '선택 적용'하면 그때 실제 GW 목록에 추가됨 (자동 반영 아님).
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QCheckBox, QLabel,
)
from PyQt5.QtCore import Qt, pyqtSignal

from lorascape.gui.widgets.dialogs import DARK, PANEL, TEXT, MUTED, BORDER, STYLE_DLG

COLS = ["적용", "제안 GW ID", "위도", "경도", "신규 커버 Node 수"]


class SuggestionWindow(QDialog):
    """제안된 GW 후보 목록을 보여주고, 선택 적용/전체 적용/취소를 지원하는 창임."""
    sig_apply_requested = pyqtSignal(list)  # 사용자가 최종 승인한 GatewaySite 리스트

    def __init__(self, title: str, suggested_gateways: list, node_gw_ids: dict, parent=None):
        """
        title: 창 제목(호출부에서 '추가 설치 위치 제안' / '신규 GW 배치 추천'처럼 구분해서 넘김)
        suggested_gateways: list[GatewaySite] - 제안된 후보들
        node_gw_ids: OptimizationResult.node_gw_ids - 각 Node가 어느 GW들에 수신되는지
                     (제안 GW별로 '몇 개 Node를 새로 커버하는지' 집계하는 데 씀)
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(STYLE_DLG)
        self.resize(600, 420)
        self.setWindowFlag(Qt.Window)

        self.suggested_gateways = suggested_gateways
        self.node_gw_ids = node_gw_ids
        self._build()
        self._fill()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet(f"color:{MUTED};font-size:11px;")
        lay.addWidget(self.lbl_summary)

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
        lay.addWidget(self.tbl)

        hint = QLabel("체크한 GW만 실제 GW 목록에 추가됩니다. 지도에서 미리 위치를 확인한 후 적용하세요.")
        hint.setStyleSheet(f"color:{MUTED};font-size:10px;")
        lay.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_select_all = QPushButton("전체 선택")
        btn_select_all.clicked.connect(lambda: self._set_all_checked(True))
        btn_select_none = QPushButton("전체 해제")
        btn_select_none.clicked.connect(lambda: self._set_all_checked(False))
        btn_cancel = QPushButton("취소")
        btn_cancel.setProperty("role", "cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton("선택 적용")
        btn_apply.setProperty("role", "ok")
        btn_apply.clicked.connect(self._on_apply)

        btn_row.addWidget(btn_select_all)
        btn_row.addWidget(btn_select_none)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_apply)
        lay.addLayout(btn_row)

    def _fill(self):
        self.tbl.setRowCount(0)
        for gw in self.suggested_gateways:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            chk = QCheckBox()
            chk.setChecked(True)  # 기본값: 전부 선택된 상태로 시작함
            self.tbl.setCellWidget(r, 0, chk)

            newly_covered = sum(1 for gw_ids in self.node_gw_ids.values() if gw.gw_id in gw_ids)

            values = [gw.gw_id, f"{gw.lat:.6f}", f"{gw.lon:.6f}", str(newly_covered)]
            for c, v in enumerate(values, start=1):
                self.tbl.setItem(r, c, QTableWidgetItem(v))

        self.lbl_summary.setText(f"제안된 GW {len(self.suggested_gateways)}개")

    def _set_all_checked(self, checked: bool):
        for r in range(self.tbl.rowCount()):
            chk = self.tbl.cellWidget(r, 0)
            if chk:
                chk.setChecked(checked)

    def _on_apply(self):
        selected = []
        for r in range(self.tbl.rowCount()):
            chk = self.tbl.cellWidget(r, 0)
            if chk and chk.isChecked():
                selected.append(self.suggested_gateways[r])

        if not selected:
            self.reject()
            return

        self.sig_apply_requested.emit(selected)
        self.accept()