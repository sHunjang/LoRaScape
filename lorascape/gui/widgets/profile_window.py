# lorascape/gui/widgets/profile_window.py
"""
GW <-> Node 지형 단면도 창임. 원본 참고 파일(profile_window.py)의 시각화 방식을
그대로 가져오되, 지형 데이터는 core.data.dem_loader.get_elevation_profile을 쓰고
Fresnel 반경/LOS 판정은 core.diffraction.deygout의 함수들을 재사용함
(계산 로직 중복 없이, 이미 검증된 core 함수 그대로 활용).
"""
from __future__ import annotations
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSizePolicy,
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

import matplotlib.font_manager as fm
def _set_korean_font():
    candidates = ['Malgun Gothic', 'NanumGothic', 'AppleGothic', 'NotoSansCJK']
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams['font.family'] = name
            return
    matplotlib.rcParams['font.family'] = 'DejaVu Sans'
_set_korean_font()

from lorascape.gui.widgets.dialogs import DARK, PANEL, TEXT, MUTED, BORDER, STYLE_DLG
from lorascape.core.diffraction.deygout import fresnel_v

STYLE = STYLE_DLG + f"""
QComboBox {{
    background:{PANEL}; color:{TEXT};
    border:1px solid {BORDER}; border-radius:4px;
    padding:4px 8px; min-height:26px; min-width:120px;
}}
QComboBox QAbstractItemView {{
    background:{PANEL}; color:{TEXT};
    selection-background-color:#253a5a;
}}
"""


def _fresnel_radius(d1, d2, fc_mhz):
    """1차 Fresnel 반경(m)임. core.diffraction.deygout에는 v값 계산만 있어서,
    화면에 존 자체를 그리려면 반경이 필요해 여기서 별도로 구함."""
    lam = 3e8 / (fc_mhz * 1e6)
    d1c = np.clip(d1, 1e-3, None)
    d2c = np.clip(d2, 1e-3, None)
    return np.sqrt(lam * d1c * d2c / (d1c + d2c))


