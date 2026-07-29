"""Kolayİndir ana kullanıcı arayüzü."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QThread, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from src.dependency_check import check_environment, get_environment_log_lines
from src.dialogs import (
    AppMessageDialog,
    DownloadCompletedDialog,
    UpdateAvailableDialog,
)
from src.download_worker import DownloadWorker
from src.models import DownloadRequest
from src.settings import load_settings, save_settings
from src.updater import UpdateWorker
from src.utils import clean_log_message, is_chrome_cookie_error


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._update_thread: QThread | None = None
        self._update_worker: UpdateWorker | None = None
        self._last_log_message: str | None = None
        self._download_succeeded_result: str | None = None
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
        self.url_input.setPlaceholderText(
            "YouTube, Instagram, X/Twitter veya desteklenen başka bir bağlantı…"
        )
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
        self.playlist_checkbox = QCheckBox(
            "Bağlantı oynatma listesiyse tamamını indir"
        )
        self.auto_open_checkbox = QCheckBox("İndirme tamamlandığında klasörü aç")
        self.auto_open_checkbox.toggled.connect(self._save_current_settings)

        for column, text in enumerate(("İndirme türü", "Kalite", "Oturum kullanımı")):
            grid.addWidget(QLabel(text), 0, column)
        grid.addWidget(self.media_combo, 1, 0)
        grid.addWidget(self.quality_combo, 1, 1)
        grid.addWidget(self.browser_combo, 1, 2)
        grid.addWidget(self.playlist_checkbox, 2, 0, 1, 2)
        grid.addWidget(self.auto_open_checkbox, 2, 2, 1, 1)
        card_layout.addWidget(options)

        card_layout.addWidget(QLabel("İndirme klasörü"))
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(False)
        self.folder_input.setPlaceholderText("İndirme klasör yolu…")
        self.folder_input.editingFinished.connect(self._on_folder_edited)

        self.folder_button = QPushButton("Klasör Seç")
        folder_menu = QMenu(self)
        folder_menu.setObjectName("folderMenu")
        folder_menu.addAction(
            "İndirilenler",
            lambda: self._set_quick_folder(Path.home() / "Downloads"),
        )
        folder_menu.addAction(
            "Masaüstü", lambda: self._set_quick_folder(Path.home() / "Desktop")
        )
        folder_menu.addAction(
            "Videolar", lambda: self._set_quick_folder(Path.home() / "Videos")
        )
        folder_menu.addSeparator()
        folder_menu.addAction("Başka Klasör Seç", self._choose_folder)
        self.folder_button.setMenu(folder_menu)

        self.open_folder_button = QPushButton("Klasörü Aç")
        self.open_folder_button.clicked.connect(self._open_current_folder)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.folder_button)
        folder_row.addWidget(self.open_folder_button)
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
        self.log_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        card_layout.addWidget(self.log_box)

        footer = QHBoxLayout()
        version_label = QLabel(f"Sürüm {APP_VERSION}")
        version_label.setObjectName("subtitleLabel")
        self.update_button = QPushButton("Güncellemeyi kontrol et")
        self.update_button.setObjectName("updateButton")
        self.update_button.clicked.connect(self.check_for_updates)
        footer.addWidget(version_label)
        footer.addStretch(1)
        footer.addWidget(self.update_button)
        card_layout.addLayout(footer)
        layout.addWidget(card, 1)
        self.setCentralWidget(root)

    def _set_quick_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.folder_input.setText(str(path))
        self._save_current_settings()

    def _on_folder_edited(self) -> None:
        path_text = self.folder_input.text().strip()
        if path_text:
            self._save_current_settings()

    def _open_current_folder(self) -> None:
        raw_path = self.folder_input.text().strip()
        if not raw_path:
            AppMessageDialog(
                "Geçersiz Klasör",
                "Lütfen bir indirme klasörü yolu girin.",
                "warning",
                self,
            ).exec()
            return
        folder_path = Path(raw_path)
        if not folder_path.exists():
            dlg = AppMessageDialog(
                "Klasör Bulunamadı",
                f"'{folder_path}' klasörü mevcut değil.\nOluşturulsun mu?",
                "question",
                self,
                [("yes", "Evet", True), ("no", "Hayır", False)],
            )
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.clicked_button_id == "yes":
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    AppMessageDialog(
                        "Klasör Oluşturulamadı",
                        f"Klasör oluşturulamadı:\n{exc}",
                        "error",
                        self,
                    ).exec()
                    return
            else:
                return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path.resolve()))):
            AppMessageDialog(
                "Klasör Açılamadı",
                "Klasör Dosya Gezgini'nde açılamadı.",
                "warning",
                self,
            ).exec()

    def _restore_settings(self) -> None:
        saved_dir = self.settings.get("output_dir", str(Path.home() / "Downloads"))
        if not Path(saved_dir).exists() or not Path(saved_dir).is_dir():
            saved_dir = str(Path.home() / "Downloads")
        self.folder_input.setText(saved_dir)
        self.media_combo.setCurrentText(
            self.settings.get("media_type", "Video (MP4)")
        )
        self.quality_combo.setCurrentText(
            self.settings.get("quality", "En iyi kalite")
        )
        self.playlist_checkbox.setChecked(False)
        self.auto_open_checkbox.setChecked(
            bool(self.settings.get("auto_open_folder", False))
        )
        self.browser_combo.setCurrentIndex(0)
        self._on_media_type_changed(self.media_combo.currentText())

    def _save_current_settings(self) -> None:
        save_settings({
            "output_dir": self.folder_input.text().strip(),
            "media_type": self.media_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "auto_open_folder": self.auto_open_checkbox.isChecked(),
        })

    def _show_dependency_status(self) -> None:
        lines = get_environment_log_lines()
        self._append_log("--- Ortam Kontrolü ---")
        for line in lines:
            self._append_log(line)

        env = check_environment()
        if not env["ffmpeg"] or not env["ffprobe"]:
            self._append_log(
                "Uyarı: FFmpeg veya FFprobe bulunamadı. Video/ses birleştirme çalışmayabilir."
            )
            self._append_log(
                "FFmpeg Kurulumu (PowerShell): winget install -e --id Gyan.FFmpeg"
            )
            self.status_label.setText(
                "FFmpeg eksik! Video ve ses birleştirme yapılamaz."
            )
        elif not env["deno"]:
            self._append_log(
                "Uyarı: Deno (JavaScript çalışma zamanı) bulunamadı. YouTube desteği bazı bağlantılarda sınırlı kalabilir."
            )
            self._append_log(
                "Deno Kurulumu (PowerShell): winget install -e --id DenoLand.Deno"
            )

    def _paste_url(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_input.setText(text)

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "İndirme klasörünü seç", self.folder_input.text()
        )
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
            AppMessageDialog(
                "Geçersiz Bağlantı",
                "Geçerli bir http veya https bağlantısı girin.",
                "warning",
                self,
            ).exec()
            return None
        raw_path = self.folder_input.text().strip()
        if not raw_path:
            AppMessageDialog(
                "Geçersiz Klasör",
                "Lütfen bir indirme klasörü yolu girin.",
                "warning",
                self,
            ).exec()
            return None
        output_dir = Path(raw_path)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            AppMessageDialog(
                "Klasör Hatası",
                f"İndirme klasörüne erişilemedi veya oluşturulamadı:\n{exc}",
                "error",
                self,
            ).exec()
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

        env = check_environment()
        if not env["ffmpeg"] or not env["ffprobe"]:
            self.status_label.setText("FFmpeg bulunamadığı için işlem durduruldu.")
            self._append_log(
                "Hata: FFmpeg veya FFprobe bulunamadığı için video ve ses birleştirme işlemi yapılamaz."
            )
            AppMessageDialog(
                "FFmpeg Eksik",
                "FFmpeg bulunamadığı için video ve ses birleştirme işlemi yapılamaz. "
                "FFmpeg’i kurduktan sonra uygulamayı yeniden başlatın.\n\n"
                "PowerShell kurulum komutu:\nwinget install -e --id Gyan.FFmpeg",
                "warning",
                self,
            ).exec()
            return

        request = self._create_request()
        if request is None:
            return
        self._save_current_settings()
        self._last_log_message = None
        self._download_succeeded_result = None
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
        self._download_succeeded_result = result

    def _download_failed(self, error: str) -> None:
        clean_err = clean_log_message(error)
        self.status_label.setText("İndirme başarısız oldu.")
        self._append_log(clean_err)

        if is_chrome_cookie_error(clean_err):
            dlg = AppMessageDialog(
                "Chrome Çerez Hatası",
                "Chrome çerez veritabanına erişilemedi. Chrome arka planda çalışıyor olabilir. "
                "Herkese açık içeriklerde Oturum Kullanımı seçeneğini Kullanma olarak ayarlayın. "
                "Oturum gerekiyorsa Chrome’u tamamen kapatıp yeniden deneyin veya Firefox kullanın.",
                "warning",
                self,
                [
                    ("retry", "Çerez kullanmadan tekrar dene", True),
                    ("close", "Kapat", False),
                ],
            )
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.clicked_button_id == "retry":
                self.browser_combo.setCurrentIndex(0)
                QTimer.singleShot(100, self.start_download)
        else:
            AppMessageDialog(
                "İndirme Hatası",
                f"İçerik indirilemedi.\n\nTeknik ayrıntı:\n{clean_err}",
                "error",
                self,
            ).exec()

    def _download_cancelled(self) -> None:
        self.status_label.setText("İndirme iptal edildi.")
        self._append_log("İşlem kullanıcı tarafından iptal edildi.")

    def _download_thread_finished(self) -> None:
        self._download_thread = None
        self._download_worker = None
        self._set_downloading_state(False)

        if self._download_succeeded_result is not None:
            result = self._download_succeeded_result
            self._download_succeeded_result = None
            if self.auto_open_checkbox.isChecked():
                self._open_current_folder()
            else:
                dlg = DownloadCompletedDialog(result_summary=result, parent=self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self._open_current_folder()

    def _set_downloading_state(self, active: bool) -> None:
        self.download_button.setEnabled(not active)
        self.cancel_button.setEnabled(active)
        self.url_input.setEnabled(not active)
        self.media_combo.setEnabled(not active)
        self.quality_combo.setEnabled(
            not active and self.media_combo.currentText() == "Video (MP4)"
        )
        self.browser_combo.setEnabled(not active)
        self.playlist_checkbox.setEnabled(not active)
        self.folder_input.setEnabled(not active)
        self.folder_button.setEnabled(not active)
        self.open_folder_button.setEnabled(not active)
        self.auto_open_checkbox.setEnabled(not active)

    def _append_log(self, message: str) -> None:
        cleaned = clean_log_message(message)
        if not cleaned:
            return
        if cleaned == self._last_log_message:
            return
        self._last_log_message = cleaned
        self.log_box.append(cleaned)

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
        dlg = UpdateAvailableDialog(tag=tag, notes=notes, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and page_url:
            QDesktopServices.openUrl(QUrl(page_url))

    def _update_up_to_date(self) -> None:
        AppMessageDialog(
            "Güncelleme Kontrolü",
            f"{APP_NAME} güncel. Sürüm: {APP_VERSION}",
            "info",
            self,
        ).exec()

    def _update_error(self, message: str) -> None:
        AppMessageDialog(
            "Güncelleme Kontrolü Başarısız",
            message,
            "warning",
            self,
        ).exec()

    def _update_thread_finished(self) -> None:
        self._update_thread = None
        self._update_worker = None
        self.update_button.setEnabled(True)
        self.update_button.setText("Güncellemeyi kontrol et")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText() and self._is_valid_url(
            event.mimeData().text()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        text = event.mimeData().text().strip()
        if self._is_valid_url(text):
            self.url_input.setText(text)
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_thread is not None:
            dlg = AppMessageDialog(
                "İndirme Sürüyor",
                "İndirme devam ediyor. Uygulama kapatılsın mı?",
                "question",
                self,
                [("yes", "Evet", True), ("no", "İptal", False)],
            )
            if dlg.exec() != QDialog.DialogCode.Accepted or dlg.clicked_button_id != "yes":
                event.ignore()
                return
            if self._download_worker is not None:
                self._download_worker.cancel()
            self._download_thread.quit()
            self._download_thread.wait(2000)
        self._save_current_settings()
        event.accept()
