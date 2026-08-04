"""İndirme geçmişi ekranını sağlayan arayüz."""

import unicodedata
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.history import (
    DownloadRecord,
    clear_history,
    load_history,
    validate_all_completed_records,
)
from src.models import format_bytes
from src.utils import apply_pointing_hand_cursor


def _normalize_search_text(text: str | None) -> str:
    value = unicodedata.normalize("NFKC", str(text or "").strip())
    value = value.translate(str.maketrans({"I": "ı", "İ": "i"}))
    return unicodedata.normalize("NFKC", value).casefold()


def _record_path_status(record):
    path_text = str(record.final_path or "").strip()
    if not path_text:
        return False, True

    path = Path(path_text)
    exists = path.exists()
    missing = record.state == "stale" or not exists
    return exists, missing


def _parse_completed_at(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _canonical_platform(platform: str | None) -> str:
    value = str(platform or "").strip().lower()
    
    if not value:
        return "unknown"
        
    if "youtube" in value or "youtu_be" in value:
        return "youtube"
    
    if "instagram" in value:
        return "instagram"
        
    if "facebook" in value or "fb" in value:
        return "facebook"

    if "threads" in value:
        return "threads"

    if "twitter" in value or value == "x" or "x_com" in value or "x / twitter" in value:
        return "x_twitter"
        
    if "tiktok" in value:
        return "tiktok"
        
    if "kick" in value:
        return "kick"
        
    return value

def _get_platform_display_name(platform: str | None) -> str:
    canon = _canonical_platform(platform)
    
    if canon == "youtube": return "YouTube"
    if canon == "facebook": return "Facebook"
    if canon == "instagram": return "Instagram"
    if canon == "threads": return "Threads"
    if canon == "x_twitter": return "X / Twitter"
    if canon == "tiktok": return "TikTok"
    if canon == "kick": return "Kick"
    if canon == "unknown": return "Bilinmiyor"
    
    value = str(platform or "").strip()
    return value.capitalize()

def _get_platform_badge_style(
    platform: str | None,
    media_type: str | None,
) -> str:
    media = str(media_type or "").lower()
    if "mp3" in media or "ses" in media:
        return "background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0;"
        
    canon = _canonical_platform(platform)
    if canon == "youtube":
        return "background-color: #fef2f2; color: #dc2626; border: 1px solid #fecaca;"
    if canon == "facebook":
        return "background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;"
    if canon == "instagram":
        return "background-color: #fdf4ff; color: #c026d3; border: 1px solid #f5d0fe;"
    if canon == "threads":
        return "background-color: #f5f5f5; color: #171717; border: 1px solid #d4d4d4;"
    if canon == "x_twitter":
        return "background-color: #f0f9ff; color: #0284c7; border: 1px solid #bae6fd;"
    if canon == "tiktok":
        return "background-color: #f0fdfa; color: #0d9488; border: 1px solid #ccfbf1;"
        
    return "background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;"


class HistoryCard(QFrame):
    """Geçmişteki tek bir indirmenin UI kartı."""

    def __init__(self, record: DownloadRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.record = record
        self.setObjectName("historyCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        def _apply_overflow_policy(label: QLabel) -> None:
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )

        # Üst Kısım: Başlık ve Durum
        top_row = QHBoxLayout()
        title_label = QLabel(self.record.display_description())
        title_label.setObjectName("historyTitle")
        _apply_overflow_policy(title_label)
        top_row.addWidget(title_label, 1)

        path_text = str(self.record.final_path or "").strip()
        target_path = Path(path_text) if path_text else None
        exists, is_missing = _record_path_status(self.record)

        if is_missing:
            status_label = QLabel("Dosya bulunamadı")
            status_label.setObjectName("historyStatusMissing")
            top_row.addWidget(status_label)
        elif (
            self.record.platform == "youtube_playlist"
            and self.record.playlist_index == 0
        ):
            status_label = QLabel("Playlist Özeti")
            status_label.setObjectName("historyStatusInfo")
            top_row.addWidget(status_label)
        else:
            status_label = QLabel("Mevcut")
            status_label.setObjectName("historyStatusOk")
            top_row.addWidget(status_label)

        layout.addLayout(top_row)

        # Alt Kısım: Detaylar
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)

        platform_text = _get_platform_display_name(self.record.platform)
        badge_style = _get_platform_badge_style(
            self.record.platform, self.record.media_type
        )

        platform_badge = QLabel(platform_text)
        platform_badge.setObjectName("platformBadge")
        platform_badge.setStyleSheet(
            badge_style
            + " border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;"
        )

        meta_row = QHBoxLayout()
        meta_row.addWidget(platform_badge)
        meta_row.addStretch(1)
        details_layout.addLayout(meta_row)

        details_1 = f"Tür: {self.record.media_type}"
        if self.record.requested_quality:
            details_1 += f" | Kalite: {self.record.requested_quality}"
        if self.record.selected_height:
            details_1 += f" ({self.record.selected_height}p)"

        details_2 = f"Dosya: {target_path.name if target_path else ''}"
        if self.record.file_size > 0:
            details_2 += f" | Boyut: {format_bytes(self.record.file_size)}"
        if self.record.completed_at:
            # Sadece tarih ve saat (kaba)
            d = self.record.completed_at.replace("T", " ")[:16]
            details_2 += f" | Tarih: {d}"

        l1 = QLabel(details_1)
        l1.setObjectName("historyDetail")
        _apply_overflow_policy(l1)
        details_layout.addWidget(l1)

        l2 = QLabel(details_2)
        l2.setObjectName("historyDetail")
        _apply_overflow_policy(l2)
        details_layout.addWidget(l2)

        layout.addLayout(details_layout)

        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.open_file_btn = QPushButton("Dosyayı Aç")
        self.open_file_btn.setObjectName("primaryButton")
        self.open_file_btn.setMinimumWidth(105)
        self.open_file_btn.setMaximumWidth(150)

        self.open_folder_btn = QPushButton("Klasörü Aç")
        self.open_folder_btn.setObjectName("secondaryButton")
        self.open_folder_btn.setMinimumWidth(105)
        self.open_folder_btn.setMaximumWidth(150)

        self.redownload_btn = QPushButton("Yeniden İndir")
        self.redownload_btn.setObjectName("accentButton")
        self.redownload_btn.setMinimumWidth(110)
        self.redownload_btn.setMaximumWidth(160)

        apply_pointing_hand_cursor(self.open_file_btn)
        apply_pointing_hand_cursor(self.open_folder_btn)
        apply_pointing_hand_cursor(self.redownload_btn)

        # Buton aktif/pasif durumları
        if (
            self.record.platform == "youtube_playlist"
            and self.record.playlist_index == 0
        ):
            # Playlist özet kaydı
            self.open_file_btn.setVisible(False)
            if not target_path or not exists or not target_path.is_dir():
                self.open_folder_btn.setEnabled(False)
        else:
            if not target_path or is_missing or not target_path.is_file():
                self.open_file_btn.setEnabled(False)

        parent_exists = target_path.parent.exists() if target_path and target_path.name else False
        if not target_path or (not exists and not parent_exists):
            self.open_folder_btn.setEnabled(False)

        if not self.record.source_url:
            self.redownload_btn.setEnabled(False)
            self.redownload_btn.setToolTip("Eski kayıt: Kaynak URL bulunamadı.")

        btn_row.addStretch(1)
        btn_row.addWidget(self.open_file_btn)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addWidget(self.redownload_btn)

        layout.addSpacing(4)
        layout.addLayout(btn_row)

        self.open_file_btn.clicked.connect(self._open_file)
        self.open_folder_btn.clicked.connect(self._open_folder)

    def _open_file(self) -> None:
        path_text = str(self.record.final_path or "").strip()
        if not path_text:
            return
        p = Path(path_text)
        if p.exists() and p.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _open_folder(self) -> None:
        path_text = str(self.record.final_path or "").strip()
        if not path_text:
            return
        p = Path(path_text)
        if p.exists():
            if p.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))
        elif p.parent.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))


