"""workers.py의 LoadDataWorker 검증 테스트임. QThread 없이 run()을 직접 호출해서 검증함."""
import pytest
from lorascape.gui.workers import LoadDataWorker

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