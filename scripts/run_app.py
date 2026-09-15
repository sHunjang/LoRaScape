# scripts/run_app.py
"""LoRaScape 앱 실행 진입점임. 지금은 성남시 sample_data로 바로 띄움 -
초기설정창(Shapefile/DEM 선택) 생기면 이 하드코딩된 경로를 그쪽으로 넘길 예정임."""
import sys
from PyQt5.QtWidgets import QApplication
from lorascape.gui.main_window import MainWindow

XLSX_PATH = "sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx"
DEM_PATH = "sample_data/seongnam/dem_build_seongnam_3857-2.img"


def main():
    app = QApplication(sys.argv)
    window = MainWindow(xlsx_path=XLSX_PATH, dem_path=DEM_PATH)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()