# lorascape/core/optimization/gw_placement.py
"""
GW(게이트웨이) 위치 최적화 모듈임 (문서에서 "AI 기반 최적화"라고 잘못 불렸던 그거 -
실제로는 K-means + 제약조건 반복 탐색이라 이 이름 그대로 감).

지금까지 만든 모든 계산 모듈(좌표변환, DEM, Song's Model, Deygout, 링크버짓)을
여기서 처음으로 한데 엮음. 흐름은 이럼:

  1. Node들의 위경도를 평면좌표로 변환
  2. K-means로 K개 클러스터 중심(=GW 후보 위치) 산출
  3. 각 후보 위치가 DEM상 설치 가능한 지형인지 확인, 아니면 클러스터 내 가장 가까운
     유효 지점(=실제 Node 위치)으로 이동
  4. 이 GW 후보들로 전체 Node의 커버리지(연결 가능 여부)를 계산
     (Song's Model + Deygout으로 PL 구하고, 링크버짓으로 실제 연결 가능한지 판정)
  5. 커버리지 목표 미달이면 K를 1 늘려서 2번부터 반복
  6. 목표 달성하거나 K가 상한에 도달하면 종료
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from sklearn.cluster import KMeans

from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.data.coord_transform import latlon_to_xy, xy_to_latlon, distance_m
from lorascape.core.propagation.song_model import path_loss as song_path_loss
from lorascape.core.diffraction.deygout import deygout_recursive
from lorascape.core.linkbudget.link_budget import rx_power_dbm, snr_db, select_sf

# 문서 3번 요구사항: Path Loss 140dB를 넘으면 제약조건 위반으로 취급함.
DEFAULT_MAX_PATH_LOSS_DB = 140.0

# Deygout 회절손실은 "순수 지형 회절분만 최대 30dB 이내로 캡핑"하라는 문서 2번 옵션을 그대로 적용함.
DEYGOUT_LOSS_CAP_DB = 30.0


@dataclass
class ConnectionResult:
    """Node 하나가 특정 GW에 연결됐을 때의 상세 결과임."""
    gw_id: str
    node_id: str
    path_loss_db: float
    rx_power_dbm: float
    snr_db: float
    sf: int  # 이 연결에서 쓸 수 있는 Spreading Factor


@dataclass
class OptimizationResult:
    """최적화 한 번 돌린 결과 전체임."""
    gateways: list[GatewaySite]
    connections: dict[str, Optional[ConnectionResult]]  # node_id -> 가장 좋은 연결 (없으면 None)
    coverage_ratio: float
    k: int
    target_met: bool


def compute_total_path_loss(
    gw: GatewaySite,
    node: NodeSite,
    dem,  # DemLoader 인터페이스(get_elevation_profile 메서드)를 만족하는 아무 객체나 받음
    fc_mhz: float = 920.0,
    environment: str = "urban",
    n_profile_samples: int = 20,
) -> float:
    """
    GW-Node 사이 최종 경로손실을 계산함. Song's Model(기본 전파손실) + Deygout(지형 회절손실)을 합침.

    dem 파라미터를 DemLoader 클래스로 못박지 않고 '인터페이스'로 받는 이유:
    실제 DEM 파일 없이도 단위테스트할 수 있게 하려고 - 테스트에서는 평지 지형을 가짜로
    반환하는 스텁 객체를 넣으면 됨 (tests/test_gw_placement.py 참고).
    """
    d_km = distance_m(gw.lat, gw.lon, node.lat, node.lon) / 1000.0
    if d_km <= 0:
        d_km = 0.001  # 거리 0이면 log10(0)에서 에러 나니까 최소값으로 방어함 (거의 안 일어날 케이스)

    base_pl = song_path_loss(fc_mhz, gw.antenna_height_m, node.antenna_height_m, d_km, environment)

    profile = dem.get_elevation_profile(gw.lat, gw.lon, node.lat, node.lon, n_profile_samples)
    diffraction_loss = deygout_recursive(
        profile, fc_mhz, tx_height=gw.antenna_height_m, rx_height=node.antenna_height_m
    )
    diffraction_loss_capped = min(diffraction_loss, DEYGOUT_LOSS_CAP_DB)

    return base_pl + diffraction_loss_capped


def evaluate_connection(
    gw: GatewaySite,
    node: NodeSite,
    dem,
    fc_mhz: float = 920.0,
    environment: str = "urban",
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
    GW 하나와 Node 하나 사이 연결 가능 여부를 판정함.

    무선 파라미터(tx_power_dbm 등)를 None으로 두면 gw/node 객체에 저장된 값을 그대로 씀
    (GUI에서 사용자가 개별 GW/Node의 파라미터를 고쳐두면 그 값이 자동으로 반영되는 구조).
    호출부에서 명시적으로 값을 넘기면 그 값이 우선함 - 일회성 시뮬레이션(예: "이 GW 출력을
    20dBm으로 올리면 어떻게 될까?" 같은 what-if 분석)에 쓸 수 있게 남겨둔 여지임.
    """
    pl = compute_total_path_loss(gw, node, dem, fc_mhz, environment)

    if pl > max_path_loss_db:
        return None  # 문서 3번 제약조건: Path Loss <= 140dB

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
        return None  # 어떤 SF로도 연결 불가능한 신호 세기

    return ConnectionResult(
        gw_id=gw.gw_id, node_id=node.node_id,
        path_loss_db=pl, rx_power_dbm=pr, snr_db=snr, sf=sf,
    )


