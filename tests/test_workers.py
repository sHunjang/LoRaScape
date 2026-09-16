"""workers.py의 LoadDataWorker 검증 테스트임. QThread 없이 run()을 직접 호출해서 검증함."""
import pytest
from lorascape.gui.workers import LoadDataWorker, HeatmapWorker

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


def test_heatmap_worker_emits_layers_for_each_gateway():
    import os
    dem_path = "sample_data/seongnam/dem_build_seongnam_3857-2.img"
    if not os.path.exists(dem_path):
        pytest.skip("성남시 DEM 샘플 파일이 없어서 건너뜀")

    from lorascape.data.schema import GatewaySite
    gw = GatewaySite(
        gw_id="TEST_GW", region="테스트", location_desc="",
        lat=37.40, lon=127.12, install_type="테스트", power_source="테스트",
    )

    worker = HeatmapWorker([gw], dem_path, grid_size=5, radius_km=0.5)
    result = {}
    errors = []
    worker.finished.connect(lambda layers: result.update(layers=layers))
    worker.error.connect(lambda msg: errors.append(msg))  # ★ 진단용 추가
    worker.run()

    assert not errors, f"워커에서 에러 발생: {errors}"  # ★ 에러 있으면 메시지 그대로 출력
    assert "layers" in result


def test_heatmap_worker_emits_error_on_missing_dem():
    from lorascape.data.schema import GatewaySite
    gw = GatewaySite(
        gw_id="TEST_GW", region="테스트", location_desc="",
        lat=37.40, lon=127.12, install_type="테스트", power_source="테스트",
    )
    worker = HeatmapWorker([gw], "nonexistent_dem.img", grid_size=5)
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))
    worker.run()
    assert len(errors) == 1