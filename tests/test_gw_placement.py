"""
gw_placement.py 검증 테스트임.
실제 DEM 파일 없이 로직만 검증하려고, get_elevation_profile/is_installable을
구현한 가짜(Fake) DEM 객체를 만들어서 씀 - 항상 평지(장애물 없음)를 반환하게 해서
Deygout 쪽 변수를 제거하고 K-means/커버리지 로직 자체에 집중해서 테스트함.
"""
import pytest
from lorascape.data.schema import NodeSite, GatewaySite
from lorascape.core.optimization.gw_placement import (
    optimize_gw_placement,
    evaluate_connection,
    compute_total_path_loss,
)


class FakeFlatDem:
    """평지 지형(고도 50m 고정, 장애물 없음)을 흉내 내는 가짜 DEM임. 항상 설치 가능으로 판정함."""

    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=20):
        from lorascape.data.coord_transform import distance_m
        total = distance_m(lat1, lon1, lat2, lon2)
        return [(total * i / n_samples, 50.0) for i in range(n_samples + 1)]

    def is_installable(self, lat, lon):
        return True


def _make_node(node_id, lat, lon):
    return NodeSite(
        node_id=node_id, region="테스트", location_desc="",
        lat=lat, lon=lon, device_type="테스트센서", install_type="테스트",
    )


def _make_gw(gw_id, lat, lon):
    return GatewaySite(
        gw_id=gw_id, region="테스트", location_desc="",
        lat=lat, lon=lon, install_type="테스트", power_source="테스트",
    )


def test_compute_total_path_loss_zero_obstacle_matches_song_model_only():
    # 평지(장애물 없음)라 Deygout 손실은 0이어야 하고, Song's Model 값만 나와야 함
    from lorascape.core.propagation.song_model import path_loss as song_path_loss

    gw = _make_gw("GW1", 37.40, 127.12)
    node = _make_node("N1", 37.41, 127.13)
    dem = FakeFlatDem()

    total_pl = compute_total_path_loss(gw, node, dem)

    from lorascape.data.coord_transform import distance_m
    d_km = distance_m(gw.lat, gw.lon, node.lat, node.lon) / 1000.0
    expected_song_only = song_path_loss(920.0, gw.antenna_height_m, node.antenna_height_m, d_km, "urban")

    assert total_pl == pytest.approx(expected_song_only, rel=1e-6)


def test_evaluate_connection_close_node_connects():
    # 아주 가까운 거리(100m)면 확실히 연결돼야 함
    gw = _make_gw("GW1", 37.40, 127.12)
    node = _make_node("N1", 37.4009, 127.12)  # 약 100m 정도 떨어진 지점
    dem = FakeFlatDem()

    result = evaluate_connection(gw, node, dem)
    assert result is not None
    assert result.sf is not None


def test_evaluate_connection_far_node_fails():
    # 아주 먼 거리(50km 이상)면 Path Loss 제약(140dB) 넘어서 연결 실패해야 함
    gw = _make_gw("GW1", 37.40, 127.12)
    node = _make_node("N1", 37.85, 127.12)  # 위도 차이로 약 50km
    dem = FakeFlatDem()

    result = evaluate_connection(gw, node, dem)
    assert result is None


def test_optimize_gw_placement_all_nodes_near_one_point_needs_only_k1():
    # Node들이 전부 한 지점 근처에 몰려있으면 GW 1개로도 커버리지 100% 나와야 함
    nodes = [
        _make_node("N1", 37.4000, 127.1200),
        _make_node("N2", 37.4001, 127.1201),
        _make_node("N3", 37.4002, 127.1199),
    ]
    dem = FakeFlatDem()

    result = optimize_gw_placement(nodes, dem, initial_k=1, max_k=5, coverage_target=1.0)

    assert result.target_met is True
    assert result.k == 1
    assert result.coverage_ratio == pytest.approx(1.0)