def _build_candidates(nodes: list[NodeSite], coords: np.ndarray, k: int, dem) -> list[GatewaySite]:
    """
    K-means 돌려서 GW 후보 K개를 만듦. 각 후보가 설치 불가 지역(저지대/수면 등)이면
    같은 클러스터에 속한 Node 중 가장 가까운 곳으로 위치를 옮김 (문서 3번 절차 4단계 그대로).
    """
    km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(coords)
    candidates = []

    for cluster_idx, center_xy in enumerate(km.cluster_centers_):
        lat, lon = xy_to_latlon(center_xy[0], center_xy[1])

        if not dem.is_installable(lat, lon):
            # 설치 불가 지역이면 같은 클러스터 소속 Node 중 가장 가까운 지점으로 이동함
            member_indices = np.where(km.labels_ == cluster_idx)[0]
            member_coords = coords[member_indices]
            dists = np.linalg.norm(member_coords - center_xy, axis=1)
            nearest_local_idx = member_indices[np.argmin(dists)]
            nearest_node = nodes[nearest_local_idx]
            lat, lon = nearest_node.lat, nearest_node.lon

        candidates.append(GatewaySite(
            gw_id=f"OPT_GW_{cluster_idx:03d}",
            region="",
            location_desc="K-means 최적화 후보지",
            lat=lat, lon=lon,
            install_type="optimizer_candidate",  # 아직 실제 설치방식 결정 안 됨을 표시
            power_source="TBD",
            source_sheet="gw_placement_optimizer",
        ))

    return candidates


def _evaluate_coverage(
    candidates: list[GatewaySite],
    nodes: list[NodeSite],
    dem,
    fc_mhz: float,
    environment: str,
    max_path_loss_db: float,
    **link_kwargs,
) -> tuple[dict, float]:
    """
    후보 GW들로 전체 Node의 커버리지를 계산함.
    Node 하나당 여러 GW에 연결 시도해보고, 그중 Path Loss가 가장 낮은(=가장 좋은) 연결을 채택함.
    (매크로 다이버시티 합산까지는 여기서 안 하고, 일단 '연결 가능한 GW가 하나라도 있는가'만 봄 -
     다이버시티 결합은 커버리지 확정 이후 신호품질 개선 단계에서 별도로 쓰면 됨.)
    """
    connections = {}
    connected_count = 0

    for node in nodes:
        best: Optional[ConnectionResult] = None
        for gw in candidates:
            result = evaluate_connection(gw, node, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs)
            if result is None:
                continue
            if best is None or result.path_loss_db < best.path_loss_db:
                best = result

        connections[node.node_id] = best
        if best is not None:
            connected_count += 1

    coverage_ratio = connected_count / len(nodes) if nodes else 0.0
    return connections, coverage_ratio


def optimize_gw_placement(
    nodes: list[NodeSite],
    dem,
    initial_k: int = 1,
    max_k: int = 15,
    coverage_target: float = 0.95,
    fc_mhz: float = 920.0,
    environment: str = "urban",
    max_path_loss_db: float = DEFAULT_MAX_PATH_LOSS_DB,
    **link_kwargs,
) -> OptimizationResult:
    """
    GW 최적 배치 메인 함수임. K를 늘려가며 커버리지 목표(기본 95%) 달성할 때까지 반복함.

    dem: DemLoader 인스턴스(또는 같은 인터페이스를 만족하는 테스트용 스텁)임.
    max_k에 도달했는데도 목표를 못 채우면, 그 시점까지의 최선 결과를 target_met=False로 반환함
    (에러를 던지지 않는 이유: 호출부에서 "이 지역은 GW를 아무리 늘려도 한계가 있다"는
     판단 정보로 쓸 수 있게 하려고 - 실패가 아니라 유용한 결과임).
    """
    if not nodes:
        raise ValueError("nodes가 비어있음 - 최적화할 대상이 없음")

    coords = np.array([latlon_to_xy(n.lat, n.lon) for n in nodes])

    k = initial_k
    last_result = None

    while k <= max_k:
        candidates = _build_candidates(nodes, coords, k, dem)
        connections, coverage_ratio = _evaluate_coverage(
            candidates, nodes, dem, fc_mhz, environment, max_path_loss_db, **link_kwargs
        )

        last_result = OptimizationResult(
            gateways=candidates, connections=connections,
            coverage_ratio=coverage_ratio, k=k, target_met=coverage_ratio >= coverage_target,
        )

        if last_result.target_met:
            return last_result

        k += 1

    # max_k까지 다 돌았는데도 목표 미달 - 그래도 마지막 결과는 반환함 (호출부가 판단하게)
    return last_result