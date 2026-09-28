"""coverage_report.py 검증 테스트임 (Qt 불필요)."""
import pytest

from lorascape.data.coord_transform import distance_m
from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.core.optimization.gw_placement import evaluate_connection, evaluate_gateways_coverage
from lorascape.core.reporting.coverage_report import (
    build_coverage_report, diagnose_link, RELATION_CONNECTED, RELATION_RECEIVE_ONLY,
)


class FakeFlatDem:
    """평지(장애물 없음) 가짜 DEM - 기존 test_gw_placement의 것과 같은 형태임."""

    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=20):
        total = distance_m(lat1, lon1, lat2, lon2)
        return [(total * i / n_samples, 50.0) for i in range(n_samples + 1)]


def gw(gw_id, lat, lon):
    return GatewaySite(gw_id=gw_id, region="탄천", location_desc=f"{gw_id} 위치", lat=lat, lon=lon,
                       install_type="테스트", power_source="테스트")


def node(node_id, lat, lon, device_type="센서", **kw):
    return NodeSite(node_id=node_id, region="탄천", location_desc="", lat=lat, lon=lon,
                    device_type=device_type, install_type="테스트", **kw)


def make_report(gateways, nodes, **kw):
    dem = FakeFlatDem()
    result = evaluate_gateways_coverage(nodes, gateways, dem)
    return build_coverage_report(result, nodes, dem, **kw), result


def test_summary_counts_and_uncovered_far_node():
    gws = [gw("G1", 37.4000, 127.1200)]
    nodes = [node("N1", 37.4001, 127.1201), node("N2", 38.50, 127.12)]   # N2는 100km 이상 떨어짐
    rep, _ = make_report(gws, nodes)
    assert (rep.total_nodes, rep.covered_nodes, rep.uncovered_nodes) == (2, 1, 1)
    assert rep.coverage_ratio == 0.5
    assert rep.gw_rows[0].connected == 1
    assert rep.uncovered_rows[0].node_id == "N2"
    assert rep.uncovered_rows[0].reason_code == "path_loss"
    assert rep.reason_counts == {"path_loss": 1}


def test_uncovered_reason_min_rx_when_node_requires_very_strong_signal():
    gws = [gw("G1", 37.4000, 127.1200)]
    n = node("N1", 37.4001, 127.1201, min_rx_dbm=0.0)   # 어떤 신호도 못 넘는 기준
    rep, _ = make_report(gws, [n])
    u = rep.uncovered_rows[0]
    assert u.reason_code == "min_rx"
    assert u.best_gw_id == "G1" and u.distance_km is not None
    assert "기준 0 dBm" in u.reason_detail


def test_connected_plus_receive_only_links():
    gws = [gw("A", 37.4000, 127.1200), gw("B", 37.4002, 127.1202)]
    n = node("N1", 37.4001, 127.1201)
    rep, res = make_report(gws, [n])
    assert len(res.node_gw_ids["N1"]) == 2
    relations = [l.relation for g in rep.gw_rows for l in g.links]
    assert sorted(relations) == sorted([RELATION_CONNECTED, RELATION_RECEIVE_ONLY])
    assert sum(g.connected for g in rep.gw_rows) == rep.covered_nodes == 1
    assert sum(g.receivable for g in rep.gw_rows) == 2
    connected_gw = next(g for g in rep.gw_rows if g.connected == 1)
    assert connected_gw.shared == 1          # 다른 GW에서도 수신됨
    assert rep.node_rows[0].receiving_gws == 2


def test_sf_counts_and_type_counts_and_avg():
    gws = [gw("G1", 37.4000, 127.1200)]
    nodes = [node("N1", 37.4001, 127.1201, "맨홀수위센서"), node("N2", 37.4002, 127.1202, "맨홀수위센서"),
             node("N3", 37.4003, 127.1203, "CCTV")]
    rep, _ = make_report(gws, nodes)
    g = rep.gw_rows[0]
    assert sum(g.sf_counts.values()) == g.connected == 3
    assert g.type_counts == {"맨홀수위센서": 2, "CCTV": 1}
    assert g.avg_rx_dbm == pytest.approx(sum(l.rx_power_dbm for l in g.links) / 3)
    assert [l.distance_km for l in g.links] == sorted(l.distance_km for l in g.links)


def test_nodes_not_in_result_are_ignored():
    gws = [gw("G1", 37.4000, 127.1200)]
    n1 = node("N1", 37.4001, 127.1201)
    dem = FakeFlatDem()
    result = evaluate_gateways_coverage([n1], gws, dem)
    later = node("N_LATER", 37.4002, 127.1202)      # 검증 이후 추가된 단말
    rep = build_coverage_report(result, [n1, later], dem)
    assert rep.total_nodes == 1


def test_target_flag_uses_given_target():
    gws = [gw("G1", 37.4000, 127.1200)]
    nodes = [node("N1", 37.4001, 127.1201), node("N2", 38.50, 127.12)]
    rep, _ = make_report(gws, nodes, coverage_target=0.5)
    assert rep.target_met is True
    rep2, _ = make_report(gws, nodes, coverage_target=0.9)
    assert rep2.target_met is False


@pytest.mark.parametrize("dlat", [0.0005, 0.01, 0.1, 0.5, 1.2])
@pytest.mark.parametrize("min_rx", [-100.0, -60.0, 0.0])
def test_diagnose_link_agrees_with_evaluate_connection(dlat, min_rx):
    """진단 함수가 실제 연결 판정과 어긋나면 미커버 사유가 거짓이 되므로 가장 중요한 회귀 테스트임."""
    g = gw("G1", 37.4, 127.12)
    n = node("N1", 37.4 + dlat, 127.12, min_rx_dbm=min_rx)
    dem = FakeFlatDem()
    connected = evaluate_connection(g, n, dem) is not None
    assert (diagnose_link(g, n, dem).reason_code is None) == connected
