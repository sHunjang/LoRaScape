"""전파 모델 선택(propagation_model)이 계산 전 구간에 실제로 전달되는지 검증하는 테스트임."""
import pytest

from lorascape.data.schema import GatewaySite, NodeSite
from lorascape.core.optimization.gw_placement import (
    compute_total_path_loss, evaluate_connection, evaluate_gateways_coverage,
    optimize_gw_placement, evaluate_and_augment,
)
from lorascape.core.reporting.coverage_report import build_coverage_report, diagnose_link


class FlatDem:
    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=20):
        return [(i * 10.0, 50.0) for i in range(n_samples + 1)]

    def is_installable(self, lat, lon):
        return True


def _gw(gw_id, lat, lon):
    return GatewaySite(gw_id=gw_id, region="테스트", location_desc="", lat=lat, lon=lon,
                       install_type="테스트", power_source="테스트")


def _node(node_id, lat, lon, **kw):
    return NodeSite(node_id=node_id, region="테스트", location_desc="", lat=lat, lon=lon,
                    device_type="테스트", install_type="테스트", **kw)


def test_positional_fc_and_environment_still_work():
    """fc_mhz, environment를 위치 인자로 부르는 기존 호출이 깨지지 않아야 함 (모델 인자가 중간에 끼면 깨짐)."""
    gw, dem = _gw("G1", 37.4000, 127.1200), FlatDem()
    node = _node("N1", 37.4030, 127.1200, min_rx_dbm=-140.0)      # 모델 값에 상관없이 연결되도록 하한을 풀어줌
    assert compute_total_path_loss(gw, node, dem, 920.0, "urban") == compute_total_path_loss(gw, node, dem)
    assert evaluate_connection(gw, node, dem, 920.0, "urban") is not None


def test_default_model_is_song_and_explicit_song_is_identical():
    gw, node, dem = _gw("G1", 37.4000, 127.1200), _node("N1", 37.4030, 127.1200), FlatDem()
    assert compute_total_path_loss(gw, node, dem) == compute_total_path_loss(gw, node, dem, propagation_model="song")


def test_models_change_path_loss():
    gw, node, dem = _gw("G1", 37.4000, 127.1200), _node("N1", 37.4050, 127.1250), FlatDem()
    song = compute_total_path_loss(gw, node, dem, propagation_model="song")
    cost = compute_total_path_loss(gw, node, dem, propagation_model="cost231")
    assert song != pytest.approx(cost, abs=0.01)


def test_unknown_model_raises_through_the_whole_chain():
    gw, node, dem = _gw("G1", 37.4000, 127.1200), _node("N1", 37.4030, 127.1200), FlatDem()
    with pytest.raises(ValueError):
        evaluate_gateways_coverage([node], [gw], dem, propagation_model="okumura")


def test_every_entry_point_forwards_the_model():
    gw, dem = _gw("G1", 37.4000, 127.1200), FlatDem()
    node = _node("N1", 37.4030, 127.1200, min_rx_dbm=-140.0)      # 두 모델 모두 연결되도록 하한을 풀어줌
    c_song = evaluate_connection(gw, node, dem, propagation_model="song")
    c_cost = evaluate_connection(gw, node, dem, propagation_model="cost231")
    assert c_song.path_loss_db != pytest.approx(c_cost.path_loss_db, abs=0.01)

    r = evaluate_gateways_coverage([node], [gw], dem, propagation_model="cost231")
    assert r.connections["N1"].path_loss_db == pytest.approx(c_cost.path_loss_db)


def test_optimizers_accept_and_use_the_model():
    dem = FlatDem()
    nodes = [_node(f"N{i}", 37.400 + 0.003 * i, 127.120 + 0.002 * i, min_rx_dbm=-140.0) for i in range(6)]
    res = optimize_gw_placement(nodes, dem, initial_k=1, max_k=2, coverage_target=1.0, propagation_model="cost231")
    assert res.k >= 1
    far_gw = _gw("EXIST", 37.30, 127.00)                            # 멀리 있는 기존 GW -> 증설 경로를 탐
    res2 = evaluate_and_augment(nodes, [far_gw], dem, max_additional=2, coverage_target=1.0, propagation_model="cost231")
    assert res2.k >= 1


def test_report_records_model_and_matches_result():
    gw, dem = _gw("G1", 37.4000, 127.1200), FlatDem()
    nodes = [_node("N1", 37.4030, 127.1200, min_rx_dbm=-140.0), _node("N2", 38.50, 127.12)]
    result = evaluate_gateways_coverage(nodes, [gw], dem, propagation_model="cost231")
    rep = build_coverage_report(result, nodes, dem, propagation_model="cost231")
    assert rep.params["propagation_model"] == "cost231"
    assert rep.covered_nodes == 1 and rep.uncovered_rows[0].node_id == "N2"


@pytest.mark.parametrize("model", ["song", "cost231"])
@pytest.mark.parametrize("dlat", [0.0005, 0.01, 0.1, 0.5, 1.2])
@pytest.mark.parametrize("min_rx", [-100.0, -60.0])
def test_diagnose_link_agrees_with_evaluate_connection_for_each_model(model, dlat, min_rx):
    """진단 함수가 실제 연결 판정과 어긋나면 미커버 사유가 거짓이 되므로, 모델별로 확인함."""
    g, n, dem = _gw("G1", 37.4, 127.12), _node("N1", 37.4 + dlat, 127.12, min_rx_dbm=min_rx), FlatDem()
    connected = evaluate_connection(g, n, dem, propagation_model=model) is not None
    assert (diagnose_link(g, n, dem, propagation_model=model).reason_code is None) == connected


def test_node_site_default_min_rx_dbm_is_minus_100():
    """(gw_placement.py 파일 끝에 잘못 들어가 있던 테스트를 옮겨옴) 기본 최소 수신 레벨은 -100dBm임."""
    assert NodeSite(node_id="T", region="", location_desc="", lat=37.4, lon=127.1,
                    device_type="", install_type="").min_rx_dbm == -100.0
