# lorascape/gui/widgets/gw_list_window.py
"""
GW 목록 창임. 추가/삭제, CSV 가져오기/내보내기, 선택한 GW만 지도에 필터링해서
보여주는 '선택 커버리지' 기능을 지원함.

거리분석/단면도/링크버짓 상세창은 이번엔 범위에서 뺌 (다음 단계에서 추가 예정) -
지금은 목록 관리 + 필터링에 집중함.
"""
import csv
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QCheckBox, QLabel,
    QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal

from lorascape.gui.widgets.dialogs import GWParamDialog, STYLE_DLG, DARK, PANEL, TEXT, MUTED, BORDER
from lorascape.data.schema import GatewaySite

COLS = ["활성", "GW ID", "지역", "위도", "경도", "Pt(dBm)", "Gt(dBi)", "높이(m)"]

# CSV 가져오기/내보내기 컬럼 순서임. 내보낸 CSV를 그대로 다시 가져올 수 있게
# 순서를 고정해둠 (헤더 이름으로 매칭하니 순서 자체는 안 바뀌어도 상관없지만,
# 일관성을 위해 export/import 양쪽에서 이 상수를 그대로 씀).
CSV_FIELDS = [
    "gw_id", "region", "location_desc", "lat", "lon",
    "tx_power_dbm", "antenna_gain_dbi", "cable_loss_db", "antenna_height_m", "enabled",
]

TOOLBAR_BTN_STYLE = (
    f"QPushButton{{background:{PANEL};color:{TEXT};"
    f"border:1px solid {BORDER};border-radius:4px;"
    f"padding:5px 10px;font-size:11px;}}"
    f"QPushButton:hover{{border-color:#4f8ef7;}}"
)


class GWListWindow(QDialog):
    """GW 목록 창임."""
    sig_gws_changed = pyqtSignal()              # 목록 내용이 바뀌면 발생 (지도 갱신 트리거용)
    sig_load_excel_requested = pyqtSignal(str)  # 엑셀 불러오기 버튼 클릭 시
    sig_selected_coverage_requested = pyqtSignal(list)  # 체크/선택된 GW id 목록. 빈 리스트면 필터 해제

    def __init__(self, gateways: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GW 목록")
        self.setStyleSheet(STYLE_DLG)
        self.resize(900, 520)
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

        def _btn(text, slot):
            b = QPushButton(text)
            b.setStyleSheet(TOOLBAR_BTN_STYLE)
            b.clicked.connect(slot)
            top.addWidget(b)
            return b

        _btn("+ GW 추가", self._on_add_gw)
        _btn("- 선택 삭제", self._on_delete_selected)
        _btn("▶ 선택 커버리지", self._on_show_selected_coverage)
        _btn("✕ 필터 해제", self._on_clear_coverage_filter)
        _btn("전체 삭제", self._on_delete_all)
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

        hint = QLabel("행을 더블클릭하면 파라미터를 편집할 수 있습니다. 여러 행을 선택해 삭제/필터할 수 있습니다.")
        hint.setStyleSheet(f"color:{MUTED};font-size:10px;")
        lay.addWidget(hint)

    # ── 표시 ─────────────────────────────────────────────────

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

    def set_gateways(self, gateways: list):
        self.gateways = gateways
        self._fill()

    def _selected_rows(self) -> list:
        return sorted({idx.row() for idx in self.tbl.selectedIndexes()})

    # ── 추가/삭제 ────────────────────────────────────────────

    def _on_add_gw(self):
        """
        새 GW를 기본값으로 만들고 바로 편집 다이얼로그를 띄움 - 사용자가 취소하면
        추가 자체를 취소함 (좌표 0,0짜리 빈 GW가 목록에 남는 걸 방지).
        """
        new_gw = GatewaySite(
            gw_id=f"NEW_GW_{len(self.gateways) + 1}",
            region="", location_desc="",
            lat=37.4, lon=127.1,
            install_type="신규", power_source="",
        )
        dlg = GWParamDialog(new_gw, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to(new_gw)
            self.gateways.append(new_gw)
            self._fill()
            self.sig_gws_changed.emit()

    def _on_delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "알림", "삭제할 행을 선택하세요.")
            return
        for r in sorted(rows, reverse=True):
            del self.gateways[r]
        self._fill()
        self.sig_gws_changed.emit()

    def _on_delete_all(self):
        if not self.gateways:
            return
        reply = QMessageBox.question(
            self, "전체 삭제", f"GW {len(self.gateways)}개를 전부 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.gateways.clear()
            self._fill()
            self.sig_gws_changed.emit()

    # ── 선택 커버리지 필터 ───────────────────────────────────

    def _on_show_selected_coverage(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "알림", "지도에 표시할 GW를 선택하세요.")
            return
        selected_ids = [self.gateways[r].gw_id for r in rows]
        self.sig_selected_coverage_requested.emit(selected_ids)

    def _on_clear_coverage_filter(self):
        self.sig_selected_coverage_requested.emit([])

    # ── CSV ──────────────────────────────────────────────────

    def _on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "GW CSV 내보내기", "gateways.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for gw in self.gateways:
                writer.writerow({field: getattr(gw, field) for field in CSV_FIELDS})
        QMessageBox.information(self, "완료", f"{len(self.gateways)}개 GW를 내보냈습니다.")

    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "GW CSV 가져오기", "", "CSV (*.csv)")
        if not path:
            return
        try:
            added = 0
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    gw = GatewaySite(
                        gw_id=row.get("gw_id") or f"CSV_GW_{added+1}",
                        region=row.get("region", ""),
                        location_desc=row.get("location_desc", ""),
                        lat=float(row["lat"]),
                        lon=float(row["lon"]),
                        install_type="CSV 가져오기",
                        power_source="",
                        tx_power_dbm=float(row.get("tx_power_dbm", 14.0)),
                        antenna_gain_dbi=float(row.get("antenna_gain_dbi", 6.0)),
                        cable_loss_db=float(row.get("cable_loss_db", 1.0)),
                        antenna_height_m=float(row.get("antenna_height_m", 1.5)),
                        enabled=row.get("enabled", "True") in ("True", "1", "true"),
                    )
                    self.gateways.append(gw)
                    added += 1
            self._fill()
            self.sig_gws_changed.emit()
            QMessageBox.information(self, "완료", f"{added}개 GW를 가져왔습니다.")
        except Exception as e:
            QMessageBox.warning(self, "가져오기 실패", f"CSV 가져오기 중 오류가 발생했습니다:\n{e}")

    # ── 엑셀 / 파라미터 편집 / 활성토글 (기존) ─────────────────

    def _on_load_excel_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "GW/Node 인벤토리 엑셀 선택", "", "Excel Files (*.xlsx)")
        if path:
            self.sig_load_excel_requested.emit(path)

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