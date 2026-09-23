"""
map_layers.py 검증 테스트임. Qt/QApplication 없이 folium.Map만으로 테스트 가능함.
"""
import folium
from lorascape.gui.widgets.map_layers import (
    pr_to_color, build_gw_color_map, add_measure_layer,
    add_gw_marker_layer, add_node_marker_layer,add_coverage_layers
)
from lorascape.data.schema import GatewaySite, NodeSite


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


def test_pr_to_color_returns_expected_color_for_known_thresholds():
    assert pr_to_color(-85) == '#FF2020'
    assert pr_to_color(-95) == '#FF8C00'
    assert pr_to_color(-200) == '#4f8ef7'


def test_build_gw_color_map_skips_disabled_gws():
    gw1 = _make_gw("GW1", 37.40, 127.12)
    gw2 = _make_gw("GW2", 37.41, 127.13)
    gw2.enabled = False

    color_map = build_gw_color_map([gw1, gw2])
    assert "GW1" in color_map
    assert "GW2" not in color_map


def test_add_measure_layer_does_not_crash_with_empty_points():
    m = folium.Map()
    add_measure_layer(m, [])  # 크래시만 안 나면 됨


def test_add_measure_layer_adds_markers_for_points():
    m = folium.Map()
    add_measure_layer(m, [(127.12, 37.40), (127.13, 37.41)])
    html = m.get_root().render()
    # DivIcon의 html 속성은 JSON 직렬화 과정에서 <, >가 \u003c, \u003e로 이스케이프되니까
    # 태그가 아니라 실제 거리 숫자+단위 텍스트로 렌더링 여부를 확인함
    assert "km" in html
    assert "1.420" in html  # (127.12,37.40)-(127.13,37.41) 사이 대략적인 거리값


def test_add_gw_marker_layer_renders_gw_id_in_html():
    m = folium.Map()
    gw = _make_gw("MY_GW_1", 37.40, 127.12)
    color_map = build_gw_color_map([gw])
    add_gw_marker_layer(m, [gw], result=None, gw_color_map=color_map)
    html = m.get_root().render()
    assert "MY_GW_1" in html


def test_add_node_marker_layer_renders_node_id_in_html():
    m = folium.Map()
    node = _make_node("MY_NODE_1", 37.40, 127.12)
    add_node_marker_layer(m, [node], result=None, gw_color_map={}, selected_gws=None)
    html = m.get_root().render()
    assert "MY_NODE_1" in html


def test_add_coverage_layers_hides_pr_layer_when_show_pr_layer_false():
    """
    히트맵이 함께 표시될 때 수신전력 분포 원형 레이어가 기본적으로 꺼지는지 확인함.
    folium.FeatureGroup의 show 속성을 직접 검사함.
    """
    import folium
    m = folium.Map(location=[37.4, 127.1], zoom_start=13)

    class FakeConn:
        def __init__(self, gw_id, pr):
            self.gw_id = gw_id
            self.rx_power_dbm = pr

    class FakeResult:
        connections = {"N1": FakeConn("GW1", -90)}
        node_gw_ids = {"N1": ["GW1"]}

    node = type("N", (), {"node_id": "N1", "lat": 37.4, "lon": 127.1})()

    add_coverage_layers(m, [node], FakeResult(), None, 0.5, show_pr_layer=False)

    # FeatureGroup 목록을 순회해서 이름과 show 속성 확인
    pr_layer = next(c for c in m._children.values() if getattr(c, "layer_name", "") == "수신전력 분포 (분석 결과)")
    assert pr_layer.show is False


def test_add_coverage_layers_shows_pr_layer_by_default():
    import folium
    m = folium.Map(location=[37.4, 127.1], zoom_start=13)

    class FakeConn:
        def __init__(self, gw_id, pr):
            self.gw_id = gw_id
            self.rx_power_dbm = pr

    class FakeResult:
        connections = {"N1": FakeConn("GW1", -90)}
        node_gw_ids = {"N1": ["GW1"]}

    node = type("N", (), {"node_id": "N1", "lat": 37.4, "lon": 127.1})()

    add_coverage_layers(m, [node], FakeResult(), None, 0.5)  # show_pr_layer 기본값(True) 사용

    pr_layer = next(c for c in m._children.values() if getattr(c, "layer_name", "") == "수신전력 분포 (분석 결과)")
    assert pr_layer.show is True