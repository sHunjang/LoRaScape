"""profile_window.py 검증 테스트임. QApplication 필요함. 실제 화면 렌더링보다는
_plot()이 크래시 없이 도는지와 배지 텍스트(LOS/NLOS)가 지형에 맞게 나오는지 확인함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.profile_window import ProfileWindow, _fresnel_radius
from lorascape.data.schema import GatewaySite, NodeSite


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeFlatDem:
    """평지 지형(장애물 없음) - LOS가 뚫려야 함."""
    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=100):
        from lorascape.data.coord_transform import distance_m
        total = distance_m(lat1, lon1, lat2, lon2)
        return [(total * i / n_samples, 50.0) for i in range(n_samples + 1)]


class FakeMountainDem:
    """중간에 산이 있는 지형 - NLOS가 나와야 함."""
    def get_elevation_profile(self, lat1, lon1, lat2, lon2, n_samples=100):
        from lorascape.data.coord_transform import distance_m
        total = distance_m(lat1, lon1, lat2, lon2)
        profile = []
        for i in range(n_samples + 1):
            t = i / n_samples
            # 중간 지점(t=0.5)에 200m 높이 산을 만듦
            elev = 50.0 + (200.0 if 0.4 < t < 0.6 else 0.0)
            profile.append((total * t, elev))
        return profile


def _make_gw(gw_id, lat, lon):
    return GatewaySite(
        gw_id=gw_id, region="테스트", location_desc="",
        lat=lat, lon=lon, install_type="테스트", power_source="테스트",
    )


def _make_node(node_id, lat, lon):
    return NodeSite(
        node_id=node_id, region="테스트", location_desc="",
        lat=lat, lon=lon, device_type="테스트", install_type="테스트",
    )


def test_fresnel_radius_positive_and_increases_toward_midpoint():
    r_edge = _fresnel_radius(10, 990, 920.0)   # 한쪽 끝에 가까움
    r_mid = _fresnel_radius(500, 500, 920.0)   # 중간
    assert r_mid > r_edge > 0


def test_profile_window_creates_without_error(qapp):
    gws = [_make_gw("GW1", 37.40, 127.10)]
    nodes = [_make_node("N1", 37.41, 127.11)]
    win = ProfileWindow(gws, nodes, FakeFlatDem())
    assert win is not None


def test_profile_window_flat_terrain_shows_los_ok(qapp):
    gws = [_make_gw("GW1", 37.40, 127.10)]
    nodes = [_make_node("N1", 37.41, 127.11)]
    win = ProfileWindow(gws, nodes, FakeFlatDem())
    assert "LOS" in win.lbl.text()
    assert "NLOS" not in win.lbl.text()


def test_profile_window_mountain_terrain_shows_nlos(qapp):
    gws = [_make_gw("GW1", 37.30, 127.10)]
    nodes = [_make_node("N1", 37.50, 127.10)]  # 충분히 멀리 둬서 중간에 산이 확실히 걸리게 함
    win = ProfileWindow(gws, nodes, FakeMountainDem())
    assert "NLOS" in win.lbl.text()


def test_profile_window_set_data_updates_combos(qapp):
    win = ProfileWindow([_make_gw("GW1", 37.4, 127.1)], [_make_node("N1", 37.41, 127.11)], FakeFlatDem())
    new_gws = [_make_gw("GWA", 37.4, 127.1), _make_gw("GWB", 37.5, 127.2)]
    new_nodes = [_make_node("NX", 37.41, 127.11)]
    win.set_data(new_gws, new_nodes)
    assert win.cb_gw.count() == 2