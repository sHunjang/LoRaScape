# lorascape/gui/widgets/map_widget.py
"""
PyQtGraph 기반 지도 위젯임. DEM 음영기복도를 배경 이미지로 깔고,
그 위에 GW(별 마커)/Node(원 마커, 커버 여부에 따라 색 다르게)를 뿌림.

folium 대신 이걸 쓰는 이유: 인터넷 없이도 완전히 오프라인으로 동작해야 하고
(현장 설치 위치가 하천변/공원이라 Wi-Fi 없을 수 있음), DEM 데이터를 이미 갖고
있으니 그걸 배경으로 활용하는 게 자연스러움 (README/설계문서 논의 참고).
"""
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor

from lorascape.data.dem_loader import DemLoader
from lorascape.data.coord_transform import latlon_to_xy
from lorascape.gui.widgets.hillshade import compute_hillshade
from lorascape.data.schema import GatewaySite, NodeSite

# 마커 색상임. 참고 디자인 팔레트(DARK/PANEL/TEXT 등)에서 그대로 가져온 색.
COLOR_GW = "#FFD700"          # GW는 노란 별
COLOR_NODE_COVERED = "#00C94A"   # 커버된 Node는 초록
COLOR_NODE_UNCOVERED = "#FF4444"  # 미커버 Node는 빨강
BG_DARK = "#181b22"


class MapWidget(QWidget):
    """
    DEM 음영기복도 + GW/Node 마커를 보여주는 지도 위젯임.
    좌표계는 위경도(EPSG:4326) 그대로 화면 x/y축으로 씀 (평면좌표로 안 바꾼 이유:
    화면 표시는 위경도 그대로가 직관적이고, 실제 거리 계산은 어차피 core 쪽에서
    coord_transform.py로 정확하게 하니까 화면 표시용으로는 위경도로 충분함).
    """

    # 사용자가 지도에서 GW/Node 마커를 클릭했을 때 발생하는 시그널임.
    # (gw_id 또는 node_id, 'gw' 또는 'node' 문자열)을 넘겨줌 - 상세창 여는 용도로 쓸 예정.
    sig_marker_clicked = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dem: DemLoader | None = None
        self._hillshade_item: pg.ImageItem | None = None
        self._gw_scatter: pg.ScatterPlotItem | None = None
        self._node_scatter: pg.ScatterPlotItem | None = None
        self._gw_lookup: dict = {}   # 화면상 인덱스 -> gw_id 매핑 (클릭 판정용)
        self._node_lookup: dict = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption("background", BG_DARK)
        pg.setConfigOption("foreground", "#a0a8be")

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True)  # 위경도 비율 왜곡 안 되게 고정
        self.plot_widget.setLabel("bottom", "경도")
        self.plot_widget.setLabel("left", "위도")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self.plot_widget)

        self._gw_scatter = pg.ScatterPlotItem(
            symbol="star", size=16, brush=pg.mkBrush(COLOR_GW), pen=pg.mkPen("#8a7000")
        )
        self._node_scatter = pg.ScatterPlotItem(symbol="o", size=8, pen=None)

        self.plot_widget.addItem(self._gw_scatter)
        self.plot_widget.addItem(self._node_scatter)

        self._gw_scatter.sigClicked.connect(self._on_gw_clicked)
        self._node_scatter.sigClicked.connect(self._on_node_clicked)

    def load_background(self, dem: DemLoader, lat_min: float, lat_max: float, lon_min: float, lon_max: float):
        """
        DEM 음영기복도를 배경으로 그림. 기존 배경 있으면 지우고 새로 그림.
        """
        self._dem = dem
        grid, extent = dem.read_elevation_grid(lat_min, lat_max, lon_min, lon_max)
        shaded = compute_hillshade(grid)

        if self._hillshade_item is not None:
            self.plot_widget.removeItem(self._hillshade_item)

        self._hillshade_item = pg.ImageItem(shaded.T)  # PyQtGraph는 (x, y) 축이 numpy와 반대라 전치 필요
        lon_min_e, lon_max_e, lat_min_e, lat_max_e = extent
        self._hillshade_item.setRect(
            lon_min_e, lat_min_e, lon_max_e - lon_min_e, lat_max_e - lat_min_e
        )
        self._hillshade_item.setZValue(-10)  # 마커보다 항상 아래에 그려지게 함
        self.plot_widget.addItem(self._hillshade_item)

    def set_gateways(self, gateways: list[GatewaySite]):
        """GW 목록을 지도에 별 마커로 표시함."""
        self._gw_lookup = {i: gw.gw_id for i, gw in enumerate(gateways)}
        if not gateways:
            self._gw_scatter.setData([])
            return
        spots = [{"pos": (gw.lon, gw.lat), "data": i} for i, gw in enumerate(gateways)]
        self._gw_scatter.setData(spots)

    def set_nodes(self, nodes: list[NodeSite], coverage: dict | None = None):
        """
        Node 목록을 지도에 원 마커로 표시함.
        coverage: {node_id: bool} 형태로 커버 여부를 넘기면 색이 초록/빨강으로 갈림.
                  안 넘기면 전부 회색으로 표시함 (아직 분석 전 상태).
        """
        self._node_lookup = {i: nd.node_id for i, nd in enumerate(nodes)}
        if not nodes:
            self._node_scatter.setData([])
            return

        spots = []
        for i, nd in enumerate(nodes):
            if coverage is None:
                color = "#7a8099"  # 분석 전에는 회색
            else:
                color = COLOR_NODE_COVERED if coverage.get(nd.node_id, False) else COLOR_NODE_UNCOVERED
            spots.append({
                "pos": (nd.lon, nd.lat), "data": i,
                "brush": pg.mkBrush(color), "pen": pg.mkPen(None),
            })
        self._node_scatter.setData(spots)

    def _on_gw_clicked(self, scatter, points):
        if not points:
            return
        idx = points[0].data()
        gw_id = self._gw_lookup.get(idx)
        if gw_id is not None:
            self.sig_marker_clicked.emit(gw_id, "gw")

    def _on_node_clicked(self, scatter, points):
        if not points:
            return
        idx = points[0].data()
        node_id = self._node_lookup.get(idx)
        if node_id is not None:
            self.sig_marker_clicked.emit(node_id, "node")

    def fit_to_data(self, gateways: list[GatewaySite], nodes: list[NodeSite]):
        """모든 GW/Node가 화면에 다 보이게 뷰 범위를 자동으로 맞춤."""
        all_lons = [g.lon for g in gateways] + [n.lon for n in nodes]
        all_lats = [g.lat for g in gateways] + [n.lat for n in nodes]
        if not all_lons:
            return
        margin_lon = (max(all_lons) - min(all_lons)) * 0.1 or 0.01
        margin_lat = (max(all_lats) - min(all_lats)) * 0.1 or 0.01
        self.plot_widget.setXRange(min(all_lons) - margin_lon, max(all_lons) + margin_lon)
        self.plot_widget.setYRange(min(all_lats) - margin_lat, max(all_lats) + margin_lat)