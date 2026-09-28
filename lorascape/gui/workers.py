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
            

class HeatmapWorker(QObject):
    """
    선택된 GW들의 커버리지 히트맵을 백그라운드에서 계산하는 워커임.

    ★ 추가: 히트맵 이미지뿐 아니라, 선택된 GW들만 기준으로 전체 Node의
    실제 연결 여부(OptimizationResult)도 같이 계산해서 반환함. 이걸로
    Node 마커를 색칠하면 "이 히트맵 커버리지 안에 있는 Node가 실제로
    초록색(커버됨)으로 표시"되게 만들 수 있음 - 예전엔 히트맵과 마커 색상이
    서로 다른 계산 결과를 참조해서 안 맞는 경우가 있었음.
    """
    finished = pyqtSignal(list, object)  # (layers, OptimizationResult)
    progress = pyqtSignal(int, str)
    error = pyqtSignal(str)

    def __init__(self, gateways: list, nodes: list, dem_path: str, grid_size: int = 40,
                 radius_km: float = 2.0, analysis_settings: dict = None):
        super().__init__()
        self.gateways = gateways
        self.nodes = nodes  # ★ 추가: 연결 판정을 위해 전체 Node 목록도 받음
        self.dem_path = dem_path
        self.grid_size = grid_size
        self.radius_km = radius_km
        self.analysis_settings = analysis_settings or {}

    def run(self):
        try:
            from lorascape.core.optimization.heatmap import compute_gw_heatmap_grid
            from lorascape.core.optimization.gw_placement import evaluate_gateways_coverage
            from lorascape.gui.widgets.heatmap_render import build_heatmap_layer_dict, get_gw_color

            multi_gw = len(self.gateways) > 1
            layers = []
            n_gws = len(self.gateways)

            with DemLoader(self.dem_path) as dem:
                for idx, gw in enumerate(self.gateways):

                    def _on_cell_progress(done_cells, total_cells, _idx=idx, _gw=gw):
                        gw_local_ratio = done_cells / total_cells
                        overall_ratio = (_idx + gw_local_ratio) / (n_gws + 1)  # +1은 아래 연결계산 단계 몫
                        pct = int(overall_ratio * 100)
                        self.progress.emit(
                            pct, f"{_gw.gw_id} 커버리지 계산 중... ({_idx+1}/{n_gws}, 셀 {done_cells}/{total_cells})"
                        )

                    grid = compute_gw_heatmap_grid(
                        gw, dem,
                        radius_km=self.radius_km, grid_size=self.grid_size,
                        fc_mhz=self.analysis_settings.get("fc_mhz", 920.0),
                        environment=self.analysis_settings.get("environment", "urban"),
                        progress_callback=_on_cell_progress,
                    )

                    base_color = get_gw_color(idx) if multi_gw else None
                    layer = build_heatmap_layer_dict(
                        grid, base_color=base_color,
                        opacity=self.analysis_settings.get("heatmap_opacity", 0.85),
                    )
                    layers.append(layer)

                self.progress.emit(int(100 * n_gws / (n_gws + 1)), "선택 GW 기준 Node 연결 여부 계산 중...")
                result = evaluate_gateways_coverage(
                    self.nodes, self.gateways, dem,
                    fc_mhz=self.analysis_settings.get("fc_mhz", 920.0),
                    environment=self.analysis_settings.get("environment", "urban"),
                    bandwidth_hz=self.analysis_settings.get("bandwidth_hz", 125_000),
                    receiver_noise_figure_db=self.analysis_settings.get("receiver_noise_figure_db", 6.0),
                )

            self.progress.emit(100, "완료")
            self.finished.emit(layers, result)
        except Exception as e:
            self.error.emit(str(e))
            

class SuggestAdditionalGWWorker(QObject):
    """
    기존 GW+Node로 커버리지를 검증하고, 부족하면 추가 설치 후보를 '제안'만 하는 워커임.
    evaluate_and_augment를 그대로 쓰되, 결과에서 기존 GW와 새로 제안된 GW를
    구분해서 반환함 - 자동으로 GW 목록에 반영하지 않고, 사용자가 검토 후
    선택적으로 승인하게 하려는 목적임 (기존 '검증 및 보강' 버튼과의 차이점).
    """
    finished = pyqtSignal(object, list)  # (OptimizationResult, list[GatewaySite] 새로 제안된 GW만)
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
            existing_ids = {gw.gw_id for gw in self.existing_gateways}

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

            # 결과의 gateways 중 기존 목록에 없던 것만 '새로 제안된 것'으로 분리함
            suggested = [gw for gw in result.gateways if gw.gw_id not in existing_ids]
            self.finished.emit(result, suggested)
        except Exception as e:
            self.error.emit(str(e))


class SuggestGreenfieldGWWorker(QObject):
    """
    GW가 하나도 없는 상태에서, Node 위치만 보고 처음부터 GW 배치를 새로 추천하는 워커임.
    기존 GW는 완전히 무시함(그린필드) - optimize_gw_placement를 그대로 씀
    (evaluate_and_augment가 아니라, K-means 후보 자체를 처음부터 뽑는 버전).
    """
    finished = pyqtSignal(object, list)  # (OptimizationResult, list[GatewaySite] 제안된 GW 전체)
    error = pyqtSignal(str)

    def __init__(self, dem_path: str, nodes: list, initial_k: int,
                 max_k: int, coverage_target: float, analysis_settings: dict = None):
        super().__init__()
        self.dem_path = dem_path
        self.nodes = nodes
        self.initial_k = initial_k
        self.max_k = max_k
        self.coverage_target = coverage_target
        self.analysis_settings = analysis_settings or {}

    def run(self):
        try:
            from lorascape.core.optimization.gw_placement import optimize_gw_placement
            with DemLoader(self.dem_path) as dem:
                result = optimize_gw_placement(
                    self.nodes, dem,
                    initial_k=self.initial_k, max_k=self.max_k,
                    coverage_target=self.coverage_target,
                    fc_mhz=self.analysis_settings.get("fc_mhz", 920.0),
                    environment=self.analysis_settings.get("environment", "urban"),
                    bandwidth_hz=self.analysis_settings.get("bandwidth_hz", 125_000),
                    receiver_noise_figure_db=self.analysis_settings.get("receiver_noise_figure_db", 6.0),
                )
            self.finished.emit(result, result.gateways)
        except Exception as e:
            self.error.emit(str(e))