class HistoryDialog(QDialog):
    """İndirme geçmişini listeleyen ana pencere."""

    redownload_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyDialog")
        self.setWindowTitle("İndirme Geçmişi")
        self.resize(900, 650)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self.setStyleSheet("""
            QDialog#historyDialog {
                background-color: #F7F9FC;
            }
            QScrollArea#historyScrollArea,
            QWidget#historyScrollViewport,
            QWidget#historyScrollContent {
                background-color: #F7F9FC;
                border: none;
            }
            QFrame#historyCard {
                background-color: #ffffff;
                border: 1px solid #dde4ee;
                border-radius: 12px;
            }
            QLabel {
                color: #172033;
            }
            QLabel#historyTitle {
                font-weight: bold;
                font-size: 15px;
                color: #1c2538;
            }
            QLabel#historyStatusMissing {
                color: #ef4444;
                font-weight: bold;
                font-size: 12px;
                background-color: #fef2f2;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #fecaca;
            }
            QLabel#historyStatusOk {
                color: #10b981;
                font-weight: bold;
                font-size: 12px;
                background-color: #ecfdf5;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #a7f3d0;
            }
            QLabel#historyStatusInfo {
                color: #8b5cf6;
                font-weight: bold;
                font-size: 12px;
                background-color: #f5f3ff;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #ddd6fe;
            }
            QLabel#historyDetail, QLabel#historyEmpty {
                color: #5f6b7a;
            }
            QLabel#historyDetail {
                font-size: 12px;
            }
            QLabel#historyEmpty {
                font-size: 14px;
            }
        """)

        self._all_records: list[DownloadRecord] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Üst Çubuk (Başlık, Badge, Arama, Yenile, Temizle)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        header_label = QLabel("İndirme Geçmişi")
        header_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #0f172a;"
        )

        self.badge_label = QLabel("0 kayıt")
        self.badge_label.setStyleSheet(
            "background-color: #e2e8f0; color: #475569; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: bold;"
        )

        top_bar.addWidget(header_label)
        top_bar.addWidget(self.badge_label)
        top_bar.addStretch(1)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Başlık, platform veya dosya adı ara...")
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self._apply_filters)

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.setProperty("historyToolbarButton", True)
        self.refresh_btn.setMinimumWidth(90)
        self.refresh_btn.setMaximumWidth(120)
        apply_pointing_hand_cursor(self.refresh_btn)
        self.refresh_btn.clicked.connect(self.load_and_display)

        self.clear_btn = QPushButton("Geçmişi Temizle")
        self.clear_btn.setObjectName("dangerButton")
        self.clear_btn.setProperty("historyToolbarButton", True)
        self.clear_btn.setMinimumWidth(135)
        self.clear_btn.setMaximumWidth(160)
        self.clear_btn.setToolTip(
            "Yalnızca geçmiş kayıtlarını temizler. İndirilen dosyalar silinmez."
        )
        apply_pointing_hand_cursor(self.clear_btn)
        self.clear_btn.clicked.connect(self._on_clear_history)

        top_bar.addWidget(self.search_input)
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.clear_btn)
        layout.addLayout(top_bar)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(
            ["Tüm Platformlar", "YouTube", "Facebook", "Instagram", "Threads", "X / Twitter", "TikTok"]
        )
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tüm Türler", "Video", "Ses"])
        self.status_combo = QComboBox()
        self.status_combo.addItems(
            ["Tüm Durumlar", "Dosya Mevcut", "Dosya Eksik", "Playlist"]
        )
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["En Yeni", "En Eski", "Başlık A-Z", "Başlık Z-A", "Platform A-Z"]
        )
        self.clear_filters_btn = QPushButton("Filtreleri Temizle")
        self.clear_filters_btn.setObjectName("secondaryButton")
        self.clear_filters_btn.setEnabled(False)
        apply_pointing_hand_cursor(self.clear_filters_btn)

        filter_bar.addWidget(self.platform_combo)
        filter_bar.addWidget(self.type_combo)
        filter_bar.addWidget(self.status_combo)
        filter_bar.addWidget(self.sort_combo)
        filter_bar.addStretch(1)
        filter_bar.addWidget(self.clear_filters_btn)
        layout.addLayout(filter_bar)

        self.platform_combo.currentIndexChanged.connect(self._apply_filters)
        self.type_combo.currentIndexChanged.connect(self._apply_filters)
        self.status_combo.currentIndexChanged.connect(self._apply_filters)
        self.sort_combo.currentIndexChanged.connect(self._apply_filters)
        self.clear_filters_btn.clicked.connect(self._clear_filters)

        # Liste Alanı
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("historyScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("historyScrollContent")
        self.scroll_area.viewport().setObjectName("historyScrollViewport")
        self.scroll_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.scroll_area.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 8, 0)
        self.scroll_layout.setSpacing(12)

        self.empty_label = QLabel("Henüz indirilen bir içerik bulunmuyor.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setObjectName("historyEmpty")
        self.scroll_layout.addWidget(self.empty_label)

        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)

        self.load_and_display()

    def load_and_display(self) -> None:
        # Doğrula ve yükle
        validate_all_completed_records()
        self._all_records = load_history()
        self._apply_filters()

    def _clear_filters(self) -> None:
        widgets = [
            self.search_input,
            self.platform_combo,
            self.type_combo,
            self.status_combo,
            self.sort_combo,
        ]

        for w in widgets:
            w.blockSignals(True)

        try:
            self.search_input.clear()
            self.platform_combo.setCurrentIndex(0)
            self.type_combo.setCurrentIndex(0)
            self.status_combo.setCurrentIndex(0)
            self.sort_combo.setCurrentIndex(0)
        finally:
            for w in widgets:
                w.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self, *args) -> None:
        query = _normalize_search_text(self.search_input.text())
        p_filter = self.platform_combo.currentText()
        t_filter = self.type_combo.currentText()
        s_filter = self.status_combo.currentText()
        sort_f = self.sort_combo.currentText()

        is_default = (
            not query
            and p_filter == "Tüm Platformlar"
            and t_filter == "Tüm Türler"
            and s_filter == "Tüm Durumlar"
            and sort_f == "En Yeni"
        )
        self.clear_filters_btn.setEnabled(not is_default)

        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), HistoryCard):
                self.scroll_layout.takeAt(i)
                item.widget().deleteLater()

        filtered_records = []
        for rec in self._all_records:
            match_search = False
            if not query:
                match_search = True
            else:
                s_title = _normalize_search_text(rec.title)
                s_platform = _normalize_search_text(
                    _get_platform_display_name(rec.platform)
                )
                s_filename = _normalize_search_text(Path(rec.final_path).name)
                s_pl_title = _normalize_search_text(rec.playlist_title)
                s_url = _normalize_search_text(rec.source_url)
                s_path = _normalize_search_text(rec.final_path)

                if (
                    query in s_title
                    or query in s_platform
                    or query in s_filename
                    or query in s_pl_title
                    or query in s_url
                    or query in s_path
                ):
                    match_search = True

            if not match_search:
                continue

            if p_filter != "Tüm Platformlar":
                canon = _canonical_platform(rec.platform)
                canon_filter = _canonical_platform(p_filter)
                if canon_filter != "unknown" and canon != canon_filter:
                    continue

            if t_filter != "Tüm Türler":
                m_type = str(rec.media_type or "").lower()
                f_path = str(rec.final_path or "").lower()
                is_audio = (
                    "ses" in m_type
                    or "mp3" in m_type
                    or "m4a" in m_type
                    or "audio" in m_type
                    or f_path.endswith((".mp3", ".m4a", ".aac", ".wav"))
                )
                is_video = (
                    "video" in m_type
                    or "mp4" in m_type
                    or f_path.endswith((".mp4", ".mkv", ".webm", ".mov"))
                )

                if t_filter == "Video" and not is_video:
                    continue
                if t_filter == "Ses" and not is_audio:
                    continue

            if s_filter != "Tüm Durumlar":
                is_playlist = (
                    rec.platform == "youtube_playlist" and rec.playlist_index == 0
                ) or rec.playlist
                _exists, is_missing = _record_path_status(rec)

                if (
                    (s_filter == "Playlist" and not is_playlist)
                    or (s_filter == "Dosya Mevcut" and is_missing)
                    or (s_filter == "Dosya Eksik" and not is_missing)
                ):
                    continue

            filtered_records.append(rec)

        indexed_records = list(enumerate(filtered_records))
        
        if sort_f == "En Yeni":
            valid_dates = []
            invalid_dates = []
            for idx, r in indexed_records:
                ts = _parse_completed_at(r.completed_at)
                if ts is not None:
                    valid_dates.append((ts, idx, r))
                else:
                    invalid_dates.append((idx, r))
            # Tarih büyükten küçüğe, eşitse index büyükten küçüğe
            valid_dates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            # Tarihsiz kayıtlar kendi aralarında son eklenen önce (index reverse)
            invalid_dates.sort(key=lambda item: item[0], reverse=True)
            filtered_records = [r for _, _, r in valid_dates] + [r for _, r in invalid_dates]
            
        elif sort_f == "En Eski":
            valid_dates = []
            invalid_dates = []
            for idx, r in indexed_records:
                ts = _parse_completed_at(r.completed_at)
                if ts is not None:
                    valid_dates.append((ts, idx, r))
                else:
                    invalid_dates.append((idx, r))
            # Tarih küçükten büyüğe, eşitse index küçükten büyüğe
            valid_dates.sort(key=lambda item: (item[0], item[1]))
            # Tarihsiz kayıtlar sonda, indeks küçükten büyüğe
            invalid_dates.sort(key=lambda item: item[0])
            filtered_records = [r for _, _, r in valid_dates] + [r for _, r in invalid_dates]
        elif sort_f == "Başlık A-Z":
            valid_titles = []
            empty_titles = []
            for r in filtered_records:
                t = (r.title or Path(r.final_path or "").name or "").strip()
                if t:
                    valid_titles.append((_normalize_search_text(t), r))
                else:
                    empty_titles.append(r)
            valid_titles.sort(key=lambda item: item[0])
            filtered_records = [r for _, r in valid_titles] + empty_titles
        elif sort_f == "Başlık Z-A":
            valid_titles = []
            empty_titles = []
            for r in filtered_records:
                t = (r.title or Path(r.final_path or "").name or "").strip()
                if t:
                    valid_titles.append((_normalize_search_text(t), r))
                else:
                    empty_titles.append(r)
            valid_titles.sort(key=lambda item: item[0], reverse=True)
            filtered_records = [r for _, r in valid_titles] + empty_titles
        elif sort_f == "Platform A-Z":
            filtered_records.sort(
                key=lambda r: (_get_platform_display_name(r.platform) or "").lower()
            )

        visible_count = 0
        for rec in filtered_records:
            card = HistoryCard(rec)
            card.redownload_btn.clicked.connect(lambda _, r=rec: self._on_redownload(r))
            self.scroll_layout.insertWidget(visible_count, card)
            visible_count += 1

        total_count = len(self._all_records)

        if total_count == 0:
            self.empty_label.setText("Henüz indirilen bir içerik bulunmuyor.")
            self.empty_label.setVisible(True)
        elif visible_count == 0:
            self.empty_label.setText(
                "Filtrelere uygun kayıt bulunamadı.\n\nArama metnini veya filtreleri değiştirmeyi deneyin."
            )
            self.empty_label.setVisible(True)
        else:
            self.empty_label.setVisible(False)

        if visible_count == total_count:
            self.badge_label.setText(f"{total_count} kayıt")
        else:
            self.badge_label.setText(f"{visible_count} / {total_count} kayıt")

        self.clear_btn.setEnabled(total_count > 0)

    def _on_clear_history(self) -> None:
        from src.dialogs import AppMessageDialog

        dlg = AppMessageDialog(
            "Geçmiş temizlensin mi?",
            f"Geçmişteki {len(self._all_records)} kayıt kaldırılacak.\n\nİndirilen video, ses ve klasörler bilgisayarınızda kalmaya devam edecek.",
            "warning",
            self,
            custom_buttons=[
                ("clear", "Geçmişi Temizle", False),
                ("cancel", "Vazgeç", True),
            ],
        )
        dlg.exec()
        if dlg.clicked_button_id == "clear":
            try:
                clear_history()
            except Exception as e:  # noqa: BLE001
                AppMessageDialog(
                    "Hata", f"Geçmiş temizlenirken bir hata oluştu: {e}", "error", self
                ).exec()
                return

            self.search_input.clear()
            self.load_and_display()
            AppMessageDialog(
                "Başarılı",
                "İndirme geçmişi temizlendi. İndirilen dosyalarınız silinmedi.",
                "success",
                self,
            ).exec()

    def _on_redownload(self, record: DownloadRecord) -> None:
        if record.source_url:
            self.redownload_requested.emit(record.source_url)
            self.accept()
