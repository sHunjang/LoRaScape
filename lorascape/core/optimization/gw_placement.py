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
    connections: dict[str, Optional[ConnectionResult]]
    coverage_ratio: float
    k: int
    target_met: bool


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
    """GW 하나와 Node 하나 사이 연결 가능 여부 판정. gw/node 객체의 무선 파라미터를 기본으로 씀."""
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
    connected_count = 0
    for node in nodes:
        best_conn: Optional[ConnectionResult] = None
        for gw in chosen:
            conn = matrix[gw.gw_id].get(node.node_id)
            if conn is None:
                continue
            if best_conn is None or conn.path_loss_db < best_conn.path_loss_db:
                best_conn = conn
        connections[node.node_id] = best_conn
        if best_conn is not None:
            connected_count += 1

    coverage_ratio = connected_count / len(nodes) if nodes else 0.0
    return chosen, connections, coverage_ratio


def optimize_gw_placement(
    nodes: list[NodeSite], dem,
    initial_k: int = 1, max_k: int = 15, coverage_target: float = 0.95,
    fc_mhz: float = 920.0, environment: str = "urban",
    max_path_loss_db: float = DEFAULT_MAX_PATH_LOSS_DB,
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
    pool_size = min(max_k, len(nodes))

    candidates = _build_candidate_pool(nodes, coords, pool_size, dem)
    matrix = _compute_link_matrix(candidates, nodes, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs)
    chosen, connections, coverage_ratio = _greedy_select(candidates, nodes, matrix, initial_k, max_k, coverage_target)

    return OptimizationResult(
        gateways=chosen, connections=connections,
        coverage_ratio=coverage_ratio, k=len(chosen),
        target_met=coverage_ratio >= coverage_target,
    )