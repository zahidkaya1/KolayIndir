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
    font-size: 30px;
    font-weight: 800;
    color: transparent;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
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
    background: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: #e2e8f0;
    color: #0f172a;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background: #cbd5e1;
    border-color: #64748b;
}

QPushButton:disabled {
    color: #94a3b8;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
}

QPushButton#primaryButton {
    color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
    border: 1px solid #2563eb;
    min-height: 38px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60a5fa, stop:1 #3b82f6);
    border: 1px solid #3b82f6;
    color: #ffffff;
}

QPushButton#primaryButton:pressed {
    background: #1d4ed8;
    border: 1px solid #1e40af;
    padding-top: 10px;
}

QPushButton#primaryButton:disabled {
    background: #93c5fd;
    color: #ffffff;
    border: 1px solid #bfdbfe;
}

QPushButton#accentButton {
    color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #9333ea);
    border: 1px solid #9333ea;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}

QPushButton#accentButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c084fc, stop:1 #a855f7);
    border: 1px solid #a855f7;
}

QPushButton#accentButton:pressed {
    background: #7e22ce;
    border: 1px solid #6b21a8;
}

QPushButton#accentButton:disabled {
    background: #d8b4fe;
    color: #f3e8ff;
    border: 1px solid #e9d5ff;
}


QPushButton#dangerButton, QPushButton#cancelButton {
    color: #dc2626;
    background: #fef2f2;
    border: 1px solid #fecaca;
    min-height: 38px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#dangerButton:hover, QPushButton#cancelButton:hover {
    color: #b91c1c;
    background: #fee2e2;
    border: 1px solid #fca5a5;
}

QPushButton#dangerButton:pressed, QPushButton#cancelButton:pressed {
    color: #991b1b;
    background: #fecaca;
    border: 1px solid #f87171;
    padding-top: 10px;
}

QPushButton#dangerButton:disabled, QPushButton#cancelButton:disabled {
    color: #94a3b8;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
}

QPushButton#secondaryButton, QPushButton#updateButton {
    background: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
}

QPushButton#secondaryButton:hover, QPushButton#updateButton:hover {
    background: #e2e8f0;
    color: #0f172a;
    border-color: #94a3b8;
}

QPushButton#secondaryButton:disabled, QPushButton#updateButton:disabled {
    color: #94a3b8;
    background: #f8fafc;
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
QDialog#downloadCompletedDialog, QDialog#updateDialog, QDialog#appMessageDialog, QDialog#downloadQueueDialog, QDialog, QMessageBox {
    background-color: #ffffff;
    color: #172033;
}

QDialog#downloadQueueDialog, QDialog#queueEditDialog {
    background-color: #f7f9fc;
    color: #172033;
}

QFrame#queueSettingsCard {
    background-color: #ffffff;
    border: 1px solid #dce2ec;
    border-radius: 8px;
}

QTextEdit#queueInput {
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #cfd6e2;
    border-radius: 8px;
    padding: 8px;
}

QTableWidget#queueTable {
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #cfd6e2;
    border-radius: 8px;
    gridline-color: #f1f5f9;
}

QTableWidget#queueTable QHeaderView::section {
    background-color: #f1f5f9;
    color: #334155;
    font-weight: 600;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #cfd6e2;
}

QHeaderView#queueVerticalHeader,
QHeaderView#queueVerticalHeader viewport {
    background-color: #ffffff;
    color: #172033;
}

QHeaderView#queueVerticalHeader::section {
    background-color: #f8fafc;
    color: #475569;
    font-size: 12px;
    padding: 4px;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #f1f5f9;
}

QTableWidget#queueTable QTableCornerButton::section {
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
}

QTableWidget#queueTable viewport {
    background-color: #ffffff;
    color: #172033;
}

QTableWidget#queueTable::item {
    padding: 4px 8px;
    color: #172033;
}

QTableWidget#queueTable::item:selected {
    background-color: #e8f0fe;
    color: #174ea6;
}

QLabel#queueSummary {
    color: #475569;
    font-weight: 600;
    font-size: 13px;
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

QScrollArea#mainScrollArea {
    border: none;
    background-color: #f7f8fa;
}

QScrollArea#mainScrollArea QWidget#qt_scrollarea_viewport {
    background-color: #f7f8fa;
}

QWidget#scrollContent {
    background-color: #f7f8fa;
}

QScrollBar:vertical {
    border: none;
    background: #f7f8fa;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QPushButton[actionRowButton="true"] {
    min-height: 42px;
    font-size: 14px;
}
QPushButton#primaryButton[actionRowButton="true"] {
    min-height: 42px;
}

QPushButton[historyToolbarButton="true"] {
    min-height: 40px;
    font-size: 14px;
}
QPushButton#dangerButton[historyToolbarButton="true"] {
    min-height: 40px;
}

QScrollBar:horizontal {
    height: 0px;
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

