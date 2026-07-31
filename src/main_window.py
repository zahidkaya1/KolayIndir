"""Kolayİndir ana kullanıcı arayüzü."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.browser_sessions import (
    is_authentication_error,
    is_chromium_encryption_error,
)
from src.config import (
    APP_NAME,
    APP_VERSION,
)
from src.dependency_check import (
    check_environment,
    dependency_warnings,
    get_environment_log_lines,
)
from src.dialogs import (
    AdvancedSessionDialog,
    AppMessageDialog,
    DownloadCompletedDialog,
    LeftoverJobsDialog,
    LogDialog,
    SessionFailedDialog,
    UpdateAvailableDialog,
)
from src.download_worker import DownloadWorker
from src.history import (
    HistoryValidationWorker,
    get_unique_filepath,
    sanitize_filename,
)
from src.metadata_worker import MetadataWorker
from src.models import (
    DownloadRequest,
    MediaMetadata,
    PlatformType,
    detect_platform_type,
    format_bytes,
    get_platform_badge_text,
    is_rehydration_error,
)
from src.settings import load_settings, save_settings
from src.updater import UpdateWorker
from src.utils import (
    apply_pointing_hand_cursor,
    calculate_detailed_format_info,
    clean_log_message,
    configure_combo_box,
    probe_media_codecs,
    set_combo_value,
)
from src.widgets import NoWheelComboBox, OptionCard


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._metadata_thread: QThread | None = None
        self._metadata_worker: MetadataWorker | None = None
        self._update_thread: QThread | None = None
        self._update_worker: UpdateWorker | None = None
        self._history_thread: QThread | None = None
        self._history_worker: HistoryValidationWorker | None = None
        self._last_log_message: str | None = None
        self._download_succeeded_result: str | None = None
        self._download_succeeded_path: str = ""
        self._log_history: list[str] = []
        self._current_metadata: MediaMetadata | None = None
        self._preferred_browser: str | None = None
        self._preferred_profile: tuple[str, str] | None = None
        self._preferred_impersonation: str | None = None
        self._close_requested: bool = False
        self._cancel_requested: bool = False
        self._pending_close: bool = False
        self._shutdown_in_progress: bool = False
        self._force_close_timer: QTimer | None = None

        self._close_dialog_open: bool = False
        self._story_notice: str | None = None
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
        self.resize(710, 650)
        self.setMinimumSize(710, 650)
        self.setAcceptDrops(True)



        self._center_on_screen()
        self._build_ui()
        self._restore_settings()
        QTimer.singleShot(250, self._show_dependency_status)


    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - 710) // 2 + geo.x()
            y = (geo.height() - 650) // 2 + geo.y()
            self.move(x, y)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(10)


        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        subtitle = QLabel("Hızlı, Kolay ve Yüksek Kaliteli Medya İndirici")
        subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        sec1_header = QLabel("1. İçerik Bağlantısı")
        sec1_header.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        sec1_sub = QLabel("Video, oynatma listesi veya sosyal medya paylaşım bağlantısını yapıştırın.")
        sec1_sub.setStyleSheet("color: #64748b; font-size: 11px;")

        sec1_box = QVBoxLayout()
        sec1_box.setSpacing(2)
        sec1_box.addWidget(sec1_header)
        sec1_box.addWidget(sec1_sub)
        content_layout.addLayout(sec1_box)

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
        content_layout.addLayout(url_row)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        self.preview_frame.setMinimumHeight(95)
        self.preview_frame.hide()
        preview_layout = QHBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(10, 8, 10, 8)
        preview_layout.setSpacing(12)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(138, 78)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet(
            "background-color: #e2e8f0; border-radius: 6px; color: #64748b;"
        )
        self.thumbnail_label.setText("Önizleme")
        preview_layout.addWidget(self.thumbnail_label)

        meta_info_box = QVBoxLayout()
        meta_info_box.setContentsMargins(0, 0, 0, 0)
        meta_info_box.setSpacing(3)

        self.platform_badge_label = QLabel("YouTube")
        self.platform_badge_label.setObjectName("platformBadgeLabel")
        self.platform_badge_label.setStyleSheet(
            "color: #1d4ed8; font-size: 11px; font-weight: 700; "
            "background-color: #eff6ff; border: 1px solid #bfdbfe; "
            "border-radius: 4px; padding: 1px 6px; max-width: 140px;"
        )

        self.meta_title_label = QLabel("İçerik başlığı yükleniyor…")
        self.meta_title_label.setStyleSheet("font-weight: 700; color: #0f172a; font-size: 13px;")
        self.meta_title_label.setWordWrap(True)
        self.meta_title_label.setMinimumHeight(32)
        self.meta_title_label.setMaximumHeight(44)

        self.meta_uploader_label = QLabel("Kanal / Yükleyen")
        self.meta_uploader_label.setStyleSheet("color: #475569; font-size: 12px;")

        self.meta_badges_label = QLabel("Kaynak: — • İndirilecek: — • Tahmini: —")
        self.meta_badges_label.setStyleSheet("color: #2563eb; font-size: 12px; font-weight: 600;")
        self.meta_badges_label.setWordWrap(True)

        meta_info_box.addWidget(self.platform_badge_label)
        meta_info_box.addWidget(self.meta_title_label)
        meta_info_box.addWidget(self.meta_uploader_label)
        meta_info_box.addWidget(self.meta_badges_label)

        preview_layout.addLayout(meta_info_box, 1)
        content_layout.addWidget(self.preview_frame)

        sec2_header = QLabel("2. İndirme Seçenekleri")
        sec2_header.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        sec2_sub = QLabel("Dosya türünü, kaliteyi ve kayıt konumunu seçin.")
        sec2_sub.setStyleSheet("color: #64748b; font-size: 11px;")

        sec2_box = QVBoxLayout()
        sec2_box.setSpacing(2)
        sec2_box.addWidget(sec2_header)
        sec2_box.addWidget(sec2_sub)
        content_layout.addLayout(sec2_box)

        options_grid = QGridLayout()
        options_grid.setContentsMargins(0, 0, 0, 0)
        options_grid.setSpacing(8)
        options_grid.setColumnStretch(0, 1)
        options_grid.setColumnStretch(1, 1)
        options_grid.setColumnStretch(2, 1)

        self.media_type_label = QLabel("Dosya türü:")
        self.quality_label = QLabel("Video kalitesi:")
        self.browser_label = QLabel("Oturum kullanımı:")

        self.media_combo = NoWheelComboBox()
        self.media_combo.setObjectName("mediaTypeCombo")
        self.media_combo.addItems(["Video (MP4)", "Ses (MP3)"])
        self.media_combo.currentTextChanged.connect(self._on_media_type_changed)
        configure_combo_box(self.media_combo)

        self.quality_combo = NoWheelComboBox()
        self.quality_combo.setObjectName("qualityCombo")
        self.quality_combo.addItems([
            "En iyi kullanılabilir kalite",
            "1080p’ye kadar",
            "720p’ye kadar",
            "480p’ye kadar",
        ])
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)
        configure_combo_box(self.quality_combo)

        self.browser_combo = NoWheelComboBox()
        self.browser_combo.setObjectName("browserCombo")
        self.browser_combo.addItem("Otomatik oturum", "auto")
        self.browser_combo.addItem("Oturum kullanma", None)
        self.browser_combo.addItem("Firefox oturumu", "firefox")
        self.browser_combo.addItem("Edge oturumu", "edge")
        self.browser_combo.addItem("Chrome oturumu", "chrome")
        self.browser_combo.addItem("Brave oturumu", "brave")
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

        options_grid.addWidget(self.media_type_label, 0, 0)
        options_grid.addWidget(self.quality_label, 0, 1)
        options_grid.addWidget(self.browser_label, 0, 2)
        options_grid.addWidget(self.media_combo, 1, 0)
        options_grid.addWidget(self.quality_combo, 1, 1)
        options_grid.addWidget(self.browser_combo, 1, 2)
        content_layout.addLayout(options_grid)

        cards_box = QVBoxLayout()
        cards_box.setSpacing(8)
        cards_box.addWidget(self.playlist_card)
        cards_box.addWidget(self.auto_open_card)
        content_layout.addLayout(cards_box)

        content_layout.addWidget(QLabel("İndirme klasörü:"))
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
        content_layout.addLayout(folder_row)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(8)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.download_button = QPushButton("Önce bağlantıyı inceleyin")
        self.download_button.setObjectName("primaryButton")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.start_download)

        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download)

        action_row.addWidget(self.download_button, 3)
        action_row.addWidget(self.cancel_button, 1)
        bottom_box.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.stats_label.setWordWrap(True)

        bottom_box.addWidget(self.progress_bar)
        bottom_box.addWidget(self.status_label)
        bottom_box.addWidget(self.stats_label)

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
        bottom_box.addLayout(footer)

        layout.addLayout(bottom_box)

        # El imleci (PointingHandCursor) uygulamasını tüm tıklanabilir bileşenlerde etkinleştir
        for w in (
            paste_button,
            self.analyze_button,
            self.download_button,
            self.cancel_button,
            self.folder_button,
            self.open_folder_button,
            self.tech_details_button,
            self.update_button,
            self.media_combo,
            self.quality_combo,
            self.browser_combo,
            self.playlist_checkbox,
            self.playlist_card,
            self.auto_open_checkbox,
            self.auto_open_card,
        ):
            apply_pointing_hand_cursor(w)

        self.setCentralWidget(root)

    def _update_download_button_state(self, is_downloading: bool = False) -> None:
        if is_downloading:
            self.download_button.setText("İndiriliyor…")
            self.download_button.setEnabled(False)
            self.download_button.setToolTip("İndirme işlemi devam ediyor.")
            self.cancel_button.setEnabled(True)
            self.cancel_button.setText("İptal")
        elif self._current_metadata is None:
            self.download_button.setText("Önce bağlantıyı inceleyin")
            self.download_button.setEnabled(False)
            self.download_button.setToolTip("İndirmeye başlamadan önce bir bağlantı girin ve 'İncele' düğmesine basın.")
            self.cancel_button.setEnabled(False)
        else:
            self.download_button.setText("İndirmeyi Başlat")
            self.download_button.setEnabled(True)
            self.download_button.setToolTip("İçeriği seçilen kalite ve konumda indirmek için tıklayın.")
            self.cancel_button.setEnabled(False)

    def _on_url_changed(self) -> None:
        url = self.url_input.text().strip()
        if self._current_metadata is not None:
            self._current_metadata = None
            self.preview_frame.hide()
        self._story_notice = None

        if not url:
            self.url_input.setStyleSheet("")
        elif self._is_valid_url(url):
            self.url_input.setStyleSheet("border: 1.5px solid #2563eb;")
        else:
            self.url_input.setStyleSheet("border: 1.5px solid #ef4444;")

        self._update_download_button_state()

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

        platform = detect_platform_type(url)
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("İnceleniyor…")
        if platform in (
            PlatformType.TIKTOK_VIDEO,
            PlatformType.TIKTOK_SHORT_LINK,
            PlatformType.TIKTOK_PROFILE,
            PlatformType.TIKTOK_LIVE,
            PlatformType.TIKTOK_SLIDESHOW,
        ):
            self.status_label.setText("TikTok bağlantısı inceleniyor…")
        else:
            self.status_label.setText("İçerik bilgileri alınıyor…")

        thread = QThread(self)
        worker = MetadataWorker(
            url=url,
            requested_quality=self.quality_combo.currentText(),
            media_type=self.media_combo.currentText(),
            browser=self.browser_combo.currentData(),
            preferred_browser=self._preferred_browser,
            preferred_profile=self._preferred_profile,
            settings=dict(self.settings),
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.metadata_ready.connect(self._on_metadata_ready)
        worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        worker.story_notice_ready.connect(self._on_story_notice)
        worker.status.connect(self.status_label.setText)
        worker.log.connect(self._append_log)
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
        self._preferred_browser = meta.session_browser
        self._preferred_profile = meta.session_profile
        self._preferred_impersonation = meta.preferred_impersonation
        self.preview_frame.show()

        if meta.platform_type in (
            PlatformType.TIKTOK_VIDEO,
            PlatformType.TIKTOK_SHORT_LINK,
            PlatformType.TIKTOK_PROFILE,
            PlatformType.TIKTOK_LIVE,
            PlatformType.TIKTOK_SLIDESHOW,
        ):
            self.status_label.setText("TikTok video bilgileri alındı.")
        else:
            self.status_label.setText("İçerik bilgileri alındı.")

        badge_text = get_platform_badge_text(meta.platform_type)
        self.platform_badge_label.setText(badge_text)

        title_text = meta.title.strip()
        if len(title_text) > 130:
            title_text = title_text[:127] + "…"
        self.meta_title_label.setText(title_text)

        uploader_text = meta.uploader if meta.uploader else meta.source_name
        duration = f" • Süre: {meta.duration_text}" if meta.duration_text else ""
        track_info = f" • Müzik: {meta.track_name}" if meta.track_name else ""
        self.meta_uploader_label.setText(f"{uploader_text}{duration}{track_info}")

        if (
            meta.is_playlist
            and meta.platform_type in (
                PlatformType.INSTAGRAM_POST,
                PlatformType.INSTAGRAM_REEL,
                PlatformType.TWITTER_POST,
            )
            and meta.playlist_count
            and meta.playlist_count > 1
        ):
            self.playlist_checkbox.setChecked(True)

        self.quality_combo.blockSignals(True)
        current_sel = self.quality_combo.currentText()
        self.quality_combo.clear()
        self.quality_combo.addItem("En iyi kullanılabilir kalite")

        if meta.available_heights:
            for h in meta.available_heights:
                self.quality_combo.addItem(f"{h}p'ye kadar")
        else:
            self.quality_combo.addItems([
                "1080p’ye kadar",
                "720p’ye kadar",
                "480p’ye kadar",
                "360p’ye kadar",
            ])

        find_idx = self.quality_combo.findText(current_sel)
        if find_idx >= 0:
            self.quality_combo.setCurrentIndex(find_idx)
        else:
            self.quality_combo.setCurrentIndex(0)
        self.quality_combo.blockSignals(False)

        self._update_download_button_state()
        self._update_preview_quality_display()

        # Hikâye URL bilgi notunu badges alanında göster
        if self._story_notice:
            self.meta_badges_label.setText(f"ℹ️ {self._story_notice}")
            self.meta_badges_label.setStyleSheet(
                "color: #92400e; font-size: 12px; font-weight: 600;"
            )

    def _update_preview_quality_display(self) -> None:
        meta = self._current_metadata
        if meta is None:
            return

        chosen_q = self.quality_combo.currentText()
        media_t = self.media_combo.currentText()
        convert_hevc = self.settings.get("convert_hevc_to_h264", True)

        info = calculate_detailed_format_info(meta, chosen_q, media_t, convert_hevc)

        meta.requested_quality = chosen_q
        meta.selected_height = info.get("selected_height")
        meta.selected_resolution = info.get("selected_resolution", "En iyi")
        meta.video_codec = info.get("selected_vcodec", "")
        meta.audio_codec = info.get("selected_acodec", "")
        meta.estimated_size_bytes = info.get("estimated_size_bytes", 0)

        max_q = f"{meta.maximum_available_height}p" if meta.maximum_available_height else "Bilinmiyor"
        sel_q = meta.selected_resolution
        size_str = info.get("size_display_text", "")
        out_codec = info.get("output_codec_text", "MP4")

        if meta.is_playlist:
            p_count = meta.playlist_count if meta.playlist_count else "Bilinmiyor"
            if (
                meta.platform_type in (
                    PlatformType.INSTAGRAM_POST,
                    PlatformType.INSTAGRAM_REEL,
                    PlatformType.TWITTER_POST,
                )
                and meta.playlist_count
                and meta.playlist_count > 1
            ):
                base_text = f"Bu gönderide {meta.playlist_count} indirilebilir video var."
            else:
                base_text = f"Oynatma Listesi ({p_count} İçerik) • {size_str}"
        else:
            if "MP3" in media_t or "Ses" in media_t:
                base_text = f"Biçim: MP3 • {size_str}"
            else:
                base_text = f"Kaynak: {max_q} • İndirilecek: {sel_q} • Codec: {out_codec} • {size_str}"
                if meta.view_count or meta.like_count:
                    extra_parts = []
                    if meta.view_count:
                        formatted_views = f"{meta.view_count:,}".replace(",", ".")
                        extra_parts.append(f"İzlenme: {formatted_views}")
                    if meta.like_count:
                        formatted_likes = f"{meta.like_count:,}".replace(",", ".")
                        extra_parts.append(f"Beğeni: {formatted_likes}")
                    base_text += " • " + " • ".join(extra_parts)

        if self._story_notice:
            self.meta_badges_label.setText(f"ℹ️ {self._story_notice}")
            self.meta_badges_label.setStyleSheet("color: #92400e; font-size: 12px; font-weight: 600;")
        else:
            self.meta_badges_label.setText(base_text)
            self.meta_badges_label.setStyleSheet("color: #2563eb; font-size: 13px; font-weight: 600;")

    def _on_story_notice(self, notice: str) -> None:
        """Hikâye URL bilgi notunu saklar; meta_badges_label'a ekler."""
        self._story_notice = notice
        # Önizleme zaten görünüyorsa hemen badges label'a yaz
        if self.preview_frame.isVisible():
            current = self.meta_badges_label.text()
            if notice not in current:
                self.meta_badges_label.setText(f"ℹ️ {notice}")
                self.meta_badges_label.setStyleSheet(
                    "color: #92400e; font-size: 12px; font-weight: 600;"
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

        if is_rehydration_error(error):
            dlg = AppMessageDialog(
                "TikTok video bilgileri alınamadı",
                "Bağlantı geçerli ve TikTok videosuna yönlendirildi ancak video verileri şu anda çözümlenemedi.",
                "error",
                self,
                [
                    ("retry", "Yeniden Dene", True),
                    ("check_update", "Güncellemeyi Kontrol Et", False),
                    ("close", "Kapat", False),
                ],
            )
            dlg.exec()
            if dlg.clicked_button_id == "retry":
                self.analyze_url()
            elif dlg.clicked_button_id == "check_update":
                self._check_for_updates(user_initiated=True)
            return

        AppMessageDialog(
            "İnceleme Başarısız",
            error if error else "İçerik önizleme bilgisi alınamadı.",
            "error",
            self,
        ).exec()

        if is_authentication_error(error) or is_chromium_encryption_error(error) or "oturum" in error.lower():
            url = self.url_input.text().strip()
            platform = detect_platform_type(url)
            dlg = SessionFailedDialog(platform_name=platform.value, failure_reason=error, parent=self)
            dlg.exec()
            if dlg.clicked_button_id == "retry":
                self._preferred_profile = None
                self._preferred_browser = None
                self.analyze_url()
            elif dlg.clicked_button_id == "install_firefox":
                self._prompt_install_firefox()
            elif dlg.clicked_button_id == "settings":
                adv = AdvancedSessionDialog(current_mode=self.browser_combo.currentData(), parent=self)
                if adv.exec() == QDialog.DialogCode.Accepted:
                    new_mode = adv.selected_mode()
                    for i in range(self.browser_combo.count()):
                        if self.browser_combo.itemData(i) == new_mode:
                            self.browser_combo.setCurrentIndex(i)
                            break



    def _on_metadata_finished(self) -> None:
        self._metadata_thread = None
        self._metadata_worker = None
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("İncele")
        if self._close_requested or self._pending_close or self._shutdown_in_progress:
            self._try_finish_close()


    def _on_quality_changed(self) -> None:
        self._save_current_settings()
        if self._current_metadata is not None:
            self._update_preview_quality_display()

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

    def _on_media_type_changed(self, text: str = "") -> None:
        media_text = text if text else self.media_combo.currentText()
        is_audio = "MP3" in media_text or "Ses" in media_text
        self.quality_combo.setEnabled(not is_audio)
        if is_audio:
            self.quality_label.setText("Ses kalitesi:")
            self.quality_combo.setToolTip("MP3 formatı için 192 kbps sabit ses kalitesi kullanılır.")
        else:
            self.quality_label.setText("Video kalitesi:")
            self.quality_combo.setToolTip("Video çözünürlük üst sınırını seçin.")

        self._save_current_settings()
        if self._current_metadata is not None:
            self._update_preview_quality_display()

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
            if dlg.exec() != QDialog.DialogCode.Accepted or dlg.clicked_button_id != "yes":
                return

        download_url = url
        platform_now = detect_platform_type(url)
        if platform_now == PlatformType.KICK_VIDEO or "kick.com" in url.lower():
            # Kick VOD: DownloadWorker indirme başında playback URL'yi yeniden alacak.
            # Signed m3u8 saklamıyoruz; her zaman orijinal kick.com URL'sini kullan.
            download_url = url
        elif self._current_metadata and self._current_metadata.successful_request_url:
            download_url = self._current_metadata.successful_request_url
        elif self._current_metadata and self._current_metadata.webpage_url and detect_platform_type(self._current_metadata.webpage_url) != PlatformType.UNKNOWN:
            download_url = self._current_metadata.webpage_url

        media_type = self.media_combo.currentText()
        quality = self.quality_combo.currentText()
        playlist = self.playlist_checkbox.isChecked()

        ext = "mp3" if ("MP3" in media_type or "Ses" in media_type) else "mp4"
        raw_title = self._current_metadata.title if (self._current_metadata and self._current_metadata.title) else "Video"
        clean_title = sanitize_filename(raw_title)
        initial_target_path = output_dir / f"{clean_title}.{ext}"

        self._append_log("İndirme isteği oluşturuldu.")
        self._append_log(f"Hedef klasör doğrulandı: {output_dir}")

        if self._current_metadata and self._current_metadata.is_playlist and playlist:
            # Playlist: yt-dlp manages its own file naming per item
            target_override: Path | None = None
        else:
            # Single video: always compute unique path to avoid overwriting completed files.
            # If the initial path doesn't exist, get_unique_filepath returns it unchanged.
            target_override = get_unique_filepath(initial_target_path)

        if target_override and target_override != initial_target_path:
            self._append_log(f"Çakışma önlendi, otomatik benzersiz dosya adı oluşturuldu: {target_override.name}")
        elif target_override:
            self._append_log(f"Hedef dosya adı belirlendi: {target_override.name}")
        else:
            self._append_log("Oynatma listesi modu: dosya adları yt-dlp tarafından belirleniyor.")

        self._force_redownload_once = False

        request = DownloadRequest(
            url=download_url,
            output_dir=output_dir,
            media_type=media_type,
            quality=quality,
            playlist=playlist,
            browser=self.browser_combo.currentData(),
            preferred_browser=self._preferred_browser,
            preferred_profile=self._preferred_profile,
            preferred_impersonation=self._preferred_impersonation,
            successful_request_url=download_url,
            convert_hevc_to_h264=self.settings.get("convert_hevc_to_h264", True),
            target_final_path=target_override,
        )

        self._set_ui_downloading(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("İndirme başlatılıyor…")
        self.stats_label.setText("")
        self._append_log("İndirme worker’ı başlatıldı.")
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
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("İptal ediliyor…")

        if self._download_worker is not None:
            self._append_log("İptal isteği gönderildi…")
            self.status_label.setText("İndirme iptal ediliyor…")
            self._download_worker.cancel()

        if self._metadata_worker is not None:
            self.status_label.setText("İnceleme iptal ediliyor…")
            self._metadata_worker.cancel()

    def _on_progress_details(self, details: dict) -> None:
        phase = details.get("phase", "downloading")
        downloaded = details.get("downloaded_bytes") or 0
        total = details.get("total_bytes") or 0
        speed = details.get("speed", "—")
        eta = details.get("eta", "—")

        is_tiktok = (
            self._current_metadata is not None
            and self._current_metadata.platform_type in (
                PlatformType.TIKTOK_VIDEO,
                PlatformType.TIKTOK_SHORT_LINK,
                PlatformType.TIKTOK_PROFILE,
                PlatformType.TIKTOK_LIVE,
                PlatformType.TIKTOK_SLIDESHOW,
            )
        )

        phase_texts = {
            "downloading": "TikTok videosu indiriliyor" if is_tiktok else "İndiriliyor",
            "video_downloading": "TikTok videosu indiriliyor" if is_tiktok else "Video indiriliyor",
            "audio_downloading": "TikTok sesi indiriliyor" if is_tiktok else "Ses indiriliyor",
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

        if is_rehydration_error(error_msg):
            dlg = AppMessageDialog(
                "TikTok video bilgileri alınamadı",
                "Bağlantı geçerli ve TikTok videosuna yönlendirildi ancak video verileri şu anda çözümlenemedi.",
                "error",
                self,
                [
                    ("retry", "Yeniden Dene", True),
                    ("check_update", "Güncellemeyi Kontrol Et", False),
                    ("close", "Kapat", False),
                ],
            )
            dlg.exec()
            if dlg.clicked_button_id == "retry":
                self.start_download()
            elif dlg.clicked_button_id == "check_update":
                self._check_for_updates(user_initiated=True)
            return

        if is_authentication_error(error_msg) or is_chromium_encryption_error(error_msg) or "oturum" in error_msg.lower():
            url = self.url_input.text().strip()
            platform = detect_platform_type(url)
            dlg = SessionFailedDialog(platform_name=platform.value, failure_reason=error_msg, parent=self)
            dlg.exec()
            if dlg.clicked_button_id == "retry":
                self._preferred_profile = None
                self._preferred_browser = None
                self.start_download()
            elif dlg.clicked_button_id == "install_firefox":
                self._prompt_install_firefox()
            elif dlg.clicked_button_id == "settings":
                adv = AdvancedSessionDialog(
                    current_mode=self.browser_combo.currentData(),
                    convert_hevc=self.settings.get("convert_hevc_to_h264", True),
                    parent=self,
                )
                if adv.exec() == QDialog.DialogCode.Accepted:
                    new_mode = adv.selected_mode()
                    for i in range(self.browser_combo.count()):
                        if self.browser_combo.itemData(i) == new_mode:
                            self.browser_combo.setCurrentIndex(i)
                            break
                    self.settings["convert_hevc_to_h264"] = adv.is_convert_hevc_enabled()
                    save_settings(self.settings)
            return

        AppMessageDialog(
            "İndirme Başarısız",
            f"İndirme işlemi tamamlanamadı:\n\n{error_msg}",
            "error",
            self,
        ).exec()

    def _prompt_install_firefox(self) -> None:
        """Kullanıcı onayından sonra Windows Terminal'de Firefox kurulum komutunu başlatır."""
        import subprocess

        WINGET_CMD = "winget install -e --id Mozilla.Firefox"
        dlg = AppMessageDialog(
            "Firefox Kurulumu",
            f"Aşağıdaki komut Windows Terminal'de çalıştırılacak:\n\n{WINGET_CMD}\n\n"
            "Devam etmek istiyor musunuz?",
            "question",
            self,
            [("yes", "Evet, Kur", True), ("no", "İptal", False)],
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.clicked_button_id == "yes":
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "cmd", "/k", WINGET_CMD],
                    shell=False,
                )
                self._append_log(f"Firefox kurulum komutu başlatıldı: {WINGET_CMD}")
            except Exception as exc:  # noqa: BLE001
                AppMessageDialog(
                    "Komut Çalıştırılamadı",
                    f"Komut başlatılamadı:\n{exc}\n\nLütfen aşağıdaki komutu kendiniz çalıştırın:\n{WINGET_CMD}",
                    "error",
                    self,
                ).exec()


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
        self._cancel_requested = False

        if self._close_requested or self._pending_close or self._shutdown_in_progress:
            self._try_finish_close()
            return

        if succeeded_result:
            self.progress_bar.setValue(100)
            if self._current_metadata and self._current_metadata.platform_type in (
                PlatformType.TIKTOK_VIDEO,
                PlatformType.TIKTOK_SHORT_LINK,
                PlatformType.TIKTOK_PROFILE,
                PlatformType.TIKTOK_LIVE,
                PlatformType.TIKTOK_SLIDESHOW,
            ):
                self.status_label.setText("TikTok indirmesi tamamlandı.")
            else:
                self.status_label.setText("İndirme tamamlandı.")

            real_size = ""
            v_codec = ""
            a_codec = ""
            res_text = ""
            if filepath and Path(filepath).exists():
                fp = Path(filepath)
                real_size = format_bytes(fp.stat().st_size)
                probe = probe_media_codecs(fp)
                v_codec = probe.get("video_codec", "")
                a_codec = probe.get("audio_codec", "")
                h = probe.get("height", 0)
                if h > 0:
                    res_text = f"{h}p"

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
                    video_codec=v_codec,
                    audio_codec=a_codec,
                    resolution=res_text,
                    filesize_text=real_size,
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
        self._preferred_browser = None
        self._preferred_profile = None
        self._preferred_impersonation = None

        self.progress_bar.setValue(0)
        self.status_label.setText("Hazır")
        self.stats_label.setText("")

        self.cancel_button.setEnabled(False)
        self.download_button.setEnabled(True)
        self.analyze_button.setEnabled(True)

        self.playlist_checkbox.setChecked(False)
        self.browser_combo.setCurrentIndex(0)
        self._preferred_browser = None
        self._preferred_profile = None


        self._download_succeeded_result = None
        self._download_succeeded_path = ""
        self._last_log_message = None

        self.url_input.setFocus()

    def _force_quit_application(self) -> None:
        self._save_current_settings()
        QApplication.quit()

    def _try_finish_close(self) -> None:
        if (
            (self._close_requested or self._pending_close or self._shutdown_in_progress)
            and self._download_thread is None
            and self._metadata_thread is None
            and self._history_thread is None
        ):
            if self._force_close_timer is not None:
                self._force_close_timer.stop()
                self._force_close_timer = None
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

    def _stop_all_threads(self) -> None:
        """Kapanışta veya test temizliğinde tüm çalışan arka plan iş parçacıklarını güvenle durdurur."""
        for attr in ("_history_thread", "_update_thread", "_metadata_thread", "_download_thread"):
            thread = getattr(self, attr, None)
            if thread is not None and not isinstance(thread, str):
                try:
                    if hasattr(thread, "requestInterruption"):
                        thread.requestInterruption()
                    thread.quit()
                    if not thread.wait(2000):
                        thread.terminate()
                        thread.wait(1000)
                except Exception:  # noqa: BLE001, S110
                    pass
                setattr(self, attr, None)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_thread is None and self._metadata_thread is None:
            self._save_current_settings()
            self._stop_all_threads()
            event.accept()
            return

        if self._shutdown_in_progress or self._pending_close or self._close_dialog_open:
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
        self._pending_close = True
        self._shutdown_in_progress = True
        event.ignore()

        if self._force_close_timer is None:
            self._force_close_timer = QTimer(self)
            self._force_close_timer.setSingleShot(True)
            self._force_close_timer.timeout.connect(self._force_quit_application)
            self._force_close_timer.start(5000)

        self.cancel_download()
        self._try_finish_close()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not getattr(self, "_leftover_checked", False):
            self._leftover_checked = True
            QTimer.singleShot(500, self.check_and_clean_leftover_jobs)
            QTimer.singleShot(600, self._start_history_validation)

    def _start_history_validation(self) -> None:
        if getattr(self, "_history_validation_started", False):
            return
        self._history_validation_started = True
        self._append_log("İndirme geçmişi doğrulanıyor.")

        self._history_thread = QThread(self)
        self._history_worker = HistoryValidationWorker()
        self._history_worker.moveToThread(self._history_thread)

        self._history_thread.started.connect(self._history_worker.run)
        self._history_worker.finished.connect(self._on_history_validation_finished)
        self._history_worker.finished.connect(self._history_thread.quit)
        self._history_worker.deleteLater()
        self._history_thread.finished.connect(self._history_thread.deleteLater)

        self._history_thread.start()

    def _on_history_validation_finished(self, total_checked: int, stale_count: int) -> None:
        self._append_log(f"{total_checked} kayıt kontrol edildi.")
        self._append_log(f"{stale_count} eksik kayıt stale olarak işaretlendi.")
        if self._history_thread is not None:
            try:
                self._history_thread.quit()
                self._history_thread.wait(3000)
            except Exception:  # noqa: BLE001, S110
                pass
        self._history_thread = None
        self._history_worker = None
        self._try_finish_close()

    def check_and_clean_leftover_jobs(self) -> None:
        raw_folder = self.folder_input.text().strip()
        if not raw_folder:
            return
        output_dir = Path(raw_folder)
        if not output_dir.exists():
            return

        leftover_files = []
        for p in output_dir.glob("*"):
            name = p.name.lower()
            if name.startswith(".kolayindir_") or name.endswith((".kolayindir_tmp", ".hevc_temp.mp4")):
                leftover_files.append(p)

        if leftover_files:
            dlg = LeftoverJobsDialog(count=len(leftover_files), parent=self)
            dlg.exec()
            if dlg.clicked_button_id == "clean":
                cleaned_count = 0
                for f in leftover_files:
                    try:
                        if f.exists():
                            f.unlink()
                            cleaned_count += 1
                    except OSError:
                        pass
                self._append_log(f"Önceki oturumdan kalan {cleaned_count} adet geçici dosya temizlendi.")
            elif dlg.clicked_button_id == "open_folder":
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir)))

