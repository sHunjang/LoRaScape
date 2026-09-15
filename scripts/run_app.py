# scripts/run_app.py
"""
LoRaScape 앱 실행 진입점임.

흐름: 초기설정창(Shapefile/DEM 선택) -> 스플래시(START 클릭) -> 데이터 검증 로딩 -> 메인윈도우
"""
import os
import sys
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtCore import QTimer

from lorascape.gui.main_window import MainWindow, _styled_message_box, MESSAGEBOX_STYLE
from lorascape.gui.widgets.initial_setup_dialog import InitialSetupDialog
from lorascape.gui.widgets.splash_screen import SplashScreen

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lorascape", "gui", "assets")


def main():
    app = QApplication(sys.argv)

    # 1) 초기설정창 - Shapefile/DEM 선택
    setup = InitialSetupDialog()
    if setup.exec_() != QDialog.Accepted:
        sys.exit(0)
    paths = setup.get_paths()

    # 2) 스플래시 - START 클릭 대기
    splash = SplashScreen(assets_dir=ASSETS_DIR)
    main_window_holder = {}  # 클로저에서 MainWindow 참조를 들고 있기 위한 컨테이너

    def _on_splash_start():
        """
        START 클릭 -> 진행바 단계별 갱신하며 데이터 유효성 확인 -> MainWindow 생성 -> 페이드아웃.
        무거운 계산(엑셀/DEM 실제 로딩)은 MainWindow가 뜬 뒤 사용자가 목록창에서
        직접 불러오는 구조라, 여기서는 파일 존재 여부/DEM 오픈 가능 여부 정도만 검증함.
        """
        splash.update_progress(20, "지역 경계 파일 확인 중...")
        if not os.path.exists(paths["shp_path"]):
            _fail(f"Shapefile을 찾을 수 없습니다: {paths['shp_path']}")
            return

        splash.update_progress(50, "DEM 파일 확인 중...")
        try:
            from lorascape.data.dem_loader import DemLoader
            with DemLoader(paths["dem_path"]) as dem:
                pass  # 열리는지만 확인 - 실제 사용은 계산 시점에 다시 엶
        except Exception as e:
            _fail(f"DEM 파일을 여는 중 오류가 발생했습니다:\n{e}")
            return

        splash.update_progress(85, "메인 화면 준비 중...")
        window = MainWindow(xlsx_path=None, dem_path=paths["dem_path"])
        main_window_holder["window"] = window

        splash.finish_loading(delay_ms=400)
        QTimer.singleShot(450, lambda: window.show())

    def _fail(message: str):
        splash.hide()
        _styled_message_box(None, QMessageBox.Critical, "초기화 실패", message).exec_()
        sys.exit(1)

    splash.sig_start.connect(_on_splash_start)
    splash.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()