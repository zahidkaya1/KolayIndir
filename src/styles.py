"""Sade uygulama teması ve yüksek kontrastlı popup / menü stilleri."""

APP_STYLE = """
QWidget {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 14px;
    color: #172033;
}

QMainWindow {
    background: #f7f8fa;
}

QFrame#previewFrame {
    background: #f1f4f9;
    border: 1px solid #dce2ec;
    border-radius: 8px;
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

QLineEdit, QTextEdit {
    background: #ffffff;
    color: #172033;
    border: 1px solid #cfd6e2;
    border-radius: 8px;
    padding: 9px;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #2563eb;
}

QComboBox, QComboBox#mediaTypeCombo, QComboBox#qualityCombo, QComboBox#browserCombo {
    min-height: 38px;
    padding: 0px 34px 0px 10px;
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #cfd6e2;
    border-radius: 8px;
    font-size: 14px;
    selection-background-color: #e8f0fe;
    selection-color: #174ea6;
}

QComboBox:focus, QComboBox#mediaTypeCombo:focus, QComboBox#qualityCombo:focus, QComboBox#browserCombo:focus {
    border: 1px solid #2563eb;
    color: #172033;
}

QComboBox:disabled, QComboBox#mediaTypeCombo:disabled, QComboBox#qualityCombo:disabled, QComboBox#browserCombo:disabled {
    background-color: #f2f4f7;
    color: #667085;
    border-color: #d0d5dd;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid #d0d5dd;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}

QComboBox QAbstractItemView {
    min-width: 180px;
    background-color: #ffffff;
    color: #172033;
    selection-background-color: #e8f0fe;
    selection-color: #174ea6;
    border: 1px solid #d0d5dd;
    outline: 0;
    padding: 4px;
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
    min-height: 38px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background: #1d4ed8;
    border: 1px solid #1d4ed8;
    color: #ffffff;
}

QPushButton#primaryButton:pressed {
    background: #1e40af;
    border: 1px solid #1e40af;
    padding-top: 10px;
}

QPushButton#primaryButton:disabled {
    background: #93c5fd;
    color: #ffffff;
    border: 1px solid #93c5fd;
}

QPushButton#dangerButton, QPushButton#cancelButton {
    color: #b42318;
    background: #fff1f0;
    border: 1px solid #fecdca;
    min-height: 38px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#dangerButton:hover, QPushButton#cancelButton:hover {
    color: #912018;
    background: #fee4e2;
    border: 1px solid #fda29b;
}

QPushButton#dangerButton:pressed, QPushButton#cancelButton:pressed {
    color: #7a1b14;
    background: #fecdca;
    border: 1px solid #f97066;
    padding-top: 10px;
}

QPushButton#dangerButton:disabled, QPushButton#cancelButton:disabled {
    color: #d0d5dd;
    background: #fcfcfc;
    border: 1px solid #eaecf0;
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

/* Option Card Ayar Kartı Stilleri */
QFrame[optionCard="true"], QFrame#playlistOptionCard, QFrame#autoOpenOptionCard {
    background-color: #ffffff;
    border: 1px solid #d9e1ec;
    border-radius: 8px;
    min-height: 38px;
}

QFrame[optionCard="true"]:hover, QFrame#playlistOptionCard:hover, QFrame#autoOpenOptionCard:hover {
    background-color: #f1f5f9;
    border: 1px solid #b8c6d9;
}

QFrame[optionCard="true"][checked="true"], QFrame#playlistOptionCard[checked="true"], QFrame#autoOpenOptionCard[checked="true"] {
    background-color: #eaf2ff;
    border: 1px solid #2563eb;
}

QCheckBox#playlistCheckBox, QCheckBox#autoOpenCheckBox, QCheckBox.settingsOptionCheck {
    font-weight: 600;
    color: #1e293b;
    font-size: 14px;
    spacing: 10px;
}

QCheckBox#playlistCheckBox::indicator, QCheckBox#autoOpenCheckBox::indicator, QCheckBox.settingsOptionCheck::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1.5px solid #94a3b8;
    background-color: #ffffff;
}

QCheckBox#playlistCheckBox::indicator:hover, QCheckBox#autoOpenCheckBox::indicator:hover, QCheckBox.settingsOptionCheck::indicator:hover {
    border-color: #2563eb;
}

QCheckBox#playlistCheckBox::indicator:checked, QCheckBox#autoOpenCheckBox::indicator:checked, QCheckBox.settingsOptionCheck::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}
"""

