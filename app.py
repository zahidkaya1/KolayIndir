"""Loadvia uygulamasının giriş noktası."""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.config import APP_NAME
from src.main_window import MainWindow
from src.styles import APP_STYLE
from src.utils import get_brand_asset_path, setup_environment_paths


def main() -> int:
    setup_environment_paths()

    if sys.platform == "win32":
        try:
            import ctypes
            app_id = "zahidkaya.Loadvia.1.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:  # noqa: BLE001, S110
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    icon_path = get_brand_asset_path("loadvia.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    app.setStyleSheet(APP_STYLE)
    window = MainWindow()

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
