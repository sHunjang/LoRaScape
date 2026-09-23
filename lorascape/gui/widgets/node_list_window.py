# lorascape/gui/widgets/node_list_window.py
"""
Node 목록 창임. 추가/삭제, CSV 가져오기/내보내기, 랜덤 배치 기능을 지원함.
'연결 GW 보기' 상세창은 다음 단계에서 추가 예정.
"""
import csv
import random
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLabel,
    QFileDialog, QMessageBox, QInputDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal

from lorascape.gui.widgets.dialogs import NodeParamDialog, STYLE_DLG, DARK, PANEL, TEXT, MUTED, BORDER
from lorascape.data.schema import NodeSite

COLS = ["Node ID", "지역", "설치물 유형", "위도", "경도", "최소수신(dBm)", "Gr(dBi)", "높이(m)"]

CSV_FIELDS = [
    "node_id", "region", "device_type", "lat", "lon",
    "antenna_gain_dbi", "cable_loss_db", "antenna_height_m", "indoor_loss_db",
]

TOOLBAR_BTN_STYLE = (
    f"QPushButton{{background:{PANEL};color:{TEXT};"
    f"border:1px solid {BORDER};border-radius:4px;"
    f"padding:5px 10px;font-size:11px;}}"
    f"QPushButton:hover{{border-color:#4f8ef7;}}"
)


class NodeListWindow(QDialog):
    """Node 목록 창임."""
    sig_nodes_changed = pyqtSignal()
    sig_load_excel_requested = pyqtSignal(str)

    def __init__(self, nodes: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단말(Node) 목록")
        self.setStyleSheet(STYLE_DLG)
        self.resize(900, 540)
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

        def _btn(text, slot):
            b = QPushButton(text)
            b.setStyleSheet(TOOLBAR_BTN_STYLE)
            b.clicked.connect(slot)
            top.addWidget(b)
            return b

        _btn("+ Node 추가", self._on_add_node)
        _btn("- 선택 삭제", self._on_delete_selected)
        _btn("전체 삭제", self._on_delete_all)
        _btn("🎲 랜덤 배치", self._on_random_placement)
        _btn("CSV 가져오기", self._on_import_csv)
        _btn("CSV 내보내기", self._on_export_csv)
        _btn("엑셀 불러오기", self._on_load_excel_clicked)
        lay.addLayout(top)

        self.tbl = QTableWidget(0, len(COLS))
        self.tbl.setHorizontalHeaderLabels(COLS)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.ExtendedSelection)
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

    def _fill(self):
        self.tbl.setRowCount(0)
        for node in self.nodes:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            values = [node.node_id, node.region, node.device_type,
                      f"{node.lat:.6f}", f"{node.lon:.6f}",
                      f"{node.antenna_gain_dbi:.1f}", f"{node.antenna_height_m:.1f}",
                      f"{node.min_rx_dbm:.1f}"]
            for c, v in enumerate(values):
                self.tbl.setItem(r, c, QTableWidgetItem(v))

        self.lbl_summary.setText(f"총 Node {len(self.nodes)}개")

    def set_nodes(self, nodes: list):
        self.nodes = nodes
        self._fill()

    def _selected_rows(self) -> list:
        return sorted({idx.row() for idx in self.tbl.selectedIndexes()})

    # ── 추가/삭제 ────────────────────────────────────────────

    def _on_add_node(self):
        new_node = NodeSite(
            node_id=f"NEW_NODE_{len(self.nodes) + 1}",
            region="", location_desc="",
            lat=37.4, lon=127.1,
            device_type="신규", install_type="신규",
        )
        dlg = NodeParamDialog(new_node, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to(new_node)
            self.nodes.append(new_node)
            self._fill()
            self.sig_nodes_changed.emit()

    def _on_delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "알림", "삭제할 행을 선택하세요.")
            return
        for r in sorted(rows, reverse=True):
            del self.nodes[r]
        self._fill()
        self.sig_nodes_changed.emit()

    def _on_delete_all(self):
        if not self.nodes:
            return
        reply = QMessageBox.question(
            self, "전체 삭제", f"Node {len(self.nodes)}개를 전부 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.nodes.clear()
            self._fill()
            self.sig_nodes_changed.emit()

    # ── 랜덤 배치 ────────────────────────────────────────────

    def _on_random_placement(self):
        """
        지정한 개수만큼 Node를 랜덤 좌표로 생성함. 범위는 기존 Node들의 위경도
        범위를 기준으로 잡되(±10% 여유), 기존 Node가 하나도 없으면 성남시
        대략 범위를 기본값으로 씀 (완전히 빈 상태에서도 쓸 수 있게).
        """
        n, ok = QInputDialog.getInt(self, "랜덤 배치", "생성할 Node 개수:", 10, 1, 1000)
        if not ok:
            return

        if self.nodes:
            lats = [n.lat for n in self.nodes]
            lons = [n.lon for n in self.nodes]
            lat_min, lat_max = min(lats), max(lats)
            lon_min, lon_max = min(lons), max(lons)
            margin_lat = (lat_max - lat_min) * 0.1 or 0.01
            margin_lon = (lon_max - lon_min) * 0.1 or 0.01
            lat_min -= margin_lat; lat_max += margin_lat
            lon_min -= margin_lon; lon_max += margin_lon
        else:
            lat_min, lat_max = 37.34, 37.47   # 성남시 실증지역 대략 범위 (기본값)
            lon_min, lon_max = 127.07, 127.16

        start_idx = len(self.nodes) + 1
        for i in range(n):
            lat = random.uniform(lat_min, lat_max)
            lon = random.uniform(lon_min, lon_max)
            self.nodes.append(NodeSite(
                node_id=f"RAND_NODE_{start_idx + i}",
                region="랜덤생성", location_desc="",
                lat=lat, lon=lon,
                device_type="랜덤생성", install_type="랜덤생성",
            ))
        self._fill()
        self.sig_nodes_changed.emit()

    # ── CSV ──────────────────────────────────────────────────

    def _on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Node CSV 내보내기", "nodes.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for node in self.nodes:
                writer.writerow({field: getattr(node, field) for field in CSV_FIELDS})
        QMessageBox.information(self, "완료", f"{len(self.nodes)}개 Node를 내보냈습니다.")

    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Node CSV 가져오기", "", "CSV (*.csv)")
        if not path:
            return
        try:
            added = 0
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    node = NodeSite(
                        node_id=row.get("node_id") or f"CSV_NODE_{added+1}",
                        region=row.get("region", ""),
                        location_desc="",
                        lat=float(row["lat"]),
                        lon=float(row["lon"]),
                        device_type=row.get("device_type", ""),
                        install_type="CSV 가져오기",
                        antenna_gain_dbi=float(row.get("antenna_gain_dbi", 0.0)),
                        cable_loss_db=float(row.get("cable_loss_db", 0.0)),
                        antenna_height_m=float(row.get("antenna_height_m", 1.5)),
                        indoor_loss_db=float(row.get("indoor_loss_db", 0.0)),
                    )
                    self.nodes.append(node)
                    added += 1
            self._fill()
            self.sig_nodes_changed.emit()
            QMessageBox.information(self, "완료", f"{added}개 Node를 가져왔습니다.")
        except Exception as e:
            QMessageBox.warning(self, "가져오기 실패", f"CSV 가져오기 중 오류가 발생했습니다:\n{e}")

    # ── 엑셀 / 파라미터 편집 (기존) ────────────────────────────

    def _on_load_excel_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "GW/Node 인벤토리 엑셀 선택", "", "Excel Files (*.xlsx)")
        if path:
            self.sig_load_excel_requested.emit(path)

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