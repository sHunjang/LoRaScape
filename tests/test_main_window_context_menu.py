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