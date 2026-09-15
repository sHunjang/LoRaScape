# lorascape/gui/widgets/map_widget.py
"""
Folium 기반 지도 위젯임 (QWebEngineView 안에 Leaflet 지도를 그림).
실제 레이어 조립 로직은 map_layers.py로, JS 브릿지는 map_bridge.py로 뺐음 -
이 파일은 Qt 위젯 껍데기(로딩 오버레이, 이벤트 연결, refresh 호출 순서)만 담당함.
"""
import tempfile
import folium
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal

from lorascape.gui.widgets.map_bridge import MapBridge, webchannel_init_script, map_event_script
from lorascape.gui.widgets import map_layers as layers



class MapWidget(QWidget):
    """Folium 기반 지도 위젯임."""
    sig_map_clicked       = pyqtSignal(float, float)
    sig_map_right_clicked = pyqtSignal(float, float)
    sig_gw_dragged        = pyqtSignal(str, float, float)
    sig_nd_dragged        = pyqtSignal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bounds = (126.0, 34.0, 130.0, 38.5)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView()
        lay.addWidget(self.view)

        self.channel = QWebChannel()
        self.bridge  = MapBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.bridge.clicked.connect(self.sig_map_clicked)
        self.bridge.right_clicked.connect(self.sig_map_right_clicked)
        self.bridge.gw_dragged.connect(self.sig_gw_dragged)
        self.bridge.nd_dragged.connect(self.sig_nd_dragged)

        self._loading_overlay = QWidget(self)
        self._loading_overlay.setStyleSheet("background: rgba(15, 17, 23, 160);")
        self._loading_overlay.hide()
        self._loading_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)

        ov_lay = QVBoxLayout(self._loading_overlay)
        ov_lay.setAlignment(Qt.AlignCenter)

        self._spinner_lbl = QLabel()
        self._spinner_lbl.setAlignment(Qt.AlignCenter)
        self._spinner_lbl.setFixedSize(64, 64)
        ov_lay.addWidget(self._spinner_lbl, alignment=Qt.AlignCenter)

        self._loading_text = QLabel("히트맵 계산 중...")
        self._loading_text.setAlignment(Qt.AlignCenter)
        self._loading_text.setStyleSheet(
            "color:#e0e4ef; font-size:13px; font-weight:bold; padding-top:12px; background:transparent;")
        ov_lay.addWidget(self._loading_text)

        self._spinner_angle = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._rotate_spinner)
        self._spinner_timer.setInterval(40)

        self.refresh()

    def _rotate_spinner(self):
        self._spinner_angle = (self._spinner_angle + 12) % 360
        self._draw_spinner()

    def _draw_spinner(self):
        from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#4f8ef7"))
        pen.setWidth(5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.translate(32, 32)
        p.rotate(self._spinner_angle)
        p.drawArc(-24, -24, 48, 48, 0, 270 * 16)
        p.end()
        self._spinner_lbl.setPixmap(pix)

    def show_loading(self, text="히트맵 계산 중..."):
        self._loading_text.setText(text)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        self._spinner_timer.start()

    def update_loading_text(self, text: str):
        if self._loading_overlay.isVisible():
            self._loading_text.setText(text)

    def hide_loading(self):
        self._loading_overlay.hide()
        self._spinner_timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    def set_bounds(self, bounds):
        """bounds: (lon_min, lat_min, lon_max, lat_max) - EPSG:4326"""
        self._bounds = bounds

    def refresh(self, gws=None, nodes=None, result=None,
                heatmaps=None, selected_gws=None, map_tile=None,
                measure_pts=None, field_data=None, settings=None):
        """
        지도를 새로 렌더링함. 실제 레이어 조립은 map_layers.py의 함수들이 담당하고,
        여기선 folium.Map 생성 -> 레이어 순서대로 추가 -> JS 브릿지 삽입 -> 렌더링만 함.
        """
        s = settings or {}
        hm_opacity  = float(s.get("heatmap_opacity",  0.65))
        cov_opacity = float(s.get("coverage_opacity", 0.40))

        b = self._bounds
        center = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
        span = max(b[2] - b[0], b[3] - b[1])
        zoom = 14 if span < 0.1 else 12 if span < 0.5 else 10 if span < 2.0 else 8
        tile = map_tile or "CartoDB Voyager"

        m = folium.Map(location=center, zoom_start=zoom, tiles=tile, prefer_canvas=True)
        gw_color_map = layers.build_gw_color_map(gws)

        layers.add_measure_layer(m, measure_pts)
        layers.add_heatmap_layers(m, heatmaps, hm_opacity)
        layers.add_coverage_layers(m, nodes, result, selected_gws, cov_opacity)
        layers.add_node_marker_layer(m, nodes, result, gw_color_map, selected_gws)
        layers.add_gw_marker_layer(m, gws, result, gw_color_map)
        layers.add_field_data_layer(m, field_data)

        folium.LayerControl(collapsed=False).add_to(m)

        map_name = m.get_name()
        m.get_root().html.add_child(folium.Element(webchannel_init_script()))
        m.get_root().script.add_child(folium.Element(map_event_script(map_name)))

        tmp = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
        m.save(tmp.name)
        self.view.setUrl(QUrl.fromLocalFile(tmp.name))