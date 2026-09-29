# scripts/diagnose_dem.py
"""
DEM의 값 없는 칸(nodata)이 GW/단말 위치와 GW-단말 지형 프로파일에 실제로 얼마나 걸리는지 재는 진단 스크립트임.
수정 전/후 어느 버전의 dem_loader에서도 돌아감 (항상 예전 동작인 '0m로 채움'으로 측정함).

사용법 (프로젝트 루트에서):
  python scripts/diagnose_dem.py
  python scripts/diagnose_dem.py <DEM 경로> <엑셀 경로>
"""
import sys

import numpy as np
from rasterio.warp import transform as rio_transform

from lorascape.data.dem_loader import DemLoader
from lorascape.data.site_inventory import load_gateways, load_nodes

DEM = sys.argv[1] if len(sys.argv) > 1 else "sample_data/seongnam/dem_build_seongnam_3857-2.img"
XLSX = sys.argv[2] if len(sys.argv) > 2 else "sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx"
MAX_PAIR_KM = 2.0     # 실제로 연결될 수 있는 거리만 봄
N_SAMPLES = 20


def open_dem(path):
    try:
        return DemLoader(path, fill_holes=False)   # 수정 후 버전: 예전 동작으로 측정
    except TypeError:
        return DemLoader(path)                     # 수정 전 버전은 원래 0m로 채움


def classify(dem, lat, lon):
    if dem.get_elevation(lat, lon) is not None:
        return "ok"
    xs, ys = rio_transform("EPSG:4326", dem.crs, [lon], [lat])
    row, col = dem.dataset.index(xs[0], ys[0])
    h, w = dem._band.shape
    return "범위 밖" if (row < 0 or row >= h or col < 0 or col >= w) else "nodata"


def main():
    gws, nodes = load_gateways(XLSX), load_nodes(XLSX)
    with open_dem(DEM) as dem:
        band, nodata = dem._band, dem._nodata
        holes = int((band == nodata).sum()) if nodata is not None else 0
        print(f"DEM 크기 {band.shape[1]}x{band.shape[0]} | nodata 값 {nodata} | 값 없는 칸 {holes:,}개 "
              f"({holes / band.size * 100:.2f}%)")

        for label, items, idattr in (("GW", gws, "gw_id"), ("단말", nodes, "node_id")):
            bad = [(getattr(i, idattr), classify(dem, i.lat, i.lon)) for i in items]
            bad = [b for b in bad if b[1] != "ok"]
            print(f"{label} {len(items)}개 중 위치에 DEM 값이 없는 것: {len(bad)}개  {bad[:8]}")

        from lorascape.data.coord_transform import distance_m
        pairs = end_zero = any_zero = 0
        gw_hit = set()
        for g in gws:
            for n in nodes:
                if distance_m(g.lat, g.lon, n.lat, n.lon) / 1000.0 > MAX_PAIR_KM:
                    continue
                elev = np.array([e for _, e in dem.get_elevation_profile(g.lat, g.lon, n.lat, n.lon, N_SAMPLES)])
                pairs += 1
                if elev[0] == 0.0 or elev[-1] == 0.0:
                    end_zero += 1
                    gw_hit.add(g.gw_id)
                if (elev == 0.0).any():
                    any_zero += 1
        if pairs:
            print(f"{MAX_PAIR_KM:.0f}km 이내 GW-단말 쌍 {pairs}개 중 - 끝점이 0m인 쌍: {end_zero}개 "
                  f"({end_zero / pairs * 100:.1f}%), 경로 어딘가가 0m인 쌍: {any_zero}개 ({any_zero / pairs * 100:.1f}%)")
            print(f"끝점이 0m로 잡히는 쌍을 가진 GW: {len(gw_hit)}개")
        print("\n해석: 끝점이 0m인 쌍이 많으면 dem_loader의 fill_holes 수정이 결과를 크게 바꿀 것이고,"
              "\n      거의 0이면 영향이 작으니 급하지 않음.")


if __name__ == "__main__":
    main()
