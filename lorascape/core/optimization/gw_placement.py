# lorascape/core/optimization/gw_placement.py
"""
GW(게이트웨이) 위치 최적화 모듈임.

★ 구조 변경: 예전엔 K를 1씩 늘려가며 매번 K-means를 새로 돌리고 GW-Node 경로손실도
매번 처음부터 다시 계산했음. 근데 GW/Node 하드웨어 스펙(Pt, Gt 등)은 고정값이고,
"누가 누구를 커버하는지"는 위치 조합에 달린 문제라 조합 계산 자체는 피할 수 없지만,
그 계산을 K값이 바뀔 때마다 반복할 필요는 없음.

그래서 지금은:
  1) 후보 GW 위치를 넉넉하게(max_k개) 한 번만 뽑고
  2) 그 후보들과 전체 Node 사이의 경로손실/연결가능여부를 "매트릭스"로 딱 한 번 계산하고
  3) 매트릭스에서 탐욕 알고리즘(greedy set cover)으로 최소 개수의 GW를 골라냄
     (이 단계는 이미 계산된 숫자를 비교만 하는 거라 매우 빠름)

이렇게 하면 무거운 연산(DEM 조회 + 전파모델 계산)은 딱 한 번만 하고,
"몇 개를 쓸지" 판단은 값싸게 반복할 수 있음.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np
from sklearn.cluster import KMeans

from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.data.coord_transform import latlon_to_xy, xy_to_latlon, distance_m
from lorascape.core.propagation.song_model import path_loss as song_path_loss
from lorascape.core.diffraction.deygout import deygout_recursive
from lorascape.core.linkbudget.link_budget import rx_power_dbm, snr_db, select_sf

DEFAULT_MAX_PATH_LOSS_DB = 140.0
DEYGOUT_LOSS_CAP_DB = 30.0


@dataclass
class ConnectionResult:
    gw_id: str
    node_id: str
    path_loss_db: float
    rx_power_dbm: float
    snr_db: float
    sf: int


@dataclass
class OptimizationResult:
    gateways: list[GatewaySite]
    connections: dict[str, Optional[ConnectionResult]]  # node_id -> 최적 연결
    node_gw_ids: dict[str, list[str]]  # ★ 추가: node_id -> 이 Node를 수신하는 선택된 GW id 목록 (중첩커버/다이버시티 표시용)
    coverage_ratio: float
    k: int
    target_met: bool

    @property
    def gw_counts(self) -> dict[str, int]:
        """GW별 담당(최적 연결로 채택된) Node 개수임. GW 마커 툴팁에 씀."""
        counts: dict[str, int] = {}
        for conn in self.connections.values():
            if conn is not None:
                counts[conn.gw_id] = counts.get(conn.gw_id, 0) + 1
        return counts


def compute_total_path_loss(
    gw: GatewaySite, node: NodeSite, dem,
    fc_mhz: float = 920.0, environment: str = "urban", n_profile_samples: int = 20,
) -> float:
    """GW-Node 사이 최종 경로손실 = Song's Model + Deygout 회절손실(30dB 캡)."""
    d_km = distance_m(gw.lat, gw.lon, node.lat, node.lon) / 1000.0
    if d_km <= 0:
        d_km = 0.001

    base_pl = song_path_loss(fc_mhz, gw.antenna_height_m, node.antenna_height_m, d_km, environment)

    profile = dem.get_elevation_profile(gw.lat, gw.lon, node.lat, node.lon, n_profile_samples)
    diffraction_loss = deygout_recursive(
        profile, fc_mhz, tx_height=gw.antenna_height_m, rx_height=node.antenna_height_m
    )
    diffraction_loss_capped = min(diffraction_loss, DEYGOUT_LOSS_CAP_DB)

    return base_pl + diffraction_loss_capped


