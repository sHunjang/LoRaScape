# lorascape/gui/widgets/distance_window.py
"""
GW <-> Node 거리 분석 창임. 원본 참고 파일(distance_window.py)의 레이아웃/정렬
기능을 그대로 가져오되, 필드명을 우리 스키마(GatewaySite/NodeSite)에 맞춤.

거리/방위각 계산은 core.coord_transform.distance_m을 그대로 씀 - 별도 계산
로직을 새로 안 만들고 기존 검증된 함수를 재사용함.
"""
from __future__ import annotations
import math
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QComboBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from lorascape.data.coord_transform import distance_m
from lorascape.gui.widgets.dialogs import DARK, PANEL, TEXT, MUTED, BORDER, STYLE_DLG

COLS = ['Node ID', '거리 (km)', '방위각 (°)', '연결 GW', '상태']


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    시작점(lat1,lon1)에서 도착점(lat2,lon2)을 바라보는 방위각(°, 0=북쪽, 시계방향)임.
    core에 없어서 여기서 간단히 구현함 - 거리와 달리 방위각은 표시 전용 정보라
    core 모듈로 승격할 만큼 재사용 빈도가 높지 않아 UI 계층에 둠.
    """
    la1, lo1 = math.radians(lat1), math.radians(lon1)
    la2, lo2 = math.radians(lat2), math.radians(lon2)
    dlon = lo2 - lo1
    x = math.sin(dlon) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon)
    brg = math.degrees(math.atan2(x, y))
    return (brg + 360) % 360


class NumericItem(QTableWidgetItem):
    """숫자 기준 정렬을 지원하는 QTableWidgetItem임."""
    def __init__(self, text: str):
        super().__init__(text)
        try:
            self._val = float(text.replace(',', '').strip())
        except (ValueError, AttributeError):
            self._val = text

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            try:
                return float(self._val) < float(other._val)
            except (TypeError, ValueError):
                return str(self._val) < str(other._val)
        return super().__lt__(other)


class DistanceWindow(QDialog):
    """GW 하나를 기준으로 모든 Node까지의 거리/방위각/연결여부를 보여주는 창임."""

    def __init__(self, gateways: list, nodes: list, result=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GW ↔ Node 거리 분석")
        self.setStyleSheet(STYLE_DLG)
        self.resize(720, 500)
        self.setWindowFlag(Qt.Window)

        self.gateways = gateways
        self.nodes = nodes
        self.result = result
        self._build()
        self._update_table()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel("GW 선택:"))
        self.cb_gw = QComboBox()
        self.cb_gw.setStyleSheet(
            f"QComboBox{{background:{PANEL};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:4px;"
            f"padding:4px 8px;min-height:26px;}}"
        )
        for gw in self.gateways:
            self.cb_gw.addItem(gw.gw_id)
        top.addWidget(self.cb_gw)

        top.addWidget(QLabel("  정렬:"))
        self.cb_sort = QComboBox()
        self.cb_sort.setStyleSheet(self.cb_gw.styleSheet())
        self.cb_sort.addItems(['거리 순', '연결됨 먼저', 'Node ID 순'])
        top.addWidget(self.cb_sort)

        btn_ref = QPushButton("🔄 갱신")
        btn_ref.setStyleSheet(
            f"QPushButton{{background:#1c2a3a;color:#7ab8e8;"
            f"border:1px solid #2a4a6a;border-radius:4px;"
            f"padding:5px 12px;font-size:11px;}}"
            f"QPushButton:hover{{background:#254d78;}}"
        )
        btn_ref.clicked.connect(self._update_table)
        top.addWidget(btn_ref)
        top.addStretch()
        lay.addLayout(top)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet(f"color:{MUTED};font-size:11px;padding:2px 4px;")
        lay.addWidget(self.lbl_summary)

        self.tbl = QTableWidget(0, len(COLS))
        self.tbl.setHorizontalHeaderLabels(COLS)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSortingEnabled(True)
        self.tbl.setStyleSheet(
            f"QTableWidget{{background:{PANEL};color:{TEXT};"
            f"gridline-color:{BORDER};alternate-background-color:#1a1d28;"
            f"selection-background-color:#253a5a;}}"
            f"QHeaderView::section{{background:{DARK};color:{MUTED};border:none;padding:4px;}}"
        )
        lay.addWidget(self.tbl)

        self.cb_gw.currentIndexChanged.connect(self._update_table)
        self.cb_sort.currentIndexChanged.connect(self._update_table)

    def set_data(self, gateways: list, nodes: list, result=None):
        """외부(main_window)에서 데이터가 갱신됐을 때 호출함."""
        self.gateways = gateways
        self.nodes = nodes
        self.result = result
        cur = self.cb_gw.currentText()
        self.cb_gw.clear()
        for gw in gateways:
            self.cb_gw.addItem(gw.gw_id)
        idx = self.cb_gw.findText(cur)
        if idx >= 0:
            self.cb_gw.setCurrentIndex(idx)
        self._update_table()

    def _update_table(self):
        gi = self.cb_gw.currentIndex()
        if gi < 0 or gi >= len(self.gateways):
            self.tbl.setRowCount(0)
            self.lbl_summary.setText("GW가 없습니다.")
            return
        gw = self.gateways[gi]

        rows = []
        for nd in self.nodes:
            dist_m = distance_m(gw.lat, gw.lon, nd.lat, nd.lon)
            dist_km = dist_m / 1000.0
            brg = bearing(gw.lat, gw.lon, nd.lat, nd.lon)

            conn = self.result.connections.get(nd.node_id) if self.result else None
            is_connected_to_this_gw = conn is not None and conn.gw_id == gw.gw_id
            connected_gw_label = conn.gw_id if conn is not None else "─"

            rows.append({
                'node_id': nd.node_id, 'dist': dist_km, 'brg': brg,
                'connected_gw': connected_gw_label, 'is_mine': is_connected_to_this_gw,
                'has_any_conn': conn is not None,
            })

        sort_idx = self.cb_sort.currentIndex()
        if sort_idx == 0:
            rows.sort(key=lambda r: r['dist'])
        elif sort_idx == 1:
            rows.sort(key=lambda r: (not r['is_mine'], r['dist']))
        else:
            rows.sort(key=lambda r: r['node_id'])

        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        n_connected_to_this = sum(1 for r in rows if r['is_mine'])

        for row in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            status = "✓ 이 GW에 연결" if row['is_mine'] else ("○ 다른 GW 연결" if row['has_any_conn'] else "✗ 미연결")

            items = [
                QTableWidgetItem(row['node_id']),
                NumericItem(f"{row['dist']:.3f}"),
                NumericItem(f"{row['brg']:.1f}"),
                QTableWidgetItem(row['connected_gw']),
                QTableWidgetItem(status),
            ]
            for c, it in enumerate(items):
                it.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(r, c, it)

            status_item = self.tbl.item(r, 4)
            if row['is_mine']:
                status_item.setForeground(QColor('#00C94A'))
            elif row['has_any_conn']:
                status_item.setForeground(QColor('#FFD700'))
            else:
                status_item.setForeground(QColor('#FF4444'))

        self.tbl.setSortingEnabled(True)

        total = len(rows)
        if total > 0:
            dists = [r['dist'] for r in rows]
            self.lbl_summary.setText(
                f"GW: {gw.gw_id}  |  Node {total}개  |  "
                f"이 GW 연결: {n_connected_to_this}개  |  "
                f"거리 최소 {min(dists):.2f}km  평균 {np.mean(dists):.2f}km  최대 {max(dists):.2f}km"
            )
        else:
            self.lbl_summary.setText(f"GW: {gw.gw_id}  |  Node 없음")