"""Kolayİndir uygulamasının giriş noktası."""

import sys

from PySide6.QtWidgets import QApplication

from src.config import APP_NAME
from src.main_window import MainWindow
from src.styles import APP_STYLE


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
