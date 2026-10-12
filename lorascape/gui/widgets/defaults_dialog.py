# lorascape/gui/widgets/defaults_dialog.py
"""
장비 기본값 편집 창임. 프로젝트의 'GW 기본값 / 단말 기본값'을 보고 바꿈.
기본값은 '값을 직접 입력하지 않은 장비'에만 적용됨 - 이미 값을 입력해 둔 장비는 그대로 두고,
화면에 "기본값을 쓰는 장비 N/M개"를 같이 보여줘서 바꾸면 몇 개에 영향이 가는지 알 수 있게 함.
저장은 이 창이 하지 않음 - 바뀐 값만 sig_defaults_applied로 내보내고, 호출한 쪽(MainWindow)이 DB에 반영함.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QDoubleSpinBox, QPushButton, QGroupBox, QLabel,
)
from PyQt5.QtCore import pyqtSignal

from lorascape.gui.widgets.settings_window import STYLE, MUTED

KIND_TITLES = {"gateway": "GW(게이트웨이) 기본값", "node": "단말 기본값"}

# 파라미터별 표시 정보: (라벨, 단위, 최솟값, 최댓값, 소수 자릿수)
PARAM_UI = {
    "antenna_height_m": ("안테나 높이 (지면 위)", " m", 0.05, 300.0, 2),
    "tx_power_dbm": ("송신 출력", " dBm", -10.0, 40.0, 1),
    "antenna_gain_dbi": ("안테나 이득", " dBi", -20.0, 40.0, 1),
    "cable_loss_db": ("케이블 손실", " dB", 0.0, 30.0, 1),
    "min_rx_dbm": ("최소 수신 레벨", " dBm", -160.0, 0.0, 1),
    "indoor_loss_db": ("실내 투과 손실", " dB", 0.0, 80.0, 1),
}


class DefaultsDialog(QDialog):
    """
    current: {종류: {파라미터: 현재 프로젝트 기본값}}
    factory: {종류: {파라미터: 공장 기본값}}   ('공장 기본값 복원' 버튼용)
    usage:   {종류: {"total": 장비 수, "params": {파라미터: {"explicit": n, "default": m}}}}
    """
    sig_defaults_applied = pyqtSignal(dict)    # {종류: {파라미터: 새 값}} - 바뀐 것만

    def __init__(self, current: dict, factory: dict, usage: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("장비 기본값")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(460)
        self._current = current
        self._factory = factory
        self.spins: dict = {}
        self._build(usage)

    def _build(self, usage: dict):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        note = QLabel(
            "장비에 성능 값을 직접 입력하지 않으면 여기 기본값이 쓰입니다. 모르는 값은 기본값으로 두고, "
            "아는 장비만 목록창에서 직접 입력하세요. 값을 직접 입력한 장비는 기본값을 바꿔도 영향받지 않습니다."
        )
        note.setStyleSheet(f"color:{MUTED};font-size:10px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        for kind in ("gateway", "node"):
            if kind not in self._current:
                continue
            grp = QGroupBox(KIND_TITLES.get(kind, kind))
            form = QFormLayout(grp)
            form.setSpacing(8)
            info = usage.get(kind, {})
            total = info.get("total", 0)
            for param, value in self._current[kind].items():
                label, suffix, lo, hi, dec = PARAM_UI.get(param, (param, "", -1e6, 1e6, 2))
                spin = QDoubleSpinBox()
                spin.setRange(lo, hi)
                spin.setDecimals(dec)
                spin.setSuffix(suffix)
                spin.setValue(value)
                self.spins[(kind, param)] = spin
                row = QHBoxLayout()
                row.addWidget(spin, 1)
                p = info.get("params", {}).get(param)
                if p is not None and total:
                    use = QLabel(f"기본값 사용 {p['default']}/{total}개")
                    use.setStyleSheet(f"color:{MUTED};font-size:10px;")
                    row.addWidget(use)
                form.addRow(label, row)
            lay.addWidget(grp)

        btns = QHBoxLayout()
        btn_reset = QPushButton("공장 기본값 복원")
        btn_reset.clicked.connect(self._reset_to_factory)
        btn_cancel = QPushButton("취소")
        btn_cancel.setProperty("role", "cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("적용")
        btn_ok.setProperty("role", "ok")
        btn_ok.clicked.connect(self._accept)
        btns.addWidget(btn_reset)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def _reset_to_factory(self):
        for (kind, param), spin in self.spins.items():
            spin.setValue(self._factory.get(kind, {}).get(param, spin.value()))

    def changes(self) -> dict:
        """지금 화면 값 중 현재 프로젝트 기본값과 다른 것만 모음."""
        out: dict = {}
        for (kind, param), spin in self.spins.items():
            if abs(spin.value() - self._current[kind][param]) > 1e-9:
                out.setdefault(kind, {})[param] = spin.value()
        return out

    def _accept(self):
        changes = self.changes()
        if changes:
            self.sig_defaults_applied.emit(changes)
        self.accept()
