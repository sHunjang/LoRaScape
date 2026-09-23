# lorascape/gui/main_window.py
"""
메인 윈도우임. 툴바 + QSplitter(지도/결과패널) + 상태바 구조.
core.optimization.gw_placement / data.* 를 직접 씀 (별도 어댑터 레이어 없음).
"""
from PyQt5.QtWidgets import (
    QMainWindow, QToolBar, QAction, QSplitter, QStatusBar, QLabel,
    QFileDialog, QMessageBox, QMenu, QApplication,
)
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QCursor

from lorascape.gui.widgets.map_widget import MapWidget
from lorascape.gui.widgets.result_panel import ResultPanel
from lorascape.gui.workers import LoadDataWorker, OptimizeWorker, HeatmapWorker, SuggestAdditionalGWWorker, SuggestGreenfieldGWWorker

from lorascape.gui.app_config import load_config


DARK = "#181b22"
PANEL = "#1e2130"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"

TOOLBAR_STYLE = f"""
QToolBar {{ background:{DARK}; border:none; border-bottom:1px solid {BORDER}; spacing:4px; padding:4px; }}
QToolButton {{ color:{TEXT}; background:#253a5a; border:1px solid #3a5a8a; border-radius:5px; padding:5px 10px; }}
QToolButton:hover {{ background:#2e4a7a; }}
"""

# ★ QMessageBox는 기본적으로 앱 스타일시트를 상속 안 받아서, 텍스트 색만 밝은 색이
# 적용되고 배경은 시스템 기본(밝은 색)이라 글자가 안 보이는 문제가 있었음.
# 그래서 QMessageBox를 쓸 때마다 이 스타일을 명시적으로 적용해야 함.
MESSAGEBOX_STYLE = f"""
QMessageBox {{ background:{DARK}; }}
QMessageBox QLabel {{ color:{TEXT}; font-size:12px; }}
QMessageBox QPushButton {{
    background:#253a5a; color:{TEXT};
    border:1px solid #3a5a8a; border-radius:5px;
    padding:6px 18px; font-size:12px; min-width:60px;
}}
QMessageBox QPushButton:hover {{ background:#2e4a7a; }}
"""

CONTEXT_MENU_STYLE = f"""
QMenu {{ background:{PANEL}; color:{TEXT}; border:1px solid {BORDER}; padding:4px; }}
QMenu::item {{ padding:6px 20px; border-radius:4px; }}
QMenu::item:selected {{ background:#253a5a; }}
QMenu::separator {{ height:1px; background:{BORDER}; margin:4px 8px; }}
"""


def _styled_message_box(parent, icon, title, text) -> QMessageBox:
    """다크 스타일이 적용된 QMessageBox를 만들어서 반환함. 호출부는 .exec_()만 부르면 됨."""
    box = QMessageBox(icon, title, text, QMessageBox.Ok, parent)
    box.setStyleSheet(MESSAGEBOX_STYLE)
    return box


