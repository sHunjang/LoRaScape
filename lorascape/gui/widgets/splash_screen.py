# lorascape/gui/widgets/splash_screen.py
"""
스플래시 스크린임. 원본 참고 파일 그대로 재사용 - 디자인을 바꾸면 안 되는 화면이라
로직 수정 없이 이미지 탐색 경로만 우리 프로젝트 구조에 맞게 조정함.

동작 모드:
- START 버튼 클릭 -> sig_start 발생 -> run_app.py가 데이터 검증/로딩 시작
- set_loading(True) 호출 시: 버튼 숨김, 진행바 표시
- update_progress(pct, msg): 진행바/상태 메시지 업데이트
- finish_loading(): 자동 페이드아웃 후 sig_start와 별개로 창을 닫음 (MainWindow 표시는
  호출부(run_app.py)가 담당함)
"""
from __future__ import annotations
import os
from PyQt5.QtWidgets import (
    QWidget, QApplication, QPushButton, QLabel, QProgressBar,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer,
)
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPen, QLinearGradient,
    QPixmap, QPainterPath,
)

APP_VERSION = "v1.0.0"
APP_NAME = "LoRaScape"
APP_SUBTITLE = "SmartCity LoRaWAN Network Simulator"
APP_COMPANY = "SOLUWINS"


