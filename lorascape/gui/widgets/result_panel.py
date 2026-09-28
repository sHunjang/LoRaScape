# lorascape/gui/widgets/result_panel.py
"""
커버리지/검증 결과 요약 패널임.

카드(커버리지, GW 수, 단말 수, 상태) + 수신전력 구간별 분포 + 중첩도 분석으로 구성됨.
수신전력 분포는 '연결된 단말'의 수신전력(dBm)을 구간별로 세어서 보여줌 - 예전에는 SF 분포를
보여줬는데, 이 지역은 GW가 촘촘해서 연결된 단말이 거의 전부 SF7이라 정보가 없었음.
(SF별 분포는 보고서 창의 GW별 표에서 계속 볼 수 있음.)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
)

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"
GREEN = "#00C94A"
YELLOW = "#FFD700"
RED = "#FF4444"
PURPLE = "#9B59B6"

# 수신전력 구간임: (표시 이름, 하한 dBm - 이 값 이상이면 이 구간, 색상). 강한 구간부터 위에서 아래로 검사함.
# 색상 순서(빨강 > 주황 > 노랑 > 초록)는 지도 히트맵과 같은 규칙임 - 강한 신호가 빨강임.
# 마지막 구간은 하한이 없음: 기본 최소 수신 레벨이 -100 dBm이라, 이 구간에는 최소 수신 레벨을
# 낮게 잡은 단말(예: 화장실 -125 dBm)만 들어올 수 있음.
PR_BINS = [
    ("-75 이상", -75.0, "#FF4444"),
    ("-75 ~ -90", -90.0, "#FF8C00"),
    ("-90 ~ -100", -100.0, "#FFD700"),
    ("-100 미만", None, "#00C94A"),
]


def pr_bin_counts(connections: dict) -> list:
    """연결된 단말(값이 None이 아닌 것)의 수신전력을 PR_BINS 구간별로 센 리스트를 반환함."""
    counts = [0] * len(PR_BINS)
    for conn in connections.values():
        if conn is None:
            continue
        for i, (_, lower, _) in enumerate(PR_BINS):
            if lower is None or conn.rx_power_dbm >= lower:
                counts[i] += 1
                break
    return counts


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
    """레이블 + 가로 막대 + 개수를 한 줄로 보여주는 위젯임 (수신전력 분포용)."""

    def __init__(self, label: str, color: str, label_width: int = 68, parent=None):
        super().__init__(parent)
        self._color = color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setFixedWidth(label_width)
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
        """ratio: 0.0~1.0. 막대 폭은 막대 배경 너비 기준 상대 비율로 씀."""
        total_width = max(self._bar_bg.width(), 1)
        self._bar_fill.setFixedWidth(int(total_width * min(max(ratio, 0.0), 1.0)))
        self._value_lbl.setText(f"{count}개")


class ResultPanel(QWidget):
    """커버리지 분석 결과 요약 패널임."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{DARK};")
        self._pr_rows: list = []
        self._last_result = None
        self._build()

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{MUTED};font-size:11px;font-weight:bold;padding-top:6px;")
        return lbl

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
        self.btn_show_heatmap.setEnabled(False)
        layout.addWidget(self.btn_show_heatmap)

        # ── 수신전력 구간별 분포 ──
        layout.addWidget(self._section_title("수신전력 분포 (연결 단말, dBm)"))

        pr_frame = QFrame()
        pr_frame.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {BORDER};border-radius:8px;}}")
        pr_layout = QVBoxLayout(pr_frame)
        pr_layout.setContentsMargins(8, 8, 8, 8)
        pr_layout.setSpacing(4)
        for name, _, color in PR_BINS:
            row = BarRow(name, color)
            self._pr_rows.append(row)
            pr_layout.addWidget(row)
        layout.addWidget(pr_frame)

        # ── 중첩도 분석 ──
        layout.addWidget(self._section_title("중첩도 분석"))
        self.card_overlap = StatCard("중첩 커버 (2개 이상 GW)", color=PURPLE)
        self.card_avg_per_gw = StatCard("GW당 평균 담당 Node 수")
        layout.addWidget(self.card_overlap)
        layout.addWidget(self.card_avg_per_gw)

        layout.addStretch()

    def show_result(self, result, total_nodes: int):
        """OptimizationResult를 받아서 전체 패널을 갱신함."""
        self._last_result = result   # 버튼 클릭 시 GW id 목록을 뽑기 위해 보관해둠
        self.btn_show_heatmap.setEnabled(bool(result.gateways))

        pct = result.coverage_ratio * 100
        self.card_coverage.set_value(f"{pct:.1f}%", _color_for_pct(pct))
        self.card_gw_count.set_value(str(result.k))
        self.card_node_count.set_value(str(total_nodes))
        status = "목표 달성" if result.target_met else "목표 미달"
        self.card_status.set_value(status, GREEN if result.target_met else YELLOW)

        # 수신전력 구간별 분포: 막대 길이는 '연결된 단말 전체 대비 비율'임
        counts = pr_bin_counts(result.connections)
        connected = sum(counts)
        for row, count, (name, _, _) in zip(self._pr_rows, counts, PR_BINS):
            share = (count / connected) if connected else 0.0
            row.set_ratio(share, count)
            row.setToolTip(f"{name} dBm: {count}개 ({share * 100:.1f}%)")

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
        for row in self._pr_rows:
            row.set_ratio(0.0, 0)
        self.card_overlap.set_value("─")
        self.card_avg_per_gw.set_value("─")

    def show_error(self, message: str):
        self.btn_show_heatmap.setEnabled(False)
        self.card_status.set_value("오류", RED)