class MainWindow(QMainWindow):
    def __init__(self, xlsx_path: str = None, dem_path: str = None):
        super().__init__()
        self.setWindowTitle("LoRaScape")
        self.resize(1400, 900)
        self.setStyleSheet(f"background:{DARK};")

        self.xlsx_path = xlsx_path
        self.dem_path = dem_path

        self.gateways: list = []
        self.nodes: list = []
        self.last_result = None

        self._gw_list_win = None
        self._node_list_win = None

        self._thread: QThread | None = None
        self._worker = None
        self._thread_active = False  # QThread deleteLater 이후에도 안전하게 실행중 여부를 판단하는 플래그

        self._settings = load_config()

        self._distance_win = None

        self._profile_win = None

        self._settings_win = None

        self._measuring = False
        self._measure_points: list = []  # [(lon, lat), ...]


        self._build_ui()

        if self.dem_path:
            self._init_map_bounds_from_dem()

        if self.xlsx_path:
            # ★ 앱 시작 시점의 자동 로딩은 "사용자가 직접 요청한 조작"이 아니라
            # "이전 세션에서 기억해둔 값을 다시 시도해보는 것"이라, 실패해도
            # 팝업으로 방해하지 않고 상태바에만 조용히 표시함.
            self._load_data(silent=True)

    def _build_ui(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(TOOLBAR_STYLE)
        self.addToolBar(Qt.TopToolBarArea, tb)

        act_gw_list = QAction("GW 목록", self)
        act_node_list = QAction("단말 목록", self)
        act_optimize = QAction("GW 배치 검증 및 보강", self)
        act_suggest_add = QAction("추가 설치 위치 제안", self)
        act_suggest_greenfield = QAction("신규 GW 배치 추천", self)
        act_distance = QAction("거리 분석", self)
        act_profile = QAction("단면도", self)
        act_settings = QAction("설정", self)

        act_gw_list.triggered.connect(self._open_gw_list)
        act_node_list.triggered.connect(self._open_node_list)
        act_optimize.triggered.connect(self._on_optimize_clicked)
        act_suggest_add.triggered.connect(self._on_suggest_additional_clicked)
        act_suggest_greenfield.triggered.connect(self._on_suggest_greenfield_clicked)
        act_distance.triggered.connect(self._open_distance_window)
        act_profile.triggered.connect(self._open_profile_window)
        act_settings.triggered.connect(self._open_settings)

        tb.addAction(act_gw_list)
        tb.addAction(act_node_list)
        tb.addAction(act_optimize)
        tb.addAction(act_suggest_add)
        tb.addAction(act_suggest_greenfield)
        tb.addAction(act_distance)
        tb.addAction(act_settings)
        tb.addAction(act_profile)

        splitter = QSplitter(Qt.Horizontal)
        self.map_widget = MapWidget()
        self.result_panel = ResultPanel()
        self.result_panel.btn_show_heatmap.clicked.connect(self._on_show_result_heatmap_clicked)
        self.result_panel.setMaximumWidth(260)
        self.result_panel.setMinimumWidth(220)

        splitter.addWidget(self.map_widget)
        splitter.addWidget(self.result_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1140, 260])
        splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};width:2px;}}")
        self.setCentralWidget(splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("데이터를 불러와주세요.")
        self.status_label.setStyleSheet(f"color:{MUTED};font-size:12px;padding:4px 12px;")
        self.status.addPermanentWidget(self.status_label)

        self.map_widget.sig_map_clicked.connect(self._on_map_clicked)
        self.map_widget.sig_gw_dragged.connect(self._on_gw_dragged)
        self.map_widget.sig_nd_dragged.connect(self._on_node_dragged)
        self.map_widget.sig_map_right_clicked.connect(self._on_map_right_clicked)
        

    # ── 목록 창 ──────────────────────────────────────────────

    def _ensure_gw_list_win(self):
        from lorascape.gui.widgets.gw_list_window import GWListWindow
        if self._gw_list_win is None:
            self._gw_list_win = GWListWindow(self.gateways, parent=self)
            self._gw_list_win.sig_gws_changed.connect(self._on_gws_changed_from_list)
            self._gw_list_win.sig_load_excel_requested.connect(
                lambda path: self._on_excel_load_requested(path, target="gw")
            )
            self._gw_list_win.sig_selected_coverage_requested.connect(self._on_selected_coverage_requested)
        else:
            self._gw_list_win.set_gateways(self.gateways)
        return self._gw_list_win


    def _on_selected_coverage_requested(self, gw_ids: list):
        if not gw_ids:
            self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
            self.status_label.setText("전체 GW 표시로 복귀")
            return

        if not self.dem_path:
            _styled_message_box(self, QMessageBox.Warning, "알림", "DEM 파일 경로가 설정되지 않았습니다.").exec_()
            return

        selected_gateways = [gw for gw in self.gateways if gw.gw_id in gw_ids]

        self.map_widget.show_loading("커버리지 히트맵 계산 중...")
        self.status_label.setText(f"선택된 GW {len(gw_ids)}개 히트맵 계산 중...")

        worker = HeatmapWorker(
            selected_gateways, self.nodes, self.dem_path,  # ★ self.nodes 추가 전달
            grid_size=self._settings.get("heatmap_grid_size", 40),
            analysis_settings=self._settings,
        )
        worker.progress.connect(
            lambda pct, msg: self.map_widget.update_loading_text(f"{msg} ({pct}%)")
        )
        self._start_worker(worker, lambda layers, result: self._on_heatmap_done(layers, result, gw_ids),
                            error_slot=self._on_heatmap_error)


    def _on_heatmap_done(self, layers: list, result, gw_ids: list):
        """
        ★ result가 이제 전체 최적화 결과(last_result)가 아니라, 방금 선택한 GW들만
        기준으로 새로 계산된 OptimizationResult임 - 그래서 히트맵 안의 Node가
        실제로 초록색(커버됨)으로 정확히 표시됨.
        """
        self.map_widget.hide_loading()
        self.map_widget.refresh(
            gws=self.gateways, nodes=self.nodes, result=result,
            heatmaps=layers, selected_gws=gw_ids,
        )
        covered = sum(1 for c in result.connections.values() if c is not None)
        self.status_label.setText(
            f"선택된 GW {len(gw_ids)}개 커버리지 표시 중 — Node {covered}/{len(self.nodes)}개 커버"
        )


    def _on_heatmap_error(self, message: str):
        self.map_widget.hide_loading()
        self.status_label.setText("히트맵 계산 실패")
        _styled_message_box(self, QMessageBox.Warning, "히트맵 계산 실패", message).exec_()


    def _open_gw_list(self):
        win = self._ensure_gw_list_win()
        win.show()
        win.raise_()

    def _ensure_node_list_win(self):
        from lorascape.gui.widgets.node_list_window import NodeListWindow
        if self._node_list_win is None:
            self._node_list_win = NodeListWindow(self.nodes, parent=self)
            self._node_list_win.sig_nodes_changed.connect(self._on_nodes_changed_from_list)
            self._node_list_win.sig_load_excel_requested.connect(
                lambda path: self._on_excel_load_requested(path, target="node")
            )
        else:
            self._node_list_win.set_nodes(self.nodes)
        return self._node_list_win

    def _open_node_list(self):
        win = self._ensure_node_list_win()
        win.show()
        win.raise_()

    def _on_gws_changed_from_list(self):
        """GW 목록창에서 파라미터가 편집되면 지도를 다시 그려서 반영함."""
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)

    def _on_nodes_changed_from_list(self):
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)

    # ── 데이터 로딩 ──────────────────────────────────────────

    def _load_data(self, silent: bool = False):
        """초기 로딩(생성자에서 xlsx_path 받았을 때)임 - GW/Node 둘 다 읽음."""
        self.status_label.setText("데이터 로딩 중...")
        worker = LoadDataWorker(self.xlsx_path, load_gateways=True, load_nodes=True)
        error_slot = self._on_data_load_error_silent if silent else self._on_data_load_error
        self._start_worker(
            worker,
            lambda gws, nds: self._on_data_loaded(gws, nds, target="both"),
            error_slot=error_slot,
        )

    def _on_excel_load_requested(self, path: str, target: str):
        """
        GW목록창 또는 단말목록창에서 '엑셀 불러오기'를 눌렀을 때 호출됨.
        target='gw'면 GW만, target='node'면 Node만 읽어서 해당 목록/지도만 갱신함.
        """
        self.status_label.setText("데이터 로딩 중...")
        worker = LoadDataWorker(
            path,
            load_gateways=(target in ("gw", "both")),
            load_nodes=(target in ("node", "both")),
        )
        self._start_worker(
            worker,
            lambda gws, nds: self._on_data_loaded(gws, nds, target=target),
            error_slot=self._on_data_load_error,
        )

    def _on_data_loaded(self, gateways, nodes, target: str):
        """
        gateways/nodes 중 로드 안 한 쪽은 None으로 들어옴 - 그 경우 기존 값을 그대로 유지함.
        """
        if gateways is not None:
            self.gateways = gateways
        if nodes is not None:
            self.nodes = nodes

        if gateways is not None and nodes is not None:
            self.status_label.setText(f"GW {len(self.gateways)}개, Node {len(self.nodes)}개 로드됨")
        elif gateways is not None:
            self.status_label.setText(f"GW {len(self.gateways)}개 로드됨 (Node는 기존 {len(self.nodes)}개 유지)")
        elif nodes is not None:
            self.status_label.setText(f"Node {len(self.nodes)}개 로드됨 (GW는 기존 {len(self.gateways)}개 유지)")

        if self.gateways or self.nodes:
            all_lats = [g.lat for g in self.gateways] + [n.lat for n in self.nodes]
            all_lons = [g.lon for g in self.gateways] + [n.lon for n in self.nodes]
            margin_lat = (max(all_lats) - min(all_lats)) * 0.1 or 0.01
            margin_lon = (max(all_lons) - min(all_lons)) * 0.1 or 0.01
            bounds = (
                min(all_lons) - margin_lon, min(all_lats) - margin_lat,
                max(all_lons) + margin_lon, max(all_lats) + margin_lat,
            )
            self.map_widget.set_bounds(bounds)

        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes)

        if gateways is not None and self._gw_list_win is not None:
            self._gw_list_win.set_gateways(self.gateways)
        if nodes is not None and self._node_list_win is not None:
            self._node_list_win.set_nodes(self.nodes)

    def _on_data_load_error(self, message: str):
        """
        사용자가 직접 요청한 로딩(목록창 버튼)이 실패했을 때 팝업으로 원인을 그대로 보여줌.
        site_inventory.py가 "필요한 시트: ... / 이 파일의 시트 목록: ..." 형태로
        구체적인 메시지를 만들어주니, 그걸 그대로 띄우면 사용자가 스스로 원인을 파악할 수 있음.
        """
        self.status_label.setText("데이터 로딩 실패")
        _styled_message_box(self, QMessageBox.Warning, "엑셀 로딩 실패", message).exec_()

    def _on_data_load_error_silent(self, message: str):
        """앱 시작 시 자동 로딩 실패는 팝업 없이 상태바에만 남김 (사용자 조작 결과가 아니라서)."""
        self.status_label.setText("이전 데이터 자동 로딩 실패 — GW/단말 목록에서 다시 불러와주세요")

    # ── 최적화 실행 ──────────────────────────────────────────

    def _on_optimize_clicked(self):
        if not self.nodes:
            _styled_message_box(self, QMessageBox.Warning, "알림", "먼저 데이터를 불러와주세요.").exec_()
            return
        if not self.dem_path:
            _styled_message_box(self, QMessageBox.Warning, "알림", "DEM 파일 경로가 설정되지 않았습니다.").exec_()
            return
        if not self.gateways:
            _styled_message_box(self, QMessageBox.Warning, "알림", "기존 GW 목록이 없습니다. 데이터를 먼저 불러와주세요.").exec_()
            return

        self.map_widget.show_loading("기존 GW 커버리지 검증 중...")
        self.result_panel.show_loading()
        self.status_label.setText("GW 배치 검증/보강 계산 중...")

        worker = OptimizeWorker(
            self.dem_path, self.nodes, existing_gateways=self.gateways,
            max_additional=self._settings.get("max_additional", 15),
            coverage_target=self._settings.get("coverage_target", 0.9),
            analysis_settings=self._settings,
        )
        self._start_worker(worker, self._on_optimize_done, error_slot=self._on_optimize_error)

    def _on_optimize_done(self, result):
        self.last_result = result
        self.map_widget.hide_loading()
        self.result_panel.show_result(result, len(self.nodes))
        self.status_label.setText(
            f"완료 — GW {result.k}개, 커버리지 {result.coverage_ratio*100:.1f}%"
        )
        self.map_widget.refresh(gws=result.gateways, nodes=self.nodes, result=result)

    def _on_optimize_error(self, message: str):
        self.map_widget.hide_loading()
        self.result_panel.show_error(message)
        self.status_label.setText("최적화 실패")
        _styled_message_box(
            self, QMessageBox.Critical, "오류", f"최적화 중 오류가 발생했습니다:\n{message}"
        ).exec_()

    # ── 워커 스레드 관리 ─────────────────────────────────────

    def _start_worker(self, worker, finished_slot, error_slot=None):
        """
        워커를 QThread로 옮겨서 실행함.
        직전 워커/스레드가 아직 안 끝났으면 새로 시작 안 하고 조용히 무시함
        (동시에 여러 계산이 겹치면 결과가 꼬일 수 있어서 - 지금은 단순 방어).

        self._thread_active 플래그로 실행중 여부를 판단함 - Qt 객체(QThread)의
        deleteLater() 이후 생존 여부에 의존하면 "wrapped C/C++ object has been
        deleted" 에러가 나서, 순수 파이썬 bool로 관리함.
        """
        if self._thread_active:
            self.status_label.setText("이전 작업이 아직 진행 중입니다.")
            return

        self._thread_active = True
        thread = QThread()
        self._thread = thread
        self._worker = worker
        worker.moveToThread(thread)

        def _mark_idle():
            self._thread_active = False

        thread.started.connect(worker.run)
        worker.finished.connect(finished_slot)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(_mark_idle)
        thread.finished.connect(thread.deleteLater)

        if error_slot:
            worker.error.connect(error_slot)
        worker.error.connect(thread.quit)

        thread.start()

    # ── 지도 이벤트 ──────────────────────────────────────────

    def _on_map_clicked(self, lon, lat):
        """
        지도 좌클릭임. 측정 모드 중이면 측정점으로 추가하고, 아니면 그냥 좌표만 상태바에 표시함.
        """
        if self._measuring:
            self._measure_points.append((lon, lat))
            self.map_widget.refresh(
                gws=self.gateways, nodes=self.nodes, result=self.last_result,
                measure_pts=self._measure_points,
            )
            self.status_label.setText(f"측정점 추가: ({lat:.5f}, {lon:.5f}) — 총 {len(self._measure_points)}개")
        else:
            self.status_label.setText(f"클릭: ({lon:.5f}, {lat:.5f})")


    def _on_gw_dragged(self, gw_id, lon, lat):
        """
        GW를 드래그해서 위치를 옮겼을 때임. 지금은 로그만 남기고, 실제로
        gateways 리스트의 좌표를 갱신하는 로직은 다음 단계에서 붙일 예정임.
        """
        self.status_label.setText(f"{gw_id} 이동: ({lon:.5f}, {lat:.5f}) — 반영은 다음 단계에서 지원 예정")

    def _on_node_dragged(self, node_id, lon, lat):
        self.status_label.setText(f"{node_id} 이동: ({lon:.5f}, {lat:.5f}) — 반영은 다음 단계에서 지원 예정")



    # ── 설정 창 ──────────────────────────────────────────
    def _open_settings(self):
        from lorascape.gui.widgets.settings_window import SettingsWindow
        if self._settings_win is None:
            self._settings_win = SettingsWindow(parent=self)
            self._settings_win.sig_settings_changed.connect(self._on_settings_changed)
        self._settings_win.show()
        self._settings_win.raise_()

    def _on_settings_changed(self, new_settings: dict):
        self._settings.update(new_settings)
        self.status_label.setText("분석 설정이 갱신되었습니다.")


    # ── 우클릭 컨텍스트 메뉴 ──────────────────────────────────

    def _on_map_right_clicked(self, lon, lat):
        """
        지도 우클릭임. 클릭한 위치(lat, lon)를 기준으로 메뉴를 띄움 - GW/단말 추가,
        분석 실행, 거리측정 시작/초기화, 좌표 복사(일반 형식/GeoJSON 형식)를 지원함.
        """
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        header = menu.addAction(f"📍 {lat:.5f}, {lon:.5f}")
        header.setEnabled(False)  # 좌표 표시용 - 클릭해도 아무 동작 안 함
        menu.addSeparator()

        act_add_gw = menu.addAction("➕ 이 위치에 GW 추가")
        act_add_node = menu.addAction("➕ 이 위치에 단말 추가")
        menu.addSeparator()

        act_run_optimize = menu.addAction("📊 커버리지 분석 실행")
        
        act_distance = menu.addAction("📏 GW-Node 거리 분석")
        
        act_run_heatmap = menu.addAction("🗺️ 히트맵 계산")
        
        act_profile = menu.addAction("📉 지형 단면도")
        
        menu.addSeparator()

        if self._measuring:
            act_measure = menu.addAction("📏 거리 측정에 이 점 추가")
            act_measure_reset = menu.addAction("✕ 측정 초기화")
        else:
            act_measure = menu.addAction("📏 거리 측정 시작")
            act_measure_reset = None
        menu.addSeparator()

        act_copy_coord = menu.addAction("📋 좌표 복사")
        act_copy_geojson = menu.addAction("📋 GeoJSON 좌표 복사")

        chosen = menu.exec_(QCursor.pos())

        if chosen == act_add_gw:
            self._add_gw_at(lat, lon)
        elif chosen == act_add_node:
            self._add_node_at(lat, lon)
        elif chosen == act_run_optimize:
            self._on_optimize_clicked()
        elif chosen == act_run_heatmap:
            self._run_heatmap_for_all_enabled()
        elif chosen == act_measure:
            self._add_measure_point(lat, lon)
        elif act_measure_reset is not None and chosen == act_measure_reset:
            self._reset_measurement()
        elif chosen == act_copy_coord:
            self._copy_coordinates(lat, lon)
        elif chosen == act_copy_geojson:
            self._copy_geojson_coordinates(lat, lon)
        elif chosen == act_distance:
            self._open_distance_window()            
        elif chosen == act_profile:
            self._open_profile_window()


    def _add_gw_at(self, lat: float, lon: float):
        """클릭한 위치에 기본값 GW를 새로 추가함."""
        from lorascape.data.schema import GatewaySite
        new_gw = GatewaySite(
            gw_id=f"RCLICK_GW_{len(self.gateways) + 1}",
            region="", location_desc="",
            lat=lat, lon=lon,
            install_type="지도에서 추가", power_source="",
        )
        self.gateways.append(new_gw)
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
        if self._gw_list_win is not None:
            self._gw_list_win.set_gateways(self.gateways)
        self.status_label.setText(f"GW 추가됨: {new_gw.gw_id} ({lat:.5f}, {lon:.5f})")

    def _add_node_at(self, lat: float, lon: float):
        """클릭한 위치에 기본값 Node를 새로 추가함."""
        from lorascape.data.schema import NodeSite
        new_node = NodeSite(
            node_id=f"RCLICK_NODE_{len(self.nodes) + 1}",
            region="", location_desc="",
            lat=lat, lon=lon,
            device_type="지도에서 추가", install_type="지도에서 추가",
        )
        self.nodes.append(new_node)
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
        if self._node_list_win is not None:
            self._node_list_win.set_nodes(self.nodes)
        self.status_label.setText(f"Node 추가됨: {new_node.node_id} ({lat:.5f}, {lon:.5f})")

    def _run_heatmap_for_all_enabled(self):
        """
        컨텍스트 메뉴의 '히트맵 계산'임. GW목록창에서 개별 선택하는 것과 달리,
        여기서는 활성화된(enabled) GW 전체를 대상으로 계산함 - 지도에서 바로
        실행할 땐 특정 GW를 미리 고를 방법이 없어서, 활성 GW 전체가 합리적인 기본값임.
        """
        enabled_ids = [g.gw_id for g in self.gateways if g.enabled]
        if not enabled_ids:
            _styled_message_box(self, QMessageBox.Information, "알림", "활성화된 GW가 없습니다.").exec_()
            return
        self._on_selected_coverage_requested(enabled_ids)

    def _copy_coordinates(self, lat: float, lon: float):
        """위도,경도 순서(일반적인 표기)로 클립보드에 복사함."""
        QApplication.clipboard().setText(f"{lat:.6f}, {lon:.6f}")
        self.status_label.setText(f"좌표 복사됨: {lat:.6f}, {lon:.6f}")

    def _copy_geojson_coordinates(self, lat: float, lon: float):
        """GeoJSON 표준 순서(경도,위도)로 클립보드에 복사함 - 일반 표기와 순서가 반대라 헷갈리기 쉬워서 별도 메뉴로 분리함."""
        QApplication.clipboard().setText(f"{lon:.6f}, {lat:.6f}")
        self.status_label.setText(f"GeoJSON 좌표 복사됨: {lon:.6f}, {lat:.6f}")

    # ── 거리 측정 ────────────────────────────────────────────

    def _add_measure_point(self, lat: float, lon: float):
        """
        측정 시작(또는 이미 측정 중이면 점 추가)임. 이후 지도를 일반 좌클릭하면
        _on_map_clicked이 self._measuring 플래그를 보고 자동으로 점을 계속 추가함.
        """
        self._measuring = True
        self._measure_points.append((lon, lat))
        self.map_widget.refresh(
            gws=self.gateways, nodes=self.nodes, result=self.last_result,
            measure_pts=self._measure_points,
        )
        self.status_label.setText(
            f"거리 측정 중 — 지도를 클릭해서 점을 추가하세요 (현재 {len(self._measure_points)}개)"
        )

    def _reset_measurement(self):
        self._measuring = False
        self._measure_points = []
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
        self.status_label.setText("측정 초기화됨")
    

    def _init_map_bounds_from_dem(self):
        """
        DEM 파일의 지리적 범위를 읽어서 지도 초기 뷰로 설정함. 실패해도(DEM이 아직
        준비 안 됐거나 손상됐거나) 앱 실행 자체를 막으면 안 되니 조용히 넘어감 -
        이 경우 지도는 기본값(대한민국 전체)으로 남아있게 됨.
        """
        try:
            from lorascape.data.dem_loader import get_dem_latlon_bounds
            bounds = get_dem_latlon_bounds(self.dem_path)
            self.map_widget.set_bounds(bounds)
            self.map_widget.refresh(gws=self.gateways, nodes=self.nodes)
        except Exception as e:
            self.status_label.setText(f"DEM 범위 자동 설정 실패 (지도 기본 범위 사용): {e}")
            
            
    def _open_distance_window(self):
        from lorascape.gui.widgets.distance_window import DistanceWindow
        if not self.gateways:
            _styled_message_box(self, QMessageBox.Information, "알림", "GW가 없습니다. 먼저 데이터를 불러오거나 추가하세요.").exec_()
            return
        if self._distance_win is None:
            self._distance_win = DistanceWindow(self.gateways, self.nodes, self.last_result, parent=self)
        else:
            self._distance_win.set_data(self.gateways, self.nodes, self.last_result)
        self._distance_win.show()
        self._distance_win.raise_()
        

    def _open_profile_window(self):
        from lorascape.gui.widgets.profile_window import ProfileWindow
        if not self.gateways or not self.nodes:
            _styled_message_box(self, QMessageBox.Information, "알림", "GW와 Node가 모두 있어야 합니다.").exec_()
            return
        if not self.dem_path:
            _styled_message_box(self, QMessageBox.Warning, "알림", "DEM 파일 경로가 설정되지 않았습니다.").exec_()
            return

        from lorascape.data.dem_loader import DemLoader
        # ProfileWindow가 살아있는 동안 DEM을 계속 조회해야 해서, 워커처럼 with문으로
        # 바로 닫지 않고 창과 함께 들고 있음 - 창 닫힐 때 명시적으로 닫아줌.
        dem = DemLoader(self.dem_path)

        if self._profile_win is None:
            self._profile_win = ProfileWindow(self.gateways, self.nodes, dem, fc_mhz=self._settings.get("fc_mhz", 920.0), parent=self)
            self._profile_win.finished.connect(lambda _: dem.close())
        else:
            self._profile_win.set_data(self.gateways, self.nodes, dem)
        self._profile_win.show()
        self._profile_win.raise_()
        

    # ── 추가 설치 위치 제안 (기존 GW+Node 있는 상태) ──────────

    def _on_suggest_additional_clicked(self):
        if not self.nodes:
            _styled_message_box(self, QMessageBox.Warning, "알림", "Node 데이터가 없습니다.").exec_()
            return
        if not self.dem_path:
            _styled_message_box(self, QMessageBox.Warning, "알림", "DEM 파일 경로가 설정되지 않았습니다.").exec_()
            return
        if not self.gateways:
            _styled_message_box(
                self, QMessageBox.Information, "알림",
                "기존 GW가 없습니다. GW가 하나도 없는 상태라면 '신규 GW 배치 추천'을 사용하세요."
            ).exec_()
            return

        self.map_widget.show_loading("추가 설치 위치 분석 중...")
        self.status_label.setText("추가 설치 위치 분석 중...")

        worker = SuggestAdditionalGWWorker(
            self.dem_path, self.nodes, existing_gateways=self.gateways,
            max_additional=self._settings.get("max_additional", 15),
            coverage_target=self._settings.get("coverage_target", 0.9),
            analysis_settings=self._settings,
        )
        self._start_worker(worker, self._on_suggestion_ready, error_slot=self._on_suggestion_error)

    def _on_suggestion_ready(self, result, suggested: list):
        self.map_widget.hide_loading()

        if not suggested:
            self.status_label.setText("이미 목표 커버리지를 달성했습니다 — 추가 설치가 필요 없습니다.")
            self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=result)
            self.last_result = result
            self.result_panel.show_result(result, len(self.nodes))
            return

        # 지도에 기존 GW + 제안된 GW(미리보기)를 같이 보여줌 - 아직 self.gateways에는 반영 안 함
        preview_gateways = self.gateways + suggested
        self.map_widget.refresh(gws=preview_gateways, nodes=self.nodes, result=result)
        self.status_label.setText(f"{len(suggested)}개 추가 설치 위치 제안됨 — 검토 후 적용하세요.")

        from lorascape.gui.widgets.suggestion_window import SuggestionWindow
        win = SuggestionWindow("추가 설치 위치 제안", suggested, result.node_gw_ids, parent=self)
        win.sig_apply_requested.connect(self._on_suggestions_applied)
        if win.exec_() != win.Accepted:
            # 취소하면 미리보기도 원래대로 되돌림
            self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
            self.status_label.setText("제안이 취소되었습니다.")

    def _on_suggestion_error(self, message: str):
        self.map_widget.hide_loading()
        self.status_label.setText("제안 분석 실패")
        _styled_message_box(self, QMessageBox.Warning, "오류", message).exec_()

    def _on_suggestions_applied(self, approved_gateways: list):
        """
        사용자가 SuggestionWindow에서 '선택 적용'한 GW들을 실제 self.gateways에 반영함.
        이 시점에서야 비로소 제안이 '확정'됨.
        """
        self.gateways.extend(approved_gateways)
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
        if self._gw_list_win is not None:
            self._gw_list_win.set_gateways(self.gateways)
        self.status_label.setText(f"{len(approved_gateways)}개 GW가 목록에 추가되었습니다.")

    # ── 신규 GW 배치 추천 (GW 없는 상태) ──────────────────────

    def _on_suggest_greenfield_clicked(self):
        if not self.nodes:
            _styled_message_box(self, QMessageBox.Warning, "알림", "Node 데이터가 없습니다.").exec_()
            return
        if not self.dem_path:
            _styled_message_box(self, QMessageBox.Warning, "알림", "DEM 파일 경로가 설정되지 않았습니다.").exec_()
            return

        if self.gateways:
            reply = QMessageBox.question(
                self, "확인",
                f"이미 GW {len(self.gateways)}개가 있습니다. 기존 GW는 무시하고 "
                f"Node 위치만으로 완전히 새로운 배치를 추천합니다. 계속할까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.map_widget.show_loading("신규 GW 배치 분석 중...")
        self.status_label.setText("신규 GW 배치 분석 중 (기존 GW 무시)...")

        worker = SuggestGreenfieldGWWorker(
            self.dem_path, self.nodes,
            initial_k=1, max_k=self._settings.get("max_additional", 15),
            coverage_target=self._settings.get("coverage_target", 0.9),
            analysis_settings=self._settings,
        )
        self._start_worker(worker, self._on_greenfield_suggestion_ready, error_slot=self._on_suggestion_error)

    def _on_greenfield_suggestion_ready(self, result, suggested: list):
        self.map_widget.hide_loading()

        if not suggested:
            self.status_label.setText("배치를 추천할 수 없습니다.")
            return

        # 기존 GW와 무관하게 미리보기(기존 GW는 화면에서 잠깐 안 보이게 함 - 그린필드 시나리오라서)
        self.map_widget.refresh(gws=suggested, nodes=self.nodes, result=result)
        self.status_label.setText(f"{len(suggested)}개 신규 GW 배치 제안됨 — 검토 후 적용하세요.")

        from lorascape.gui.widgets.suggestion_window import SuggestionWindow
        win = SuggestionWindow("신규 GW 배치 추천", suggested, result.node_gw_ids, parent=self)
        win.sig_apply_requested.connect(self._on_suggestions_applied)
        if win.exec_() != win.Accepted:
            self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)
            self.status_label.setText("제안이 취소되었습니다.")
            

    def _on_show_result_heatmap_clicked(self):
        """
        결과패널의 '이 결과를 히트맵으로 보기' 버튼임. 방금 실행된 최적화 결과에
        쓰인 GW 전체를 대상으로 기존 '선택 커버리지' 파이프라인을 그대로 재사용함
        (중복 로직 없이, 대상 GW id 목록만 다르게 넘기는 방식).

        GW가 많으면(예: 35개) 히트맵 계산이 상당히 오래 걸릴 수 있어서, 실행 전에
        경고를 한 번 띄움 - "검증 및 보강" 버튼 자체는 항상 마커로 빠르게 결과를
        보여주고, 히트맵은 사용자가 명시적으로 원할 때만 계산하는 구조를 유지함.
        """
        if self.last_result is None or not self.last_result.gateways:
            return

        gw_ids = [gw.gw_id for gw in self.last_result.gateways]

        if len(gw_ids) > 10:
            reply = QMessageBox.question(
                self, "확인",
                f"GW {len(gw_ids)}개 전체의 히트맵을 계산합니다. GW 수가 많아 "
                f"시간이 다소 걸릴 수 있습니다. 계속할까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._on_selected_coverage_requested(gw_ids)