def evaluate_connection(
    gw: GatewaySite, node: NodeSite, dem,
    fc_mhz: float = 920.0, environment: str = "urban",
    max_path_loss_db: float = DEFAULT_MAX_PATH_LOSS_DB,
    tx_power_dbm: Optional[float] = None,
    gw_antenna_gain_dbi: Optional[float] = None,
    gw_cable_loss_db: Optional[float] = None,
    node_antenna_gain_dbi: Optional[float] = None,
    node_cable_loss_db: Optional[float] = None,
    bandwidth_hz: float = 125_000,
    receiver_noise_figure_db: float = 6.0,
) -> Optional[ConnectionResult]:
    """
    GW 하나와 Node 하나 사이 연결 가능 여부 판정. gw/node 객체의 무선 파라미터를 기본으로 씀.

    node.min_rx_dbm을 하드 하한선으로 반영함. 예전엔 이 필드가 스키마에만
    있고 실제 판정에는 SF별 SNR 임계값만 썼는데, 그러면 Node마다 다르게 설정한
    최소 수신 레벨이 아무 의미가 없었음. 이제는 "SF 기준을 만족하더라도, 이
    Node가 개별적으로 요구하는 최소 수신 레벨보다 약하면 연결 실패"로 처리함
    (SF 판정과 min_rx_dbm 판정 둘 다 통과해야 연결됨 - AND 조건).
    """
    pl = compute_total_path_loss(gw, node, dem, fc_mhz, environment)

    if pl > max_path_loss_db:
        return None

    pr = rx_power_dbm(
        tx_power_dbm if tx_power_dbm is not None else gw.tx_power_dbm,
        gw_antenna_gain_dbi if gw_antenna_gain_dbi is not None else gw.antenna_gain_dbi,
        gw_cable_loss_db if gw_cable_loss_db is not None else gw.cable_loss_db,
        pl,
        node_antenna_gain_dbi if node_antenna_gain_dbi is not None else node.antenna_gain_dbi,
        node_cable_loss_db if node_cable_loss_db is not None else node.cable_loss_db,
        indoor_penetration_loss_db=node.indoor_loss_db,
    )

    if pr < node.min_rx_dbm:
        return None  # ★ Node별 최소 수신 레벨 하한선 미달 - SF 판정 이전에 바로 탈락시킴

    snr = snr_db(pr, bandwidth_hz, receiver_noise_figure_db)
    sf = select_sf(snr)

    if sf is None:
        return None

    return ConnectionResult(
        gw_id=gw.gw_id, node_id=node.node_id,
        path_loss_db=pl, rx_power_dbm=pr, snr_db=snr, sf=sf,
    )


def _build_candidate_pool(nodes: list[NodeSite], coords: np.ndarray, pool_size: int, dem) -> list[GatewaySite]:
    """
    K-means로 GW 후보를 pool_size개 뽑음 (이번 한 번만 실행 - 최적화 루프 안에서 반복 안 함).
    설치 불가 지역(저지대/수면 등)이면 같은 클러스터 소속 Node 중 가장 가까운 지점으로 이동.
    """
    km = KMeans(n_clusters=pool_size, random_state=42, n_init=10).fit(coords)
    candidates = []

    for cluster_idx, center_xy in enumerate(km.cluster_centers_):
        lat, lon = xy_to_latlon(center_xy[0], center_xy[1])

        if not dem.is_installable(lat, lon):
            member_indices = np.where(km.labels_ == cluster_idx)[0]
            member_coords = coords[member_indices]
            dists = np.linalg.norm(member_coords - center_xy, axis=1)
            nearest_local_idx = member_indices[np.argmin(dists)]
            nearest_node = nodes[nearest_local_idx]
            lat, lon = nearest_node.lat, nearest_node.lon

        candidates.append(GatewaySite(
            gw_id=f"OPT_GW_{cluster_idx:03d}",
            region="", location_desc="K-means 최적화 후보지",
            lat=lat, lon=lon,
            install_type="optimizer_candidate", power_source="TBD",
            source_sheet="gw_placement_optimizer",
        ))

    return candidates


def _compute_link_matrix(
    candidates: list[GatewaySite], nodes: list[NodeSite], dem,
    fc_mhz: float, environment: str, max_path_loss_db: float, **link_kwargs,
) -> dict:
    """
    후보 GW 전체 × Node 전체 조합의 연결가능여부를 딱 한 번 계산해서 매트릭스로 만듦.
    이게 이번 리팩터링의 핵심임 - 이 함수는 최적화 과정에서 정확히 한 번만 호출됨.

    반환값: {gw_id: {node_id: ConnectionResult | None}} 형태의 중첩 딕셔너리임.
    """
    matrix = {}
    for gw in candidates:
        row = {}
        for node in nodes:
            row[node.node_id] = evaluate_connection(
                gw, node, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs
            )
        matrix[gw.gw_id] = row
    return matrix