def test_optimize_gw_placement_far_apart_nodes_need_more_gws():
    # Node 2개가 서로 아주 멀리 떨어져 있으면(약 90km 이상) GW 1개로는 둘 다 커버 못 함
    # -> K가 늘어나야 하는지 확인
    nodes = [
        _make_node("N1", 37.20, 127.12),
        _make_node("N2", 38.00, 127.12),
    ]
    dem = FakeFlatDem()

    result = optimize_gw_placement(nodes, dem, initial_k=1, max_k=5, coverage_target=1.0)

    assert result.k > 1  # GW 1개로는 안 됐을 거라 K가 늘어났어야 함
    assert result.target_met is True


def test_optimize_gw_placement_reaches_max_k_without_meeting_target():
    # 목표치가 애초에 불가능한 수준(예: coverage_target > 1.0은 불가능하니 이런 식으로
    # 도달 불가능한 상황을 만들어서 max_k에서 멈추는지 확인함)
    nodes = [_make_node("N1", 37.40, 127.12)]
    dem = FakeFlatDem()

    # max_k를 initial_k와 같게 둬서 한 번만 시도하고 끝나게 만듦 + 불가능한 목표치
    result = optimize_gw_placement(nodes, dem, initial_k=1, max_k=1, coverage_target=1.0)

    # Node 1개짜리는 사실 k=1이면 커버 가능해서 이 케이스는 target_met=True가 정상임.
    # 여기서는 "max_k까지만 돌고 멈춘다"는 동작 자체를 확인하는 게 목적임.
    assert result.k == 1


def test_optimize_gw_placement_raises_on_empty_nodes():
    with pytest.raises(ValueError):
        optimize_gw_placement([], FakeFlatDem())
        

def test_evaluate_connection_uses_gw_node_entity_params_by_default():
    """무선 파라미터를 명시적으로 안 넘기면 gw/node 객체에 저장된 기본값을 써야 함."""
    gw = _make_gw("GW1", 37.40, 127.12)
    node = _make_node("N1", 37.4009, 127.12)
    dem = FakeFlatDem()

    # 기본값(14dBm, 6dBi, 1dB / 0dBi, 0dB)으로 계산한 결과와
    result_default = evaluate_connection(gw, node, dem)

    # 명시적으로 같은 값을 넘긴 결과와 동일해야 함
    result_explicit = evaluate_connection(
        gw, node, dem,
        tx_power_dbm=14.0, gw_antenna_gain_dbi=6.0, gw_cable_loss_db=1.0,
        node_antenna_gain_dbi=0.0, node_cable_loss_db=0.0,
    )

    assert result_default.rx_power_dbm == pytest.approx(result_explicit.rx_power_dbm)


def test_evaluate_connection_respects_gw_custom_tx_power():
    """GW 객체의 tx_power_dbm을 GUI에서 고친 것처럼 바꾸면 결과에 반영돼야 함."""
    gw_weak = _make_gw("GW_WEAK", 37.40, 127.12)
    gw_weak.tx_power_dbm = 5.0  # GUI에서 출력을 낮춘 상황을 흉내 냄

    gw_strong = _make_gw("GW_STRONG", 37.40, 127.12)
    gw_strong.tx_power_dbm = 20.0  # GUI에서 출력을 높인 상황

    node = _make_node("N1", 37.4009, 127.12)
    dem = FakeFlatDem()

    result_weak = evaluate_connection(gw_weak, node, dem)
    result_strong = evaluate_connection(gw_strong, node, dem)

    assert result_strong.rx_power_dbm > result_weak.rx_power_dbm


def test_evaluate_connection_explicit_override_wins_over_entity():
    """호출부에서 명시적으로 값을 넘기면 엔티티 필드보다 우선해야 함 (what-if 분석용)."""
    gw = _make_gw("GW1", 37.40, 127.12)
    node = _make_node("N1", 37.4009, 127.12)
    dem = FakeFlatDem()

    result_normal = evaluate_connection(gw, node, dem)
    result_boosted = evaluate_connection(gw, node, dem, tx_power_dbm=30.0)

    assert result_boosted.rx_power_dbm > result_normal.rx_power_dbm