# lorascape/gui/widgets/result_panel.py
"""
커버리지/최적화 결과 요약 패널임.

★ 지금은 1차 버전임 - 원본 참고 파일(result_panel.py, 524줄)은 SF별 색상분포,
진행바, 스크롤 영역까지 갖춘 상세 버전인데, 오늘은 뼈대(카드 몇 개)만 만들고
디테일은 다음 단계에서 원본과 동일하게 맞춰나갈 예정임.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"
GREEN = "#00C94A"
YELLOW = "#FFD700"
RED = "#FF4444"


def _color_for_pct(pct: float) -> str:
    if pct >= 90:
        return GREEN
    if pct >= 70:
        return YELLOW
    return RED


class StatCard(QFrame):
    """제목 + 값 하나를 보여주는 작은 카드임. 원본의 StatCard와 스타일 맞춤."""

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


class ResultPanel(QWidget):
    """커버리지 분석 결과 요약 패널임."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{DARK};")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("분석 결과")
        title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:bold;")
        layout.addWidget(title)

        self.card_coverage = StatCard("전체 커버리지")
        self.card_gw_count = StatCard("사용 GW 수")
        self.card_node_count = StatCard("총 Node 수")
        self.card_status = StatCard("상태", "대기 중")

        for card in (self.card_coverage, self.card_gw_count, self.card_node_count, self.card_status):
            layout.addWidget(card)

        layout.addStretch()

    def show_result(self, result, total_nodes: int):
        """OptimizationResult를 받아서 카드들을 갱신함."""
        pct = result.coverage_ratio * 100
        self.card_coverage.set_value(f"{pct:.1f}%", _color_for_pct(pct))
        self.card_gw_count.set_value(str(result.k))
        self.card_node_count.set_value(str(total_nodes))
        status = "목표 달성" if result.target_met else "목표 미달"
        self.card_status.set_value(status, GREEN if result.target_met else YELLOW)

    def show_loading(self):
        self.card_status.set_value("계산 중...", MUTED)

    def show_error(self, message: str):
        self.card_status.set_value("오류", RED)