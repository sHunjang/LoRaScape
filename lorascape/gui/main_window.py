# lorascape/gui/main_window.py
"""
메인 윈도우임. 툴바 + QSplitter(지도/결과패널) + 상태바 구조.
core.optimization.gw_placement / data.* 를 직접 씀 (별도 어댑터 레이어 없음).
"""
from PyQt5.QtWidgets import (
    QMainWindow, QToolBar, QAction, QSplitter, QStatusBar, QLabel,
    QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread

from lorascape.gui.widgets.map_widget import MapWidget
from lorascape.gui.widgets.result_panel import ResultPanel
from lorascape.gui.workers import LoadDataWorker, OptimizeWorker

from lorascape.gui.app_config import load_config


DARK = "#181b22"
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

        self._settings_win = None

        self._build_ui()

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
        act_settings = QAction("설정", self)

        act_gw_list.triggered.connect(self._open_gw_list)
        act_node_list.triggered.connect(self._open_node_list)
        act_optimize.triggered.connect(self._on_optimize_clicked)
        act_settings.triggered.connect(self._open_settings)

        tb.addAction(act_gw_list)
        tb.addAction(act_node_list)
        tb.addAction(act_optimize)
        tb.addAction(act_settings)

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
        """
        GW목록창에서 특정 GW들만 골라 '선택 커버리지'를 눌렀을 때임.
        빈 리스트면 필터 해제(전체 다시 표시).
        """
        selected = gw_ids if gw_ids else None
        self.map_widget.refresh(gws=self.gateways, nodes=self.nodes, result=self.last_result, selected_gws=selected)
        if gw_ids:
            self.status_label.setText(f"선택된 GW {len(gw_ids)}개만 표시 중")
        else:
            self.status_label.setText("전체 GW 표시로 복귀")


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