class ProfileWindow(QDialog):
    """GW <-> Node 지형 단면도임."""

    def __init__(self, gateways: list, nodes: list, dem, fc_mhz: float = 920.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("지형 단면도 (Profile)")
        self.setStyleSheet(STYLE)
        self.resize(860, 560)
        self.setWindowFlag(Qt.Window)

        self.gateways = gateways
        self.nodes = nodes
        self.dem = dem
        self.fc = fc_mhz
        self._build()
        if gateways and nodes:
            self._draw()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("GW:"))
        self.cb_gw = QComboBox()
        for g in self.gateways:
            self.cb_gw.addItem(g.gw_id)
        ctrl.addWidget(self.cb_gw)

        ctrl.addWidget(QLabel("  →  Node:"))
        self.cb_nd = QComboBox()
        for n in self.nodes:
            self.cb_nd.addItem(n.node_id)
        ctrl.addWidget(self.cb_nd)

        self.cb_gw.currentIndexChanged.connect(self._draw)
        self.cb_nd.currentIndexChanged.connect(self._draw)

        btn_draw = QPushButton("단면도 그리기")
        btn_draw.setStyleSheet(
            f"QPushButton{{background:#1c3a5a;color:#7ab8e8;"
            f"border:1px solid #2a5a8a;border-radius:4px;"
            f"padding:5px 14px;font-size:11px;}}"
            f"QPushButton:hover{{background:#254d78;}}"
        )
        btn_draw.clicked.connect(self._draw)
        ctrl.addWidget(btn_draw)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.fig = Figure(figsize=(10, 5), dpi=96, facecolor='#1c1f26')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#252930')
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.canvas)

        self.lbl = QLabel("")
        self.lbl.setStyleSheet(
            "font-size:11px;padding:4px 6px;"
            "background:#1e2130;border:1px solid #2a2f3b;border-radius:6px;"
        )
        self.lbl.setTextFormat(Qt.RichText)
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)

    def set_data(self, gateways: list, nodes: list, dem=None):
        """외부(main_window)에서 데이터가 갱신됐을 때 호출함."""
        self.gateways = gateways
        self.nodes = nodes
        if dem is not None:
            self.dem = dem

        cur_gw = self.cb_gw.currentText()
        cur_nd = self.cb_nd.currentText()
        self.cb_gw.clear()
        self.cb_nd.clear()
        for g in gateways:
            self.cb_gw.addItem(g.gw_id)
        for n in nodes:
            self.cb_nd.addItem(n.node_id)
        gi = self.cb_gw.findText(cur_gw)
        ni = self.cb_nd.findText(cur_nd)
        if gi >= 0:
            self.cb_gw.setCurrentIndex(gi)
        if ni >= 0:
            self.cb_nd.setCurrentIndex(ni)
        if gateways and nodes:
            self._draw()

    def _draw(self):
        gi = self.cb_gw.currentIndex()
        ni = self.cb_nd.currentIndex()
        if gi < 0 or ni < 0 or gi >= len(self.gateways) or ni >= len(self.nodes):
            return
        gw = self.gateways[gi]
        nd = self.nodes[ni]
        self._plot(gw, nd)

    def _plot(self, gw, nd):
        self.ax.cla()
        self.ax.set_facecolor('#252930')
        self.fig.patch.set_facecolor('#1c1f26')

        n_samples = 100
        profile = self.dem.get_elevation_profile(gw.lat, gw.lon, nd.lat, nd.lon, n_samples)
        dists = np.array([p[0] for p in profile])
        elevs = np.array([p[1] for p in profile])
        d_total = dists[-1]

        if d_total < 1:
            self.lbl.setText("GW와 Node가 너무 가깝습니다.")
            return

        gw_elev = elevs[0] + gw.antenna_height_m
        nd_elev = elevs[-1] + nd.antenna_height_m
        los_line = gw_elev + (nd_elev - gw_elev) * (dists / d_total)

        d1 = dists
        d2 = d_total - dists
        fres = _fresnel_radius(d1, d2, self.fc)

        h_eff = elevs - los_line  # 양수면 지형이 LOS 위로 튀어나온 것 (deygout.py와 동일한 부호 규약)
        blocked = h_eff > -0.01

        dist_km = dists / 1000

        self.ax.fill_between(dist_km, 0, elevs, color='#3a4a2a', alpha=0.85, linewidth=0, zorder=2, label='지형')
        self.ax.plot(dist_km, elevs, color='#6a9a4a', linewidth=1.2, zorder=3)

        fres_upper = los_line + fres
        fres_lower = los_line - fres
        self.ax.fill_between(dist_km, fres_lower, fres_upper, color='#4f8ef7', alpha=0.12, zorder=1, label='Fresnel 1존')
        self.ax.plot(dist_km, fres_upper, color='#4f8ef7', linewidth=0.6, linestyle='--', alpha=0.5, zorder=1)
        self.ax.plot(dist_km, fres_lower, color='#4f8ef7', linewidth=0.6, linestyle='--', alpha=0.5, zorder=1)

        self.ax.plot(dist_km, los_line, color='#00C94A', linewidth=1.5, zorder=4, label='시선(LOS)')

        if blocked.any():
            self.ax.fill_between(dist_km, los_line, elevs, where=blocked, color='#FF4444', alpha=0.5, zorder=5, label='LOS 차단')
            self.ax.plot(dist_km[blocked], elevs[blocked], color='#FF4444', linewidth=2.0, zorder=6)

        fresnel_violated = (elevs > fres_lower) & ~blocked
        if fresnel_violated.any():
            self.ax.fill_between(dist_km, fres_lower, elevs, where=fresnel_violated, color='#FF8C00', alpha=0.35, zorder=4, label='Fresnel 침범')

        self.ax.plot(0, gw_elev, marker='^', color='#FFD700', markersize=10, zorder=7)
        self.ax.plot(dist_km[-1], nd_elev, marker='o', color='#FF69B4', markersize=9, zorder=7)

        self.ax.annotate(
            f'{gw.gw_id}\n({gw_elev:.0f}m)', xy=(0, gw_elev),
            xytext=(dist_km[-1] * 0.03, gw_elev + fres.max() * 0.3),
            color='#FFD700', fontsize=9, arrowprops=dict(arrowstyle='->', color='#FFD700', lw=0.8),
        )
        self.ax.annotate(
            f'{nd.node_id}\n({nd_elev:.0f}m)', xy=(dist_km[-1], nd_elev),
            xytext=(dist_km[-1] * 0.88, nd_elev + fres.max() * 0.3),
            color='#FF69B4', fontsize=9, arrowprops=dict(arrowstyle='->', color='#FF69B4', lw=0.8),
        )

        self.ax.set_xlabel('거리 (km)', color='#a0a8be', fontsize=10)
        self.ax.set_ylabel('고도 (m)', color='#a0a8be', fontsize=10)
        self.ax.tick_params(colors='#a0a8be', labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#2a2f3b')
        self.ax.grid(True, color='#2a2f3b', linestyle='--', alpha=0.5, linewidth=0.5)
        self.ax.legend(loc='upper right', fontsize=8, facecolor='#1e2130', edgecolor='#2a2f3b', labelcolor='#a0a8be')

        los_ok = not blocked.any()
        n_block = int(blocked.sum())
        max_pen = float(np.max(elevs - fres_lower)) if fresnel_violated.any() else 0
        fres_ok = max_pen <= 0

        if los_ok:
            los_color, los_text, los_bg = '#00C94A', '✓ LOS', '#0d2010'
        else:
            los_color, los_text, los_bg = '#FF4444', f'✗ NLOS ({n_block}개 지점 차단)', '#200d0d'

        fres_color = '#00C94A' if fres_ok else '#FF8C00'
        fres_text = '✓ Fresnel OK' if fres_ok else f'△ Fresnel 침범 {max_pen:.1f}m'

        badge_html = (
            f'<span style="background:{los_bg};color:{los_color};'
            f'border:1px solid {los_color};border-radius:4px;'
            f'padding:2px 8px;font-weight:bold;font-size:12px;">{los_text}</span>'
            f'&nbsp;&nbsp;<span style="color:{fres_color};font-size:11px;">{fres_text}</span>'
            f'&nbsp;&nbsp;<span style="color:#7a8099;font-size:11px;">'
            f'거리: {d_total/1000:.2f}km | GW: {elevs[0]:.0f}m+{gw.antenna_height_m:.0f}m | '
            f'Node: {elevs[-1]:.0f}m+{nd.antenna_height_m:.0f}m</span>'
        )
        self.lbl.setText(badge_html)

        self.canvas.draw()