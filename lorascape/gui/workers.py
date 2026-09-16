# lorascape/gui/workers.py
"""
무거운 계산(엑셀+DEM 로딩, GW 배치 검증/보강)을 백그라운드 스레드에서 돌리기 위한
워커 클래스들임. QObject를 만들고 QThread로 옮겨서(moveToThread) 돌리는 방식임.

★ 최적화 계산이 실측으로 143 Node/max_k=20 기준 약 38초 걸림. 메인 스레드에서
그냥 돌리면 그 시간 동안 창이 멈춘 것처럼 보여서(입력도 안 먹고 다시그리기도
안 됨), 반드시 분리해야 함.
"""
from PyQt5.QtCore import QObject, pyqtSignal

from lorascape.data.dem_loader import DemLoader


class LoadDataWorker(QObject):
    """
    엑셀 인벤토리를 백그라운드에서 로딩하는 워커임.

    load_gateways/load_nodes 플래그로 어느 쪽을 읽을지 선택함 - GW목록창에서
    불러오면 GW만, 단말목록창에서 불러오면 Node만 갱신되게 하려고 분리함.
    """
    finished = pyqtSignal(object, object)  # gateways(list|None), nodes(list|None)
    error = pyqtSignal(str)

    def __init__(self, xlsx_path: str, load_gateways: bool = True, load_nodes: bool = True):
        super().__init__()
        self.xlsx_path = xlsx_path
        self.should_load_gateways = load_gateways
        self.should_load_nodes = load_nodes

    def run(self):
        try:
            from lorascape.data.site_inventory import load_gateways as _load_gw, load_nodes as _load_nd
            gateways = _load_gw(self.xlsx_path) if self.should_load_gateways else None
            nodes = _load_nd(self.xlsx_path) if self.should_load_nodes else None
            self.finished.emit(gateways, nodes)
        except Exception as e:
            # 워커 스레드 안에서 예외가 나면 조용히 죽어버리니까, 반드시 시그널로
            # 메인 스레드에 전달해서 사용자에게 보여줘야 함.
            self.error.emit(str(e))


class OptimizeWorker(QObject):
    """
    기존 설치된 GW를 검증하고, 부족하면 추가 GW를 배치하는 계산을 백그라운드에서 돌리는 워커임.
    analysis_settings로 fc_mhz/bandwidth_hz/environment/receiver_noise_figure_db 같은
    시스템 전체 파라미터를 받음 - GW/Node 개별 무선 파라미터는 각 엔티티 필드에서
    그대로 읽어감 (evaluate_connection 기본 동작).
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, dem_path: str, nodes: list, existing_gateways: list,
                 max_additional: int, coverage_target: float, analysis_settings: dict = None):
        super().__init__()
        self.dem_path = dem_path
        self.nodes = nodes
        self.existing_gateways = existing_gateways
        self.max_additional = max_additional
        self.coverage_target = coverage_target
        self.analysis_settings = analysis_settings or {}

    def run(self):
        try:
            from lorascape.core.optimization.gw_placement import evaluate_and_augment
            with DemLoader(self.dem_path) as dem:
                result = evaluate_and_augment(
                    self.nodes, self.existing_gateways, dem,
                    max_additional=self.max_additional,
                    coverage_target=self.coverage_target,
                    fc_mhz=self.analysis_settings.get("fc_mhz", 920.0),
                    environment=self.analysis_settings.get("environment", "urban"),
                    bandwidth_hz=self.analysis_settings.get("bandwidth_hz", 125_000),
                    receiver_noise_figure_db=self.analysis_settings.get("receiver_noise_figure_db", 6.0),
                )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))