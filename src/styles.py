"""Sade uygulama teması ve yüksek kontrastlı popup / menü stilleri."""

APP_STYLE = """
QWidget {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 14px;
    color: #172033;
}

QMainWindow {
    background: #f4f6fa;
}

QFrame#contentCard {
    background: #ffffff;
    border: 1px solid #dce2ec;
    border-radius: 14px;
}

QLabel#titleLabel {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
}

QLabel#subtitleLabel {
    color: #667085;
}

QLabel#statusLabel {
    color: #344054;
    font-weight: 600;
}

QLineEdit, QComboBox, QTextEdit {
    background: #ffffff;
    color: #172033;
    border: 1px solid #cfd6e2;
    border-radius: 8px;
    padding: 9px;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #2563eb;
}

QPushButton {
    background: #eef2f7;
    color: #172033;
    border: 1px solid #d4dbe7;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: #e4eaf3;
    color: #0f172a;
}

QPushButton:pressed {
    background: #dce4f0;
}

QPushButton:disabled {
    color: #98a2b3;
    background: #f2f4f7;
    border: 1px solid #eaecf0;
}

QPushButton#primaryButton {
    color: #ffffff;
    background: #2563eb;
    border: 1px solid #2563eb;
}

QPushButton#primaryButton:hover {
    background: #1d4ed8;
    color: #ffffff;
}

QPushButton#primaryButton:disabled {
    background: #93c5fd;
    color: #ffffff;
    border: 1px solid #93c5fd;
}

QPushButton#dangerButton {
    color: #b42318;
    background: #fff1f0;
    border: 1px solid #fecdca;
}

QPushButton#updateButton {
    background: #eef2f7;
    color: #172033;
    border: 1px solid #d4dbe7;
}

QPushButton#updateButton:hover {
    background: #e4eaf3;
    color: #0f172a;
}

QPushButton#updateButton:disabled {
    color: #98a2b3;
    background: #f2f4f7;
}

QProgressBar {
    border: 1px solid #d0d5dd;
    border-radius: 7px;
    background: #f2f4f7;
    text-align: center;
    color: #172033;
    min-height: 18px;
}

QProgressBar::chunk {
    border-radius: 6px;
    background: #2563eb;
}

/* QMenu Açılır Menü Stilleri */
QMenu#folderMenu, QMenu {
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d0d5dd;
    border-radius: 8px;
    padding: 6px;
}

QMenu#folderMenu::item, QMenu::item {
    background-color: transparent;
    color: #172033;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
}

QMenu#folderMenu::item:selected, QMenu::item:selected {
    background-color: #e8f0fe;
    color: #174ea6;
}

QMenu#folderMenu::item:disabled, QMenu::item:disabled {
    color: #98a2b3;
}

QMenu#folderMenu::separator, QMenu::separator {
    height: 1px;
    background-color: #e2e8f0;
    margin: 4px 0px;
}

/* QDialog & Özel Popup Pencere Stilleri */
QDialog#downloadCompletedDialog, QDialog#updateDialog, QDialog#appMessageDialog, QDialog, QMessageBox {
    background-color: #ffffff;
    color: #172033;
}

QLabel#dialogTitleLabel, QLabel#updateDialogTitle {
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
}

QLabel#dialogMessageLabel {
    font-size: 14px;
    color: #334155;
}

QLabel#updateDialogMessage {
    font-size: 13px;
    color: #334155;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px;
}

QPushButton#dialogPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #2563eb;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    min-height: 36px;
    min-width: 100px;
}

QPushButton#dialogPrimaryButton:hover {
    background-color: #1d4ed8;
    color: #ffffff;
}

QPushButton#dialogPrimaryButton:pressed {
    background-color: #1e40af;
}

QPushButton#dialogSecondaryButton {
    background-color: #eef2f7;
    color: #172033;
    border: 1px solid #d4dbe7;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    min-height: 36px;
    min-width: 80px;
}

QPushButton#dialogSecondaryButton:hover {
    background-color: #e4eaf3;
    color: #0f172a;
}

QPushButton#dialogSecondaryButton:pressed {
    background-color: #dce4f0;
}

QScrollArea {
    border: none;
    background-color: transparent;
}
"""
