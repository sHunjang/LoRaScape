# scripts/run_app.py
"""
LoRaScape 앱 실행 진입점임.

흐름: 라이선스 인증(조용한 재검증 우선, 실패 시 다이얼로그) -> 초기설정창(Shapefile/DEM 선택)
     -> 스플래시(START 클릭) -> 데이터 검증 로딩 -> 메인윈도우
"""
import os
import sys
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtCore import QTimer

from lorascape.gui.main_window import MainWindow, _styled_message_box
from lorascape.gui.widgets.initial_setup_dialog import InitialSetupDialog
from lorascape.gui.widgets.splash_screen import SplashScreen
from lorascape.gui.widgets.license_dialog import LicenseDialog, try_silent_login

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lorascape", "gui", "assets")


def _ensure_licensed(app) -> bool:
    """
    라이선스 인증을 확인함. 저장된 값으로 조용히 재검증되면 다이얼로그 없이
    바로 True를 반환하고, 안 되면 LicenseDialog를 띄워서 사용자가 인증할
    때까지 재시도 기회를 줌 (취소하면 False - 앱 종료).
    """
    if try_silent_login():
        return True

    dialog = LicenseDialog()
    return dialog.exec_() == QDialog.Accepted


def main():
    app = QApplication(sys.argv)

    if not _ensure_licensed(app):
        sys.exit(0)  # 인증 취소 시 조용히 종료함

    setup = InitialSetupDialog()
    if setup.exec_() != QDialog.Accepted:
        sys.exit(0)
    paths = setup.get_paths()

    splash = SplashScreen(assets_dir=ASSETS_DIR)
    main_window_holder = {}

    def _on_splash_start():
        splash.update_progress(20, "지역 경계 파일 확인 중...")
        if not os.path.exists(paths["shp_path"]):
            _fail(f"Shapefile을 찾을 수 없습니다: {paths['shp_path']}")
            return

        splash.update_progress(50, "DEM 파일 확인 중...")
        try:
            from lorascape.data.dem_loader import DemLoader
            with DemLoader(paths["dem_path"]) as dem:
                pass
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