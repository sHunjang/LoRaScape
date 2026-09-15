# scripts/smoke_test_map.py
"""
MapWidget 단독 실행 스모크 테스트임. 실제 엑셀 데이터 + DEM으로 지도를 띄워서
눈으로 직접 확인하는 용도임 (자동화 테스트가 아니라 수동 확인용 스크립트).

실행: python scripts/smoke_test_map.py
"""
import sys
from PyQt5.QtWidgets import QApplication

from lorascape.gui.widgets.map_widget import MapWidget
from lorascape.data.dem_loader import DemLoader
from lorascape.data.site_inventory import load_gateways, load_nodes

XLSX_PATH = "sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx"
DEM_PATH = "sample_data/seongnam/dem_build_seongnam_3857-2.img"


def main():
    app = QApplication(sys.argv)

    gateways = load_gateways(XLSX_PATH)
    nodes = load_nodes(XLSX_PATH)
    print(f"GW {len(gateways)}개, Node {len(nodes)}개 로드됨")

    widget = MapWidget()
    widget.resize(1000, 800)
    widget.setWindowTitle("LoRaScape - MapWidget 스모크 테스트")

    # DEM 배경 로드 - 성남시 실증지역 대략 범위
    with DemLoader(DEM_PATH) as dem:
        widget.load_background(dem, lat_min=37.34, lat_max=37.47, lon_min=127.07, lon_max=127.16)
        # DemLoader가 with 블록 끝나면 닫히지만, 이미 배경 이미지는 만들어져서 화면엔 문제 없음

    widget.set_gateways(gateways)
    widget.set_nodes(nodes)  # coverage 없이 회색으로 표시
    widget.fit_to_data(gateways, nodes)

    widget.sig_marker_clicked.connect(
        lambda id_, kind: print(f"클릭됨: {kind} / {id_}")
    )

    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()