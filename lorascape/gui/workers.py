# lorascape/gui/workers.py
"""
무거운 계산(엑셀+DEM 로딩, GW 최적 배치)을 백그라운드 스레드에서 돌리기 위한
워커 클래스들임. 원본 참고 파일의 CoverageWorker/HeatmapWorker와 같은 패턴임:
QObject를 만들고 QThread로 옮겨서(moveToThread) 돌리는 방식.

★ 왜 필요한가: 최적화 계산(gw_placement.optimize_gw_placement)이 실측으로
143 Node/max_k=20 기준 약 38초 걸림. 메인 스레드에서 그냥 돌리면 그 시간 동안
창이 멈춘 것처럼 보여서(입력도 안 먹고 다시그리기도 안 됨), 반드시 분리해야 함.
"""
from PyQt5.QtCore import QObject, pyqtSignal

from lorascape.data.dem_loader import DemLoader
from lorascape.data.site_inventory import load_gateways, load_nodes
from lorascape.core.optimization.gw_placement import optimize_gw_placement


class LoadDataWorker(QObject):
    """
    엑셀 인벤토리를 백그라운드에서 로딩하는 워커임.

    load_gateways/load_nodes 플래그로 어느 쪽을 읽을지 선택함 - GW목록창에서
    불러오면 GW만, 단말목록창에서 불러오면 Node만 갱신되게 하려고 분리함
    (전에는 무조건 둘 다 읽어서, 한쪽 창에서 다른 종류의 엑셀을 넣어도
    반대쪽 목록까지 같이 바뀌어버리는 문제가 있었음).
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
            self.error.emit(str(e))


class OptimizeWorker(QObject):
    """
    기존 설치된 GW를 검증하고, 부족하면 추가 GW를 배치하는 계산을 백그라운드에서 돌리는 워커임.
    (문서 2번+3번 통합: 기존 GW로 커버리지 검증 후, 목표 미달이면 부족한 만큼만 증설)
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, dem_path: str, nodes: list, existing_gateways: list, max_additional: int, coverage_target: float):
        super().__init__()
        self.dem_path = dem_path
        self.nodes = nodes
        self.existing_gateways = existing_gateways
        self.max_additional = max_additional
        self.coverage_target = coverage_target

    def run(self):
        try:
            from lorascape.core.optimization.gw_placement import evaluate_and_augment
            with DemLoader(self.dem_path) as dem:
                result = evaluate_and_augment(
                    self.nodes, self.existing_gateways, dem,
                    max_additional=self.max_additional, coverage_target=self.coverage_target,
                )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))