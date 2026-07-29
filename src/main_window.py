"""Kolayİndir ana kullanıcı arayüzü."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QThread, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from src.config import APP_NAME, APP_VERSION, DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH
from src.dependency_check import dependency_warnings
from src.download_worker import DownloadWorker
from src.models import DownloadRequest
from src.settings import load_settings, save_settings
from src.updater import UpdateWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._update_thread: QThread | None = None
        self._update_worker: UpdateWorker | None = None
        self.settings = load_settings()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(680, 610)
        self.setAcceptDrops(True)
        self._build_ui()
        self._restore_settings()
        QTimer.singleShot(250, self._show_dependency_status)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        subtitle = QLabel("Bağlantıyı yapıştır, biçimi seç ve indir.")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)

        card = QFrame()
        card.setObjectName("contentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        card_layout.addWidget(QLabel("İçerik bağlantısı"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube, Instagram, X/Twitter veya desteklenen başka bir bağlantı…")
        self.url_input.returnPressed.connect(self.start_download)
        paste_button = QPushButton("Yapıştır")
        paste_button.clicked.connect(self._paste_url)
        url_row = QHBoxLayout()
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(paste_button)
        card_layout.addLayout(url_row)

        options = QFrame()
        grid = QGridLayout(options)
        self.media_combo = QComboBox()
        self.media_combo.addItems(["Video (MP4)", "Ses (MP3)"])
        self.media_combo.currentTextChanged.connect(self._on_media_type_changed)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["En iyi kalite", "1080p", "720p", "480p"])
        self.browser_combo = QComboBox()
        self.browser_combo.addItem("Oturum kullanma", None)
        self.browser_combo.addItem("Chrome oturumu", "chrome")
        self.browser_combo.addItem("Edge oturumu", "edge")
        self.browser_combo.addItem("Firefox oturumu", "firefox")
        self.playlist_checkbox = QCheckBox("Bağlantı oynatma listesiyse tamamını indir")
        for column, text in enumerate(("İndirme türü", "Kalite", "Oturum kullanımı")):
            grid.addWidget(QLabel(text), 0, column)
        grid.addWidget(self.media_combo, 1, 0)
        grid.addWidget(self.quality_combo, 1, 1)
        grid.addWidget(self.browser_combo, 1, 2)
        grid.addWidget(self.playlist_checkbox, 2, 0, 1, 3)
        card_layout.addWidget(options)

        card_layout.addWidget(QLabel("İndirme klasörü"))
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        folder_button = QPushButton("Klasör seç")
        folder_button.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(folder_button)
        card_layout.addLayout(folder_row)

        action_row = QHBoxLayout()
        self.download_button = QPushButton("İndirmeyi başlat")
        self.download_button.setObjectName("primaryButton")
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download)
        action_row.addWidget(self.download_button, 1)
        action_row.addWidget(self.cancel_button)
        card_layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        card_layout.addWidget(self.progress_bar)
        card_layout.addWidget(self.status_label)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("İşlem ayrıntıları burada görünecek.")
        self.log_box.setMinimumHeight(105)
        self.log_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout.addWidget(self.log_box)

        footer = QHBoxLayout()
        version_label = QLabel(f"Sürüm {APP_VERSION}")
        version_label.setObjectName("subtitleLabel")
        self.update_button = QPushButton("Güncellemeyi kontrol et")
        self.update_button.clicked.connect(self.check_for_updates)
        footer.addWidget(version_label)
        footer.addStretch(1)
        footer.addWidget(self.update_button)
        card_layout.addLayout(footer)
        layout.addWidget(card, 1)
        self.setCentralWidget(root)

    def _restore_settings(self) -> None:
        self.folder_input.setText(self.settings.get("output_dir", str(Path.home() / "Downloads")))
        self.media_combo.setCurrentText(self.settings.get("media_type", "Video (MP4)"))
        self.quality_combo.setCurrentText(self.settings.get("quality", "En iyi kalite"))
        self.playlist_checkbox.setChecked(bool(self.settings.get("playlist", False)))
        browser = self.settings.get("browser")
        for index in range(self.browser_combo.count()):
            if self.browser_combo.itemData(index) == browser:
                self.browser_combo.setCurrentIndex(index)
                break
        self._on_media_type_changed(self.media_combo.currentText())

    def _save_current_settings(self) -> None:
        save_settings({
            "output_dir": self.folder_input.text(),
            "media_type": self.media_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "playlist": self.playlist_checkbox.isChecked(),
            "browser": self.browser_combo.currentData(),
        })

    def _show_dependency_status(self) -> None:
        warnings = dependency_warnings()
        if warnings:
            self.status_label.setText(warnings[0])
            for warning in warnings:
                self._append_log(f"Ortam uyarısı: {warning}")

    def _paste_url(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_input.setText(text)

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "İndirme klasörünü seç", self.folder_input.text())
        if selected:
            self.folder_input.setText(selected)
            self._save_current_settings()

    def _on_media_type_changed(self, media_type: str) -> None:
        self.quality_combo.setEnabled(media_type == "Video (MP4)")

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _create_request(self) -> DownloadRequest | None:
        url = self.url_input.text().strip()
        if not self._is_valid_url(url):
            QMessageBox.warning(self, "Geçersiz bağlantı", "Geçerli bir http veya https bağlantısı girin.")
            return None
        output_dir = Path(self.folder_input.text().strip())
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Klasör hatası", f"İndirme klasörü oluşturulamadı:\n{exc}")
            return None
        return DownloadRequest(
            url=url,
            output_dir=output_dir,
            media_type=self.media_combo.currentText(),
            quality=self.quality_combo.currentText(),
            playlist=self.playlist_checkbox.isChecked(),
            browser=self.browser_combo.currentData(),
        )

    def start_download(self) -> None:
        if self._download_thread is not None:
            return
        request = self._create_request()
        if request is None:
            return
        self._save_current_settings()
        self.log_box.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("İndirme hazırlanıyor…")
        self._set_downloading_state(True)
        thread = QThread(self)
        worker = DownloadWorker(request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress_bar.setValue)
        worker.status.connect(self.status_label.setText)
        worker.log.connect(self._append_log)
        worker.succeeded.connect(self._download_succeeded)
        worker.failed.connect(self._download_failed)
        worker.cancelled.connect(self._download_cancelled)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._download_thread_finished)
        self._download_thread = thread
        self._download_worker = worker
        thread.start()

    def cancel_download(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel()
            self.cancel_button.setEnabled(False)

    def _download_succeeded(self, result: str) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText("İndirme başarıyla tamamlandı.")
        self._append_log(f"Tamamlandı: {result}")
        if QMessageBox.question(self, "İndirme tamamlandı", "İndirme klasörü açılsın mı?") == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_input.text()))

    def _download_failed(self, error: str) -> None:
        self.status_label.setText("İndirme başarısız oldu.")
        self._append_log(error)
        QMessageBox.critical(self, "İndirme hatası", f"İçerik indirilemedi.\n\nTeknik ayrıntı:\n{error}")

    def _download_cancelled(self) -> None:
        self.status_label.setText("İndirme iptal edildi.")
        self._append_log("İşlem kullanıcı tarafından iptal edildi.")

    def _download_thread_finished(self) -> None:
        self._download_thread = None
        self._download_worker = None
        self._set_downloading_state(False)

    def _set_downloading_state(self, active: bool) -> None:
        self.download_button.setEnabled(not active)
        self.cancel_button.setEnabled(active)
        self.url_input.setEnabled(not active)
        self.media_combo.setEnabled(not active)
        self.quality_combo.setEnabled(not active and self.media_combo.currentText() == "Video (MP4)")
        self.browser_combo.setEnabled(not active)
        self.playlist_checkbox.setEnabled(not active)

    def _append_log(self, message: str) -> None:
        if message.strip():
            self.log_box.append(message.strip())

    def check_for_updates(self) -> None:
        if self._update_thread is not None:
            return
        self.update_button.setEnabled(False)
        self.update_button.setText("Kontrol ediliyor…")
        thread = QThread(self)
        worker = UpdateWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.update_available.connect(self._update_available)
        worker.up_to_date.connect(self._update_up_to_date)
        worker.error.connect(self._update_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._update_thread_finished)
        self._update_thread = thread
        self._update_worker = worker
        thread.start()

    def _update_available(self, tag: str, page_url: str, notes: str) -> None:
        summary = notes[:500] if notes else "Yeni sürüm notu bulunmuyor."
        answer = QMessageBox.question(self, "Yeni sürüm bulundu", f"{tag} yayınlanmış.\n\n{summary}\n\nRelease sayfası açılsın mı?")
        if answer == QMessageBox.StandardButton.Yes and page_url:
            QDesktopServices.openUrl(QUrl(page_url))

    def _update_up_to_date(self) -> None:
        QMessageBox.information(self, "Güncelleme", f"{APP_NAME} güncel. Sürüm: {APP_VERSION}")

    def _update_error(self, message: str) -> None:
        QMessageBox.warning(self, "Güncelleme kontrolü", message)

    def _update_thread_finished(self) -> None:
        self._update_thread = None
        self._update_worker = None
        self.update_button.setEnabled(True)
        self.update_button.setText("Güncellemeyi kontrol et")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText() and self._is_valid_url(event.mimeData().text()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        text = event.mimeData().text().strip()
        if self._is_valid_url(text):
            self.url_input.setText(text)
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_thread is not None:
            answer = QMessageBox.question(self, "İndirme sürüyor", "İndirme devam ediyor. Uygulama kapatılsın mı?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self._download_worker is not None:
                self._download_worker.cancel()
            self._download_thread.quit()
            self._download_thread.wait(2000)
        self._save_current_settings()
        event.accept()
