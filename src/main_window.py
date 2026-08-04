"""Kolayİndir ana kullanıcı arayüzü."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Slot
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
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
    APP_DESCRIPTION,
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
    get_unique_directory_path,
    get_unique_filepath,
    sanitize_filename,
)
from src.history_dialog import HistoryDialog
from src.metadata_worker import MetadataWorker
from src.models import (
    KICK_DISABLED_MESSAGE,
    KICK_DISABLED_TITLE,
    DownloadRequest,
    MediaMetadata,
    PlatformType,
    QueueItem,
    detect_platform_type,
    format_bytes,
    get_platform_badge_text,
    is_platform_temporarily_disabled,
    is_rehydration_error,
)
from src.settings import load_settings, save_settings
from src.updater import UpdateWorker
from src.utils import (
    apply_pointing_hand_cursor,
    calculate_detailed_format_info,
    clean_log_message,
    configure_combo_box,
    format_rate_limit,
    get_brand_asset_path,
    probe_media_codecs,
    rate_limit_to_bps,
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
        self._last_failed_request = None
        self._queue_items = []
        self._is_queue_active = False
        self._queue_dialog = None
        self._pending_queue_download_item_id: str | None = None
        self._pending_queue_metadata: MediaMetadata | None = None
        self._log_history: list[str] = []
        self._current_metadata: MediaMetadata | None = None
        self._preferred_browser: str | None = None
        self._preferred_profile: tuple[str, str] | None = None
        self._preferred_impersonation: str | None = None
        self._close_requested: bool = False
        self._cancel_requested: bool = False
        self._pending_close: bool = False
        self._shutdown_in_progress: bool = False
        self._is_closing: bool = False
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
        icon_path = get_brand_asset_path("loadvia.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.resize(710, 650)
        self.setMinimumSize(710, 650)
        self.setAcceptDrops(True)



        self._center_on_screen()
        self._build_ui()
        self._restore_settings()
        self._dep_timer = QTimer(self)
        self._dep_timer.setSingleShot(True)
        self._dep_timer.setInterval(250)
        self._dep_timer.timeout.connect(self._show_dependency_status)
        self._dep_timer.start()
        self._check_clipboard_on_startup()

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


        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        symbol_path = get_brand_asset_path("loadvia-symbol.png")
        if symbol_path.exists():
            symbol_label = QLabel()
            pixmap = QPixmap(str(symbol_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    46,
                    46,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                symbol_label.setPixmap(scaled_pixmap)
                symbol_label.setFixedSize(46, 46)
                header_layout.addWidget(symbol_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        subtitle = QLabel(APP_DESCRIPTION)
        subtitle.setObjectName("subtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
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
        self.paste_button = QPushButton("Panodan Yapıştır")
        self.paste_button.setObjectName("secondaryButton")
        self.paste_button.setProperty("actionRowButton", True)
        self.paste_button.setMinimumWidth(110)
        self.paste_button.setMaximumWidth(150)
        self.paste_button.clicked.connect(self._paste_url)

        self.analyze_button = QPushButton("İncele")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.setProperty("actionRowButton", True)
        self.analyze_button.clicked.connect(self.analyze_url)

        self.queue_button = QPushButton("İndirme Kuyruğu")
        self.queue_button.setObjectName("secondaryButton")
        self.queue_button.setProperty("actionRowButton", True)
        self.queue_button.clicked.connect(self._open_queue_dialog)

        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.paste_button)
        url_row.addWidget(self.queue_button)
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
            "1080p'ye kadar",
            "720p'ye kadar",
            "480p'ye kadar",
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

        self.rate_limit_label = QLabel("İndirme hızı sınırı:")

        self.rate_limit_combo = NoWheelComboBox()
        self.rate_limit_combo.setObjectName("rateLimitCombo")
        self.rate_limit_combo.addItem("Sınırsız", None)
        self.rate_limit_combo.addItem("512 KB/sn", 524288)
        self.rate_limit_combo.addItem("1 MB/sn", 1048576)
        self.rate_limit_combo.addItem("2 MB/sn", 2097152)
        self.rate_limit_combo.addItem("5 MB/sn", 5242880)
        self.rate_limit_combo.addItem("10 MB/sn", 10485760)
        self.rate_limit_combo.addItem("Özel...", "custom")
        self.rate_limit_combo.setToolTip(
            "İndirme sırasında kullanılabilecek azami ağ hızını belirler.\n"
            "Gerçek hız bağlantıya ve kaynağa göre daha düşük olabilir."
        )
        self.rate_limit_combo.currentIndexChanged.connect(self._on_rate_limit_combo_changed)
        configure_combo_box(self.rate_limit_combo)

        self.custom_rate_limit_container = QWidget()
        custom_layout = QHBoxLayout(self.custom_rate_limit_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(6)

        self.custom_rate_limit_spin = QDoubleSpinBox()
        self.custom_rate_limit_spin.setObjectName("customRateLimitSpin")
        self.custom_rate_limit_spin.setRange(0.06, 100.0)
        self.custom_rate_limit_spin.setDecimals(2)
        self.custom_rate_limit_spin.setSingleStep(0.5)
        self.custom_rate_limit_spin.setValue(2.5)
        self.custom_rate_limit_spin.valueChanged.connect(lambda _: self._save_current_settings())

        self.custom_rate_limit_unit_combo = NoWheelComboBox()
        self.custom_rate_limit_unit_combo.setObjectName("customRateLimitUnitCombo")
        self.custom_rate_limit_unit_combo.addItems(["MB/sn", "KB/sn"])
        self.custom_rate_limit_unit_combo.currentTextChanged.connect(self._on_custom_unit_changed)
        configure_combo_box(self.custom_rate_limit_unit_combo)

        custom_layout.addWidget(self.custom_rate_limit_spin)
        custom_layout.addWidget(self.custom_rate_limit_unit_combo)
        self.custom_rate_limit_container.setVisible(False)

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
        options_grid.addWidget(self.rate_limit_label, 2, 0)
        options_grid.addWidget(self.rate_limit_combo, 3, 0)
        options_grid.addWidget(self.custom_rate_limit_container, 3, 1, 1, 2)
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
        self.folder_button.setObjectName("secondaryButton")
        self.folder_button.setMinimumWidth(90)
        self.folder_button.setMaximumWidth(120)
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
        self.open_folder_button.setObjectName("secondaryButton")
        self.open_folder_button.setMinimumWidth(105)
        self.open_folder_button.setMaximumWidth(150)
        self.open_folder_button.clicked.connect(self._open_current_folder)

        self.history_button = QPushButton("Geçmiş")
        self.history_button.setObjectName("secondaryButton")
        self.history_button.setMinimumWidth(90)
        self.history_button.setMaximumWidth(120)
        self.history_button.clicked.connect(self._show_history_dialog)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.folder_button)
        folder_row.addWidget(self.open_folder_button)
        folder_row.addWidget(self.history_button)
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
        self.tech_details_button.setObjectName("secondaryButton")
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
            self.paste_button,
            self.analyze_button,
            self.download_button,
            self.cancel_button,
            self.folder_button,
            self.open_folder_button,
            self.history_button,
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
        self._last_failed_request = None
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
        if self._is_queue_active:
            AppMessageDialog(
                "Kuyruk Aktif",
                "Kuyruk aktifken yeni inceleme başlatılamaz.",
                "warning",
                self,
            ).exec()
            return

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
        if is_platform_temporarily_disabled(platform, url):
            AppMessageDialog(
                KICK_DISABLED_TITLE,
                KICK_DISABLED_MESSAGE,
                "warning",
                self,
            ).exec()
            return

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
                PlatformType.FACEBOOK_VIDEO,
                PlatformType.FACEBOOK_REEL,
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
                "1080p'ye kadar",
                "720p'ye kadar",
                "480p'ye kadar",
                "360p'ye kadar",
            ])

        find_idx = self.quality_combo.findText(current_sel)
        if find_idx < 0 and current_sel:
            norm_sel = current_sel.replace("’", "'")
            for i in range(self.quality_combo.count()):
                if self.quality_combo.itemText(i).replace("’", "'") == norm_sel:
                    find_idx = i
                    break

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
                    PlatformType.FACEBOOK_VIDEO,
                    PlatformType.FACEBOOK_REEL,
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
            return

        if getattr(self, "_is_queue_active", False) and getattr(self, "_pending_queue_download_item_id", None):
            item_id = self._pending_queue_download_item_id
            meta = self._pending_queue_metadata
            self._pending_queue_download_item_id = None
            self._pending_queue_metadata = None
            item = next((x for x in self._queue_items if x.id == item_id), None)
            if item and meta:
                self._start_queue_download(item, meta)


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
        self._restore_rate_limit_setting(self.settings.get("rate_limit_bps"))
        self._on_media_type_changed(self.media_combo.currentText())

    def _restore_rate_limit_setting(self, rate_limit_bps: int | None) -> None:
        if rate_limit_bps is None or rate_limit_bps <= 0:
            self.rate_limit_combo.setCurrentIndex(0)
            self.custom_rate_limit_container.setVisible(False)
            return

        matched_index = -1
        for i in range(self.rate_limit_combo.count()):
            data = self.rate_limit_combo.itemData(i)
            if isinstance(data, int) and data == rate_limit_bps:
                matched_index = i
                break

        if matched_index >= 0:
            self.rate_limit_combo.setCurrentIndex(matched_index)
            self.custom_rate_limit_container.setVisible(False)
        else:
            for i in range(self.rate_limit_combo.count()):
                if self.rate_limit_combo.itemData(i) == "custom":
                    self.rate_limit_combo.setCurrentIndex(i)
                    break
            self.custom_rate_limit_container.setVisible(True)
            if rate_limit_bps >= 1024 * 1024 and (rate_limit_bps % 1024 == 0):
                mb_val = rate_limit_bps / (1024 * 1024)
                self.custom_rate_limit_unit_combo.setCurrentText("MB/sn")
                self._update_custom_spin_limits("MB/sn")
                self.custom_rate_limit_spin.setValue(round(mb_val, 2))
            else:
                kb_val = rate_limit_bps / 1024
                self.custom_rate_limit_unit_combo.setCurrentText("KB/sn")
                self._update_custom_spin_limits("KB/sn")
                self.custom_rate_limit_spin.setValue(round(kb_val, 2))

    def _on_rate_limit_combo_changed(self, index: int) -> None:
        data = self.rate_limit_combo.itemData(index)
        is_custom = data == "custom"
        self.custom_rate_limit_container.setVisible(is_custom)
        if is_custom:
            self._update_custom_spin_limits(self.custom_rate_limit_unit_combo.currentText())
        self._save_current_settings()

    def _on_custom_unit_changed(self, unit: str) -> None:
        current_val = self.custom_rate_limit_spin.value()
        self.custom_rate_limit_spin.blockSignals(True)
        if "MB" in unit:
            new_val = max(0.06, min(100.0, current_val / 1024.0))
            self._update_custom_spin_limits("MB/sn")
            self.custom_rate_limit_spin.setValue(round(new_val, 2))
        else:
            new_val = max(64.0, min(102400.0, current_val * 1024.0))
            self._update_custom_spin_limits("KB/sn")
            self.custom_rate_limit_spin.setValue(round(new_val, 0))
        self.custom_rate_limit_spin.blockSignals(False)
        self._save_current_settings()

    def _update_custom_spin_limits(self, unit: str) -> None:
        self.custom_rate_limit_spin.blockSignals(True)
        if "MB" in unit:
            self.custom_rate_limit_spin.setRange(0.06, 100.0)
            self.custom_rate_limit_spin.setDecimals(2)
            self.custom_rate_limit_spin.setSingleStep(0.5)
        else:
            self.custom_rate_limit_spin.setRange(64.0, 102400.0)
            self.custom_rate_limit_spin.setDecimals(0)
            self.custom_rate_limit_spin.setSingleStep(64.0)
        self.custom_rate_limit_spin.blockSignals(False)

    def get_current_rate_limit_bps(self) -> int | None:
        data = self.rate_limit_combo.currentData()
        if data is None:
            return None
        if isinstance(data, int):
            return data if data > 0 else None
        if data == "custom":
            val = self.custom_rate_limit_spin.value()
            unit = self.custom_rate_limit_unit_combo.currentText()
            return rate_limit_to_bps(val, unit)
        return None

    def _save_current_settings(self) -> None:
        save_settings({
            "output_dir": self.folder_input.text().strip(),
            "media_type": self.media_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "auto_open_folder": self.auto_open_checkbox.isChecked(),
            "rate_limit_bps": self.get_current_rate_limit_bps(),
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
        if not self.url_input.isEnabled():
            self.status_label.setText("Devam eden işlem tamamlanmadan bağlantı değiştirilemez.")
            return

        import re

        from src.utils import extract_supported_url_from_text

        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()

        if not text:
            self.status_label.setText("Panoda bir bağlantı bulunamadı.")
            return

        url = extract_supported_url_from_text(text)
        if url:
            self.url_input.setText(url)
            self.status_label.setText("Bağlantı panodan yapıştırıldı.")
        else:
            url_pattern = re.compile(r'https?://[^\s]+')
            if url_pattern.search(text):
                self.status_label.setText("Bu bağlantı henüz desteklenmiyor.")
            else:
                self.status_label.setText("Panoda desteklenen bir bağlantı bulunamadı.")

    def _check_clipboard_on_startup(self) -> None:
        from src.utils import extract_supported_url_from_text
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            return

        url = extract_supported_url_from_text(text)
        if url:
            self.status_label.setText("Panoda desteklenen bir bağlantı bulundu.")

    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except (ValueError, TypeError, AttributeError):
            return False

    def _show_dependency_status(self) -> None:
        from shiboken6 import isValid
        if getattr(self, '_is_closing', False) or not isValid(self):
            return

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
        if self._is_queue_active:
            AppMessageDialog(
                "Kuyruk Aktif",
                "Kuyruk aktifken yeni indirme başlatılamaz.",
                "warning",
                self,
            ).exec()
            return

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
        if is_platform_temporarily_disabled(platform_now, url):
            AppMessageDialog(
                KICK_DISABLED_TITLE,
                KICK_DISABLED_MESSAGE,
                "warning",
                self,
            ).exec()
            return
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
        if clean_title.lower() in {"manifest", "master", "playlist", "index", "chunklist", ""}:
            clean_title = "Kick Videosu" if (platform_now == PlatformType.KICK_VIDEO or "kick.com" in url.lower()) else "Video"

        initial_target_path = output_dir / f"{clean_title}.{ext}"

        self._append_log("İndirme isteği oluşturuldu.")
        self._append_log(f"Hedef klasör doğrulandı: {output_dir}")

        if self._current_metadata and self._current_metadata.is_playlist and playlist:
            playlist_name = clean_title
            if not playlist_name or playlist_name.lower() in {"video", "kick videosu", "manifest", "master", "playlist", "index", "chunklist"}:
                playlist_name = "Playlist"

            target_override = get_unique_directory_path(output_dir / playlist_name)
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

        current_rate_limit = self.get_current_rate_limit_bps()
        if current_rate_limit and current_rate_limit > 0:
            self._append_log(f"İndirme hızı sınırı: {format_rate_limit(current_rate_limit)}")

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
            rate_limit_bps=current_rate_limit,
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

    def _retry_download(self) -> None:
        if self._download_worker is not None or self._metadata_worker is not None:
            self.status_label.setText("Devam eden işlem tamamlanmadan yeniden deneme başlatılamaz.")
            return

        if not self._last_failed_request:
            return

        req = self._last_failed_request
        self.url_input.setText(req.url)
        self.media_combo.setCurrentText(req.media_type)
        self.quality_combo.setCurrentText(req.quality)
        self.playlist_checkbox.setChecked(req.playlist)
        self.folder_input.setText(str(req.output_dir))
        self._restore_rate_limit_setting(req.rate_limit_bps)

        self.start_download()

    def _retry_with_session(self) -> None:
        if self._download_worker is not None or self._metadata_worker is not None:
            self.status_label.setText("Devam eden işlem tamamlanmadan yeniden deneme başlatılamaz.")
            return

        if not self._last_failed_request:
            return

        if self._last_failed_request.browser == "auto":
            self.status_label.setText("Kullanılabilir bir tarayıcı oturumu bulunamadı veya oturum doğrulanamadı.")
            AppMessageDialog(
                "Oturum Hatası",
                "Kullanılabilir bir tarayıcı oturumu bulunamadı veya oturum doğrulanamadı.",
                "error",
                self
            ).exec()
            return

        for i in range(self.browser_combo.count()):
            if self.browser_combo.itemData(i) == "auto":
                self.browser_combo.setCurrentIndex(i)
                break

        self._preferred_profile = None
        self._preferred_browser = None

        self._retry_download()

    def _edit_url_after_failure(self) -> None:
        if not self._last_failed_request:
            return

        req = self._last_failed_request
        self.url_input.setText(req.url)
        self.media_combo.setCurrentText(req.media_type)
        self.quality_combo.setCurrentText(req.quality)
        self.playlist_checkbox.setChecked(req.playlist)
        self.folder_input.setText(str(req.output_dir))
        self._restore_rate_limit_setting(req.rate_limit_bps)
        self.url_input.setEnabled(True)
        self.url_input.setFocus()
        self.url_input.selectAll()

        self._current_metadata = None
        self.preview_frame.hide()
        self._update_download_button_state()
        self._last_failed_request = None

        if self._metadata_worker is not None:
            self.status_label.setText("İnceleme iptal ediliyor…")
            self._metadata_worker.cancel()

    def _on_progress_details(self, details: dict) -> None:
        phase = details.get("phase", "downloading")
        downloaded = details.get("downloaded_bytes") or 0
        total = details.get("total_bytes") or 0
        speed = details.get("speed") or "Hız hesaplanıyor…"
        eta = details.get("eta") or "Kalan süre hesaplanıyor…"
        frag_idx = details.get("fragment_index")
        frag_cnt = details.get("fragment_count")
        pct = details.get("percent", 0)

        if phase == "merging_video_audio":
            self.status_label.setText(f"Video MP4 olarak hazırlanıyor: %{pct}" if pct > 0 else "Video ve ses birleştiriliyor…")
            self.stats_label.setText("Hız: Dosya işleniyor • Kalan: Hesaplanıyor")
            return

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
        is_kick = (
            self._current_metadata is not None
            and self._current_metadata.platform_type == PlatformType.KICK_VIDEO
        )

        if is_kick:
            if frag_cnt and frag_idx:
                header_text = f"HLS parçaları indiriliyor… (Parça {frag_idx} / {frag_cnt})"
            elif downloaded > 0:
                header_text = f"HLS parçaları indiriliyor… ({format_bytes(downloaded)} indirildi)"
            else:
                header_text = "HLS parçaları indiriliyor…"
        else:
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
        elif frag_cnt and frag_idx:
            dl_str = format_bytes(downloaded) if downloaded > 0 else ""
            size_part = f" • {dl_str}" if dl_str else ""
            self.stats_label.setText(f"Parça {frag_idx} / {frag_cnt}{size_part} • Hız: {speed} • Kalan: {eta}")
        elif downloaded > 0:
            dl_str = format_bytes(downloaded)
            self.stats_label.setText(f"{dl_str} indirildi • Hız: {speed} • Kalan: {eta}")
        else:
            self.stats_label.setText(f"Hız: {speed} • Kalan: {eta}")

    def _on_download_succeeded(self, filename: str) -> None:
        self._last_failed_request = None
        if filename.lower() in {"manifest", "master", "playlist", "index", "chunklist"}:
            filename = "Kick Videosu.mp4"
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

        if self._download_worker:
            self._last_failed_request = self._download_worker.request

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

        dlg = AppMessageDialog(
            "İndirme Başarısız",
            f"İndirme tamamlanamadı. İşlemi tekrar deneyebilir veya bağlantıyı düzenleyebilirsiniz.\n\n{error_msg}",
            "error",
            self,
            [
                ("retry", "Tekrar Dene", True),
                ("retry_session", "Oturumla Tekrar Dene", False),
                ("edit_url", "Bağlantıyı Düzenle", False),
                ("close", "Kapat", False),
            ]
        )
        dlg.exec()

        if dlg.clicked_button_id == "retry":
            self._retry_download()
        elif dlg.clicked_button_id == "retry_session":
            self._retry_with_session()
        elif dlg.clicked_button_id == "edit_url":
            self._edit_url_after_failure()

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
                if not getattr(self, "_shutdown_in_progress", False):
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

    def _show_history_dialog(self) -> None:
        dlg = HistoryDialog(self)
        dlg.redownload_requested.connect(self._on_history_redownload_requested)
        dlg.exec()

    def _on_history_redownload_requested(self, url: str) -> None:
        if self._download_thread is not None or self._metadata_thread is not None:
            AppMessageDialog(
                title="İşlem Devam Ediyor",
                message="Şu anda aktif bir indirme veya inceleme işlemi var. Lütfen önce onun bitmesini bekleyin.",
                parent=self
            ).exec()
            return

        self.url_input.setText(url)
        self.analyze_url()

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

    def _stop_all_threads(self, for_shutdown: bool = True) -> None:
        """Kapanışta veya test temizliğinde tüm çalışan arka plan iş parçacıklarını güvenle durdurur."""
        if for_shutdown:
            self._shutdown_in_progress = True

        for w_attr in ("_history_worker", "_update_worker", "_metadata_worker", "_download_worker"):
            worker = getattr(self, w_attr, None)
            if worker is not None and hasattr(worker, "cancel"):
                try:
                    worker.cancel()
                except Exception:  # noqa: BLE001, S110
                    pass

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

    def _open_queue_dialog(self) -> None:
        if not self._queue_dialog:
            from src.queue_dialog import DownloadQueueDialog

            default_folder = Path(self.folder_input.text().strip()) if self.folder_input.text().strip() else Path.home() / "Downloads"
            self._queue_dialog = DownloadQueueDialog(default_folder=default_folder, parent=self)
            self._queue_dialog.urls_added.connect(self._on_queue_urls_added)
            self._queue_dialog.current_url_added.connect(self._on_queue_current_url_added)
            self._queue_dialog.start_queue_requested.connect(self._start_queue)
            self._queue_dialog.stop_queue_requested.connect(self._stop_queue)
            self._queue_dialog.delete_selected_requested.connect(self._delete_queue_item)
            self._queue_dialog.clear_completed_requested.connect(self._clear_completed_queue)
            self._queue_dialog.retry_failed_requested.connect(self._retry_failed_queue)

        self._queue_dialog.refresh_table(self._queue_items)
        self._queue_dialog.show()
        self._queue_dialog.raise_()
        self._queue_dialog.activateWindow()

    def _on_queue_urls_added(
        self,
        urls: list[str],
        media_type: str | None = None,
        quality: str | None = None,
        playlist: bool | None = None,
        output_dir: Path | None = None,
        rate_limit_bps: int | None | object = ...,
    ) -> None:
        added_count = 0
        media_type = media_type or self.media_combo.currentText()
        quality = quality or self.quality_combo.currentText()
        playlist = playlist if playlist is not None else self.playlist_checkbox.isChecked()
        output_dir = output_dir or (Path(self.folder_input.text().strip()) if self.folder_input.text().strip() else Path.home() / "Downloads")
        rate_limit_bps = self.get_current_rate_limit_bps() if rate_limit_bps is ... else rate_limit_bps
        browser = self.browser_combo.currentData()

        import uuid

        for u in urls:
            is_dup = any(
                item.url == u
                and item.media_type == media_type
                and item.quality == quality
                and item.playlist == playlist
                and item.output_dir == output_dir
                and item.rate_limit_bps == rate_limit_bps
                for item in self._queue_items
            )
            if is_dup:
                continue

            platform = detect_platform_type(u)
            if platform == PlatformType.UNKNOWN:
                continue

            q_item = QueueItem(
                id=str(uuid.uuid4()),
                url=u,
                platform=platform.value,
                media_type=media_type,
                quality=quality,
                playlist=playlist,
                output_dir=output_dir,
                browser=browser,
                rate_limit_bps=rate_limit_bps,
            )
            self._queue_items.append(q_item)
            added_count += 1

        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

        if added_count == 0 and urls:
            AppMessageDialog("Bilgi", "Bu bağlantı aynı ayarlarla zaten kuyrukta bulunuyor.", "info", self._queue_dialog or self).exec()
        elif added_count == 0:
            AppMessageDialog("Hata", "Desteklenen bir bağlantı bulunamadı.", "error", self._queue_dialog or self).exec()
        elif added_count < len(urls):
            AppMessageDialog("Bilgi", f"{added_count} bağlantı kuyruğa eklendi. {len(urls) - added_count} bağlantı atlandı veya desteklenmedi.", "info", self._queue_dialog or self).exec()

    def _on_queue_current_url_added(
        self,
        media_type: str | None = None,
        quality: str | None = None,
        playlist: bool | None = None,
        output_dir: Path | None = None,
        rate_limit_bps: int | None | object = ...,
    ) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        from src.utils import extract_supported_urls_from_text

        valid = extract_supported_urls_from_text(url)
        if valid:
            self._on_queue_urls_added(
                valid,
                media_type=media_type,
                quality=quality,
                playlist=playlist,
                output_dir=output_dir,
                rate_limit_bps=self.get_current_rate_limit_bps() if rate_limit_bps is ... else rate_limit_bps,
            )
        else:
            AppMessageDialog("Hata", "Desteklenen bir bağlantı bulunamadı.", "error", self._queue_dialog or self).exec()

    def _start_queue(self) -> None:
        if self._download_thread is not None or self._metadata_thread is not None:
            if not self._is_queue_active:
                AppMessageDialog("Hata", "Devam eden indirme tamamlanmadan kuyruk başlatılamaz.", "error", self._queue_dialog or self).exec()
            return

        waiting = any(item.status == "Bekliyor" for item in self._queue_items)
        if not waiting:
            AppMessageDialog("Bilgi", "Kuyrukta indirilecek bağlantı bulunmuyor.", "info", self._queue_dialog or self).exec()
            return

        self._is_queue_active = True
        self._process_next_queue_item()

    def _process_next_queue_item(self) -> None:
        if not self._is_queue_active:
            return

        if self._download_thread is not None or self._metadata_thread is not None:
            return

        active_item = None
        for item in self._queue_items:
            if item.status == "Bekliyor":
                active_item = item
                break

        if not active_item:
            self._is_queue_active = False
            self._on_queue_finished()
            return

        active_item.status = "Analiz ediliyor"
        active_item.progress_text = "Başlatılıyor..."
        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

        self._start_queue_metadata(active_item)

    def _start_queue_metadata(self, item: QueueItem) -> None:
        self._active_queue_item_id = item.id
        self.status_label.setText(f"Kuyruk: {item.url} inceleniyor…")

        thread = QThread(self)
        worker = MetadataWorker(
            url=item.url,
            requested_quality=item.quality,
            media_type=item.media_type,
            browser=item.browser,
            preferred_browser=item.browser,
            preferred_profile=None,
            settings=dict(self.settings),
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.metadata_ready.connect(self._on_queue_metadata_ready)
        worker.failed.connect(self._on_queue_metadata_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_metadata_finished)

        self._metadata_thread = thread
        self._metadata_worker = worker
        thread.start()

    @Slot(object)
    def _on_queue_metadata_ready(self, meta: MediaMetadata) -> None:
        item = self._get_active_queue_item()
        if not item:
            return
        self._current_metadata = meta
        if meta.title:
            item.title = meta.title
        item.progress_text = "Analiz tamamlandı..."
        self._pending_queue_download_item_id = item.id
        self._pending_queue_metadata = meta
        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

    @Slot(str)
    def _on_queue_metadata_failed(self, error_msg: str) -> None:
        item = self._get_active_queue_item()
        self._pending_queue_download_item_id = None
        self._pending_queue_metadata = None
        if item:
            item.status = "Başarısız"
            item.error_msg = clean_log_message(error_msg).split("\n")[0] if error_msg else "Bilinmeyen Hata"
            if self._queue_dialog:
                self._queue_dialog.refresh_table(self._queue_items)

    def _start_queue_download(self, item: QueueItem, meta: MediaMetadata) -> None:
        try:
            from src.history import (
                get_unique_directory_path,
                get_unique_filepath,
                sanitize_filename,
            )

            download_url = item.url
            if meta and meta.successful_request_url:
                download_url = meta.successful_request_url
            elif meta and meta.webpage_url and detect_platform_type(meta.webpage_url) != PlatformType.UNKNOWN:
                download_url = meta.webpage_url

            ext = "mp3" if ("MP3" in item.media_type or "Ses" in item.media_type) else "mp4"
            raw_title = meta.title if meta and meta.title else "Video"
            clean_title = sanitize_filename(raw_title)
            if clean_title.lower() in {"manifest", "master", "playlist", "index", "chunklist", ""}:
                clean_title = "Video"

            initial_target_path = item.output_dir / f"{clean_title}.{ext}"

            if meta and meta.is_playlist and item.playlist:
                playlist_name = clean_title
                if not playlist_name or playlist_name.lower() in {"video", "manifest", "master", "playlist", "index", "chunklist"}:
                    playlist_name = "Playlist"
                target_override = get_unique_directory_path(item.output_dir / playlist_name)
            else:
                target_override = get_unique_filepath(initial_target_path)

            if item.rate_limit_bps and item.rate_limit_bps > 0:
                self._append_log(f"Kuyruk hız sınırı: {format_rate_limit(item.rate_limit_bps)}")

            request = DownloadRequest(
                url=download_url,
                output_dir=item.output_dir,
                media_type=item.media_type,
                quality=item.quality,
                playlist=item.playlist,
                browser=item.browser,
                preferred_browser=item.browser,
                preferred_profile=None,
                preferred_impersonation=None,
                successful_request_url=download_url,
                convert_hevc_to_h264=self.settings.get("convert_hevc_to_h264", True),
                target_final_path=target_override,
                rate_limit_bps=item.rate_limit_bps,
            )

            self._download_succeeded_result = None
            self._download_succeeded_path = ""

            thread = QThread(self)
            worker = DownloadWorker(request)
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.progress.connect(self._on_queue_progress)
            worker.progress_details.connect(self._on_queue_progress_details)
            worker.succeeded.connect(self._on_queue_download_succeeded)
            worker.failed.connect(self._on_queue_download_failed)
            worker.cancelled.connect(self._on_queue_download_cancelled)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(self._on_queue_download_thread_finished)

            item.status = "İndiriliyor"
            item.progress_text = "İndirme başlatılıyor…"
            if self._queue_dialog:
                self._queue_dialog.refresh_table(self._queue_items)

            self.status_label.setText(f"Kuyruk: {item.title} indiriliyor…")

            self._download_thread = thread
            self._download_worker = worker
            thread.start()
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Kuyruk indirme başlatma hatası: {exc}")
            item.status = "Başarısız"
            item.error_msg = clean_log_message(str(exc)).split("\n")[0] if str(exc) else "Başatılama hatası"
            item.progress_percent = 0
            item.progress_text = ""
            if self._queue_dialog:
                self._queue_dialog.refresh_table(self._queue_items)

            self._download_thread = None
            self._download_worker = None
            self._active_queue_item_id = None
            if self._is_queue_active:
                self._process_next_queue_item()

    @Slot(int)
    def _on_queue_progress(self, percent: int) -> None:
        item = self._get_active_queue_item()
        if not item:
            return
        item.progress_percent = percent
        if self._queue_dialog:
            self._queue_dialog.update_item_progress(item.id, percent=percent)

    @Slot(str)
    def _on_queue_progress_details(self, details: str) -> None:
        item = self._get_active_queue_item()
        if not item:
            return
        item.progress_text = details
        if self._queue_dialog:
            self._queue_dialog.update_item_progress(item.id, text=details)

    @Slot(str)
    def _on_queue_download_succeeded(self, filename: str) -> None:
        try:
            item = self._get_active_queue_item()
            if item:
                item.status = "Tamamlandı"
                item.progress_percent = 100
                item.progress_text = "Başarılı"
                item.error_msg = ""
                if self._queue_dialog:
                    self._queue_dialog.refresh_table(self._queue_items)
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Kuyruk indirme başarı işleme hatası: {exc}")

    @Slot(str)
    def _on_queue_download_failed(self, error_msg: str) -> None:
        item = self._get_active_queue_item()
        if item:
            item.status = "Başarısız"
            item.error_msg = clean_log_message(error_msg).split("\n")[0] if error_msg else "Bilinmeyen Hata"
            if self._queue_dialog:
                self._queue_dialog.refresh_table(self._queue_items)

    @Slot()
    def _on_queue_download_cancelled(self) -> None:
        item = self._get_active_queue_item()
        if item:
            item.status = "İptal edildi"
            item.progress_text = "Kullanıcı iptal etti"
        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

        self._is_queue_active = False

    @Slot()
    def _on_queue_download_thread_finished(self) -> None:
        self._download_thread = None
        self._download_worker = None
        self._set_ui_downloading(False)
        self._cancel_requested = False
        self._active_queue_item_id = None

        if self._close_requested or self._pending_close or self._shutdown_in_progress:
            self._try_finish_close()
            return

        if self._is_queue_active:
            self._process_next_queue_item()

    def _get_active_queue_item(self) -> QueueItem | None:
        if getattr(self, "_active_queue_item_id", None):
            for item in self._queue_items:
                if item.id == self._active_queue_item_id and item.status in ("Analiz ediliyor", "İndiriliyor"):
                    return item
        for item in self._queue_items:
            if item.status in ("Analiz ediliyor", "İndiriliyor"):
                return item
        return None

    def _stop_queue(self) -> None:
        if not self._is_queue_active:
            return

        self._is_queue_active = False

        if self._download_worker:
            self._download_worker.cancel()
        if self._metadata_worker:
            self._metadata_worker.cancel()

    def _delete_queue_item(self, item_id: str) -> None:
        for i, item in enumerate(self._queue_items):
            if item.id == item_id:
                if item.status in ("Analiz ediliyor", "İndiriliyor"):
                    AppMessageDialog("Hata", "Aktif kuyruk öğesi silinemez. Önce kuyruğu durdurun.", "error", self._queue_dialog or self).exec()
                    return
                self._queue_items.pop(i)
                break
        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

    def _clear_completed_queue(self) -> None:
        self._queue_items = [item for item in self._queue_items if item.status != "Tamamlandı"]
        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

    def _retry_failed_queue(self) -> None:
        for item in self._queue_items:
            if item.status == "Başarısız":
                item.status = "Bekliyor"
                item.error_msg = ""
                item.progress_text = ""
                item.progress_percent = 0
        if self._queue_dialog:
            self._queue_dialog.refresh_table(self._queue_items)

    def _on_queue_finished(self) -> None:
        completed = sum(1 for item in self._queue_items if item.status == "Tamamlandı")
        failed = sum(1 for item in self._queue_items if item.status == "Başarısız")

        AppMessageDialog(
            "Kuyruk Tamamlandı",
            f"{completed} bağlantı tamamlandı, {failed} bağlantı başarısız oldu.",
            "info",
            self._queue_dialog or self,
        ).exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._is_closing = True
        if hasattr(self, '_dep_timer') and self._dep_timer and self._dep_timer.isActive():
            self._dep_timer.stop()
            try:
                self._dep_timer.timeout.disconnect()
            except RuntimeError:
                pass

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

