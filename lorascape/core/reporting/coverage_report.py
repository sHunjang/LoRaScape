# lorascape/core/reporting/coverage_report.py
"""
GW 배치 검증 결과(OptimizationResult)를 'GW별 / 단말별 / 미커버 단말' 보고서 데이터로 집계함.
Qt에 의존하지 않음 - 보고서 창(ReportWindow)과 내보내기(엑셀/CSV/PDF)가 이 결과를 그대로 씀.

'연결'과 '수신'을 구분함:
  - 연결(connected): 그 단말이 실제로 붙는 GW (단말 1개당 GW 1개). GW별 연결 단말을 다 더하면 커버된 단말 수와 같음.
  - 수신(receivable): 그 GW의 신호가 닿는 단말 (여러 GW에 겹쳐 셈). 연결되지 않고 수신만 되는 경우가 '수신만'임.

미커버 단말은 결과에 사유가 저장돼 있지 않아서, 각 GW에 대해 evaluate_connection과 같은 순서로
다시 판정해서(diagnose_link) 가장 신호가 좋은 GW 기준으로 사유를 분류함.

전파 모델(propagation_model)은 검증 때 쓴 것과 같은 값을 넘겨야 함 - 다르면 결과(연결 정보)는
한 모델로, '수신만'/미커버 사유는 다른 모델로 계산돼서 보고서가 서로 어긋남.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from lorascape.data.coord_transform import distance_m
from lorascape.core.linkbudget.link_budget import rx_power_dbm, snr_db, select_sf
from lorascape.core.optimization.gw_placement import (
    DEFAULT_MAX_PATH_LOSS_DB, compute_total_path_loss, evaluate_connection,
)

SF_LEVELS = (7, 8, 9, 10, 11, 12)

RELATION_CONNECTED = "연결"
RELATION_RECEIVE_ONLY = "수신만"

REASON_LABELS = {
    "path_loss": "경로손실 한계 초과",
    "min_rx": "최소 수신 레벨 미달",
    "snr": "SNR 미달",
    "no_gw": "활성 GW 없음",
    "mismatch": "판정 불일치(재검증 필요)",
}


@dataclass
class LinkRow:
    """GW 하나와 단말 하나의 관계 한 줄임."""
    node_id: str
    device_type: str
    region: str
    location_desc: str
    relation: str                  # RELATION_CONNECTED | RELATION_RECEIVE_ONLY
    distance_km: float
    rx_power_dbm: float
    snr_db: float
    sf: int


@dataclass
class GwRow:
    gw_id: str
    region: str
    location_desc: str
    lat: float
    lon: float
    connected: int
    receivable: int                # 연결 + 수신만
    shared: int                    # 연결 단말 중 다른 GW에서도 수신되는 수
    sf_counts: dict = field(default_factory=dict)      # {7: n, ..., 12: n} (연결 단말 기준)
    avg_rx_dbm: Optional[float] = None                 # 연결 단말 평균 수신전력
    type_counts: dict = field(default_factory=dict)    # {유형: 연결 단말 수}, 많은 순
    links: list = field(default_factory=list)          # list[LinkRow], 거리 순


@dataclass
class NodeRow:
    node_id: str
    device_type: str
    region: str
    location_desc: str
    covered: bool
    gw_id: str                     # 연결 GW, 미커버면 ""
    rx_power_dbm: Optional[float]
    sf: Optional[int]
    receiving_gws: int


@dataclass
class UncoveredRow:
    node_id: str
    device_type: str
    region: str
    location_desc: str
    best_gw_id: str                # 수신 신호가 가장 좋은 GW (없으면 "")
    distance_km: Optional[float]
    best_rx_dbm: Optional[float]
    reason_code: str
    reason_label: str
    reason_detail: str


@dataclass
class CoverageReport:
    generated_at: str
    params: dict
    total_nodes: int
    covered_nodes: int
    uncovered_nodes: int
    coverage_ratio: float
    coverage_target: float
    target_met: bool
    gw_count: int
    reason_counts: dict = field(default_factory=dict)  # {reason_code: 개수}
    gw_rows: list = field(default_factory=list)
    node_rows: list = field(default_factory=list)
    uncovered_rows: list = field(default_factory=list)


@dataclass
class LinkDiagnosis:
    reason_code: Optional[str]     # None이면 연결 가능
    path_loss_db: float
    rx_power_dbm: float
    snr_db: float
    sf: Optional[int]


def diagnose_link(gw, node, dem, *, fc_mhz=920.0, environment="urban",
                  max_path_loss_db=DEFAULT_MAX_PATH_LOSS_DB, bandwidth_hz=125_000,
                  receiver_noise_figure_db=6.0, propagation_model="song") -> LinkDiagnosis:
    """
    GW-단말 한 쌍이 왜 연결되거나 안 되는지 판정함. evaluate_connection과 같은 순서
    (경로손실 한계 -> 단말 최소 수신 레벨 -> SF/SNR)로 검사하고, 실패해도 수치는 계산해서 돌려줌.
    """
    pl = compute_total_path_loss(gw, node, dem, fc_mhz=fc_mhz, environment=environment,
                                 propagation_model=propagation_model)
    pr = rx_power_dbm(
        gw.tx_power_dbm, gw.antenna_gain_dbi, gw.cable_loss_db, pl,
        node.antenna_gain_dbi, node.cable_loss_db, indoor_penetration_loss_db=node.indoor_loss_db,
    )
    snr = snr_db(pr, bandwidth_hz, receiver_noise_figure_db)
    sf = select_sf(snr)

    if pl > max_path_loss_db:
        code = "path_loss"
    elif pr < node.min_rx_dbm:
        code = "min_rx"
    elif sf is None:
        code = "snr"
    else:
        code = None
    return LinkDiagnosis(code, pl, pr, snr, sf)


def _reason_detail(code: str, node, d: LinkDiagnosis, max_path_loss_db: float) -> str:
    if code == "path_loss":
        return f"경로손실 {d.path_loss_db:.1f} dB > 한계 {max_path_loss_db:.0f} dB"
    if code == "min_rx":
        return f"수신 {d.rx_power_dbm:.1f} dBm < 기준 {node.min_rx_dbm:.0f} dBm"
    if code == "snr":
        return f"SNR {d.snr_db:.1f} dB (SF12 한계 미달)"
    if code == "no_gw":
        return "평가할 GW가 없음"
    return "현재 설정으로는 연결 가능 - 검증을 다시 실행하세요"


def _diagnose_uncovered(node, gws, dem, link_kw, max_path_loss_db) -> UncoveredRow:
    best_gw, best = None, None
    for gw in gws:
        d = diagnose_link(gw, node, dem, **link_kw)
        if best is None or d.rx_power_dbm > best.rx_power_dbm:
            best_gw, best = gw, d

    if best is None:
        code = "no_gw"
        return UncoveredRow(node.node_id, node.device_type, node.region, node.location_desc,
                            "", None, None, code, REASON_LABELS[code],
                            _reason_detail(code, node, None, max_path_loss_db))

    code = best.reason_code or "mismatch"
    dist_km = distance_m(best_gw.lat, best_gw.lon, node.lat, node.lon) / 1000.0
    return UncoveredRow(node.node_id, node.device_type, node.region, node.location_desc,
                        best_gw.gw_id, dist_km, best.rx_power_dbm, code, REASON_LABELS[code],
                        _reason_detail(code, node, best, max_path_loss_db))


def build_coverage_report(result, nodes, dem, *, fc_mhz=920.0, environment="urban",
                          max_path_loss_db=DEFAULT_MAX_PATH_LOSS_DB, bandwidth_hz=125_000,
                          receiver_noise_figure_db=6.0, coverage_target=0.9,
                          propagation_model="song",
                          now: Optional[datetime] = None) -> CoverageReport:
    """
    result: OptimizationResult (evaluate_gateways_coverage 결과)
    nodes:  NodeSite 목록 - 유형/지역/상세위치/좌표를 얻기 위해 필요함. result에 없는 단말은 제외함.
    dem:    '수신만' 관계의 수신전력과 미커버 사유를 다시 계산하는 데 씀 (get_elevation_profile 필요).
    propagation_model: result를 만들 때 쓴 전파 모델과 같아야 함.
    """
    link_kw = dict(fc_mhz=fc_mhz, environment=environment, max_path_loss_db=max_path_loss_db,
                   bandwidth_hz=bandwidth_hz, receiver_noise_figure_db=receiver_noise_figure_db,
                   propagation_model=propagation_model)

    gws = list(result.gateways)
    gw_by_id = {g.gw_id: g for g in gws}
    evaluated = [n for n in nodes if n.node_id in result.connections]

    links_by_gw = {g.gw_id: [] for g in gws}
    receiving_count = {}
    node_rows, uncovered_rows = [], []

    for node in evaluated:
        conn = result.connections.get(node.node_id)
        receiving = set(result.node_gw_ids.get(node.node_id, []))
        if conn is not None:
            receiving.add(conn.gw_id)
        receiving &= set(gw_by_id)
        receiving_count[node.node_id] = len(receiving)

        for gid in sorted(receiving):
            gw = gw_by_id[gid]
            dist_km = distance_m(gw.lat, gw.lon, node.lat, node.lon) / 1000.0
            if conn is not None and conn.gw_id == gid:
                c, relation = conn, RELATION_CONNECTED
            else:
                c = evaluate_connection(gw, node, dem, **link_kw)
                if c is None:
                    continue
                relation = RELATION_RECEIVE_ONLY
            links_by_gw[gid].append(LinkRow(
                node.node_id, node.device_type, node.region, node.location_desc,
                relation, dist_km, c.rx_power_dbm, c.snr_db, c.sf,
            ))

        if conn is not None:
            node_rows.append(NodeRow(node.node_id, node.device_type, node.region, node.location_desc,
                                     True, conn.gw_id, conn.rx_power_dbm, conn.sf, len(receiving)))
        else:
            node_rows.append(NodeRow(node.node_id, node.device_type, node.region, node.location_desc,
                                     False, "", None, None, len(receiving)))
            uncovered_rows.append(_diagnose_uncovered(node, gws, dem, link_kw, max_path_loss_db))

    gw_rows = []
    for gw in gws:
        links = sorted(links_by_gw[gw.gw_id], key=lambda l: l.distance_km)
        connected = [l for l in links if l.relation == RELATION_CONNECTED]
        sf_counts = {sf: sum(1 for l in connected if l.sf == sf) for sf in SF_LEVELS}
        type_counts = dict(Counter(l.device_type for l in connected).most_common())
        avg_rx = (sum(l.rx_power_dbm for l in connected) / len(connected)) if connected else None
        shared = sum(1 for l in connected if receiving_count.get(l.node_id, 0) >= 2)
        gw_rows.append(GwRow(
            gw.gw_id, gw.region, gw.location_desc, gw.lat, gw.lon,
            len(connected), len(links), shared, sf_counts, avg_rx, type_counts, links,
        ))

    total = len(evaluated)
    covered = sum(1 for r in node_rows if r.covered)
    ratio = covered / total if total else 0.0

    return CoverageReport(
        generated_at=(now or datetime.now()).strftime("%Y-%m-%d %H:%M"),
        params=dict(link_kw),
        total_nodes=total, covered_nodes=covered, uncovered_nodes=total - covered,
        coverage_ratio=ratio, coverage_target=coverage_target,
        target_met=ratio >= coverage_target, gw_count=len(gws),
        reason_counts=dict(Counter(u.reason_code for u in uncovered_rows)),
        gw_rows=gw_rows, node_rows=node_rows, uncovered_rows=uncovered_rows,
    )
