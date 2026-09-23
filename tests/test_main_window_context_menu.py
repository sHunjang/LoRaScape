"""
main_window.py의 우클릭 컨텍스트 메뉴 액션 핸들러 검증 테스트임.
실제 QMenu.exec_()는 팝업이 떠서 테스트가 멈추니, 각 핸들러 메서드를
직접 호출해서 검증함 (메뉴 자체는 수동으로 확인).
"""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_add_gw_at_appends_gateway(qapp):
    window = MainWindow()
    window._add_gw_at(37.40, 127.12)
    assert len(window.gateways) == 1
    assert window.gateways[0].lat == 37.40
    assert window.gateways[0].lon == 127.12


def test_add_node_at_appends_node(qapp):
    window = MainWindow()
    window._add_node_at(37.41, 127.13)
    assert len(window.nodes) == 1
    assert window.nodes[0].lat == 37.41
    assert window.nodes[0].lon == 127.13


def test_copy_coordinates_sets_clipboard_lat_lon_order(qapp):
    window = MainWindow()
    window._copy_coordinates(37.4, 127.1)
    assert QApplication.clipboard().text() == "37.400000, 127.100000"


def test_copy_geojson_coordinates_sets_clipboard_lon_lat_order(qapp):
    window = MainWindow()
    window._copy_geojson_coordinates(37.4, 127.1)
    assert QApplication.clipboard().text() == "127.100000, 37.400000"


def test_add_measure_point_starts_measuring_and_appends_point(qapp):
    window = MainWindow()
    window._add_measure_point(37.4, 127.1)
    assert window._measuring is True
    assert window._measure_points == [(127.1, 37.4)]


def test_add_measure_point_accumulates_multiple_points(qapp):
    window = MainWindow()
    window._add_measure_point(37.4, 127.1)
    window._add_measure_point(37.5, 127.2)
    assert len(window._measure_points) == 2


def test_reset_measurement_clears_state(qapp):
    window = MainWindow()
    window._add_measure_point(37.4, 127.1)
    window._reset_measurement()
    assert window._measuring is False
    assert window._measure_points == []


def test_on_map_clicked_appends_point_while_measuring(qapp):
    window = MainWindow()
    window._measuring = True
    window._on_map_clicked(127.1, 37.4)
    assert window._measure_points == [(127.1, 37.4)]


def test_on_map_clicked_does_not_append_point_when_not_measuring(qapp):
    window = MainWindow()
    window._on_map_clicked(127.1, 37.4)
    assert window._measure_points == []


def test_run_heatmap_for_all_enabled_shows_info_when_no_gateways(qapp, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    window = MainWindow()

    called = []
    monkeypatch.setattr(
        "lorascape.gui.main_window._styled_message_box",
        lambda *a, **k: type("_M", (), {"exec_": lambda self: called.append(True)})()
    )
    window._run_heatmap_for_all_enabled()
    assert called == [True]
    

def test_init_map_bounds_from_dem_sets_bounds_when_dem_exists(qapp, tmp_path, monkeypatch):
    """
    실제 DEM 파일 없이도 로직 검증 가능하게, get_dem_latlon_bounds를 가짜로 대체해서
    MainWindow가 그 결과로 map_widget.set_bounds를 호출하는지 확인함.
    """
    import lorascape.gui.main_window as mw

    fake_bounds = (127.0, 37.3, 127.2, 37.5)
    monkeypatch.setattr(
        "lorascape.data.dem_loader.get_dem_latlon_bounds",
        lambda path: fake_bounds,
    )

    window = MainWindow(dem_path="fake_dem_path.img")
    window._init_map_bounds_from_dem()

    assert window.map_widget._bounds == fake_bounds


def test_init_map_bounds_from_dem_fails_silently_on_bad_path(qapp):
    """DEM 파일이 없어도 예외가 앱 밖으로 튀어나가면 안 됨 - 상태바 메시지로만 처리됨."""
    window = MainWindow(dem_path="nonexistent_dem.img")
    window._init_map_bounds_from_dem()  # 예외 안 나고 조용히 처리돼야 함
    assert "실패" in window.status_label.text() or window.status_label.text() != ""


def test_on_show_result_heatmap_clicked_does_nothing_without_result(qapp):
    """결과가 없으면 그냥 조용히 무시되고 크래시 없어야 함."""
    window = MainWindow()
    window.last_result = None
    window._on_show_result_heatmap_clicked()  # 예외 없이 지나가야 함


def test_on_show_result_heatmap_clicked_triggers_selected_coverage(qapp, monkeypatch):
    """결과가 있으면 결과의 GW id 목록으로 _on_selected_coverage_requested를 호출해야 함."""
    from lorascape.core.optimization.gw_placement import OptimizationResult
    from lorascape.data.schema import GatewaySite

    window = MainWindow()
    gw = GatewaySite(
        gw_id="GW1", region="테스트", location_desc="",
        lat=37.4, lon=127.1, install_type="테스트", power_source="테스트",
    )
    window.last_result = OptimizationResult(
        gateways=[gw], connections={}, node_gw_ids={}, coverage_ratio=1.0, k=1, target_met=True,
    )

    received = []
    monkeypatch.setattr(window, "_on_selected_coverage_requested", lambda ids: received.append(ids))
    window._on_show_result_heatmap_clicked()

    assert received == [["GW1"]]


def test_on_show_result_heatmap_clicked_warns_when_many_gateways(qapp, monkeypatch):
    """GW가 10개 넘으면 확인 팝업을 띄우고, No를 누르면 실행 안 되어야 함."""
    from lorascape.core.optimization.gw_placement import OptimizationResult
    from lorascape.data.schema import GatewaySite
    from PyQt5.QtWidgets import QMessageBox

    window = MainWindow()
    gws = [
        GatewaySite(gw_id=f"GW{i}", region="테스트", location_desc="",
                    lat=37.4, lon=127.1, install_type="테스트", power_source="테스트")
        for i in range(15)
    ]
    window.last_result = OptimizationResult(
        gateways=gws, connections={}, node_gw_ids={}, coverage_ratio=1.0, k=15, target_met=True,
    )

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    received = []
    monkeypatch.setattr(window, "_on_selected_coverage_requested", lambda ids: received.append(ids))
    window._on_show_result_heatmap_clicked()

    assert received == []  # No 눌렀으니 실행 안 되어야 함