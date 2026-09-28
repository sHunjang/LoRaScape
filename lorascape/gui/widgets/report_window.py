# lorascape/gui/widgets/report_window.py
"""
GW 커버리지 보고서 창임. 표시할 데이터는 전부 CoverageReport에서 오고(계산 없음),
엑셀/CSV/PDF 내보내기 버튼도 여기서 처리함.
  - GW별 탭: 왼쪽 GW 표, 오른쪽에 선택한 GW의 상세(유형별 개수 + 단말 목록) + '히트맵 보기'
  - 단말별 탭 / 미커버 단말 탭
"""
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QSplitter, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from lorascape.core.reporting.coverage_report import SF_LEVELS
from lorascape.core.reporting.exporters import (
    NODE_HEADERS, UNCOVERED_HEADERS, export_excel, export_nodes_csv,
)
from lorascape.gui.report_pdf import export_report_pdf
from lorascape.gui.widgets.dialogs import BORDER, DARK, MUTED, PANEL, STYLE_DLG, TEXT
from lorascape.gui.widgets.distance_window import NumericItem

SF_COLORS = ["#cfe8ff", "#9ccbff", "#6aa7ff", "#4b83e6", "#3a63b8", "#2b4a8a"]   # 밝음 = SF7, 어두움 = SF12

EXTRA_STYLE = f"""
QTabWidget::pane {{ border:1px solid {BORDER}; background:{PANEL}; top:-1px; }}
QTabBar::tab {{ background:transparent; color:{MUTED}; padding:10px 20px; border:1px solid transparent; }}
QTabBar::tab:selected {{ background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
    border-bottom:1px solid {PANEL}; font-weight:bold; }}
QTableWidget {{ background:{PANEL}; color:{TEXT}; gridline-color:{BORDER};
    alternate-background-color:#1a1d28; selection-background-color:#253a5a; border:none; }}
QHeaderView::section {{ background:{DARK}; color:{MUTED}; border:none; padding:6px; }}
QPushButton {{ background:{PANEL}; color:{TEXT}; border:1px solid {BORDER}; border-radius:6px; padding:8px 14px; }}
QPushButton:hover {{ border-color:#4f8ef7; }}
QPushButton[primary="true"] {{ background:#2f5fb3; border-color:#4b7bd0; }}
"""