def _greedy_select(
    candidates: list[GatewaySite], nodes: list[NodeSite], matrix: dict,
    initial_k: int, max_k: int, coverage_target: float,
) -> tuple[list[GatewaySite], dict, float]:
    """
    탐욕 알고리즘(greedy set cover)으로 최소 개수의 GW를 골라냄.
    매 스텝마다 "아직 안 커버된 Node를 가장 많이 새로 커버하는 후보"를 하나씩 고름.

    이 함수는 이미 계산된 matrix 안의 숫자를 비교만 하는 거라 DEM/전파모델 재계산이
    전혀 없음 - 그래서 매우 빠름. initial_k는 "최소 이만큼은 배치해본다"는 하한선이고,
    그 이후부터 목표 커버리지 달성 여부를 확인함.
    """
    node_ids = [n.node_id for n in nodes]
    uncovered = set(node_ids)
    remaining_candidates = list(candidates)
    chosen: list[GatewaySite] = []

    while remaining_candidates and len(chosen) < max_k:
        best_gw = None
        best_newly_covered: set = set()

        for gw in remaining_candidates:
            newly_covered = {nid for nid in uncovered if matrix[gw.gw_id].get(nid) is not None}
            if len(newly_covered) > len(best_newly_covered):
                best_gw = gw
                best_newly_covered = newly_covered

        if best_gw is None or not best_newly_covered:
            break  # 남은 후보 중 어느 것도 미커버 Node를 더 커버 못 함 - 더 늘려도 소용없음

        chosen.append(best_gw)
        remaining_candidates.remove(best_gw)
        uncovered -= best_newly_covered

        covered_count = len(node_ids) - len(uncovered)
        coverage_ratio = covered_count / len(node_ids) if node_ids else 0.0

        if len(chosen) >= initial_k and coverage_ratio >= coverage_target:
            break

    # 최종 연결 결과: 각 Node에 대해 선택된 GW들 중 경로손실이 가장 낮은 연결을 채택
    connections = {}
    node_gw_ids: dict[str, list[str]] = {}
    connected_count = 0
    for node in nodes:
        best_conn: Optional[ConnectionResult] = None
        receiving_gw_ids: list[str] = []
        for gw in chosen:
            conn = matrix[gw.gw_id].get(node.node_id)
            if conn is None:
                continue
            receiving_gw_ids.append(gw.gw_id)
            if best_conn is None or conn.path_loss_db < best_conn.path_loss_db:
                best_conn = conn
        connections[node.node_id] = best_conn
        node_gw_ids[node.node_id] = receiving_gw_ids
        if best_conn is not None:
            connected_count += 1

    coverage_ratio = connected_count / len(nodes) if nodes else 0.0
    return chosen, connections, node_gw_ids, coverage_ratio


def optimize_gw_placement(
    nodes: list[NodeSite], dem,
    initial_k: int = 1, max_k: int = 20, coverage_target: float = 0.95,
    fc_mhz: float = 920.0, environment: str = "urban",
    max_path_loss_db: float = DEFAULT_MAX_PATH_LOSS_DB,
    candidate_pool_multiplier: int = 3,  # ★ 추가: 후보 풀을 max_k보다 넉넉하게 뽑기 위한 배수
    **link_kwargs,
) -> OptimizationResult:
    """
    GW 최적 배치 메인 함수임.

    ★ 이번에 바뀐 부분: 예전엔 K를 늘려가며 매번 K-means + 경로손실 계산을 반복했는데,
    지금은 후보 풀을 한 번만 뽑고(_build_candidate_pool), 경로손실도 한 번만 계산해서
    (_compute_link_matrix), 그 결과 위에서 탐욕 선택(_greedy_select)만 반복함.
    최종 결과(어떤 GW가 몇 개 선택되고 커버리지가 얼마인지)는 기존과 동일한 의미를 갖되,
    계산량은 훨씬 줄어듦.
    """
    if not nodes:
        raise ValueError("nodes가 비어있음 - 최적화할 대상이 없음")

    coords = np.array([latlon_to_xy(n.lat, n.lon) for n in nodes])
    pool_size = min(max_k * candidate_pool_multiplier, len(nodes))

    candidates = _build_candidate_pool(nodes, coords, pool_size, dem)
    matrix = _compute_link_matrix(candidates, nodes, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs)
    chosen, connections, node_gw_ids, coverage_ratio = _greedy_select(
        candidates, nodes, matrix, initial_k, max_k, coverage_target
    )

    return OptimizationResult(
        gateways=chosen, connections=connections, node_gw_ids=node_gw_ids,
        coverage_ratio=coverage_ratio, k=len(chosen),
        target_met=coverage_ratio >= coverage_target,
    )
    

