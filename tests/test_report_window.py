import pytest
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from tests.test_coverage_report import gw, node, make_report
from lorascape.gui.widgets.report_window import ReportWindow
from lorascape.gui.report_pdf import export_report_pdf


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def sample_report():
    gws = [gw("A", 37.4000, 127.1200), gw("B", 37.4002, 127.1202)]
    nodes = [node("N1", 37.4001, 127.1201, "맨홀수위센서"), node("N2", 38.50, 127.12, "CCTV")]
    rep, _ = make_report(gws, nodes)
    return rep


def test_window_tables_match_report(qapp):
    rep = sample_report()
    win = ReportWindow(rep)
    assert win.tabs.count() == 3
    assert win.tbl_gw.rowCount() == len(rep.gw_rows)
    assert win.tbl_node.rowCount() == len(rep.node_rows)
    assert win.tbl_uncovered.rowCount() == len(rep.uncovered_rows)


def test_first_gw_selected_shows_detail(qapp):
    rep = sample_report()
    win = ReportWindow(rep)
    assert win._current_gw_id == win.tbl_gw.item(0, 0).text()
    g = win._gw_by_id[win._current_gw_id]
    assert win.tbl_detail.rowCount() == len(g.links)
    assert win.lbl_stat_conn.text() == str(g.connected)


def test_selecting_other_row_switches_detail(qapp):
    win = ReportWindow(sample_report())
    win.tbl_gw.selectRow(1)
    assert win._current_gw_id == win.tbl_gw.item(1, 0).text()


def test_heatmap_button_emits_selected_gw_id(qapp):
    win = ReportWindow(sample_report())
    got = []
    win.sig_show_heatmap.connect(got.append)
    win.btn_heatmap.click()
    assert got == [win._current_gw_id]


def test_pdf_export_creates_pdf(qapp, tmp_path):
    p = tmp_path / "r.pdf"
    export_report_pdf(sample_report(), str(p))
    data = p.read_bytes()
    assert data[:5] == b"%PDF-" and len(data) > 2000


def test_export_buttons_write_files(qapp, tmp_path, monkeypatch):
    win = ReportWindow(sample_report())
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    for ext, btn in [("xlsx", win.btn_excel), ("csv", win.btn_csv), ("pdf", win.btn_pdf)]:
        target = str(tmp_path / f"out.{ext}")
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, _t=target, **k: (_t, "")))
        btn.click()
        assert (tmp_path / f"out.{ext}").exists()


def test_export_failure_shows_warning_not_crash(qapp, tmp_path, monkeypatch):
    win = ReportWindow(sample_report())
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(True))
    bad = str(tmp_path / "no_such_dir" / "x.xlsx")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (bad, "")))
    win.btn_excel.click()
    assert warned == [True]


def test_empty_report_opens_without_error(qapp):
    from lorascape.core.reporting.coverage_report import CoverageReport
    rep = CoverageReport(generated_at="2026-09-28 00:00", params={}, total_nodes=0, covered_nodes=0,
                         uncovered_nodes=0, coverage_ratio=0.0, coverage_target=0.9,
                         target_met=False, gw_count=0)
    win = ReportWindow(rep)
    assert win.tbl_gw.rowCount() == 0 and win._current_gw_id == ""
    win.btn_heatmap.click()   # 선택된 GW가 없으면 아무 일도 안 일어나야 함