def _draw_background(p: QPainter, w: int, h: int, assets_dir: str = ""):
    bg = QLinearGradient(0, 0, 0, h)
    bg.setColorAt(0.0, QColor("#0d1117"))
    bg.setColorAt(1.0, QColor("#161b27"))
    p.setBrush(bg)
    p.setPen(Qt.NoPen)
    p.drawRect(0, 0, w, h)

    p.setPen(QPen(QColor("#2a2f3b"), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(1, 1, w - 2, h - 2, 16, 16)

    MAP_X, MAP_Y = 40, 100
    MAP_W = w - 80
    MAP_H = h - 230

    p.setBrush(QColor("#0a1628"))
    p.setPen(QPen(QColor("#1e3050"), 1))
    p.drawRoundedRect(MAP_X, MAP_Y, MAP_W, MAP_H, 8, 8)

    _base = os.path.dirname(os.path.abspath(__file__))
    img_candidates = [
        os.path.join(assets_dir, 'world_map.png'),
        os.path.join(_base, '..', 'assets', 'world_map.png'),  # lorascape/gui/assets/world_map.png
        os.path.join(_base, 'world_map.png'),
    ]
    world_map_px = None
    for path in img_candidates:
        if os.path.exists(path):
            world_map_px = QPixmap(path)
            break

    if world_map_px and not world_map_px.isNull():
        scaled = world_map_px.scaled(
            MAP_W, MAP_H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
        )
        crop_x = (scaled.width() - MAP_W) // 2
        crop_y = (scaled.height() - MAP_H) // 2
        cropped = scaled.copy(crop_x, crop_y, MAP_W, MAP_H)

        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(MAP_X, MAP_Y, MAP_W, MAP_H, 8, 8)
        p.setClipPath(clip)
        p.drawPixmap(MAP_X, MAP_Y, cropped)
        p.restore()

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#2a4a6a"), 1))
        p.drawRoundedRect(MAP_X, MAP_Y, MAP_W, MAP_H, 8, 8)

    gw_points = [
        (0.55, 0.25), (0.62, 0.30), (0.20, 0.18),
        (0.72, 0.55), (0.45, 0.48), (0.15, 0.52),
    ]
    for rx, ry in gw_points:
        cx = MAP_X + int(MAP_W * rx)
        cy = MAP_Y + int(MAP_H * ry)
        for radius, alpha in [(20, 18), (13, 45), (6, 110)]:
            c = QColor("#4f8ef7")
            c.setAlpha(alpha)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        p.setBrush(QColor("#7ab8e8"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - 3, cy - 3, 6, 6)

    pts_px = [(MAP_X + int(MAP_W * rx), MAP_Y + int(MAP_H * ry)) for rx, ry in gw_points]
    p.setPen(QPen(QColor(79, 142, 247, 35), 1))
    for i in range(len(pts_px)):
        for j in range(i + 1, len(pts_px)):
            p.drawLine(pts_px[i][0], pts_px[i][1], pts_px[j][0], pts_px[j][1])

    p.setRenderHint(QPainter.TextAntialiasing)

    p.setPen(QColor("#a0b4cc"))
    p.setFont(QFont("Segoe UI", 17, QFont.Normal))
    p.drawText(0, 18, w, 34, Qt.AlignHCenter, APP_SUBTITLE)

    p.setFont(QFont("Segoe UI", 24, QFont.Bold))
    grad_text = QLinearGradient(w // 2 - 120, 52, w // 2 + 120, 78)
    grad_text.setColorAt(0.0, QColor("#4f8ef7"))
    grad_text.setColorAt(1.0, QColor("#7ab8e8"))
    p.setPen(QPen(grad_text, 0))
    p.drawText(0, 52, w, 42, Qt.AlignHCenter, APP_NAME)

    p.setFont(QFont("Segoe UI", 9, QFont.Normal))
    p.setPen(QColor("#4a5580"))
    p.drawText(14, 8, 100, 18, Qt.AlignLeft | Qt.AlignVCenter, APP_VERSION)

    LOGO_Y = h - 30
    icon_x = w - 160
    icon_y = LOGO_Y - 10

    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1a6fc4"))
    p.drawRoundedRect(icon_x, icon_y, 14, 14, 2, 2)
    p.setBrush(QColor("#4f8ef7"))
    p.drawRoundedRect(icon_x + 16, icon_y + 6, 10, 10, 2, 2)
    p.setBrush(QColor("#FFD700"))
    p.drawRoundedRect(icon_x + 16, icon_y, 10, 5, 1, 1)
    p.setFont(QFont("Segoe UI", 13, QFont.Bold))
    p.setPen(QColor("#e0e4ef"))
    p.drawText(icon_x + 30, LOGO_Y - 12, 120, 22, Qt.AlignLeft | Qt.AlignVCenter, APP_COMPANY)


class SplashScreen(QWidget):
    sig_start = pyqtSignal()

    def __init__(self, assets_dir: str = ""):
        super().__init__()
        self._assets_dir = assets_dir
        self._loading = False
        self._auto_close = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(900, 580)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

        self._build()

        self.setWindowOpacity(0.0)
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(600)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.start()

    def _build(self):
        W, H = 900, 580
        MAP_Y = 100
        MAP_H = H - 230
        BTN_Y = MAP_Y + MAP_H + 14

        self.btn_start = QPushButton("▶  START", self)
        self.btn_start.setFixedSize(200, 48)
        self.btn_start.move((W - 200) // 2, BTN_Y)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a4fa0, stop:1 #2a7a5a);
                color: #e0e4ef; border: 1px solid #4f8ef7; border-radius: 24px;
                font-size: 15px; font-weight: bold; font-family: 'Segoe UI'; letter-spacing: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2a6fd0, stop:1 #3aaa7a);
                border-color: #7ab8e8;
            }
            QPushButton:pressed { background: #1a3060; }
            QPushButton:disabled { background: #1a2030; color: #3a4060; border-color: #2a2f3b; }
        """)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start)

        self.lbl_hint = QLabel("Click START to launch the simulator", self)
        self.lbl_hint.setFixedWidth(W)
        self.lbl_hint.move(0, BTN_Y + 56)
        self.lbl_hint.setAlignment(Qt.AlignHCenter)
        self.lbl_hint.setStyleSheet(
            "color:#3a4565;font-size:10px;font-family:'Segoe UI';background:transparent;")

        self.prog = QProgressBar(self)
        self.prog.setFixedSize(W - 80, 6)
        self.prog.move(40, BTN_Y + 4)
        self.prog.setRange(0, 100)
        self.prog.setValue(0)
        self.prog.setTextVisible(False)
        self.prog.setStyleSheet("""
            QProgressBar { background: #1a1e2a; border: none; border-radius: 3px; }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a4fa0, stop:1 #4f8ef7);
                border-radius: 3px;
            }
        """)
        self.prog.hide()

        self.lbl_status = QLabel("", self)
        self.lbl_status.setFixedWidth(W)
        self.lbl_status.move(0, BTN_Y + 16)
        self.lbl_status.setAlignment(Qt.AlignHCenter)
        self.lbl_status.setStyleSheet(
            "color:#5a6a8a;font-size:10px;font-family:'Segoe UI';background:transparent;")
        self.lbl_status.hide()

        self.lbl_pct = QLabel("", self)
        self.lbl_pct.setFixedWidth(W)
        self.lbl_pct.move(0, BTN_Y + 30)
        self.lbl_pct.setAlignment(Qt.AlignHCenter)
        self.lbl_pct.setStyleSheet(
            "color:#3a4a6a;font-size:9px;font-family:'Segoe UI';background:transparent;")
        self.lbl_pct.hide()

    def set_loading(self, loading: bool):
        self._loading = loading
        if loading:
            self.btn_start.hide()
            self.lbl_hint.hide()
            self.prog.show()
            self.lbl_status.show()
            self.lbl_pct.show()
        else:
            self.btn_start.show()
            self.lbl_hint.show()
            self.prog.hide()
            self.lbl_status.hide()
            self.lbl_pct.hide()

    def update_progress(self, pct: int, msg: str = ""):
        self.prog.setValue(max(0, min(100, pct)))
        if msg:
            self.lbl_status.setText(msg)
        self.lbl_pct.setText(f"{pct}%")
        QApplication.processEvents()

    def finish_loading(self, delay_ms: int = 500):
        self.update_progress(100, "준비 완료")
        self._auto_close = True
        QTimer.singleShot(delay_ms, self._fade_out)

    def _on_start(self):
        self.btn_start.setEnabled(False)
        self.set_loading(True)
        self.update_progress(0, "초기화 중...")
        self.sig_start.emit()

    def _fade_out(self):
        self._anim_out = QPropertyAnimation(self, b"windowOpacity")
        self._anim_out.setDuration(400)
        self._anim_out.setStartValue(1.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim_out.finished.connect(self.close)
        self._anim_out.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        _draw_background(p, self.width(), self.height(), self._assets_dir)
        p.end()