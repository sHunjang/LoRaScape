# scripts/measure_coverage.py
"""
GW 33개 x 단말로 커버리지를 재는 스크립트임. 코드를 바꾸기 전/후에 같은 조건으로 돌려서 숫자를 비교하는 용도임.
  python scripts/measure_coverage.py                 # 현재 코드의 기본 전파 모델
  python scripts/measure_coverage.py cost231         # 전파 모델을 지정 (propagation_model 연결 후에 사용 가능)
"""
import sys
import time
from collections import Counter

from lorascape.core.optimization.gw_placement import evaluate_gateways_coverage
from lorascape.data.dem_loader import DemLoader
from lorascape.data.site_inventory import load_gateways, load_nodes

XLSX = "sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx"
DEM = "sample_data/seongnam/dem_build_seongnam_3857-2.img"

kwargs = {"propagation_model": sys.argv[1]} if len(sys.argv) > 1 else {}
gws, nodes = load_gateways(XLSX), load_nodes(XLSX)
with DemLoader(DEM) as dem:
    start = time.time()
    r = evaluate_gateways_coverage(nodes, gws, dem, **kwargs)
    elapsed = time.time() - start

connected = [c for c in r.connections.values() if c is not None]
mean_pl = sum(c.path_loss_db for c in connected) / len(connected) if connected else float("nan")
print(f"GW {len(gws)}개 x 단말 {len(nodes)}개 | 모델 {kwargs.get('propagation_model', '(기본)')} | {elapsed:.2f}초")
print(f"커버율 {r.coverage_ratio * 100:.2f}% ({len(connected)}/{len(r.connections)}) | 연결된 링크 평균 경로손실 {mean_pl:.1f} dB")
print("SF 분포", dict(sorted(Counter(c.sf for c in connected).items())))
