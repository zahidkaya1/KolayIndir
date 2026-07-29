"""Kolayİndir özel açık temalı diyalog pencere bileşenleri."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

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
        if has_encryption_err and is_instagram:
            main_text = (
                "Edge veya Chrome oturumu bulundu ancak Windows çerez koruması nedeniyle okunamadı. "
                "Instagram hikâyeleri için Firefox kullanılması önerilir."
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
                main_text = (
                    "Bu içerik için Instagram oturumu gerekiyor ancak kullanılabilir bir oturum bulunamadı."
                )
            else:
                main_text = (
                    "Instagram hesabının açık olduğu bir tarayıcı oturumu bulunamadı. "
                    "Tarayıcıda Instagram'a giriş yapıp tarayıcıyı tamamen kapatarak yeniden deneyin."
                )
        elif is_twitter:
            main_text = "İçeriği görebildiğiniz hesabın açık olduğu tarayıcıyı kapatıp yeniden deneyin."
        elif is_youtube:
            main_text = "Video yaş kısıtlamalı veya oturum doğrulaması gerektiriyor olabilir."
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


class AdvancedSessionDialog(QDialog):
    """Gelişmiş oturum tercihlerini ayarlamak için küçük diyalog penceresi."""

    def __init__(
        self,
        current_mode: str = "auto",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("advancedSessionDialog")
        self.setWindowTitle("Gelişmiş Oturum Ayarları")
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Gelişmiş Oturum Ayarları")
        title.setObjectName("dialogTitleLabel")

        desc = QLabel("Özel bir tarayıcı oturumu seçin veya otomatik oturum yönetimini kullanın:")
        desc.setObjectName("dialogMessageLabel")
        desc.setWordWrap(True)

        from PySide6.QtWidgets import QComboBox

        from src.utils import configure_combo_box

        self.combo = QComboBox()
        self.combo.addItem("Otomatik oturum (Önerilen)", "auto")
        self.combo.addItem("Oturum kullanma", None)
        self.combo.addItem("Firefox oturumu", "firefox")
        self.combo.addItem("Edge oturumu", "edge")
        self.combo.addItem("Chrome oturumu", "chrome")
        self.combo.addItem("Brave oturumu", "brave")
        configure_combo_box(self.combo)

        # Set current selection
        found_idx = 0
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == current_mode:
                found_idx = i
                break
        self.combo.setCurrentIndex(found_idx)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        save_btn = QPushButton("Kaydet")
        save_btn.setObjectName("dialogPrimaryButton")
        save_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("İptal")
        cancel_btn.setObjectName("dialogSecondaryButton")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(self.combo)
        layout.addSpacing(6)
        layout.addLayout(btn_row)

    def selected_mode(self) -> str | None:
        return self.combo.currentData()


