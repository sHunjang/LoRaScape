"""workers.py의 LoadDataWorker 검증 테스트임. QThread 없이 run()을 직접 호출해서 검증함."""
import pytest
from lorascape.gui.workers import LoadDataWorker, HeatmapWorker, SuggestGreenfieldGWWorker, SuggestAdditionalGWWorker

XLSX_PATH = "sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx"


@pytest.mark.skipif(
    not __import__("os").path.exists(XLSX_PATH),
    reason="샘플 엑셀 파일이 없어서 건너뜀",
)
def test_load_data_worker_loads_both_by_default():
    worker = LoadDataWorker(XLSX_PATH, load_gateways=True, load_nodes=True)
    result = {}
    worker.finished.connect(lambda gws, nds: result.update(gateways=gws, nodes=nds))
    worker.run()
    assert result["gateways"] is not None
    assert result["nodes"] is not None
    assert len(result["gateways"]) > 0
    assert len(result["nodes"]) > 0


@pytest.mark.skipif(
    not __import__("os").path.exists(XLSX_PATH),
    reason="샘플 엑셀 파일이 없어서 건너뜀",
)
def test_load_data_worker_gateways_only():
    worker = LoadDataWorker(XLSX_PATH, load_gateways=True, load_nodes=False)
    result = {}
    worker.finished.connect(lambda gws, nds: result.update(gateways=gws, nodes=nds))
    worker.run()
    assert result["gateways"] is not None
    assert result["nodes"] is None


@pytest.mark.skipif(
    not __import__("os").path.exists(XLSX_PATH),
    reason="샘플 엑셀 파일이 없어서 건너뜀",
)
def test_load_data_worker_nodes_only():
    worker = LoadDataWorker(XLSX_PATH, load_gateways=False, load_nodes=True)
    result = {}
    worker.finished.connect(lambda gws, nds: result.update(gateways=gws, nodes=nds))
    worker.run()
    assert result["gateways"] is None
    assert result["nodes"] is not None


def test_load_data_worker_emits_error_on_bad_path():
    worker = LoadDataWorker("nonexistent_file.xlsx")
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))
    worker.run()
    assert len(errors) == 1


def test_heatmap_worker_reports_progress_up_to_100():
    import os
    dem_path = "sample_data/seongnam/dem_build_seongnam_3857-2.img"
    if not os.path.exists(dem_path):
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    from lorascape.data.schema import GatewaySite, NodeSite
    gw = GatewaySite(
        gw_id="TEST_GW", region="테스트", location_desc="",
        lat=37.40, lon=127.12, install_type="테스트", power_source="테스트",
    )
    node = NodeSite(
        node_id="N1", region="테스트", location_desc="",
        lat=37.4005, lon=127.1205, device_type="테스트", install_type="테스트",
    )

    worker = HeatmapWorker([gw], [node], dem_path, grid_size=5, radius_km=0.5)
    progress_values = []
    worker.progress.connect(lambda pct, msg: progress_values.append(pct))
    worker.run()

    assert progress_values
    assert progress_values[-1] == 100


def test_heatmap_worker_emits_error_on_missing_dem():
    from lorascape.data.schema import GatewaySite, NodeSite
    gw = GatewaySite(
        gw_id="TEST_GW", region="테스트", location_desc="",
        lat=37.40, lon=127.12, install_type="테스트", power_source="테스트",
    )
    node = NodeSite(
        node_id="N1", region="테스트", location_desc="",
        lat=37.41, lon=127.13, device_type="테스트", install_type="테스트",
    )
    worker = HeatmapWorker([gw], [node], "nonexistent_dem.img", grid_size=5)
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))
    worker.run()
    assert len(errors) == 1


def test_suggest_additional_gw_worker_separates_new_from_existing():
    import os
    dem_path = "sample_data/seongnam/dem_build_seongnam_3857-2.img"
    if not os.path.exists(dem_path):
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    from lorascape.data.schema import GatewaySite, NodeSite

    existing = [GatewaySite(
        gw_id="EXISTING_1", region="테스트", location_desc="",
        lat=37.20, lon=127.12, install_type="테스트", power_source="테스트",
    )]
    nodes = [
        NodeSite(node_id="N1", region="테스트", location_desc="", lat=37.201, lon=127.121, device_type="테스트", install_type="테스트"),
        NodeSite(node_id="N2", region="테스트", location_desc="", lat=37.60, lon=127.30, device_type="테스트", install_type="테스트"),
    ]

    worker = SuggestAdditionalGWWorker(dem_path, nodes, existing_gateways=existing, max_additional=5, coverage_target=1.0)
    result_holder = {}
    worker.finished.connect(lambda result, suggested: result_holder.update(result=result, suggested=suggested))
    worker.run()

    assert "suggested" in result_holder
    for gw in result_holder["suggested"]:
        assert gw.gw_id != "EXISTING_1"  # 기존 GW는 제안 목록에 포함되면 안 됨


def test_suggest_greenfield_gw_worker_ignores_no_existing_concept():
    import os
    dem_path = "sample_data/seongnam/dem_build_seongnam_3857-2.img"
    if not os.path.exists(dem_path):
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    from lorascape.data.schema import NodeSite

    nodes = [
        NodeSite(node_id="N1", region="테스트", location_desc="", lat=37.40, lon=127.12, device_type="테스트", install_type="테스트"),
    ]

    worker = SuggestGreenfieldGWWorker(dem_path, nodes, initial_k=1, max_k=3, coverage_target=1.0)
    result_holder = {}
    worker.finished.connect(lambda result, suggested: result_holder.update(result=result, suggested=suggested))
    worker.run()

    assert len(result_holder["suggested"]) >= 1


def test_heatmap_worker_returns_scoped_connection_result():
    import os
    dem_path = "sample_data/seongnam/dem_build_seongnam_3857-2.img"
    if not os.path.exists(dem_path):
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    from lorascape.data.schema import GatewaySite, NodeSite

    gw = GatewaySite(
        gw_id="TEST_GW", region="테스트", location_desc="",
        lat=37.40, lon=127.12, install_type="테스트", power_source="테스트",
    )
    node = NodeSite(
        node_id="N1", region="테스트", location_desc="",
        lat=37.4005, lon=127.1205, device_type="테스트", install_type="테스트",
    )

    worker = HeatmapWorker([gw], [node], dem_path, grid_size=5, radius_km=0.5)
    holder = {}
    worker.finished.connect(lambda layers, result: holder.update(layers=layers, result=result))
    worker.run()

    assert "result" in holder
    assert holder["result"].k == 1
    assert "N1" in holder["result"].connections