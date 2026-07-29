"""Kolayİndir ana kullanıcı arayüzü."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QPixmap,
)
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
    QVBoxLayout,
    QWidget,
)

from src.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from src.dependency_check import (
    check_environment,
    dependency_warnings,
    get_environment_log_lines,
)
from src.dialogs import (
    AppMessageDialog,
    DownloadCompletedDialog,
    LogDialog,
    UpdateAvailableDialog,
)
from src.download_worker import DownloadWorker
from src.metadata_worker import MetadataWorker
from src.models import DownloadRequest, MediaMetadata, format_bytes
from src.settings import load_settings, save_settings
from src.updater import UpdateWorker
from src.utils import (
    clean_log_message,
    configure_combo_box,
    set_combo_value,
)
from src.widgets import OptionCard


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._metadata_thread: QThread | None = None
        self._metadata_worker: MetadataWorker | None = None
        self._update_thread: QThread | None = None
        self._update_worker: UpdateWorker | None = None
        self._last_log_message: str | None = None
        self._download_succeeded_result: str | None = None
        self._download_succeeded_path: str = ""
        self._log_history: list[str] = []
        self._current_metadata: MediaMetadata | None = None
        self._close_requested: bool = False
        self._close_dialog_open: bool = False
        self.settings = load_settings()

        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowFlags(flags)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setFixedSize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setAcceptDrops(True)



        self._center_on_screen()
        self._build_ui()
        self._restore_settings()
        QTimer.singleShot(250, self._show_dependency_status)


    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - DEFAULT_WINDOW_WIDTH) // 2 + geo.x()
            y = (geo.height() - DEFAULT_WINDOW_HEIGHT) // 2 + geo.y()
            self.move(x, y)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(8)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        subtitle = QLabel("Bağlantıyı yapıştır, biçimi seç ve indir.")
        subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        layout.addWidget(QLabel("İçerik bağlantısı"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "YouTube, Instagram, X/Twitter veya desteklenen başka bir bağlantı…"
        )
        self.url_input.setMinimumHeight(38)
        self.url_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.url_input.textChanged.connect(self._on_url_changed)
        self.url_input.returnPressed.connect(self.analyze_url)

        paste_button = QPushButton("Yapıştır")
        paste_button.clicked.connect(self._paste_url)

        self.analyze_button = QPushButton("İncele")
        self.analyze_button.clicked.connect(self.analyze_url)

        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(paste_button)
        url_row.addWidget(self.analyze_button)
        layout.addLayout(url_row)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        self.preview_frame.hide()
        preview_layout = QHBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(10, 8, 10, 8)
        preview_layout.setSpacing(12)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(140, 78)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet(
            "background-color: #e2e8f0; border-radius: 6px; color: #64748b;"
        )
        self.thumbnail_label.setText("Önizleme")
        preview_layout.addWidget(self.thumbnail_label)

        meta_info_box = QVBoxLayout()
        meta_info_box.setSpacing(3)
        self.meta_title_label = QLabel("İçerik başlığı yükleniyor…")
        self.meta_title_label.setStyleSheet("font-weight: 700; color: #0f172a;")
        self.meta_title_label.setWordWrap(True)

        self.meta_uploader_label = QLabel("Kanal / Yükleyen")
        self.meta_uploader_label.setStyleSheet("color: #475569; font-size: 13px;")

        self.meta_badges_label = QLabel("Kaynak: — • İndirilecek: — • Tahmini: —")
        self.meta_badges_label.setStyleSheet("color: #2563eb; font-size: 13px; font-weight: 600;")

        meta_info_box.addWidget(self.meta_title_label)
        meta_info_box.addWidget(self.meta_uploader_label)
        meta_info_box.addWidget(self.meta_badges_label)
        preview_layout.addLayout(meta_info_box, 1)
        layout.addWidget(self.preview_frame)

        options_grid = QGridLayout()
        options_grid.setContentsMargins(0, 0, 0, 0)
        options_grid.setSpacing(8)
        options_grid.setColumnStretch(0, 1)
        options_grid.setColumnStretch(1, 1)
        options_grid.setColumnStretch(2, 1)

        self.media_combo = QComboBox()
        self.media_combo.setObjectName("mediaTypeCombo")
        self.media_combo.addItems(["Video (MP4)", "Ses (MP3)"])
        self.media_combo.currentTextChanged.connect(self._on_media_type_changed)
        configure_combo_box(self.media_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("qualityCombo")
        self.quality_combo.addItems([
            "En iyi kullanılabilir kalite",
            "1080p’ye kadar",
            "720p’ye kadar",
            "480p’ye kadar",
        ])
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)
        configure_combo_box(self.quality_combo)

        self.browser_combo = QComboBox()
        self.browser_combo.setObjectName("browserCombo")
        self.browser_combo.addItem("Oturum kullanma", None)
        self.browser_combo.addItem("Chrome oturumu", "chrome")
        self.browser_combo.addItem("Edge oturumu", "edge")
        self.browser_combo.addItem("Firefox oturumu", "firefox")
        configure_combo_box(self.browser_combo)

        self.playlist_checkbox = QCheckBox(
            "Oynatma listesinin tamamını indir"
        )
        self.playlist_checkbox.setObjectName("playlistCheckBox")
        self.playlist_card = OptionCard(
            self.playlist_checkbox,
            object_name="playlistOptionCard",
        )

        self.auto_open_checkbox = QCheckBox("İndirme tamamlandığında klasörü aç")
        self.auto_open_checkbox.setObjectName("autoOpenCheckBox")
        self.auto_open_checkbox.toggled.connect(self._save_current_settings)
        self.auto_open_card = OptionCard(
            self.auto_open_checkbox,
            object_name="autoOpenOptionCard",
        )

        for column, text in enumerate(("İndirme türü", "Kalite", "Oturum kullanımı")):
            options_grid.addWidget(QLabel(text), 0, column)
        options_grid.addWidget(self.media_combo, 1, 0)
        options_grid.addWidget(self.quality_combo, 1, 1)
        options_grid.addWidget(self.browser_combo, 1, 2)
        layout.addLayout(options_grid)

        cards_box = QVBoxLayout()
        cards_box.setSpacing(6)
        cards_box.addWidget(self.playlist_card)
        cards_box.addWidget(self.auto_open_card)
        layout.addLayout(cards_box)


        layout.addWidget(QLabel("İndirme klasörü"))
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(False)
        self.folder_input.setPlaceholderText("İndirme klasör yolu…")
        self.folder_input.setMinimumHeight(38)
        self.folder_input.setMinimumWidth(180)
        self.folder_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
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
        layout.addLayout(folder_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.download_button = QPushButton("İndirmeyi başlat")
        self.download_button.setObjectName("primaryButton")
        self.download_button.clicked.connect(self.start_download)

        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download)

        action_row.addWidget(self.download_button, 3)
        action_row.addWidget(self.cancel_button, 1)
        layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.stats_label.setWordWrap(True)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.stats_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        version_label = QLabel(f"Sürüm {APP_VERSION}")
        version_label.setObjectName("subtitleLabel")

        self.tech_details_button = QPushButton("Teknik Ayrıntılar")
        self.tech_details_button.clicked.connect(self._show_tech_details)

        self.update_button = QPushButton("Güncellemeyi kontrol et")
        self.update_button.setObjectName("updateButton")
        self.update_button.clicked.connect(self.check_for_updates)

        footer.addWidget(version_label)
        footer.addWidget(self.tech_details_button)
        footer.addStretch(1)
        footer.addWidget(self.update_button)
        layout.addLayout(footer)

        self.setCentralWidget(root)

    def _on_url_changed(self) -> None:
        if self._current_metadata is not None:
            self._current_metadata = None
            self.preview_frame.hide()

    def analyze_url(self) -> None:
        if self._metadata_thread is not None:
            return

        url = self.url_input.text().strip()
        if not url or not self._is_valid_url(url):
            AppMessageDialog(
                "Geçersiz URL",
                "Lütfen geçerli bir indirme bağlantısı girin.\nÖrnek: https://www.youtube.com/watch?v=...",
                "warning",
                self,
            ).exec()
            return

        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("İnceleniyor…")
        self.status_label.setText("İçerik bilgileri alınıyor…")

        thread = QThread(self)
        worker = MetadataWorker(
            url=url,
            requested_quality=self.quality_combo.currentText(),
            media_type=self.media_combo.currentText(),
            browser=self.browser_combo.currentData(),
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.metadata_ready.connect(self._on_metadata_ready)
        worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        worker.status.connect(self.status_label.setText)
        worker.failed.connect(self._on_metadata_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_metadata_finished)

        self._metadata_thread = thread
        self._metadata_worker = worker
        thread.start()

    def _on_metadata_ready(self, meta: MediaMetadata) -> None:
        self._current_metadata = meta
        self.preview_frame.show()
        self.meta_title_label.setText(meta.title)

        uploader_text = meta.uploader if meta.uploader else meta.source_name
        duration = f" • Süre: {meta.duration_text}" if meta.duration_text else ""
        self.meta_uploader_label.setText(f"{uploader_text}{duration}")

        if meta.is_playlist:
            p_count = meta.playlist_count if meta.playlist_count else "Bilinmiyor"
            size_str = format_bytes(meta.estimated_size_bytes)
            self.meta_badges_label.setText(
                f"Oynatma Listesi ({p_count} İçerik) • Tahmini: {size_str}"
            )
        else:
            max_q = f"{meta.maximum_available_height}p" if meta.maximum_available_height else "Bilinmiyor"
            sel_q = meta.selected_resolution
            ext = meta.selected_extension.upper()
            size_str = format_bytes(meta.estimated_size_bytes)
            self.meta_badges_label.setText(
                f"Kaynak: {max_q} • İndirilecek: {sel_q} • {ext} • Tahmini: {size_str}"
            )

    def _on_thumbnail_ready(self, data: bytes) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            scaled = pixmap.scaled(
                140,
                78,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail_label.setPixmap(scaled)

    def _on_metadata_failed(self, error: str) -> None:
        self.status_label.setText("İçerik önizleme bilgisi alınamadı.")
        self._append_log(f"İnceleme Uyarısı: {error}")

    def _on_metadata_finished(self) -> None:
        self._metadata_thread = None
        self._metadata_worker = None
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("İncele")
        if self._close_requested:
            self._try_finish_close()


    def _on_quality_changed(self) -> None:
        self._save_current_settings()
        if self._current_metadata is not None:
            self.analyze_url()

    def _show_tech_details(self) -> None:
        LogDialog("\n".join(self._log_history), parent=self).exec()

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
        set_combo_value(
            self.media_combo, self.settings.get("media_type", "Video (MP4)")
        )
        set_combo_value(
            self.quality_combo, self.settings.get("quality", "En iyi kullanılabilir kalite")
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

    def _choose_folder(self) -> None:
        current_dir = self.folder_input.text().strip()
        start_dir = current_dir if Path(current_dir).exists() else str(Path.home() / "Downloads")
        folder = QFileDialog.getExistingDirectory(
            self,
            "İndirme Klasörü Seç",
            start_dir,
        )
        if folder:
            self.folder_input.setText(folder)
            self._save_current_settings()

    def _on_media_type_changed(self, text: str) -> None:
        is_audio = "MP3" in text or "Ses" in text
        self.quality_combo.setEnabled(not is_audio)
        self._save_current_settings()

    def _paste_url(self) -> None:
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text and self._is_valid_url(text):
            self.url_input.setText(text)
            self.analyze_url()

    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except (ValueError, TypeError, AttributeError):
            return False

    def _show_dependency_status(self) -> None:
        for line in get_environment_log_lines():
            self._append_log(line)
        warnings = dependency_warnings()
        if warnings:
            AppMessageDialog(
                "Eksik Bağımlılıklar",
                "\n".join(warnings),
                "warning",
                self,
            ).exec()

    def start_download(self) -> None:
        if self._download_thread is not None:
            return

        url = self.url_input.text().strip()
        if not url or not self._is_valid_url(url):
            AppMessageDialog(
                "Geçersiz URL",
                "Lütfen geçerli bir indirme bağlantısı girin.\nÖrnek: https://www.youtube.com/watch?v=...",
                "warning",
                self,
            ).exec()
            return

        raw_folder = self.folder_input.text().strip()
        if not raw_folder:
            AppMessageDialog(
                "Geçersiz Klasör",
                "Lütfen bir indirme klasör yolu girin.",
                "warning",
                self,
            ).exec()
            return

        output_dir = Path(raw_folder)
        if not output_dir.exists():
            dlg = AppMessageDialog(
                "Klasör Bulunamadı",
                f"'{output_dir}' klasörü mevcut değil.\nOluşturulsun mu?",
                "question",
                self,
                [("yes", "Evet", True), ("no", "Hayır", False)],
            )
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.clicked_button_id == "yes":
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
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

        env = check_environment()
        if not env["ffmpeg"]:
            dlg = AppMessageDialog(
                "FFmpeg Bulunamadı",
                "FFmpeg bulunamadı. Yüksek kaliteli video ve ses birleştirme yapılamayabilir.\nYine de indirmeye devam etmek istiyor musunuz?",
                "warning",
                self,
                [("yes", "Devam Et", True), ("no", "İptal", False)],
            )
            if dlg.exec() != QDialog.DialogCode.Accepted or dlg.clicked_button_id == "yes":
                return

        request = DownloadRequest(
            url=url,
            output_dir=output_dir,
            media_type=self.media_combo.currentText(),
            quality=self.quality_combo.currentText(),
            playlist=self.playlist_checkbox.isChecked(),
            browser=self.browser_combo.currentData(),
        )

        self._set_ui_downloading(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("İndirme başlatılıyor…")
        self.stats_label.setText("")
        self._append_log(f"İndirme isteği gönderildi: {url}")
        self._download_succeeded_result = None
        self._download_succeeded_path = ""

        thread = QThread(self)
        worker = DownloadWorker(request)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self.progress_bar.setValue)
        worker.status.connect(self.status_label.setText)
        worker.log.connect(self._append_log)
        worker.progress_details.connect(self._on_progress_details)
        worker.succeeded.connect(self._on_download_succeeded)
        worker.failed.connect(self._on_download_failed)
        worker.cancelled.connect(self._on_download_cancelled)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_download_thread_finished)

        self._download_thread = thread
        self._download_worker = worker
        thread.start()

    def cancel_download(self) -> None:
        if self._download_worker is not None:
            self._append_log("İptal isteği gönderildi…")
            self._download_worker.cancel()
            self.cancel_button.setEnabled(False)

    def _on_progress_details(self, details: dict) -> None:
        phase = details.get("phase", "downloading")
        downloaded = details.get("downloaded_bytes") or 0
        total = details.get("total_bytes") or 0
        speed = details.get("speed", "—")
        eta = details.get("eta", "—")

        phase_texts = {
            "downloading": "İndiriliyor",
            "video_downloading": "Video indiriliyor",
            "audio_downloading": "Ses indiriliyor",
            "merging_video_audio": "Video ve ses birleştiriliyor",
            "preparing_mp3": "MP3 dosyası hazırlanıyor",
            "finished": "Dosya hazırlanıyor",
        }
        header_text = phase_texts.get(phase, "İndiriliyor")
        self.status_label.setText(header_text)

        if total > 0:
            dl_str = format_bytes(downloaded)
            tot_str = format_bytes(total)
            self.stats_label.setText(f"{dl_str} / {tot_str} • Hız: {speed} • Kalan: {eta}")
        else:
            self.stats_label.setText(f"Hız: {speed} • Kalan: {eta}")

    def _on_download_succeeded(self, filename: str) -> None:
        self._download_succeeded_result = filename
        if os.path.isabs(filename):
            self._download_succeeded_path = filename
        else:
            self._download_succeeded_path = str(Path(self.folder_input.text().strip()) / filename)

    def _on_download_failed(self, error_msg: str) -> None:
        self.status_label.setText("İndirme başarısız.")
        self.stats_label.setText("")
        self._set_ui_downloading(False)
        self._append_log(error_msg if error_msg.startswith("Hata:") else f"Hata: {error_msg}")

    def _on_download_cancelled(self) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText("İndirme iptal edildi.")
        self.stats_label.setText("")
        self._set_ui_downloading(False)
        self._append_log("İndirme kullanıcı tarafından iptal edildi.")

    def _on_download_thread_finished(self) -> None:
        succeeded_result = self._download_succeeded_result
        filepath = self._download_succeeded_path
        self._download_thread = None
        self._download_worker = None
        self._set_ui_downloading(False)

        if self._close_requested:
            self._try_finish_close()
            return

        if succeeded_result:
            self.progress_bar.setValue(100)
            self.status_label.setText("İndirme tamamlandı.")

            real_size = ""
            if filepath and Path(filepath).exists():
                real_size = format_bytes(Path(filepath).stat().st_size)

            size_info = f" • Boyut: {real_size}" if real_size else ""
            self.stats_label.setText(f"Dosya: {Path(succeeded_result).name}{size_info}")
            self._append_log("İndirme başarıyla tamamlandı.")

            if self.auto_open_checkbox.isChecked():
                self._open_current_folder()
                self._reset_after_successful_download()
            else:
                dlg = DownloadCompletedDialog(
                    result_summary=succeeded_result,
                    filepath=filepath,
                    parent=self,
                )
                dlg.exec()
                if dlg.action_choice == "open_folder":
                    self._open_current_folder()
                elif dlg.action_choice == "open_file" and filepath and Path(filepath).exists():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
                self._reset_after_successful_download()

    def _reset_after_successful_download(self) -> None:
        self.url_input.clear()
        self.preview_frame.hide()
        self.thumbnail_label.clear()
        self.thumbnail_label.setText("Önizleme")
        self.meta_title_label.setText("")
        self.meta_uploader_label.setText("")
        self.meta_badges_label.setText("")
        self._current_metadata = None

        self.progress_bar.setValue(0)
        self.status_label.setText("Hazır")
        self.stats_label.setText("")

        self.cancel_button.setEnabled(False)
        self.download_button.setEnabled(True)
        self.analyze_button.setEnabled(True)

        self.playlist_checkbox.setChecked(False)
        self.browser_combo.setCurrentIndex(0)

        self._download_succeeded_result = None
        self._download_succeeded_path = ""
        self._last_log_message = None

        self.url_input.setFocus()

    def _try_finish_close(self) -> None:
        if (
            self._close_requested
            and self._download_thread is None
            and self._metadata_thread is None
        ):
            self._save_current_settings()
            QApplication.quit()

    def _set_ui_downloading(self, active: bool) -> None:
        self.download_button.setEnabled(not active)
        self.cancel_button.setEnabled(active)
        self.url_input.setEnabled(not active)
        self.analyze_button.setEnabled(not active)
        self.media_combo.setEnabled(not active)
        self.quality_combo.setEnabled(
            not active and ("MP3" not in self.media_combo.currentText())
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
        self._log_history.append(cleaned)

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
        worker.no_release_found.connect(self._update_no_release_found)
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

    def _update_no_release_found(self) -> None:
        AppMessageDialog(
            "Henüz yayınlanmış sürüm yok",
            "GitHub üzerinde henüz yayınlanmış bir Kolayİndir sürümü bulunmuyor.",
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
            self.analyze_url()
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_thread is None and self._metadata_thread is None:
            self._save_current_settings()
            event.accept()
            return

        if self._close_dialog_open:
            event.ignore()
            return

        self._close_dialog_open = True
        dlg = AppMessageDialog(
            "İndirme devam ediyor",
            "Devam eden indirme veya işlem iptal edilip uygulama kapatılsın mı?",
            "question",
            self,
            [
                ("yes", "İndirmeyi iptal et ve kapat", True),
                ("no", "Vazgeç", False),
            ],
        )
        result = dlg.exec()
        self._close_dialog_open = False

        if result != QDialog.DialogCode.Accepted or dlg.clicked_button_id != "yes":
            event.ignore()
            return

        self._close_requested = True
        event.ignore()

        if self._download_worker is not None:
            self._download_worker.cancel()
        if self._metadata_worker is not None:
            self._metadata_worker.cancel()

        self._try_finish_close()

