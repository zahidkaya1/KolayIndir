"""Kolayİndir özel açık temalı diyalog pencere bileşenleri."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.browser_sessions import (
    is_chromium_encryption_error,
    is_firefox_has_instagram_session,
    is_firefox_installed,
)
from src.config import APP_VERSION


class DownloadCompletedDialog(QDialog):
    """İndirme tamamlandığında gösterilen açık temalı özel onay penceresi."""

    def __init__(
        self,
        result_summary: str = "",
        filepath: str = "",
        video_codec: str = "",
        audio_codec: str = "",
        resolution: str = "",
        filesize_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("downloadCompletedDialog")
        self.setWindowTitle("İndirme tamamlandı")
        self.setMinimumWidth(420)
        self.setMaximumWidth(600)
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

        msg_parts = []
        if result_summary:
            import os

            clean_res = (
                Path(result_summary).stem
                if os.path.isabs(result_summary)
                else result_summary
            )
            if clean_res.lower() in {
                "manifest",
                "master",
                "playlist",
                "index",
                "chunklist",
            }:
                clean_res = (
                    Path(filepath).stem
                    if (
                        filepath
                        and Path(filepath).stem.lower()
                        not in {"manifest", "master", "playlist", "index", "chunklist"}
                    )
                    else "Kick Videosu"
                )
            msg_parts.append(f"Tamamlanan: {clean_res}")

        info_parts = []
        if video_codec:
            if "264" in video_codec or "avc" in video_codec.lower():
                c_display = "H.264 (AVC)"
            elif (
                "hevc" in video_codec.lower()
                or "265" in video_codec
                or "bytevc" in video_codec.lower()
            ):
                c_display = "HEVC (H.265)"
            else:
                c_display = video_codec.upper()
            info_parts.append(f"• Video Codec: {c_display}")
        if audio_codec:
            info_parts.append(f"• Ses Codec: {audio_codec.upper()}")
        if resolution:
            info_parts.append(f"• Çözünürlük: {resolution}")
        if filesize_text:
            info_parts.append(f"• Boyut: {filesize_text}")
        if self.filepath:
            fn = Path(self.filepath).name
            if fn.lower() not in {
                "manifest",
                "master",
                "playlist",
                "index",
                "chunklist",
            }:
                info_parts.append(f"• Dosya: {fn}")

        if info_parts:
            msg_parts.append("\n".join(info_parts))

        msg_parts.append("İndirme klasörünü açmak ister misiniz?")

        self.message_label = QLabel("\n\n".join(msg_parts))
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
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

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

        notes_content = QLabel(
            notes if notes.strip() else "Yeni sürüm notu bulunmuyor."
        )
        notes_content.setObjectName("updateDialogMessage")
        notes_content.setWordWrap(True)
        notes_content.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

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
        if custom_buttons and len(custom_buttons) >= 4:
            self.setMinimumWidth(760)
            self.setMaximumWidth(840)
        else:
            self.setMinimumWidth(380)
            self.setMaximumWidth(560)

        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

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
            from src.utils import apply_pointing_hand_cursor

            for btn_id, label, is_primary in custom_buttons:
                btn = QPushButton(label)
                if is_primary:
                    btn.setObjectName("dialogPrimaryButton")
                else:
                    btn.setObjectName("dialogSecondaryButton")

                btn.setMinimumHeight(44)
                btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                min_w = btn.fontMetrics().horizontalAdvance(label) + 32
                btn.setMinimumWidth(min_w)
                apply_pointing_hand_cursor(btn)

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


class SessionFailedDialog(QDialog):
    """Tüm oturum denemeleri başarısız olduğunda gösterilen özel diyalog penceresi."""

    def __init__(
        self,
        platform_name: str = "instagram",
        failure_reason: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sessionFailedDialog")
        self.setWindowTitle("Oturum alınamadı")
        self.setMinimumWidth(460)
        self.setMaximumWidth(600)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Oturum alınamadı")
        title.setObjectName("dialogTitleLabel")

        reason_lower = failure_reason.lower()
        platform_lower = platform_name.lower()
        is_instagram = "instagram" in platform_lower
        is_twitter = "twitter" in platform_lower or "x" in platform_lower
        is_youtube = "youtube" in platform_lower
        is_facebook = "facebook" in platform_lower or "fb" in platform_lower
        is_threads = "threads" in platform_lower

        # --- Durum tespiti ---
        has_encryption_err = is_chromium_encryption_error(failure_reason)
        has_lock_err = "kilit" in reason_lower or "lock" in reason_lower
        has_expired = (
            "süresi dolmuş" in reason_lower
            or "expired" in reason_lower
            or "404" in reason_lower
            or "erişilemiyor" in reason_lower
            or "story_inaccessible" in reason_lower
        )
        ff_installed = is_firefox_installed()
        ff_has_session = is_firefox_has_instagram_session() if ff_installed else False

        # --- Ana mesaj ---
        if has_encryption_err:
            main_text = (
                "Bu tarayıcının oturum bilgileri Windows güvenlik kısıtlamaları nedeniyle okunamadı. "
                "Firefox veya çerez dosyası kullanabilirsiniz."
            )
        elif has_lock_err:
            main_text = (
                "Tarayıcı çerez veritabanı kilitli. "
                "Tarayıcıyı tamamen kapatıp yeniden deneyin."
            )
        elif has_expired:
            main_text = "Bu hikâye sona ermiş, silinmiş veya hesabınız tarafından görüntülenemiyor olabilir."
        elif is_instagram:
            if ff_installed and not ff_has_session:
                main_text = (
                    "Firefox bulundu ancak Instagram hesabının açık olduğu bir oturum bulunamadı. "
                    "Firefox'ta Instagram'a giriş yapıp tarayıcıyı tamamen kapatarak yeniden deneyin."
                )
            elif not ff_installed:
                main_text = "Bu içerik için Instagram oturumu gerekiyor ancak kullanılabilir bir oturum bulunamadı."
            else:
                main_text = (
                    "Instagram hesabının açık olduğu bir tarayıcı oturumu bulunamadı. "
                    "Tarayıcıda Instagram'a giriş yapıp tarayıcıyı tamamen kapatarak yeniden deneyin."
                )
        elif is_facebook:
            main_text = "Facebook hesabınızın açık olduğu bir tarayıcı oturumu seçebilir veya tarayıcıyı tamamen kapatıp yeniden deneyebilirsiniz."
        elif is_threads:
            main_text = "Threads hesabınızın açık olduğu bir tarayıcı oturumu seçebilir veya tarayıcıyı tamamen kapatıp yeniden deneyebilirsiniz."
        elif is_twitter:
            main_text = "İçeriği görebildiğiniz hesabın açık olduğu tarayıcıyı kapatıp yeniden deneyin."
        elif is_youtube:
            main_text = (
                "Video yaş kısıtlamalı veya oturum doğrulaması gerektiriyor olabilir."
            )
        else:
            main_text = "Lütfen tarayıcınızda hesabınızın açık olduğundan ve oturumun aktif olduğundan emin olun."

        msg = QLabel(main_text)
        msg.setObjectName("dialogMessageLabel")
        msg.setWordWrap(True)

        # --- Firefox ipucu kutusu (yalnız Instagram + Firefox yok) ---
        ff_hint_widget: QFrame | None = None
        if is_instagram and not ff_installed and not has_expired and not has_lock_err:
            ff_hint_widget = QFrame()
            ff_hint_widget.setObjectName("ffHintFrame")
            ff_hint_widget.setStyleSheet(
                "QFrame#ffHintFrame { background: #eff6ff; border: 1px solid #bfdbfe; "
                "border-radius: 6px; padding: 8px; }"
            )
            ff_layout = QVBoxLayout(ff_hint_widget)
            ff_layout.setContentsMargins(10, 8, 10, 8)
            ff_layout.setSpacing(4)
            ff_hint_lbl = QLabel(
                "Firefox'u bir kez kurup Instagram hesabınıza giriş yaptıktan sonra "
                "Kolayİndir oturumu otomatik kullanacaktır."
            )
            ff_hint_lbl.setStyleSheet("color: #1e40af; font-size: 12px;")
            ff_hint_lbl.setWordWrap(True)
            ff_layout.addWidget(ff_hint_lbl)

        # --- Düğmeler ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        self.clicked_button_id: str = "close"

        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("dialogSecondaryButton")
        close_btn.clicked.connect(lambda: self._set_choice("close"))
        btn_row.addWidget(close_btn)

        retry_btn = QPushButton("Yeniden Dene")
        retry_btn.setObjectName("dialogSecondaryButton")
        retry_btn.clicked.connect(lambda: self._set_choice("retry"))
        btn_row.addWidget(retry_btn)

        # Firefox kurulum düğmesi: Instagram + (encryption hatası VEYA Firefox yok)
        show_ff_btn = is_instagram and (has_encryption_err or not ff_installed)
        if show_ff_btn:
            ff_btn = QPushButton("Firefox Kurulumunu Aç")
            ff_btn.setObjectName("dialogPrimaryButton")
            ff_btn.clicked.connect(lambda: self._set_choice("install_firefox"))
            btn_row.addWidget(ff_btn)
        else:
            # Başka durumlarda Yeniden Dene birincil
            retry_btn.setObjectName("dialogPrimaryButton")

        layout.addWidget(title)
        layout.addWidget(msg)
        if ff_hint_widget is not None:
            layout.addWidget(ff_hint_widget)
        layout.addSpacing(8)
        layout.addLayout(btn_row)

    def _set_choice(self, choice: str) -> None:
        self.clicked_button_id = choice
        self.accept()


class SessionRetryDialog(QDialog):
    """Tarayıcı oturumu veya çerez dosyası ile yeniden deneme diyalogu."""

    def __init__(
        self,
        title: str = "Oturum Doğrulaması Gerekebilir",
        message: str = "",
        platform_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sessionRetryDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setMaximumWidth(580)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.selected_method: str = "auto"
        self.selected_cookie_file: str | None = None
        self.clicked_button_id: str = "close"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitleLabel")
        layout.addWidget(title_label)

        msg_label = QLabel(
            message
            if message
            else "Bu içeriği görüntülemek için tarayıcı oturumu gerekebilir."
        )
        msg_label.setObjectName("dialogMessageLabel")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        from src.browser_sessions import is_chromium_encryption_error

        if is_chromium_encryption_error(message):
            warn_frame = QFrame()
            warn_frame.setObjectName("warnFrame")
            warn_frame.setStyleSheet(
                "QFrame#warnFrame { background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px; }"
            )
            warn_layout = QVBoxLayout(warn_frame)
            warn_layout.setContentsMargins(8, 6, 8, 6)
            warn_lbl = QLabel(
                "Bu tarayıcının oturum bilgileri Windows güvenlik kısıtlamaları nedeniyle okunamadı. Firefox oturumunu veya bir çerez dosyasını kullanabilirsiniz."
            )
            warn_lbl.setStyleSheet("color: #991b1b; font-size: 12px;")
            warn_lbl.setWordWrap(True)
            warn_layout.addWidget(warn_lbl)
            layout.addWidget(warn_frame)

        combo_label = QLabel("Kullanılacak oturum yöntemi:")
        combo_label.setStyleSheet("color: #334155; font-size: 13px; font-weight: 600;")
        layout.addWidget(combo_label)

        from PySide6.QtWidgets import QComboBox

        from src.utils import apply_pointing_hand_cursor, configure_combo_box

        self.method_combo = QComboBox()
        self.method_combo.setObjectName("sessionMethodCombo")
        self.method_combo.addItem("Otomatik (Önerilen)", "auto")
        self.method_combo.addItem("Oturumsuz", "none")
        self.method_combo.addItem("Firefox", "firefox")
        self.method_combo.addItem("Microsoft Edge", "edge")
        self.method_combo.addItem("Chrome", "chrome")
        self.method_combo.addItem("Brave", "brave")
        self.method_combo.addItem("Çerez dosyası seç...", "cookie_file")
        configure_combo_box(self.method_combo)
        layout.addWidget(self.method_combo)

        self.cookie_path_label = QLabel("")
        self.cookie_path_label.setStyleSheet("color: #0284c7; font-size: 12px;")
        self.cookie_path_label.setWordWrap(True)
        self.cookie_path_label.setVisible(False)
        layout.addWidget(self.cookie_path_label)

        self.method_combo.currentIndexChanged.connect(self._on_method_changed)

        layout.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        self.close_btn = QPushButton("Kapat")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.clicked.connect(lambda: self._choose("close"))

        self.edit_btn = QPushButton("Bağlantıyı Düzenle")
        self.edit_btn.setObjectName("editUrlButton")
        self.edit_btn.clicked.connect(lambda: self._choose("edit_url"))

        self.retry_btn = QPushButton("Oturumla İncele")
        self.retry_btn.setObjectName(
            "threadsSessionRetryButton"
            if "threads" in platform_name.lower()
            else "dialogSessionRetryButton"
        )
        self.retry_btn.clicked.connect(lambda: self._choose("session_retry"))

        apply_pointing_hand_cursor(self.close_btn)
        apply_pointing_hand_cursor(self.edit_btn)
        apply_pointing_hand_cursor(self.retry_btn)

        btn_row.addWidget(self.close_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.retry_btn)

        layout.addLayout(btn_row)

    def _on_method_changed(self, idx: int) -> None:
        data = self.method_combo.itemData(idx)
        if data == "cookie_file":
            from PySide6.QtWidgets import QFileDialog

            from src.browser_sessions import validate_cookie_file

            path, _ = QFileDialog.getOpenFileName(
                self,
                "Çerez Dosyası Seç (Netscape formatı)",
                "",
                "Metin Dosyaları (*.txt);;Tüm Dosyalar (*.*)",
            )
            if path:
                is_valid, err_msg = validate_cookie_file(path)
                if not is_valid:
                    self.cookie_path_label.setText(f"❌ {err_msg}")
                    self.cookie_path_label.setStyleSheet(
                        "color: #dc2626; font-size: 12px;"
                    )
                    self.cookie_path_label.setVisible(True)
                    self.selected_cookie_file = None
                else:
                    self.selected_cookie_file = path
                    self.cookie_path_label.setText(
                        f"✓ Seçilen dosya: {Path(path).name}"
                    )
                    self.cookie_path_label.setStyleSheet(
                        "color: #16a34a; font-size: 12px;"
                    )
                    self.cookie_path_label.setVisible(True)
            else:
                if not self.selected_cookie_file:
                    self.method_combo.setCurrentIndex(0)
        else:
            self.selected_cookie_file = None
            self.cookie_path_label.setVisible(False)

    def _choose(self, choice: str) -> None:
        self.clicked_button_id = choice
        self.selected_method = self.method_combo.currentData() or "auto"
        if (
            choice == "session_retry"
            and self.selected_method == "cookie_file"
            and not self.selected_cookie_file
        ):
            from PySide6.QtWidgets import QFileDialog

            from src.browser_sessions import validate_cookie_file

            path, _ = QFileDialog.getOpenFileName(
                self,
                "Çerez Dosyası Seç (Netscape formatı)",
                "",
                "Metin Dosyaları (*.txt);;Tüm Dosyalar (*.*)",
            )
            if path:
                is_valid, err_msg = validate_cookie_file(path)
                if is_valid:
                    self.selected_cookie_file = path
                else:
                    self.cookie_path_label.setText(f"❌ {err_msg}")
                    self.cookie_path_label.setVisible(True)
                    return
            else:
                return
        self.accept()


class AdvancedSessionDialog(QDialog):
    """Gelişmiş oturum tercihlerini ve format tercihlerini ayarlamak için diyalog penceresi."""

    def __init__(
        self,
        current_mode: str = "auto",
        convert_hevc: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("advancedSessionDialog")
        self.setWindowTitle("Gelişmiş Ayarlar")
        self.setMinimumWidth(400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Gelişmiş Oturum ve Format Ayarları")
        title.setObjectName("dialogTitleLabel")

        desc = QLabel(
            "Özel bir tarayıcı oturumu seçin veya otomatik oturum yönetimini kullanın:"
        )
        desc.setObjectName("dialogMessageLabel")
        desc.setWordWrap(True)

        from PySide6.QtWidgets import QComboBox

        from src.utils import configure_combo_box

        self.combo = QComboBox()
        self.combo.addItem("Otomatik (Önerilen)", "auto")
        self.combo.addItem("Oturumsuz", "none")
        self.combo.addItem("Firefox", "firefox")
        self.combo.addItem("Microsoft Edge", "edge")
        self.combo.addItem("Chrome", "chrome")
        self.combo.addItem("Brave", "brave")
        self.combo.addItem("Çerez dosyası seç...", "cookie_file")
        configure_combo_box(self.combo)

        # Set current selection
        found_idx = 0
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == current_mode:
                found_idx = i
                break
        self.combo.setCurrentIndex(found_idx)

        self.convert_hevc_check = QCheckBox("Windows uyumlu MP4 oluştur")
        self.convert_hevc_check.setChecked(convert_hevc)
        self.convert_hevc_check.setStyleSheet(
            "color: #172033; font-size: 13px; font-weight: 600;"
        )

        hevc_desc = QLabel(
            "HEVC/H.265 videoları gerekirse H.264'e dönüştürür. Dönüştürme işlemi ek süre alabilir."
        )
        hevc_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        hevc_desc.setWordWrap(True)

        self.cookie_path_label = QLabel("")
        self.cookie_path_label.setStyleSheet("color: #0284c7; font-size: 12px;")
        self.cookie_path_label.setWordWrap(True)
        self.cookie_path_label.setVisible(False)

        self.cookie_info_label = QLabel(
            "Çerez dosyası, hesap erişim bilgilerini içerir. Lütfen yalnızca güvendiğiniz uygulamalarla paylaşın."
        )
        self.cookie_info_label.setStyleSheet("color: #64748b; font-size: 11px;")
        self.cookie_info_label.setWordWrap(True)
        self.cookie_info_label.setVisible(False)

        self.selected_cookie_file = None
        self.combo.currentIndexChanged.connect(self._on_combo_changed)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        save_btn = QPushButton("Kaydet")
        save_btn.setObjectName("dialogPrimaryButton")
        save_btn.clicked.connect(self._on_save_clicked)

        cancel_btn = QPushButton("İptal")
        cancel_btn.setObjectName("dialogSecondaryButton")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(self.combo)
        layout.addWidget(self.cookie_path_label)
        layout.addWidget(self.cookie_info_label)
        layout.addSpacing(6)
        layout.addWidget(self.convert_hevc_check)
        layout.addWidget(hevc_desc)
        layout.addSpacing(8)
        layout.addLayout(btn_row)

    def _on_combo_changed(self, idx: int) -> None:
        data = self.combo.itemData(idx)
        if data == "cookie_file":
            from PySide6.QtWidgets import QFileDialog

            from src.browser_sessions import validate_cookie_file

            path, _ = QFileDialog.getOpenFileName(
                self,
                "Çerez Dosyası Seç (Netscape formatı)",
                "",
                "Metin Dosyaları (*.txt);;Tüm Dosyalar (*.*)",
            )
            if path:
                is_valid, err_msg = validate_cookie_file(path)
                if not is_valid:
                    self.cookie_path_label.setText(f"❌ {err_msg}")
                    self.cookie_path_label.setStyleSheet(
                        "color: #dc2626; font-size: 12px;"
                    )
                    self.cookie_path_label.setVisible(True)
                    self.cookie_info_label.setVisible(False)
                    self.selected_cookie_file = None
                else:
                    self.selected_cookie_file = path
                    self.cookie_path_label.setText(
                        f"✓ Seçilen dosya: {Path(path).name}"
                    )
                    self.cookie_path_label.setStyleSheet(
                        "color: #16a34a; font-size: 12px;"
                    )
                    self.cookie_path_label.setVisible(True)
                    self.cookie_info_label.setVisible(True)
            else:
                if not self.selected_cookie_file:
                    self.combo.blockSignals(True)
                    self.combo.setCurrentIndex(0)
                    self.combo.blockSignals(False)
        else:
            self.selected_cookie_file = None
            self.cookie_path_label.setVisible(False)
            self.cookie_info_label.setVisible(False)

    def _on_save_clicked(self) -> None:
        if self.combo.currentData() == "cookie_file" and not self.selected_cookie_file:
            from PySide6.QtWidgets import QFileDialog

            from src.browser_sessions import validate_cookie_file

            path, _ = QFileDialog.getOpenFileName(
                self,
                "Çerez Dosyası Seç (Netscape formatı)",
                "",
                "Metin Dosyaları (*.txt);;Tüm Dosyalar (*.*)",
            )
            if path:
                is_valid, err_msg = validate_cookie_file(path)
                if is_valid:
                    self.selected_cookie_file = path
                else:
                    self.cookie_path_label.setText(f"❌ {err_msg}")
                    self.cookie_path_label.setStyleSheet(
                        "color: #dc2626; font-size: 12px;"
                    )
                    self.cookie_path_label.setVisible(True)
                    self.cookie_info_label.setVisible(False)
                    return
            else:
                return
        self.accept()

    def selected_mode(self) -> str | None:
        return self.combo.currentData()

    def get_cookie_file_path(self) -> str | None:
        return self.selected_cookie_file

    def is_convert_hevc_enabled(self) -> bool:
        return self.convert_hevc_check.isChecked()


class AlreadyDownloadedDialog(QDialog):
    """Aynı içerik önceden indirildiğinde gösterilen açık temalı diyalog."""

    def __init__(
        self,
        filename: str = "",
        filepath: str = "",
        filesize_text: str = "",
        resolution_or_format: str = "",
        completed_at: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("alreadyDownloadedDialog")
        self.setWindowTitle("Bu içerik daha önce indirilmiş")
        self.setMinimumWidth(440)
        self.setMaximumWidth(620)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.clicked_button_id: str = "cancel"
        self.filepath = filepath

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Bu içerik daha önce indirilmiş")
        title.setObjectName("dialogTitleLabel")

        info_parts = [
            f"• Dosya Adı: {filename}",
            f"• Dosya Yolu: {filepath}",
        ]
        if filesize_text:
            info_parts.append(f"• Boyut: {filesize_text}")
        if resolution_or_format:
            info_parts.append(f"• Biçim/Kalite: {resolution_or_format}")
        if completed_at:
            info_parts.append(f"• İndirilme Tarihi: {completed_at}")

        info_text = "\n".join(info_parts) + "\n\nNe yapmak istersiniz?"
        message = QLabel(info_text)
        message.setObjectName("dialogMessageLabel")
        message.setWordWrap(True)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        open_file_btn = QPushButton("Dosyayı Aç")
        open_file_btn.setObjectName("dialogSecondaryButton")
        open_file_btn.clicked.connect(lambda: self._choose("open_file"))

        open_folder_btn = QPushButton("Klasörü Aç")
        open_folder_btn.setObjectName("dialogSecondaryButton")
        open_folder_btn.clicked.connect(lambda: self._choose("open_folder"))

        row1.addWidget(open_file_btn)
        row1.addWidget(open_folder_btn)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        redownload_btn = QPushButton("Yeniden İndir")
        redownload_btn.setObjectName("dialogPrimaryButton")
        redownload_btn.clicked.connect(lambda: self._choose("redownload"))

        save_as_btn = QPushButton("Farklı Adla İndir")
        save_as_btn.setObjectName("dialogSecondaryButton")
        save_as_btn.clicked.connect(lambda: self._choose("save_as"))

        cancel_btn = QPushButton("Vazgeç")
        cancel_btn.setObjectName("dialogSecondaryButton")
        cancel_btn.clicked.connect(lambda: self._choose("cancel"))

        row2.addWidget(redownload_btn)
        row2.addWidget(save_as_btn)
        row2.addWidget(cancel_btn)

        from src.utils import apply_pointing_hand_cursor

        for btn in (
            open_file_btn,
            open_folder_btn,
            redownload_btn,
            save_as_btn,
            cancel_btn,
        ):
            apply_pointing_hand_cursor(btn)

        btn_layout.addLayout(row1)
        btn_layout.addLayout(row2)

        layout.addWidget(title)
        layout.addWidget(message)
        layout.addSpacing(6)
        layout.addLayout(btn_layout)

    def _choose(self, button_id: str) -> None:
        self.clicked_button_id = button_id
        if button_id == "cancel":
            self.reject()
        else:
            self.accept()


class LeftoverJobsDialog(QDialog):
    """Uygulama çökmesi/zorla kapatılmasından kalan yarım dosyalar için diyalog."""

    def __init__(
        self,
        count: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("leftoverJobsDialog")
        self.setWindowTitle("Önceki yarım indirmeler bulundu")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.clicked_button_id: str = "keep"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Önceki yarım indirmeler bulundu")
        title.setObjectName("dialogTitleLabel")

        message = QLabel(
            f"Daha önceki bir oturumdan kalan {count} adet tamamlanmamış geçici indirme dosyası tespit edildi.\n\n"
            "Bu dosyaları temizlemek ister misiniz?"
        )
        message.setObjectName("dialogMessageLabel")
        message.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        clean_btn = QPushButton("Temizle")
        clean_btn.setObjectName("dialogPrimaryButton")
        clean_btn.clicked.connect(lambda: self._choose("clean"))

        folder_btn = QPushButton("Klasörü Aç")
        folder_btn.setObjectName("dialogSecondaryButton")
        folder_btn.clicked.connect(lambda: self._choose("open_folder"))

        keep_btn = QPushButton("Şimdilik Sakla")
        keep_btn.setObjectName("dialogSecondaryButton")
        keep_btn.clicked.connect(lambda: self._choose("keep"))

        from src.utils import apply_pointing_hand_cursor

        for btn in (clean_btn, folder_btn, keep_btn):
            apply_pointing_hand_cursor(btn)

        btn_row.addWidget(clean_btn)
        btn_row.addWidget(folder_btn)
        btn_row.addWidget(keep_btn)

        layout.addWidget(title)
        layout.addWidget(message)
        layout.addSpacing(6)
        layout.addLayout(btn_row)

    def _choose(self, button_id: str) -> None:
        self.clicked_button_id = button_id
        if button_id == "keep":
            self.reject()
        else:
            self.accept()
