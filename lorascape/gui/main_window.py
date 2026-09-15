# lorascape/gui/main_window.py
"""
메인 윈도우임. 원본 참고 파일(main_window.py)의 구조(툴바 + QSplitter(지도/결과패널) +
상태바)를 그대로 따르되, core.coverage.CoverageEngine 같은 대신 우리가 만든
lorascape.core.optimization.gw_placement / lorascape.data.* 를 직접 씀.

★ 지금은 1차 버전임 - '데이터 불러오기'와 'GW 최적 배치 실행' 두 가지 핵심 동작만
동작하게 만들고, GW목록/Node목록/설정/리포트 등 나머지 툴바 버튼들은
해당 창을 포팅하는 대로 하나씩 추가해나갈 예정임 (지금 안 넣은 이유는
동작 안 하는 버튼을 미리 만들어두는 것보다, 만들 때마다 바로 연결하는 게
"눌러보니 안 됨" 상태를 안 만드는 방법이라서).
"""
from PyQt5.QtWidgets import (
    QMainWindow, QToolBar, QAction, QSplitter, QStatusBar, QLabel, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread

from lorascape.gui.widgets.map_widget import MapWidget
from lorascape.gui.widgets.result_panel import ResultPanel
from lorascape.gui.workers import LoadDataWorker, OptimizeWorker

DARK = "#181b22"
TEXT = "#e0e4ef"
MUTED = "#7a8099"
BORDER = "#2a2f3b"

TOOLBAR_STYLE = f"""
QToolBar {{ background:{DARK}; border:none; border-bottom:1px solid {BORDER}; spacing:4px; padding:4px; }}
QToolButton {{ color:{TEXT}; background:#253a5a; border:1px solid #3a5a8a; border-radius:5px; padding:5px 10px; }}
QToolButton:hover {{ background:#2e4a7a; }}
"""


class MainWindow(QMainWindow):
    def __init__(self, xlsx_path: str = None, dem_path: str = None):
        super().__init__()
        self.setWindowTitle("LoRaScape")
        self.resize(1400, 900)
        self.setStyleSheet(f"background:{DARK};")

        # 초기 데이터 경로임 - 지금은 생성자 인자로 받지만, 나중에 초기설정창(Shapefile/DEM
        # 선택창)이 생기면 그쪽에서 값을 받아오는 구조로 바뀔 예정임.
        self.xlsx_path = xlsx_path
        self.dem_path = dem_path

        self._gw_list_win = None
        self._node_list_win = None

        self.gateways: list = []
        self.nodes: list = []
        self.last_result = None

        self._thread: QThread | None = None
        self._worker = None
        self._thread_active = False

        self._build_ui()

        if self.xlsx_path:
            self._load_data()

    def _build_ui(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(TOOLBAR_STYLE)
        self.addToolBar(Qt.TopToolBarArea, tb)

        act_gw_list = QAction("GW 목록", self)
        act_node_list = QAction("단말 목록", self)
        act_gw_list.triggered.connect(self._open_gw_list)
        act_node_list.triggered.connect(self._open_node_list)
        tb.addAction(act_gw_list)
        tb.addAction(act_node_list)

        act_load = QAction("데이터 불러오기", self)
        act_optimize = QAction("GW 배치 검증 및 보강", self)

        act_load.triggered.connect(self._on_load_clicked)
        act_optimize.triggered.connect(self._on_optimize_clicked)

        tb.addAction(act_load)
        tb.addAction(act_optimize)

        splitter = QSplitter(Qt.Horizontal)
        self.map_widget = MapWidget()
        self.result_panel = ResultPanel()
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

    # ── 데이터 로딩 ──────────────────────────────────────────

    def _on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "엑셀 인벤토리 선택", "", "Excel Files (*.xlsx)")
        if not path:
            return
        self.xlsx_path = path
        self._load_data()

    def _load_data(self):
        self.status_label.setText("데이터 로딩 중...")
        self._start_worker(LoadDataWorker(self.xlsx_path), self._on_data_loaded)

    def _on_data_loaded(self, gateways, nodes):
        self.gateways = gateways
        self.nodes = nodes
        self.status_label.setText(f"GW {len(gateways)}개, Node {len(nodes)}개 로드됨")

        if gateways or nodes:
            all_lats = [g.lat for g in gateways] + [n.lat for n in nodes]
            all_lons = [g.lon for g in gateways] + [n.lon for n in nodes]
            margin_lat = (max(all_lats) - min(all_lats)) * 0.1 or 0.01
            margin_lon = (max(all_lons) - min(all_lons)) * 0.1 or 0.01
            bounds = (
                min(all_lons) - margin_lon, min(all_lats) - margin_lat,
                max(all_lons) + margin_lon, max(all_lats) + margin_lat,
            )
            self.map_widget.set_bounds(bounds)

        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes)

        # 목록창이 이미 열려있으면 같이 갱신함
        if self._gw_list_win is not None:
            self._gw_list_win.set_gateways(self.gateways)
        if self._node_list_win is not None:
            self._node_list_win.set_nodes(self.nodes)

    # ── 최적화 실행 ──────────────────────────────────────────

    def _on_optimize_clicked(self):
        if not self.nodes:
            QMessageBox.warning(self, "알림", "먼저 데이터를 불러와주세요.")
            return
        if not self.dem_path:
            QMessageBox.warning(self, "알림", "DEM 파일 경로가 설정되지 않았습니다.")
            return
        if not self.gateways:
            QMessageBox.warning(self, "알림", "기존 GW 목록이 없습니다. 데이터를 먼저 불러와주세요.")
            return

        self.map_widget.show_loading("기존 GW 커버리지 검증 중...")
        self.result_panel.show_loading()
        self.status_label.setText("GW 배치 검증/보강 계산 중...")

        worker = OptimizeWorker(
            self.dem_path, self.nodes, existing_gateways=self.gateways,
            max_additional=15, coverage_target=0.9,
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
        QMessageBox.critical(self, "오류", f"최적화 중 오류가 발생했습니다:\n{message}")

    # ── 워커 스레드 관리 ─────────────────────────────────────

    def _start_worker(self, worker, finished_slot, error_slot=None):
        """
        워커를 QThread로 옮겨서 실행함.

        ★ 버그 수정: 예전엔 self._thread.isRunning()으로 실행 중 여부를 판단했는데,
        워커가 끝나면 thread.deleteLater()로 C++ 객체가 실제 삭제되어버려서
        다음 호출 때 삭제된 객체에 접근하다가 RuntimeError가 났음.
        이제는 단순 bool 플래그(self._thread_active)로 관리함 - Qt 객체 생존 여부에
        의존하지 않아서 안전함.
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
        self.status_label.setText(f"클릭: ({lon:.5f}, {lat:.5f})")

    def _on_gw_dragged(self, gw_id, lon, lat):
        """
        GW를 드래그해서 위치를 옮겼을 때임. 지금은 로그만 남기고, 실제로
        gateways 리스트의 좌표를 갱신하는 로직은 GW목록창 포팅할 때 같이 붙일 예정임
        (지금 섣불리 좌표만 바꾸면, 최적화 결과와 실제 표시가 어긋날 수 있어서).
        """
        self.status_label.setText(f"{gw_id} 이동: ({lon:.5f}, {lat:.5f}) — 반영은 다음 단계에서 지원 예정")

    def _on_node_dragged(self, node_id, lon, lat):
        self.status_label.setText(f"{node_id} 이동: ({lon:.5f}, {lat:.5f}) — 반영은 다음 단계에서 지원 예정")
        

    # ── 목록 창 ──────────────────────────────────────────────

    def _ensure_gw_list_win(self):
        from lorascape.gui.widgets.gw_list_window import GWListWindow
        if self._gw_list_win is None:
            self._gw_list_win = GWListWindow(self.gateways, parent=self)
            self._gw_list_win.sig_gws_changed.connect(self._on_gws_changed_from_list)
            self._gw_list_win.sig_load_excel_requested.connect(self._on_excel_load_requested)
        else:
            self._gw_list_win.set_gateways(self.gateways)
        return self._gw_list_win

    def _ensure_node_list_win(self):
        from lorascape.gui.widgets.node_list_window import NodeListWindow
        if self._node_list_win is None:
            self._node_list_win = NodeListWindow(self.nodes, parent=self)
            self._node_list_win.sig_nodes_changed.connect(self._on_nodes_changed_from_list)
            self._node_list_win.sig_load_excel_requested.connect(self._on_excel_load_requested)
        else:
            self._node_list_win.set_nodes(self.nodes)
        return self._node_list_win

    def _on_excel_load_requested(self, path: str):
        """
        GW목록창 또는 단말목록창에서 '엑셀 불러오기'를 눌렀을 때 호출됨.
        어느 창에서 눌렀든 GW/Node 둘 다 다시 로드하고, 지도와 두 목록창을 전부 갱신함
        (한 엑셀에 GW/Node 시트가 같이 있으니, 하나만 갱신하면 서로 데이터가 어긋날 수 있어서).
        """
        self.xlsx_path = path
        self._load_data()

    def _open_gw_list(self):
        win = self._ensure_gw_list_win()
        win.show()
        win.raise_()

    def _open_node_list(self):
        win = self._ensure_node_list_win()
        win.show()
        win.raise_()

    def _on_gws_changed_from_list(self):
        """GW 목록창에서 파라미터가 편집되면 지도를 다시 그려서 반영함."""
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)

    def _on_nodes_changed_from_list(self):
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result)