def _connections_from_chosen(chosen: list[GatewaySite], nodes: list[NodeSite], matrix: dict) -> tuple[dict, dict, float]:
    """
    선택된 GW 집합(chosen)과 매트릭스가 주어졌을 때, 각 Node의 최적 연결을 뽑아내는 공용 함수임.
    _greedy_select 끝부분에서 하던 걸 여기로 빼서, evaluate_and_augment에서도 재사용함
    (같은 로직을 두 군데서 따로 짜면 나중에 한쪽만 고치는 실수가 나기 쉬워서 공용화함).
    """
    connections = {}
    node_gw_ids: dict[str, list[str]] = {}
    connected_count = 0

    for node in nodes:
        best_conn: Optional[ConnectionResult] = None
        receiving_gw_ids: list[str] = []
        for gw in chosen:
            conn = matrix.get(gw.gw_id, {}).get(node.node_id)
            if conn is None:
                continue
            receiving_gw_ids.append(gw.gw_id)
            if best_conn is None or conn.path_loss_db < best_conn.path_loss_db:
                best_conn = conn
        connections[node.node_id] = best_conn
        node_gw_ids[node.node_id] = receiving_gw_ids
        if best_conn is not None:
            connected_count += 1

    coverage_ratio = connected_count / len(nodes) if nodes else 0.0
    return connections, node_gw_ids, coverage_ratio


def evaluate_and_augment(
    nodes: list[NodeSite],
    existing_gateways: list[GatewaySite],
    dem,
    max_additional: int = 15,
    coverage_target: float = 0.95,
    fc_mhz: float = 920.0,
    environment: str = "urban",
    max_path_loss_db: float = DEFAULT_MAX_PATH_LOSS_DB,
    candidate_pool_multiplier: int = 3,
    **link_kwargs,
) -> OptimizationResult:
    """
    문서 요청사항 2번+3번을 합친 함수임:
      1) 기존에 이미 설치된 GW(existing_gateways)들로 커버리지를 먼저 계산함 - 검증 단계.
      2) 목표 커버리지(coverage_target) 이미 달성했으면 그대로 반환함 (추가 배치 없음
         -> 이게 순수 "검증" 케이스, 2번 요구사항).
      3) 미달이면, 미커버 Node들 위치 기준으로 K-means 후보를 새로 뽑아서, 부족한 만큼만
         탐욕 선택으로 추가 GW를 골라 기존 GW 목록에 더함 (기존 GW는 절대 빼거나 옮기지 않음
         -> 3번 요구사항인 "기존은 고정, 부족한 곳만 증설").

    기존 GW들은 위치/개수가 그대로 유지된다는 게 핵심 - K-means/탐욕선택은 오직
    "추가로 놓을 위치"를 찾는 데만 쓰임.
    """
    if not nodes:
        raise ValueError("nodes가 비어있음 - 평가할 대상이 없음")

    # 1) 기존 GW로 커버리지 검증
    existing_matrix = _compute_link_matrix(
        existing_gateways, nodes, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs
    )
    connections, node_gw_ids, coverage_ratio = _connections_from_chosen(existing_gateways, nodes, existing_matrix)

    if coverage_ratio >= coverage_target or max_additional <= 0:
        # 이미 목표 달성 -> 추가 배치 없이 검증 결과만 반환함 (2번 케이스)
        return OptimizationResult(
            gateways=list(existing_gateways), connections=connections, node_gw_ids=node_gw_ids,
            coverage_ratio=coverage_ratio, k=len(existing_gateways),
            target_met=coverage_ratio >= coverage_target,
        )

    # 2) 미커버 Node 위치 기준으로 추가 후보 풀 생성
    uncovered_nodes = [n for n in nodes if connections.get(n.node_id) is None]
    coords = np.array([latlon_to_xy(n.lat, n.lon) for n in uncovered_nodes])
    pool_size = max(1, min(max_additional * candidate_pool_multiplier, len(uncovered_nodes)))
    candidates = _build_candidate_pool(uncovered_nodes, coords, pool_size, dem)

    # 3) 후보들과 전체 Node 사이 매트릭스 계산 (전체로 계산하는 이유: 추가 GW가
    #    이미 커버된 Node의 신호품질/다이버시티도 개선할 수 있어서, node_gw_ids 집계에 반영되게 함)
    add_matrix = _compute_link_matrix(candidates, nodes, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs)

    # 4) 탐욕 선택 - 아직 안 커버된 Node만 기준으로 추가 GW를 골라나감
    remaining_uncovered = {nid for nid, c in connections.items() if c is None}
    remaining_candidates = list(candidates)
    chosen_additional: list[GatewaySite] = []

    while remaining_candidates and len(chosen_additional) < max_additional and remaining_uncovered:
        best_gw = None
        best_newly_covered: set = set()

        for gw in remaining_candidates:
            newly_covered = {nid for nid in remaining_uncovered if add_matrix[gw.gw_id].get(nid) is not None}
            if len(newly_covered) > len(best_newly_covered):
                best_gw = gw
                best_newly_covered = newly_covered

        if best_gw is None or not best_newly_covered:
            break  # 남은 후보 어느 것도 미커버 Node를 더 커버 못 함

        chosen_additional.append(best_gw)
        remaining_candidates.remove(best_gw)
        remaining_uncovered -= best_newly_covered

        covered_count = len(nodes) - len(remaining_uncovered)
        if covered_count / len(nodes) >= coverage_target:
            break

    # 5) 기존 GW + 추가 GW를 합쳐서 최종 연결/커버리지 재계산
    final_gateways = list(existing_gateways) + chosen_additional
    combined_matrix = dict(existing_matrix)
    combined_matrix.update(add_matrix)
    connections, node_gw_ids, coverage_ratio = _connections_from_chosen(final_gateways, nodes, combined_matrix)

    return OptimizationResult(
        gateways=final_gateways, connections=connections, node_gw_ids=node_gw_ids,
        coverage_ratio=coverage_ratio, k=len(final_gateways),
        target_met=coverage_ratio >= coverage_target,
    )


