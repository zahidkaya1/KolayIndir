"""Sade uygulama teması."""

APP_STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 14px; color: #172033; }
QMainWindow { background: #f4f6fa; }
QFrame#contentCard { background: white; border: 1px solid #dce2ec; border-radius: 14px; }
QLabel#titleLabel { font-size: 28px; font-weight: 700; color: #111827; }
QLabel#subtitleLabel { color: #667085; }
QLabel#statusLabel { color: #344054; font-weight: 600; }
QLineEdit, QComboBox, QTextEdit { background: white; border: 1px solid #cfd6e2; border-radius: 8px; padding: 9px; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 1px solid #2563eb; }
QPushButton { background: #eef2f7; border: 1px solid #d4dbe7; border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #e4eaf3; }
QPushButton:disabled { color: #98a2b3; background: #f2f4f7; }
QPushButton#primaryButton { color: white; background: #2563eb; border: 1px solid #2563eb; }
QPushButton#primaryButton:hover { background: #1d4ed8; }
QPushButton#dangerButton { color: #b42318; background: #fff1f0; border: 1px solid #fecdca; }
QProgressBar { border: 1px solid #d0d5dd; border-radius: 7px; background: #f2f4f7; text-align: center; min-height: 18px; }
QProgressBar::chunk { border-radius: 6px; background: #2563eb; }
"""
