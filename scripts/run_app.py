# scripts/run_app.py
"""LoRaScape 앱 실행 진입점임."""
import sys
from PyQt5.QtWidgets import QApplication, QDialog
from lorascape.gui.main_window import MainWindow
from lorascape.gui.widgets.initial_setup_dialog import InitialSetupDialog


def main():
    app = QApplication(sys.argv)

    setup = InitialSetupDialog()
    if setup.exec_() != QDialog.Accepted:
        sys.exit(0)

    paths = setup.get_paths()

    # xlsx_path가 비어있으면(첫 실행이거나 아직 한 번도 불러온 적 없으면) None으로 넘겨서
    # MainWindow가 자동 로딩을 시도하지 않게 함 - 사용자가 GW/단말 목록창에서 직접 불러오면 됨.
    window = MainWindow(xlsx_path=paths["xlsx_path"] or None, dem_path=paths["dem_path"])
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()