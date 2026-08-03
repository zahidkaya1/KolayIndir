"""İndirme kuyruğu için kullanıcı arayüzü ve diyalog sınıfları."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config import APP_NAME
from src.dialogs import AppMessageDialog
from src.models import QueueItem
from src.utils import apply_pointing_hand_cursor, extract_supported_urls_from_text


def format_folder_display(path: Path | str | None) -> str:
    """Klasör yolunu tablo için kısaltılmış biçimde gösterir."""
    if not path:
        return "İndirilenler"
    p = Path(path)
    parts = p.parts
    if len(parts) > 2:
        return f".../{parts[-2]}/{parts[-1]}"
    return p.name or str(p)


class QueueItemEditDialog(QDialog):
    """Kuyruk öğesinin ayarlarını düzenleme penceresi."""

    def __init__(self, item: QueueItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueEditDialog")
        self.setWindowTitle("Kuyruk Öğesini Düzenle")
        self.setMinimumWidth(500)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.item = item

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # URL Bilgisi
        title_text = item.title if item.title and item.title != "Video" else item.url
        info_label = QLabel(f"<b>Bağlantı:</b> {title_text}")
        info_label.setWordWrap(True)
        info_label.setToolTip(item.url)
        layout.addWidget(info_label)

        # Tür & Kalite
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        media_label = QLabel("Dosya Türü:")
        self.media_combo = QComboBox()
        self.media_combo.addItems(["Video (MP4)", "Ses (MP3)"])
        idx = self.media_combo.findText(item.media_type)
        if idx >= 0:
            self.media_combo.setCurrentIndex(idx)
        self.media_combo.currentTextChanged.connect(self._on_media_type_changed)

        quality_label = QLabel("Kalite:")
        self.quality_combo = QComboBox()
        self._update_quality_options(self.media_combo.currentText())
        q_idx = self.quality_combo.findText(item.quality)
        if q_idx >= 0:
            self.quality_combo.setCurrentIndex(q_idx)

        row1.addWidget(media_label)
        row1.addWidget(self.media_combo)
        row1.addWidget(quality_label)
        row1.addWidget(self.quality_combo, 1)
        layout.addLayout(row1)

        # İndirme Klasörü
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        folder_label = QLabel("Klasör:")
        self.folder_input = QLineEdit()
        self.folder_input.setText(str(item.output_dir) if item.output_dir else str(Path.home() / "Downloads"))

        self.browse_btn = QPushButton("Klasör Seç")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.clicked.connect(self._browse_folder)
        apply_pointing_hand_cursor(self.browse_btn)

        row2.addWidget(folder_label)
        row2.addWidget(self.folder_input, 1)
        row2.addWidget(self.browse_btn)
        layout.addLayout(row2)

        # Playlist Checkbox
        self.playlist_checkbox = QCheckBox("Oynatma listesinin tamamını indir")
        self.playlist_checkbox.setChecked(item.playlist)
        layout.addWidget(self.playlist_checkbox)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        apply_pointing_hand_cursor(self.save_btn)

        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        apply_pointing_hand_cursor(self.cancel_btn)

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _on_media_type_changed(self, media_text: str) -> None:
        self._update_quality_options(media_text)

    def _update_quality_options(self, media_text: str) -> None:
        current = self.quality_combo.currentText()
        self.quality_combo.clear()
        if "Ses" in media_text or "MP3" in media_text:
            self.quality_combo.addItems([
                "320 kbps (En iyi)",
                "256 kbps",
                "192 kbps",
                "128 kbps",
            ])
        else:
            self.quality_combo.addItems([
                "En iyi kullanılabilir kalite",
                "1080p'ye kadar",
                "720p'ye kadar",
                "480p'ye kadar",
                "360p'ye kadar",
            ])
        idx = self.quality_combo.findText(current)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)

    def _browse_folder(self) -> None:
        current = self.folder_input.text().strip() or str(Path.home() / "Downloads")
        res = QFileDialog.getExistingDirectory(self, "İndirme Klasörü Seç", current)
        if res:
            self.folder_input.setText(res)

    def _save(self) -> None:
        folder_text = self.folder_input.text().strip()
        if not folder_text:
            return
        self.item.media_type = self.media_combo.currentText()
        self.item.quality = self.quality_combo.currentText()
        self.item.output_dir = Path(folder_text)
        self.item.playlist = self.playlist_checkbox.isChecked()
        self.accept()


class DownloadQueueDialog(QDialog):
    """Çoklu indirme kuyruğunu görüntüleyen ve yöneten diyalog penceresi."""

    # Sinyaller (MainWindow koordinasyonu için)
    urls_added = Signal(list, str, str, bool, Path)  # urls, media_type, quality, playlist, output_dir
    current_url_added = Signal(str, str, bool, Path)  # media_type, quality, playlist, output_dir
    start_queue_requested = Signal()
    stop_queue_requested = Signal()
    delete_selected_requested = Signal(str)
    clear_completed_requested = Signal()
    retry_failed_requested = Signal()
    item_edited = Signal(str)  # item_id

    def __init__(self, default_folder: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("downloadQueueDialog")
        self.setWindowTitle(f"{APP_NAME} — İndirme Kuyruğu")
        self.setMinimumSize(940, 640)

        # Standart Windows başlık çubuğu ve sağ üst X kapatma düğmesi
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._queue_items_ref: list[QueueItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Kuyruk Ayarları Bölümü (Kompakt Card)
        settings_frame = QFrame()
        settings_frame.setObjectName("queueSettingsCard")
        settings_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(12, 10, 12, 10)
        settings_layout.setSpacing(8)

        settings_title = QLabel("<b>Kuyruk Ayarları (Yeni Eklenen Bağlantılar İçin)</b>")
        settings_title.setStyleSheet("color: #334155; font-size: 13px;")
        settings_layout.addWidget(settings_title)

        row1 = QHBoxLayout()
        row1.setSpacing(12)

        media_label = QLabel("Tür:")
        self.media_combo = QComboBox()
        self.media_combo.addItems(["Video (MP4)", "Ses (MP3)"])
        self.media_combo.currentTextChanged.connect(self._on_media_type_changed)

        quality_label = QLabel("Kalite:")
        self.quality_combo = QComboBox()
        self._update_quality_options(self.media_combo.currentText())

        self.playlist_checkbox = QCheckBox("Oynatma listesinin tamamını indir")

        row1.addWidget(media_label)
        row1.addWidget(self.media_combo)
        row1.addWidget(quality_label)
        row1.addWidget(self.quality_combo, 1)
        row1.addWidget(self.playlist_checkbox)
        settings_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        folder_label = QLabel("Klasör:")
        self.folder_input = QLineEdit()
        initial_dir = str(default_folder) if default_folder else str(Path.home() / "Downloads")
        self.folder_input.setText(initial_dir)

        self.browse_btn = QPushButton("Klasör Seç")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.clicked.connect(self._browse_folder)
        apply_pointing_hand_cursor(self.browse_btn)

        row2.addWidget(folder_label)
        row2.addWidget(self.folder_input, 1)
        row2.addWidget(self.browse_btn)
        settings_layout.addLayout(row2)

        layout.addWidget(settings_frame)

        # Üst bölüm: Bağlantı ekleme alanı
        input_layout = QVBoxLayout()
        input_layout.setSpacing(8)

        self.urls_input = QTextEdit()
        self.urls_input.setObjectName("queueInput")
        self.urls_input.setPlaceholderText(
            "İndirilecek bağlantıları buraya yapıştırın (Her satıra bir bağlantı veya metin içinde karışık bağlantılar)."
        )
        self.urls_input.setMaximumHeight(70)
        self.urls_input.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        input_layout.addWidget(self.urls_input)

        add_buttons_layout = QHBoxLayout()
        add_buttons_layout.setSpacing(10)

        self.add_urls_btn = QPushButton("Bağlantıları Ekle")
        self.add_urls_btn.setObjectName("primaryButton")
        self.add_urls_btn.clicked.connect(self._on_add_urls_clicked)
        apply_pointing_hand_cursor(self.add_urls_btn)

        self.add_current_btn = QPushButton("Mevcut Bağlantıyı Ekle")
        self.add_current_btn.setObjectName("secondaryButton")
        self.add_current_btn.clicked.connect(self._on_add_current_clicked)
        apply_pointing_hand_cursor(self.add_current_btn)

        add_buttons_layout.addWidget(self.add_urls_btn)
        add_buttons_layout.addWidget(self.add_current_btn)
        add_buttons_layout.addStretch(1)

        input_layout.addLayout(add_buttons_layout)
        layout.addLayout(input_layout)

        # Orta bölüm: Kontrol butonları
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)

        self.start_btn = QPushButton("Kuyruğu Başlat")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self.start_queue_requested.emit)
        apply_pointing_hand_cursor(self.start_btn)

        self.stop_btn = QPushButton("Kuyruğu Durdur")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self.stop_queue_requested.emit)
        apply_pointing_hand_cursor(self.stop_btn)

        self.edit_btn = QPushButton("Seçileni Düzenle")
        self.edit_btn.setObjectName("secondaryButton")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        apply_pointing_hand_cursor(self.edit_btn)

        self.delete_btn = QPushButton("Seçileni Sil")
        self.delete_btn.setObjectName("secondaryButton")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        apply_pointing_hand_cursor(self.delete_btn)

        self.clear_completed_btn = QPushButton("Tamamlananları Temizle")
        self.clear_completed_btn.setObjectName("secondaryButton")
        self.clear_completed_btn.clicked.connect(self.clear_completed_requested.emit)
        apply_pointing_hand_cursor(self.clear_completed_btn)

        self.retry_failed_btn = QPushButton("Başarısızları Yeniden Dene")
        self.retry_failed_btn.setObjectName("secondaryButton")
        self.retry_failed_btn.clicked.connect(self.retry_failed_requested.emit)
        apply_pointing_hand_cursor(self.retry_failed_btn)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.edit_btn)
        control_layout.addWidget(self.delete_btn)
        control_layout.addWidget(self.clear_completed_btn)
        control_layout.addWidget(self.retry_failed_btn)
        control_layout.addStretch(1)

        layout.addLayout(control_layout)

        # Tablo (7 Sütun)
        self.table = QTableWidget()
        self.table.setObjectName("queueTable")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Başlık / URL",
            "Platform",
            "Tür",
            "Kalite",
            "Klasör",
            "Durum",
            "İlerleme",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 140)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 130)
        self.table.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        v_header = self.table.verticalHeader()
        v_header.setObjectName("queueVerticalHeader")
        v_header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v_header.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout.addWidget(self.table)

        # Alt bölüm: Durum özeti
        self.summary_label = QLabel("0 bekliyor • 0 indiriliyor • 0 tamamlandı • 0 başarısız")
        self.summary_label.setObjectName("queueSummary")
        layout.addWidget(self.summary_label)

    def _on_media_type_changed(self, media_text: str) -> None:
        self._update_quality_options(media_text)

    def _update_quality_options(self, media_text: str) -> None:
        current = self.quality_combo.currentText()
        self.quality_combo.clear()
        if "Ses" in media_text or "MP3" in media_text:
            self.quality_combo.addItems([
                "320 kbps (En iyi)",
                "256 kbps",
                "192 kbps",
                "128 kbps",
            ])
        else:
            self.quality_combo.addItems([
                "En iyi kullanılabilir kalite",
                "1080p'ye kadar",
                "720p'ye kadar",
                "480p'ye kadar",
                "360p'ye kadar",
            ])
        idx = self.quality_combo.findText(current)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)

    def _browse_folder(self) -> None:
        current = self.folder_input.text().strip() or str(Path.home() / "Downloads")
        res = QFileDialog.getExistingDirectory(self, "İndirme Klasörü Seç", current)
        if res:
            self.folder_input.setText(res)

    def get_current_settings(self) -> tuple[str, str, bool, Path]:
        """Diyalogdaki güncel varsayılan ayarları döndürür."""
        media_type = self.media_combo.currentText()
        quality = self.quality_combo.currentText()
        playlist = self.playlist_checkbox.isChecked()
        folder_text = self.folder_input.text().strip()
        output_dir = Path(folder_text) if folder_text else Path.home() / "Downloads"
        return media_type, quality, playlist, output_dir

    def _on_add_urls_clicked(self) -> None:
        text = self.urls_input.toPlainText()
        if not text.strip():
            return

        urls = extract_supported_urls_from_text(text)
        media_type, quality, playlist, output_dir = self.get_current_settings()
        self.urls_added.emit(urls, media_type, quality, playlist, output_dir)
        self.urls_input.clear()

    def _on_add_current_clicked(self) -> None:
        media_type, quality, playlist, output_dir = self.get_current_settings()
        self.current_url_added.emit(media_type, quality, playlist, output_dir)

    def _on_delete_clicked(self) -> None:
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        row = selected_items[0].row()
        item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if item_id:
            self.delete_selected_requested.emit(item_id)

    def _on_edit_clicked(self) -> None:
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        row = selected_items[0].row()
        item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not item_id:
            return

        target_item = next((x for x in self._queue_items_ref if x.id == item_id), None)
        if not target_item:
            return

        if target_item.status in ("Analiz ediliyor", "İndiriliyor", "Tamamlandı"):
            AppMessageDialog(
                "Düzenleme Engellendi",
                "Aktif veya tamamlanmış kuyruk öğesinin ayarları değiştirilemez.",
                "warning",
                self,
            ).exec()
            return

        dlg = QueueItemEditDialog(target_item, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.item_edited.emit(target_item.id)
            self.refresh_table(self._queue_items_ref)

    def refresh_table(self, queue_items: list[QueueItem]) -> None:
        self._queue_items_ref = queue_items
        self.table.setRowCount(0)
        for i, item in enumerate(queue_items):
            self.table.insertRow(i)

            title_text = item.title if item.title and item.title != "Video" else item.url
            title_widget = QTableWidgetItem(title_text)
            title_widget.setData(Qt.ItemDataRole.UserRole, item.id)
            title_widget.setToolTip(item.url)
            self.table.setItem(i, 0, title_widget)

            self.table.setItem(i, 1, QTableWidgetItem(item.platform))
            self.table.setItem(i, 2, QTableWidgetItem(item.media_type))
            self.table.setItem(i, 3, QTableWidgetItem(item.quality))

            folder_widget = QTableWidgetItem(format_folder_display(item.output_dir))
            folder_widget.setToolTip(str(item.output_dir) if item.output_dir else "")
            self.table.setItem(i, 4, folder_widget)

            status_text = item.status
            if item.error_msg:
                status_text += f" ({item.error_msg})"
            status_widget = QTableWidgetItem(status_text)
            if item.error_msg:
                status_widget.setToolTip(item.error_msg)

            if item.status == "Tamamlandı":
                status_widget.setForeground(Qt.GlobalColor.darkGreen)
            elif item.status == "Başarısız":
                status_widget.setForeground(Qt.GlobalColor.red)
            elif item.status in ("Analiz ediliyor", "İndiriliyor"):
                status_widget.setForeground(Qt.GlobalColor.blue)

            self.table.setItem(i, 5, status_widget)

            if item.status == "İndiriliyor":
                progress = QProgressBar()
                progress.setRange(0, 100)
                progress.setValue(item.progress_percent)
                progress.setFormat(f"%p% - {item.progress_text}" if item.progress_text else "%p%")
                self.table.setCellWidget(i, 6, progress)
            else:
                self.table.setItem(i, 6, QTableWidgetItem(item.progress_text))

        self._update_summary(queue_items)

    def update_item_progress(self, item_id: str, percent: int | None = None, text: str | None = None) -> None:
        """Kuyruk listesini tamamen baştan oluşturmadan tek bir öğenin ilerleme hücresini günceller."""
        for row in range(self.table.rowCount()):
            item_widget = self.table.item(row, 0)
            if item_widget and item_widget.data(Qt.ItemDataRole.UserRole) == item_id:
                cell_widget = self.table.cellWidget(row, 6)
                if isinstance(cell_widget, QProgressBar):
                    if percent is not None:
                        cell_widget.setValue(percent)
                    if text is not None:
                        cell_widget.setFormat(f"%p% - {text}")
                break

    def _update_summary(self, items: list[QueueItem]) -> None:
        waiting = sum(1 for x in items if x.status == "Bekliyor")
        downloading = sum(1 for x in items if x.status in ("Analiz ediliyor", "İndiriliyor"))
        completed = sum(1 for x in items if x.status == "Tamamlandı")
        failed = sum(1 for x in items if x.status == "Başarısız")

        self.summary_label.setText(
            f"{waiting} bekliyor • {downloading} indiriliyor • {completed} tamamlandı • {failed} başarısız"
        )
