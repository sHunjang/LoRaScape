import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.defaults_dialog import DefaultsDialog


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


CURRENT = {"gateway": {"antenna_height_m": 1.5, "tx_power_dbm": 14.0},
           "node": {"min_rx_dbm": -100.0}}
FACTORY = {"gateway": {"antenna_height_m": 1.5, "tx_power_dbm": 14.0}, "node": {"min_rx_dbm": -100.0}}
USAGE = {"gateway": {"total": 33, "params": {"antenna_height_m": {"explicit": 2, "default": 31},
                                             "tx_power_dbm": {"explicit": 0, "default": 33}}},
         "node": {"total": 143, "params": {"min_rx_dbm": {"explicit": 45, "default": 98}}}}


def test_shows_current_values_for_every_param(qapp):
    dlg = DefaultsDialog(CURRENT, FACTORY, USAGE)
    assert dlg.spins[("gateway", "antenna_height_m")].value() == 1.5
    assert dlg.spins[("node", "min_rx_dbm")].value() == -100.0
    assert len(dlg.spins) == 3


def test_changes_contains_only_modified_values(qapp):
    dlg = DefaultsDialog(CURRENT, FACTORY, USAGE)
    assert dlg.changes() == {}
    dlg.spins[("gateway", "antenna_height_m")].setValue(6.0)
    assert dlg.changes() == {"gateway": {"antenna_height_m": 6.0}}


def test_apply_emits_changes_and_noop_apply_emits_nothing(qapp):
    dlg = DefaultsDialog(CURRENT, FACTORY, USAGE)
    got = []
    dlg.sig_defaults_applied.connect(got.append)
    dlg._accept()
    assert got == []
    dlg2 = DefaultsDialog(CURRENT, FACTORY, USAGE)
    dlg2.sig_defaults_applied.connect(got.append)
    dlg2.spins[("node", "min_rx_dbm")].setValue(-90.0)
    dlg2._accept()
    assert got == [{"node": {"min_rx_dbm": -90.0}}]


def test_reset_to_factory_restores_factory_values(qapp):
    current = {"gateway": {"antenna_height_m": 9.0, "tx_power_dbm": 14.0}, "node": {"min_rx_dbm": -100.0}}
    dlg = DefaultsDialog(current, FACTORY, USAGE)
    dlg._reset_to_factory()
    assert dlg.spins[("gateway", "antenna_height_m")].value() == 1.5
    assert dlg.changes() == {"gateway": {"antenna_height_m": 1.5}}


def test_usage_labels_show_how_many_devices_follow_the_default(qapp):
    from PyQt5.QtWidgets import QLabel
    dlg = DefaultsDialog(CURRENT, FACTORY, USAGE)
    texts = [l.text() for l in dlg.findChildren(QLabel)]
    assert "기본값 사용 31/33개" in texts and "기본값 사용 98/143개" in texts
