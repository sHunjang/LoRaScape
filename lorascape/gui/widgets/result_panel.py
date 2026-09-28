# lorascape/gui/widgets/result_panel.py
"""
커버리지/최적화 결과 요약 패널임.

이번 상세화에서 추가한 것: SF별 커버리지 분포, 중첩 커버 비율, GW당 평균 담당
Node 수. 전부 OptimizationResult에 이미 들어있는 데이터(connections의 sf,
node_gw_ids, gw_counts)로만 계산함 - core 쪽 변경 없이 표시 로직만 추가함.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton,
)
from PyQt5.QtCore import Qt

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"
GREEN = "#00C94A"
YELLOW = "#FFD700"
RED = "#FF4444"
PURPLE = "#9B59B6"

# SF별 대표 색상임. SF가 낮을수록(=속도 빠름, 신호 좋음) 초록 계열,
# 높을수록(=속도 느림, 신호 약함) 빨강 계열로 배정함.
SF_COLORS = {
    7: "#00C94A", 8: "#7ED321", 9: "#FFD700",
    10: "#FF8C00", 11: "#FF6060", 12: "#FF4444",
}


def _color_for_pct(pct: float) -> str:
    if pct >= 90:
        return GREEN
    if pct >= 70:
        return YELLOW
    return RED


class StatCard(QFrame):
    """제목 + 값 하나를 보여주는 작은 카드임."""

    def __init__(self, title: str, value: str = "─", color: str = TEXT, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:{PANEL};border:1px solid {BORDER};"
            f"border-radius:8px;padding:4px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;border:none;")
        self._title_lbl.setWordWrap(True)
        layout.addWidget(self._title_lbl)

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(f"color:{color};font-size:18px;font-weight:bold;border:none;")
        layout.addWidget(self._value_lbl)

    def set_value(self, value: str, color: str = None):
        self._value_lbl.setText(value)
        if color:
            self._value_lbl.setStyleSheet(f"color:{color};font-size:18px;font-weight:bold;border:none;")


class BarRow(QWidget):
    """레이블 + 가로 막대 + 수치를 한 줄로 보여주는 위젯임 (SF 분포용)."""

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setFixedWidth(38)
        self._label.setStyleSheet(f"color:{color};font-size:11px;font-weight:bold;border:none;")
        layout.addWidget(self._label)

        self._bar_bg = QFrame()
        self._bar_bg.setFixedHeight(12)
        self._bar_bg.setStyleSheet(f"background:{BORDER};border-radius:6px;")
        bar_layout = QHBoxLayout(self._bar_bg)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        self._bar_fill = QFrame()
        self._bar_fill.setStyleSheet(f"background:{color};border-radius:6px;")
        bar_layout.addWidget(self._bar_fill)
        bar_layout.addStretch()
        layout.addWidget(self._bar_bg, 1)

        self._value_lbl = QLabel("0개")
        self._value_lbl.setFixedWidth(46)
        self._value_lbl.setStyleSheet(f"color:{TEXT};font-size:10px;border:none;")
        layout.addWidget(self._value_lbl)

    def set_ratio(self, ratio: float, count: int):
        """ratio: 0.0~1.0. 막대 폭은 부모(BarRow) 너비 기준 상대 비율로 씀."""
        total_width = max(self._bar_bg.width(), 1)
        self._bar_fill.setFixedWidth(int(total_width * min(max(ratio, 0.0), 1.0)))
        self._value_lbl.setText(f"{count}개")


class ResultPanel(QWidget):
    """커버리지 분석 결과 요약 패널임."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{DARK};")
        self._sf_rows: dict[int, BarRow] = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("분석 결과")
        title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:bold;")
        layout.addWidget(title)

        # ── 요약 카드 ──
        self.card_coverage = StatCard("전체 커버리지")
        self.card_gw_count = StatCard("사용 GW 수")
        self.card_node_count = StatCard("총 Node 수")
        self.card_status = StatCard("상태", "대기 중")
        for card in (self.card_coverage, self.card_gw_count, self.card_node_count, self.card_status):
            layout.addWidget(card)

        # ── 히트맵 보기 버튼 ──
        self.btn_show_heatmap = QPushButton("🗺️ 이 결과를 히트맵으로 보기")
        self.btn_show_heatmap.setStyleSheet(
            f"QPushButton{{background:#1c3a5a;color:#7ab8e8;"
            f"border:1px solid #2a5a8a;border-radius:5px;"
            f"padding:8px;font-size:11px;font-weight:bold;}}"
            f"QPushButton:hover{{background:#254d78;}}"
            f"QPushButton:disabled{{background:#1a1e2a;color:{MUTED};border-color:{BORDER};}}"
        )
        self.btn_show_heatmap.setEnabled(False)  # 결과가 없을 땐 비활성화
        layout.addWidget(self.btn_show_heatmap)

        # ── SF별 커버리지 분포 ──
        sf_title = QLabel("SF별 커버리지 분포")
        sf_title.setStyleSheet(f"color:{MUTED};font-size:11px;font-weight:bold;padding-top:6px;")
        layout.addWidget(sf_title)

        sf_frame = QFrame()
        sf_frame.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {BORDER};border-radius:8px;}}")
        sf_layout = QVBoxLayout(sf_frame)
        sf_layout.setContentsMargins(8, 8, 8, 8)
        sf_layout.setSpacing(4)
        for sf in sorted(SF_COLORS.keys()):
            row = BarRow(f"SF{sf}", SF_COLORS[sf])
            self._sf_rows[sf] = row
            sf_layout.addWidget(row)
        layout.addWidget(sf_frame)

        # ── 중첩도 분석 ──
        overlap_title = QLabel("중첩도 분석")
        overlap_title.setStyleSheet(f"color:{MUTED};font-size:11px;font-weight:bold;padding-top:6px;")
        layout.addWidget(overlap_title)

        self.card_overlap = StatCard("중첩 커버 (2개 이상 GW)", color=PURPLE)
        self.card_avg_per_gw = StatCard("GW당 평균 담당 Node 수")
        layout.addWidget(self.card_overlap)
        layout.addWidget(self.card_avg_per_gw)

        layout.addStretch()

    def show_result(self, result, total_nodes: int):
        """OptimizationResult를 받아서 전체 패널을 갱신함."""
        self._last_result = result  # ★ 버튼 클릭 시 GW id 목록을 뽑기 위해 보관해둠
        self.btn_show_heatmap.setEnabled(bool(result.gateways))
        pct = result.coverage_ratio * 100
        self.card_coverage.set_value(f"{pct:.1f}%", _color_for_pct(pct))
        self.card_gw_count.set_value(str(result.k))
        self.card_node_count.set_value(str(total_nodes))
        status = "목표 달성" if result.target_met else "목표 미달"
        self.card_status.set_value(status, GREEN if result.target_met else YELLOW)

        # SF별 분포 집계: 연결된 Node들의 sf 값을 세어서 각 막대에 반영함
        sf_counts = {sf: 0 for sf in SF_COLORS}
        connected_count = 0
        for conn in result.connections.values():
            if conn is not None:
                sf_counts[conn.sf] = sf_counts.get(conn.sf, 0) + 1
                connected_count += 1

        max_count = max(sf_counts.values()) if sf_counts.values() else 0
        for sf, row in self._sf_rows.items():
            count = sf_counts.get(sf, 0)
            ratio = (count / max_count) if max_count > 0 else 0.0
            row.set_ratio(ratio, count)

        # 중첩 커버 비율: node_gw_ids에서 수신 GW가 2개 이상인 Node 비율
        overlap_count = sum(1 for gw_ids in result.node_gw_ids.values() if len(gw_ids) >= 2)
        overlap_pct = (overlap_count / total_nodes * 100) if total_nodes > 0 else 0.0
        self.card_overlap.set_value(f"{overlap_pct:.1f}% ({overlap_count}개)")

        # GW당 평균 담당 Node 수: gw_counts(연결로 채택된 것 기준) 평균
        gw_counts = result.gw_counts
        avg_per_gw = (sum(gw_counts.values()) / len(gw_counts)) if gw_counts else 0.0
        self.card_avg_per_gw.set_value(f"{avg_per_gw:.1f}개")

    def show_loading(self):
        self.btn_show_heatmap.setEnabled(False)
        self.card_status.set_value("계산 중...", MUTED)
        for row in self._sf_rows.values():
            row.set_ratio(0.0, 0)
        self.card_overlap.set_value("─")
        self.card_avg_per_gw.set_value("─")

    def show_error(self, message: str):
        self.btn_show_heatmap.setEnabled(False)
        self.card_status.set_value("오류", RED)