# scripts/smoke_test_map.py
"""
MapWidget(folium 버전) 단독 실행 스모크 테스트임. 실제 엑셀 데이터로 지도를 띄워서
눈으로 직접 확인하는 용도임.

실행: python scripts/smoke_test_map.py
"""
import sys
from PyQt5.QtWidgets import QApplication

from lorascape.gui.widgets.map_widget import MapWidget
from lorascape.data.site_inventory import load_gateways, load_nodes

XLSX_PATH = "sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx"

# 성남시 실증지역 대략 경계 (lon_min, lat_min, lon_max, lat_max)
BOUNDS = (127.07, 37.34, 127.16, 37.47)


def main():
    app = QApplication(sys.argv)

    gateways = load_gateways(XLSX_PATH)
    nodes = load_nodes(XLSX_PATH)
    print(f"GW {len(gateways)}개, Node {len(nodes)}개 로드됨")

    widget = MapWidget()
    widget.resize(1200, 900)
    widget.setWindowTitle("LoRaScape - MapWidget(Folium) 스모크 테스트")

    widget.set_bounds(BOUNDS)
    widget.refresh(gws=gateways, nodes=nodes)  # result 없이 GW/Node 마커만 우선 확인

    widget.sig_map_clicked.connect(lambda lon, lat: print(f"지도 클릭: ({lon:.5f}, {lat:.5f})"))
    widget.sig_gw_dragged.connect(lambda gw_id, lon, lat: print(f"GW 드래그: {gw_id} -> ({lon:.5f}, {lat:.5f})"))
    widget.sig_nd_dragged.connect(lambda node_id, lon, lat: print(f"Node 드래그: {node_id} -> ({lon:.5f}, {lat:.5f})"))

    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()