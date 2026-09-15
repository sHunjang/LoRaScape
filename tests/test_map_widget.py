"""
map_widget.py 검증 테스트임. 실제 화면 렌더링 자체보다는
'데이터를 넣으면 내부 상태가 의도대로 반영되는지'를 확인함.
"""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.map_widget import MapWidget
from lorascape.data.schema import GatewaySite, NodeSite

# PyQt 위젯 테스트는 QApplication 인스턴스가 하나 떠 있어야 함.
# 세션 전체에서 하나만 만들어서 재사용함 (여러 개 만들면 에러 남).
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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


def test_map_widget_creates_without_error(qapp):
    widget = MapWidget()
    assert widget is not None


def test_set_gateways_builds_lookup_table(qapp):
    widget = MapWidget()
    gws = [_make_gw("GW1", 37.40, 127.12), _make_gw("GW2", 37.41, 127.13)]
    widget.set_gateways(gws)
    assert widget._gw_lookup == {0: "GW1", 1: "GW2"}


def test_set_nodes_builds_lookup_table(qapp):
    widget = MapWidget()
    nodes = [_make_node("N1", 37.40, 127.12), _make_node("N2", 37.41, 127.13)]
    widget.set_nodes(nodes)
    assert widget._node_lookup == {0: "N1", 1: "N2"}


def test_set_gateways_empty_list_does_not_crash(qapp):
    widget = MapWidget()
    widget.set_gateways([])
    assert widget._gw_lookup == {}


def test_set_nodes_with_coverage_does_not_crash(qapp):
    widget = MapWidget()
    nodes = [_make_node("N1", 37.40, 127.12), _make_node("N2", 37.41, 127.13)]
    widget.set_nodes(nodes, coverage={"N1": True, "N2": False})
    # 크래시만 안 나면 됨 - 실제 색상 렌더링 검증은 스크린샷 비교가 필요해서 여기선 생략


def test_fit_to_data_sets_range_without_crashing(qapp):
    widget = MapWidget()
    gws = [_make_gw("GW1", 37.40, 127.12)]
    nodes = [_make_node("N1", 37.41, 127.13)]
    widget.fit_to_data(gws, nodes)  # 크래시만 안 나면 됨


def test_fit_to_data_empty_lists_does_not_crash(qapp):
    widget = MapWidget()
    widget.fit_to_data([], [])