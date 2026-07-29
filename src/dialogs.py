"""Kolayİndir özel açık temalı diyalog pencere bileşenleri."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config import APP_VERSION


class DownloadCompletedDialog(QDialog):
    """İndirme tamamlandığında gösterilen açık temalı özel onay penceresi."""

    def __init__(
        self,
        result_summary: str = "",
        filepath: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("downloadCompletedDialog")
        self.setWindowTitle("İndirme tamamlandı")
        self.setMinimumWidth(400)
        self.setMaximumWidth(580)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.filepath = filepath
        self.action_choice = "cancel"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self.title_label = QLabel("İçerik başarıyla indirildi.")
        self.title_label.setObjectName("dialogTitleLabel")

        msg_text = "İndirme klasörünü açmak ister misiniz?"
        if result_summary:
            msg_text = f"Tamamlanan: {result_summary}\n\n{msg_text}"

        self.message_label = QLabel(msg_text)
        self.message_label.setObjectName("dialogMessageLabel")
        self.message_label.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        self.secondary_button = QPushButton("Kapat")
        self.secondary_button.setObjectName("dialogSecondaryButton")
        self.secondary_button.clicked.connect(self.reject)
        btn_row.addWidget(self.secondary_button)

        if self.filepath and Path(self.filepath).exists():
            self.open_file_button = QPushButton("Dosyayı Aç")
            self.open_file_button.setObjectName("dialogSecondaryButton")
            self.open_file_button.clicked.connect(self._on_open_file)
            btn_row.addWidget(self.open_file_button)

        self.primary_button = QPushButton("Klasörü Aç")
        self.primary_button.setObjectName("dialogPrimaryButton")
        self.primary_button.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self.primary_button)

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addSpacing(8)
        layout.addLayout(btn_row)

    def _on_open_folder(self) -> None:
        self.action_choice = "open_folder"
        self.accept()

    def _on_open_file(self) -> None:
        self.action_choice = "open_file"
        self.accept()


class LogDialog(QDialog):
    """Teknik ayrıntıları ve yt-dlp loglarını gösteren özel diyalog penceresi."""

    def __init__(self, log_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("logDialog")
        self.setWindowTitle("Teknik Ayrıntılar")
        self.setMinimumWidth(480)
        self.setMaximumWidth(600)
        self.setMinimumHeight(320)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        title = QLabel("Teknik İndirme Günlüğü")
        title.setObjectName("dialogTitleLabel")

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(
            log_text if log_text.strip() else "Henüz teknik kayıt bulunmuyor."
        )

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        copy_btn = QPushButton("Metni Kopyala")
        copy_btn.setObjectName("dialogSecondaryButton")
        copy_btn.clicked.connect(self._copy_text)

        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("dialogPrimaryButton")
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)

        layout.addWidget(title)
        layout.addWidget(self.text_edit, 1)
        layout.addLayout(btn_row)

    def _copy_text(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.text_edit.toPlainText())



class UpdateAvailableDialog(QDialog):
    """Yeni sürüm bulunduğunda gösterilen özel diyalog penceresi."""

    def __init__(
        self, tag: str, notes: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("updateDialog")
        self.setWindowTitle("Yeni Sürüm Bulundu")
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)
        self.setMaximumHeight(560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self.title_label = QLabel("Yeni Sürüm Bulundu")
        self.title_label.setObjectName("updateDialogTitle")

        info_label = QLabel(f"Mevcut sürüm: {APP_VERSION}\nYeni sürüm: {tag}")
        info_label.setObjectName("dialogMessageLabel")

        notes_header = QLabel("Sürüm Notları:")
        notes_header.setObjectName("dialogMessageLabel")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)
        scroll.setMaximumHeight(220)

        notes_content = QLabel(notes if notes.strip() else "Yeni sürüm notu bulunmuyor.")
        notes_content.setObjectName("updateDialogMessage")
        notes_content.setWordWrap(True)
        notes_content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(notes_content)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        self.primary_button = QPushButton("Güncelleme sayfasını aç")
        self.primary_button.setObjectName("dialogPrimaryButton")
        self.primary_button.clicked.connect(self.accept)

        self.secondary_button = QPushButton("Kapat")
        self.secondary_button.setObjectName("dialogSecondaryButton")
        self.secondary_button.clicked.connect(self.reject)

        btn_row.addWidget(self.secondary_button)
        btn_row.addWidget(self.primary_button)

        layout.addWidget(self.title_label)
        layout.addWidget(info_label)
        layout.addWidget(notes_header)
        layout.addWidget(scroll, 1)
        layout.addSpacing(8)
        layout.addLayout(btn_row)


class AppMessageDialog(QDialog):
    """Genel bilgi, uyarı ve hata bildirimleri için açık temalı diyalog penceresi."""

    def __init__(
        self,
        title: str,
        message: str,
        dialog_type: str = "info",
        parent: QWidget | None = None,
        custom_buttons: list[tuple[str, str, bool]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("appMessageDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.setMaximumWidth(560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("dialogTitleLabel")

        self.message_label = QLabel(message)
        self.message_label.setObjectName("dialogMessageLabel")
        self.message_label.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        self.clicked_button_id: str | None = None

        if custom_buttons:
            for btn_id, label, is_primary in custom_buttons:
                btn = QPushButton(label)
                if is_primary:
                    btn.setObjectName("dialogPrimaryButton")
                else:
                    btn.setObjectName("dialogSecondaryButton")
                btn.clicked.connect(lambda _, b_id=btn_id: self._on_button_click(b_id))
                btn_row.addWidget(btn)
        else:
            close_btn = QPushButton("Tamam")
            close_btn.setObjectName("dialogPrimaryButton")
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addSpacing(8)
        layout.addLayout(btn_row)

    def _on_button_click(self, btn_id: str) -> None:
        self.clicked_button_id = btn_id
        self.accept()