def evaluate_gateways_coverage(
    nodes: list[NodeSite],
    gateways: list[GatewaySite],
    dem,
    fc_mhz: float = 920.0,
    environment: str = "urban",
    max_path_loss_db: float = DEFAULT_MAX_PATH_LOSS_DB,
    **link_kwargs,
) -> OptimizationResult:
    """
    지정한 GW들(gateways)만 기준으로 전체 Node의 커버리지를 평가함. 최적화나
    K-means 없이 "이 GW들만 있다면 어떻게 되는가"를 그대로 계산하는 함수임.

    지도에서 GW를 몇 개 선택해서 '선택 커버리지'를 볼 때 씀 - 이 결과로
    Node 마커를 색칠하면, 방금 선택한 GW 기준의 실제 연결 여부가 반영됨
    (예전엔 이전에 실행했던 전체 최적화 결과를 그대로 재활용해서, 선택한
    GW랑 안 맞는 정보가 표시되는 문제가 있었음).
    """
    if not nodes:
        raise ValueError("nodes가 비어있음 - 평가할 대상이 없음")

    matrix = _compute_link_matrix(gateways, nodes, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs)
    connections, node_gw_ids, coverage_ratio = _connections_from_chosen(gateways, nodes, matrix)

    return OptimizationResult(
        gateways=list(gateways), connections=connections, node_gw_ids=node_gw_ids,
        coverage_ratio=coverage_ratio, k=len(gateways),
        target_met=coverage_ratio >= 1.0,  # 이 뷰에서는 목표치 개념이 없어서 100% 여부만 참고용으로 표시
    )
    

def test_node_site_default_min_rx_dbm_is_minus_100():
    """
    NodeSite의 min_rx_dbm 기본값이 -100dBm으로 고정되어 있는지 확인함
    (요청에 따라 -126.6에서 변경됨) - 여전히 개별 Node마다 다르게 설정 가능함.
    """
    from lorascape.data.schema import NodeSite
    node = NodeSite(
        node_id="TEST", region="", location_desc="",
        lat=37.4, lon=127.1, device_type="", install_type="",
    )
    assert node.min_rx_dbm == -100.0