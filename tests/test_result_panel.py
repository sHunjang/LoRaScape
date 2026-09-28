from types import SimpleNamespace as NS
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.result_panel import ResultPanel, pr_bin_counts, PR_BINS


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def fake_result(prs, gateways=("G1",)):
    conns = {f"N{i}": (NS(rx_power_dbm=p) if p is not None else None) for i, p in enumerate(prs)}
    return NS(gateways=list(gateways), connections=conns, node_gw_ids={k: ["G1"] for k in conns},
              coverage_ratio=0.5, k=len(gateways), target_met=False, gw_counts={"G1": 2})


def test_pr_bin_counts_boundaries():
    conns = {"a": NS(rx_power_dbm=-75.0), "b": NS(rx_power_dbm=-75.1), "c": NS(rx_power_dbm=-90.0),
             "d": NS(rx_power_dbm=-90.1), "e": NS(rx_power_dbm=-100.0), "f": NS(rx_power_dbm=-100.1), "g": None}
    assert pr_bin_counts(conns) == [1, 2, 2, 1]


def test_pr_bin_counts_ignores_uncovered_and_handles_empty():
    assert pr_bin_counts({}) == [0, 0, 0, 0]
    assert pr_bin_counts({"a": None}) == [0, 0, 0, 0]


def test_show_result_fills_rows_and_sums_to_connected(qapp):
    panel = ResultPanel()
    panel.show_result(fake_result([-60, -80, -80, -95, -110, None]), total_nodes=6)
    texts = [r._value_lbl.text() for r in panel._pr_rows]
    assert texts == ["1개", "2개", "1개", "1개"]
    assert len(panel._pr_rows) == len(PR_BINS)


def test_show_loading_resets_rows(qapp):
    panel = ResultPanel()
    panel.show_result(fake_result([-60, -80]), total_nodes=2)
    panel.show_loading()
    assert [r._value_lbl.text() for r in panel._pr_rows] == ["0개"] * 4


def test_show_result_with_no_connections_does_not_divide_by_zero(qapp):
    panel = ResultPanel()
    panel.show_result(fake_result([None, None]), total_nodes=2)
    assert [r._value_lbl.text() for r in panel._pr_rows] == ["0개"] * 4