class SfBarDelegate(QStyledItemDelegate):
    """SF 분포를 막대로 그림. 셀 위젯 대신 델리게이트를 써서 정렬해도 막대가 행을 따라감."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)   # 선택 배경 등 기본 처리 (텍스트는 비어 있음)
        counts = index.data(Qt.UserRole) or []
        total = sum(counts)
        r = option.rect
        w, h = r.width() - 16, 10
        x0, y = r.x() + 8, r.y() + (r.height() - h) // 2
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BORDER))
        painter.drawRoundedRect(x0, y, w, h, 5, 5)
        if total:
            clip = QPainterPath()
            clip.addRoundedRect(x0, y, w, h, 5, 5)
            painter.setClipPath(clip)
            x = float(x0)
            for c, col in zip(counts, SF_COLORS):
                if not c:
                    continue
                seg = w * c / total
                painter.setBrush(QColor(col))
                painter.drawRect(int(round(x)), y, int(seg) + 1, h)
                x += seg
        painter.restore()


def _item(value, align_right=False):
    it = NumericItem("" if value is None else str(value))
    it.setTextAlignment((Qt.AlignRight if align_right else Qt.AlignLeft) | Qt.AlignVCenter)
    return it


def _num(value, spec):
    return _item("—" if value is None else format(value, spec), True)


def _make_table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class ReportWindow(QDialog):
    sig_show_heatmap = pyqtSignal(str)   # 선택한 GW id로 히트맵을 보여 달라는 요청

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.report = report
        self._gw_by_id = {g.gw_id: g for g in report.gw_rows}
        self._current_gw_id = ""

        self.setWindowTitle("GW 커버리지 보고서")
        self.setStyleSheet(STYLE_DLG + EXTRA_STYLE)
        self.resize(1320, 820)
        self.setWindowFlag(Qt.Window)

        self._build()
        self._fill_gw_table()
        self._fill_node_table()
        self._fill_uncovered_table()
        if self.tbl_gw.rowCount():
            self.tbl_gw.selectRow(0)

    # ── 화면 구성 ────────────────────────────────────────────

    def _card(self, title, value, color=TEXT):
        f = QFrame()
        f.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {BORDER};border-radius:10px;}}")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"color:{MUTED};font-size:12px;border:none;")
        v = QLabel(value)
        v.setStyleSheet(f"color:{color};font-size:26px;font-weight:bold;border:none;")
        lay.addWidget(t)
        lay.addWidget(v)
        return f

    def _build(self):
        r = self.report
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        col = QVBoxLayout()
        title = QLabel("GW 커버리지 보고서")
        title.setStyleSheet(f"color:{TEXT};font-size:22px;font-weight:bold;")
        sub = QLabel(f"검증 시점 기준 · 활성 GW {r.gw_count}개 · 단말 {r.total_nodes}개 · 생성 {r.generated_at}")
        sub.setStyleSheet(f"color:{MUTED};font-size:12px;")
        col.addWidget(title)
        col.addWidget(sub)
        head.addLayout(col)
        head.addStretch()
        self.btn_excel = QPushButton("엑셀로 내보내기")
        self.btn_excel.setProperty("primary", True)
        self.btn_csv = QPushButton("CSV (단말별)")
        self.btn_pdf = QPushButton("PDF 저장")
        self.btn_excel.clicked.connect(self._export_excel)
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_pdf.clicked.connect(self._export_pdf)
        for b in (self.btn_excel, self.btn_csv, self.btn_pdf):
            head.addWidget(b)
        root.addLayout(head)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        ratio_color = "#00C94A" if r.target_met else "#f5b95f"
        status = "달성" if r.target_met else "미달"
        for title_, val, color in [
            ("전체 단말", str(r.total_nodes), TEXT),
            ("커버된 단말", str(r.covered_nodes), TEXT),
            (f"커버율 (목표 {r.coverage_target * 100:.0f}% {status})", f"{r.coverage_ratio * 100:.1f}%", ratio_color),
            ("사용 GW", str(r.gw_count), TEXT),
            ("미커버 단말", str(r.uncovered_nodes), "#ff9a94" if r.uncovered_nodes else TEXT),
        ]:
            cards.addWidget(self._card(title_, val, color))
        root.addLayout(cards)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_gw_tab(), "GW별")
        self.tabs.addTab(self._build_node_tab(), "단말별")
        self.tabs.addTab(self._build_uncovered_tab(), f"미커버 단말 ({r.uncovered_nodes})")
        root.addWidget(self.tabs, 1)

    def _build_gw_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)

        self.tbl_gw = _make_table(["GW ID", "지역 · 상세위치", "연결 단말", "수신 가능", "SF 분포", "평균 Pr (dBm)"])
        self.tbl_gw.setItemDelegateForColumn(4, SfBarDelegate(self.tbl_gw))
        self.tbl_gw.itemSelectionChanged.connect(self._on_gw_selected)
        split.addWidget(self.tbl_gw)

        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(16, 12, 16, 12)
        dl.setSpacing(10)
        top = QHBoxLayout()
        tcol = QVBoxLayout()
        cap = QLabel("선택한 GW")
        cap.setStyleSheet(f"color:{MUTED};font-size:12px;")
        self.lbl_gw_title = QLabel("")
        self.lbl_gw_title.setStyleSheet(f"color:{TEXT};font-size:20px;font-weight:bold;")
        self.lbl_gw_sub = QLabel("")
        self.lbl_gw_sub.setStyleSheet(f"color:{MUTED};font-size:12px;")
        tcol.addWidget(cap)
        tcol.addWidget(self.lbl_gw_title)
        tcol.addWidget(self.lbl_gw_sub)
        top.addLayout(tcol)
        top.addStretch()
        self.btn_heatmap = QPushButton("히트맵 보기")
        self.btn_heatmap.clicked.connect(lambda: self._current_gw_id and self.sig_show_heatmap.emit(self._current_gw_id))
        top.addWidget(self.btn_heatmap, 0, Qt.AlignTop)
        dl.addLayout(top)

        stats = QHBoxLayout()
        self.lbl_stat_conn, self.lbl_stat_recv, self.lbl_stat_shared = QLabel(), QLabel(), QLabel()
        for cap_, lbl in [("연결 단말", self.lbl_stat_conn), ("수신 가능 (중첩 포함)", self.lbl_stat_recv),
                          ("다른 GW에도 수신", self.lbl_stat_shared)]:
            f = QFrame()
            f.setStyleSheet(f"QFrame{{background:#191c27;border:1px solid {BORDER};border-radius:8px;}}")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(12, 8, 12, 8)
            c = QLabel(cap_)
            c.setStyleSheet(f"color:{MUTED};font-size:11px;border:none;")
            lbl.setStyleSheet(f"color:{TEXT};font-size:20px;font-weight:bold;border:none;")
            fl.addWidget(c)
            fl.addWidget(lbl)
            stats.addWidget(f)
        dl.addLayout(stats)

        self.lbl_types = QLabel("")
        self.lbl_types.setWordWrap(True)
        self.lbl_types.setStyleSheet(f"color:{TEXT};font-size:13px;")
        dl.addWidget(self.lbl_types)

        self.tbl_detail = _make_table(["단말 ID", "유형", "거리 (km)", "Pr (dBm)", "SF", "구분"])
        dl.addWidget(self.tbl_detail, 1)
        self.lbl_detail_foot = QLabel("")
        self.lbl_detail_foot.setStyleSheet(f"color:{MUTED};font-size:12px;")
        dl.addWidget(self.lbl_detail_foot)

        split.addWidget(detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay.addWidget(split)
        return w

    def _build_node_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tbl_node = _make_table(NODE_HEADERS)
        lay.addWidget(self.tbl_node)
        return w

    def _build_uncovered_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_reasons = QLabel("")
        self.lbl_reasons.setStyleSheet(f"color:{MUTED};font-size:12px;padding:8px 12px;")
        lay.addWidget(self.lbl_reasons)
        self.tbl_uncovered = _make_table(UNCOVERED_HEADERS)
        lay.addWidget(self.tbl_uncovered)
        return w

    # ── 표 채우기 ────────────────────────────────────────────

    def _fill_gw_table(self):
        t = self.tbl_gw
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for g in self.report.gw_rows:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _item(g.gw_id))
            t.setItem(r, 1, _item(f"{g.region} · {g.location_desc}" if g.location_desc else g.region))
            t.setItem(r, 2, _item(g.connected, True))
            t.setItem(r, 3, _item(g.receivable, True))
            bar = QTableWidgetItem("")
            counts = [g.sf_counts.get(sf, 0) for sf in SF_LEVELS]
            bar.setData(Qt.UserRole, counts)
            bar.setToolTip(" · ".join(f"SF{sf}: {c}" for sf, c in zip(SF_LEVELS, counts) if c) or "연결 단말 없음")
            t.setItem(r, 4, bar)
            t.setItem(r, 5, _num(g.avg_rx_dbm, ".1f"))
        t.setSortingEnabled(True)
        for c, w in enumerate([190, 240, 90, 90, 150, 110]):
            t.setColumnWidth(c, w)

    def _fill_node_table(self):
        t = self.tbl_node
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for n in self.report.node_rows:
            r = t.rowCount()
            t.insertRow(r)
            for c, v in enumerate([n.node_id, n.device_type, n.region, n.location_desc,
                                   "연결" if n.covered else "미커버", n.gw_id or "—"]):
                t.setItem(r, c, _item(v))
            t.setItem(r, 6, _num(n.rx_power_dbm, ".1f"))
            t.setItem(r, 7, _item("—" if n.sf is None else f"SF{n.sf}", True))
            t.setItem(r, 8, _item(n.receiving_gws, True))
            if not n.covered:
                t.item(r, 4).setForeground(QColor("#ff9a94"))
        t.setSortingEnabled(True)
        for c, w in enumerate([190, 130, 110, 240, 80, 190, 90, 60]):
            t.setColumnWidth(c, w)

    def _fill_uncovered_table(self):
        from lorascape.core.reporting.coverage_report import REASON_LABELS
        t = self.tbl_uncovered
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for u in self.report.uncovered_rows:
            r = t.rowCount()
            t.insertRow(r)
            for c, v in enumerate([u.node_id, u.device_type, u.region, u.location_desc, u.best_gw_id or "—"]):
                t.setItem(r, c, _item(v))
            t.setItem(r, 5, _num(u.distance_km, ".2f"))
            t.setItem(r, 6, _num(u.best_rx_dbm, ".1f"))
            t.setItem(r, 7, _item(u.reason_label))
            t.setItem(r, 8, _item(u.reason_detail))
        t.setSortingEnabled(True)
        for c, w in enumerate([190, 130, 110, 240, 190, 90, 110, 170]):
            t.setColumnWidth(c, w)
        if self.report.reason_counts:
            self.lbl_reasons.setText("사유별: " + " · ".join(
                f"{REASON_LABELS.get(k, k)} {v}" for k, v in sorted(self.report.reason_counts.items(), key=lambda kv: -kv[1])))
        else:
            self.lbl_reasons.setText("미커버 단말이 없습니다.")

    # ── GW 상세 ──────────────────────────────────────────────

    def _on_gw_selected(self):
        rows = self.tbl_gw.selectionModel().selectedRows()
        if not rows:
            return
        item = self.tbl_gw.item(rows[0].row(), 0)
        if item is not None:
            self._show_gw_detail(item.text())

    def _show_gw_detail(self, gw_id):
        g = self._gw_by_id.get(gw_id)
        if g is None:
            return
        self._current_gw_id = gw_id
        self.lbl_gw_title.setText(g.gw_id)
        self.lbl_gw_sub.setText(f"{g.region} · {g.location_desc} · ({g.lat:.6f}, {g.lon:.6f})")
        self.lbl_stat_conn.setText(str(g.connected))
        self.lbl_stat_recv.setText(str(g.receivable))
        self.lbl_stat_shared.setText(str(g.shared))
        self.lbl_types.setText("연결 단말 유형: " + (" · ".join(f"{t} {c}" for t, c in g.type_counts.items()) or "없음"))

        t = self.tbl_detail
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for l in g.links:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _item(l.node_id))
            t.setItem(r, 1, _item(l.device_type))
            t.setItem(r, 2, _num(l.distance_km, ".2f"))
            t.setItem(r, 3, _num(l.rx_power_dbm, ".1f"))
            t.setItem(r, 4, _item(f"SF{l.sf}"))
            t.setItem(r, 5, _item(l.relation))
            if l.relation != "연결":
                for c in range(6):
                    t.item(r, c).setForeground(QColor(MUTED))
        t.setSortingEnabled(True)
        for c, w in enumerate([170, 110, 80, 80, 60]):
            t.setColumnWidth(c, w)
        self.lbl_detail_foot.setText(f"{g.receivable}개 · 수신만 = 다른 GW에 연결된 단말")

    # ── 내보내기 ─────────────────────────────────────────────

    @staticmethod
    def _default_name(ext):
        return f"GW_커버리지_보고서_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"

    def _run_export(self, title, ext, filter_, fn):
        path, _ = QFileDialog.getSaveFileName(self, title, self._default_name(ext), filter_)
        if not path:
            return
        try:
            fn(path)
        except Exception as e:   # 파일이 엑셀에서 열려 있는 경우 등
            QMessageBox.warning(self, "내보내기 실패", f"저장하지 못했습니다:\n{e}")
            return
        QMessageBox.information(self, "완료", f"저장했습니다:\n{path}")

    def _export_excel(self):
        self._run_export("엑셀로 내보내기", "xlsx", "Excel (*.xlsx)", lambda p: export_excel(self.report, p))

    def _export_csv(self):
        self._run_export("CSV로 내보내기 (단말별)", "csv", "CSV (*.csv)", lambda p: export_nodes_csv(self.report, p))

    def _export_pdf(self):
        self._run_export("PDF로 저장", "pdf", "PDF (*.pdf)", lambda p: export_report_pdf(self.report, p))
