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
    """엑셀 인벤토리 + DEM을 백그라운드에서 로딩하는 워커임."""
    finished = pyqtSignal(list, list)  # gateways, nodes
    error = pyqtSignal(str)

    def __init__(self, xlsx_path: str):
        super().__init__()
        self.xlsx_path = xlsx_path

    def run(self):
        try:
            gateways = load_gateways(self.xlsx_path)
            nodes = load_nodes(self.xlsx_path)
            self.finished.emit(gateways, nodes)
        except Exception as e:
            # 워커 스레드 안에서 예외가 나면 조용히 죽어버리니까, 반드시 시그널로
            # 메인 스레드에 전달해서 사용자에게 보여줘야 함 (안 그러면 원인 파악 불가능).
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