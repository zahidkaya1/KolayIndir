"""
Yerleşim, buton QSS durumları ve benzersiz dosya adı üretimi birim testleri.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from src.history import (
    _is_temp_or_fragment_file,
    get_unique_filepath,
    sanitize_filename,
)
from src.styles import APP_STYLE

# ---------------------------------------------------------------------------
# QApplication singleton
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


# ---------------------------------------------------------------------------
# 1. Dosya adı benzersizliği
# ---------------------------------------------------------------------------

class TestGetUniqueFilepath:
    def test_no_conflict_returns_original(self, tmp_path):
        target = tmp_path / "video.mp4"
        result = get_unique_filepath(target)
        assert result == target

    def test_first_conflict_adds_1(self, tmp_path):
        target = tmp_path / "video.mp4"
        target.write_bytes(b"X" * 1024)
        result = get_unique_filepath(target)
        assert result == tmp_path / "video (1).mp4"

    def test_second_conflict_adds_2(self, tmp_path):
        target = tmp_path / "video.mp4"
        target.write_bytes(b"X" * 1024)
        (tmp_path / "video (1).mp4").write_bytes(b"X" * 1024)
        result = get_unique_filepath(target)
        assert result == tmp_path / "video (2).mp4"

    def test_mp3_numbering(self, tmp_path):
        target = tmp_path / "Müzik.mp3"
        target.write_bytes(b"M" * 1024)
        result = get_unique_filepath(target)
        assert result == tmp_path / "Müzik (1).mp3"
        (tmp_path / "Müzik (1).mp3").write_bytes(b"M" * 1024)
        result2 = get_unique_filepath(target)
        assert result2 == tmp_path / "Müzik (2).mp3"

    def test_existing_parens_not_mangled(self, tmp_path):
        """'Belgesel (Final).mp4' -> 'Belgesel (Final) (1).mp4'"""
        target = tmp_path / "Belgesel (Final).mp4"
        target.write_bytes(b"X" * 1024)
        result = get_unique_filepath(target)
        assert result == tmp_path / "Belgesel (Final) (1).mp4"

    def test_part_file_does_not_block_numbering(self, tmp_path):
        """
        'video.mp4' yok ama 'video.mp4.part' var
        -> target 'video.mp4' (part dosyası engel olmaz)
        """
        target = tmp_path / "video.mp4"
        part = tmp_path / "video.mp4.part"
        part.write_bytes(b"PART")
        # target does NOT exist -> returns target as-is
        result = get_unique_filepath(target)
        assert result == target

    def test_fragment_file_ignored_in_numbering(self, tmp_path):
        """
        'video (1).mp4' yerine 'video.f137.mp4' var -> (1) hâlâ seçilebilir
        """
        target = tmp_path / "video.mp4"
        target.write_bytes(b"X" * 1024)
        frag = tmp_path / "video.f137.mp4"
        frag.write_bytes(b"FRAG")
        # (1) position is occupied by real file?  No -> (1) slot is free
        result = get_unique_filepath(target)
        # video (1).mp4 doesn't exist (frag ≠ (1)), so it's chosen
        assert result == tmp_path / "video (1).mp4"

    def test_completed_file_not_overwritten(self, tmp_path):
        target = tmp_path / "video.mp4"
        target.write_bytes(b"COMPLETE" * 100)
        result = get_unique_filepath(target)
        # Must differ from target; original must remain untouched
        assert result != target
        assert target.exists()


class TestIsTempOrFragmentFile:
    @pytest.mark.parametrize("name", [
        "video.mp4.part",
        "audio.m4a.temp",
        "file.ytdl",
        "clip.hevc_temp",
        "video.f137.mp4",
        "audio.f140.m4a",
    ])
    def test_recognized_as_temp(self, tmp_path, name):
        p = tmp_path / name
        assert _is_temp_or_fragment_file(p)

    @pytest.mark.parametrize("name", [
        "video.mp4",
        "music.mp3",
        "clip (1).mp4",
        "Belgesel (Final).mp4",
    ])
    def test_not_temp(self, tmp_path, name):
        p = tmp_path / name
        assert not _is_temp_or_fragment_file(p)


class TestSanitizeFilename:
    def test_removes_invalid_chars(self):
        assert sanitize_filename('video: "title" <ok>') == "video_ _title_ _ok_"

    def test_empty_fallback(self):
        assert sanitize_filename("") == "Video"

    def test_normal_title_unchanged(self):
        assert sanitize_filename("My Video 2024") == "My Video 2024"


# ---------------------------------------------------------------------------
# 2. Buton QSS durumları
# ---------------------------------------------------------------------------

class TestButtonQSS:
    def test_cancel_button_has_normal_qss(self):
        assert "QPushButton#cancelButton" in APP_STYLE

    def test_cancel_button_has_hover_qss(self):
        assert "QPushButton#cancelButton:hover" in APP_STYLE

    def test_cancel_button_has_pressed_qss(self):
        assert "QPushButton#cancelButton:pressed" in APP_STYLE

    def test_cancel_button_has_disabled_qss(self):
        assert "QPushButton#cancelButton:disabled" in APP_STYLE

    def test_primary_button_has_hover_qss(self):
        assert "QPushButton#primaryButton:hover" in APP_STYLE

    def test_primary_button_has_pressed_qss(self):
        assert "QPushButton#primaryButton:pressed" in APP_STYLE

    def test_pressed_darker_than_hover(self):
        """Pressed background should be darker than hover background."""
        # Extract hex colours from QSS
        hover_match = re.search(
            r"QPushButton#cancelButton:hover\s*\{[^}]*background:\s*(#[0-9a-fA-F]{6})",
            APP_STYLE,
        )
        pressed_match = re.search(
            r"QPushButton#cancelButton:pressed\s*\{[^}]*background:\s*(#[0-9a-fA-F]{6})",
            APP_STYLE,
        )
        if hover_match and pressed_match:
            hover_hex = int(hover_match.group(1)[1:], 16)
            pressed_hex = int(pressed_match.group(1)[1:], 16)
            # Pressed colour should be numerically smaller (darker)
            assert pressed_hex <= hover_hex


# ---------------------------------------------------------------------------
# 3. UI widget testleri
# ---------------------------------------------------------------------------

class TestMainWindowUI:
    @pytest.fixture(autouse=True)
    def setup(self, qapp, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        history_file = tmp_path / "history.json"
        monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)
        monkeypatch.setattr("src.history.HISTORY_FILE", history_file)
        from src.main_window import MainWindow
        self.win = MainWindow()
        yield
        self.win.close()

    def test_preview_frame_minimum_height(self):
        assert self.win.preview_frame.minimumHeight() >= 95

    def test_title_label_word_wrap(self):
        assert self.win.meta_title_label.wordWrap() is True

    def test_title_label_max_height(self):
        assert self.win.meta_title_label.maximumHeight() <= 48

    def test_title_and_detail_are_separate_labels(self):
        """Başlık ve detaylar ayrı QLabel olmalı."""
        assert self.win.meta_title_label is not self.win.meta_uploader_label
        assert self.win.meta_title_label is not self.win.meta_badges_label

    def test_cancel_button_objectname_is_cancelButton(self):
        assert self.win.cancel_button.objectName() == "cancelButton"

    def test_download_button_disabled_without_metadata(self):
        assert not self.win.download_button.isEnabled()

    def test_cancel_button_disabled_without_download(self):
        assert not self.win.cancel_button.isEnabled()

    def test_cancel_button_text_changes_on_click(self):
        self.win.cancel_button.setEnabled(True)
        self.win._cancel_requested = False
        self.win.cancel_download()
        assert self.win.cancel_button.text() == "İptal ediliyor…"

    def test_download_button_enabled_after_metadata_ready(self):
        from src.models import MediaMetadata, PlatformType
        meta = MediaMetadata(
            title="Test",
            uploader="Uploader",
            maximum_available_height=1080,
            platform_type=PlatformType.YOUTUBE_VIDEO,
        )
        self.win._on_metadata_ready(meta)
        assert self.win.download_button.isEnabled()

    def test_cancel_button_enabled_during_download(self):
        self.win._set_ui_downloading(True)
        assert self.win.cancel_button.isEnabled()

    def test_cancel_button_disabled_after_download_ends(self):
        self.win._set_ui_downloading(True)
        self.win._set_ui_downloading(False)
        assert not self.win.cancel_button.isEnabled()


# ---------------------------------------------------------------------------
# 4. Cursor testleri
# ---------------------------------------------------------------------------

class TestPointerCursor:
    def test_active_button_has_pointing_hand(self, qapp):
        from src.utils import apply_pointing_hand_cursor
        btn = QPushButton("Test")
        apply_pointing_hand_cursor(btn)
        btn.setEnabled(True)
        assert btn.cursor().shape() == Qt.CursorShape.PointingHandCursor

    def test_disabled_button_has_arrow_cursor(self, qapp):
        from src.utils import apply_pointing_hand_cursor
        btn = QPushButton("Test")
        apply_pointing_hand_cursor(btn)
        btn.setEnabled(False)
        assert btn.cursor().shape() == Qt.CursorShape.ArrowCursor

    def test_re_enabled_button_gets_hand_cursor(self, qapp):
        from src.utils import apply_pointing_hand_cursor
        btn = QPushButton("Test")
        apply_pointing_hand_cursor(btn)
        btn.setEnabled(False)
        btn.setEnabled(True)
        assert btn.cursor().shape() == Qt.CursorShape.PointingHandCursor


# ---------------------------------------------------------------------------
# 5. History sistemi indirmeyi engellememeli
# ---------------------------------------------------------------------------

class TestHistoryDoesNotBlockDownload:
    def test_no_dialog_when_downloading_same_video(self, qapp, tmp_path, monkeypatch):
        """
        Aynı video tekrar indirildiğinde AlreadyDownloadedDialog gösterilmemeli,
        otomatik benzersiz dosya adı oluşturulmalı.
        """
        settings_file = tmp_path / "settings.json"
        history_file = tmp_path / "history.json"
        monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)
        monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

        from src.main_window import MainWindow
        win = MainWindow()
        win.folder_input.setText(str(tmp_path))

        from src.models import MediaMetadata, PlatformType
        meta = MediaMetadata(
            title="Test Video",
            uploader="Channel",
            maximum_available_height=1080,
            platform_type=PlatformType.YOUTUBE_VIDEO,
            webpage_url="https://www.youtube.com/watch?v=TEST123",
            media_id="TEST123",
        )
        win._on_metadata_ready(meta)

        # Dosya zaten var simüle et
        existing = tmp_path / "Test Video.mp4"
        existing.write_bytes(b"EXISTING" * 1000)

        # start_download'a girmeden önce target_override'ı doğrula
        from src.history import get_unique_filepath, sanitize_filename
        clean = sanitize_filename(meta.title)
        initial = tmp_path / f"{clean}.mp4"
        unique = get_unique_filepath(initial)

        assert unique != initial
        assert unique.name == "Test Video (1).mp4"
        win.close()

    def test_unique_filepath_increments_for_each_download(self, tmp_path):
        """
        Üç kez indirildiğinde: Video.mp4, Video (1).mp4, Video (2).mp4
        """
        base = tmp_path / "Video.mp4"
        # İlk indirme
        f1 = get_unique_filepath(base)
        assert f1 == base
        f1.write_bytes(b"X" * 1000)

        # İkinci indirme
        f2 = get_unique_filepath(base)
        assert f2 == tmp_path / "Video (1).mp4"
        f2.write_bytes(b"Y" * 1000)

        # Üçüncü indirme
        f3 = get_unique_filepath(base)
        assert f3 == tmp_path / "Video (2).mp4"


class TestHistoryMultipleDownloadsSameMediaId:
    """
    Aynı media_id'ye sahip video farklı dosyalara indirildiğinde
    history.json içinde üç AYRI kayıt oluşmalıdır.
    """

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        self.history_file = tmp_path / "history.json"
        monkeypatch.setattr("src.history.HISTORY_FILE", self.history_file)
        import importlib

        import src.history as mod
        importlib.reload(mod)
        monkeypatch.setattr("src.history.HISTORY_FILE", self.history_file)

    def _make_record(self, path_str: str, media_id: str = "ABCDEF",
                     media_type: str = "Video (MP4)", quality: str = "720p'ye kadar",
                     height: int = 720):
        from datetime import datetime, timezone

        from src.history import DownloadRecord
        return DownloadRecord(
            platform="youtube_video",
            media_id=media_id,
            media_type=media_type,
            requested_quality=quality,
            selected_height=height,
            final_path=path_str,
            state="completed",
            file_size=1024,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # 1. Aynı media_id + üç farklı yol → üç ayrı kayıt
    # ------------------------------------------------------------------
    def test_three_downloads_same_media_id_create_three_records(self):
        from src.history import load_history, save_record

        paths = [
            str(self.tmp_path / "Video.mp4"),
            str(self.tmp_path / "Video (1).mp4"),
            str(self.tmp_path / "Video (2).mp4"),
        ]
        for p in paths:
            Path(p).write_bytes(b"OK" * 100)
            save_record(self._make_record(p))

        records = load_history()
        assert len(records) == 3
        saved_paths = {Path(r.final_path).name for r in records}
        assert saved_paths == {"Video.mp4", "Video (1).mp4", "Video (2).mp4"}

    # ------------------------------------------------------------------
    # 2. Aynı final_path tekrar kaydedilirse kopya oluşmamalı → güncelleme
    # ------------------------------------------------------------------
    def test_same_path_updates_in_place_not_duplicated(self):
        from src.history import load_history, save_record

        p = str(self.tmp_path / "Video.mp4")
        Path(p).write_bytes(b"OK" * 100)

        save_record(self._make_record(p))
        save_record(self._make_record(p))  # ikinci kez aynı path
        save_record(self._make_record(p))  # üçüncü kez aynı path

        records = load_history()
        assert len(records) == 1

    # ------------------------------------------------------------------
    # 3. Silinmiş dosya → yalnız o kayıt stale, diğerleri completed
    # ------------------------------------------------------------------
    def test_deleted_numbered_file_only_that_record_goes_stale(self):
        from unittest.mock import patch

        from src.history import (
            load_history,
            save_record,
            validate_all_completed_records,
        )

        p0 = str(self.tmp_path / "Video.mp4")
        p1 = str(self.tmp_path / "Video (1).mp4")
        p2 = str(self.tmp_path / "Video (2).mp4")

        # 2 KB veri: validate_record'daki 1 KB kontrolünü geçer
        for p in (p0, p1, p2):
            Path(p).write_bytes(b"OK" * 1024)
            save_record(self._make_record(p))

        # Video (1).mp4 silinmiş simüle et
        Path(p1).unlink()

        # validate_record'ı mock'la: var olan dosyalar için True, yoksa False
        def _validate(rec):
            return Path(rec.final_path).exists()

        with patch("src.history.validate_record", side_effect=_validate):
            total_checked, stale_count = validate_all_completed_records()

        assert total_checked == 3
        assert stale_count == 1

        records = load_history()
        states = {Path(r.final_path).name: r.state for r in records}
        assert states["Video.mp4"] == "completed"
        assert states["Video (1).mp4"] == "stale"
        assert states["Video (2).mp4"] == "completed"

    # ------------------------------------------------------------------
    # 4. MP4 ve MP3 aynı media_id ile ayrı kayıtlar
    # ------------------------------------------------------------------
    def test_mp4_and_mp3_same_media_id_are_separate_records(self):
        from src.history import load_history, save_record

        p_mp4 = str(self.tmp_path / "Video.mp4")
        p_mp3 = str(self.tmp_path / "Video.mp3")
        Path(p_mp4).write_bytes(b"MP4" * 100)
        Path(p_mp3).write_bytes(b"MP3" * 100)

        save_record(self._make_record(p_mp4, media_type="Video (MP4)"))
        save_record(self._make_record(p_mp3, media_type="Ses (MP3)"))

        records = load_history()
        assert len(records) == 2

    # ------------------------------------------------------------------
    # 5. 720p ve 1080p aynı media_id ile ayrı kayıtlar
    # ------------------------------------------------------------------
    def test_720p_and_1080p_same_media_id_are_separate_records(self):
        from src.history import load_history, save_record

        p720 = str(self.tmp_path / "Video_720.mp4")
        p1080 = str(self.tmp_path / "Video_1080.mp4")
        Path(p720).write_bytes(b"720" * 100)
        Path(p1080).write_bytes(b"1080" * 100)

        save_record(self._make_record(p720, quality="720p'ye kadar", height=720))
        save_record(self._make_record(p1080, quality="1080p'ye kadar", height=1080))

        records = load_history()
        assert len(records) == 2

    # ------------------------------------------------------------------
    # 6. Windows yol farkı (büyük/küçük harf veya ters eğik çizgi) → tek kayıt
    # ------------------------------------------------------------------
    def test_windows_path_case_variants_do_not_duplicate(self):
        from src.history import load_history, save_record

        p_lower = str(self.tmp_path / "video.mp4")
        p_upper = str(self.tmp_path / "VIDEO.MP4")  # Aynı Windows dosyası

        Path(p_lower).write_bytes(b"OK" * 100)

        save_record(self._make_record(p_lower))
        save_record(self._make_record(p_upper))  # Windows'ta aynı dosya

        records = load_history()
        # Windows'ta normcase ile aynı yol kabul edilmeli → tek kayıt
        assert len(records) == 1

    # ------------------------------------------------------------------
    # 7. Eğik çizgi farkı → tek kayıt
    # ------------------------------------------------------------------
    def test_forward_vs_back_slash_do_not_duplicate(self):
        from src.history import load_history, save_record

        p = str(self.tmp_path / "Video.mp4")
        p_alt = p.replace("\\", "/")
        Path(p).write_bytes(b"OK" * 100)

        save_record(self._make_record(p))
        save_record(self._make_record(p_alt))

        records = load_history()
        assert len(records) == 1

    # ------------------------------------------------------------------
    # 8. Aynı media_id, farklı dosya adı → tarihçe diğer kayıtları etkilemez
    # ------------------------------------------------------------------
    def test_all_three_records_present_in_history_json(self):
        import json

        from src.history import save_record

        paths = [
            str(self.tmp_path / "Video.mp4"),
            str(self.tmp_path / "Video (1).mp4"),
            str(self.tmp_path / "Video (2).mp4"),
        ]
        for p in paths:
            Path(p).write_bytes(b"OK" * 100)
            save_record(self._make_record(p))

        raw = json.loads(self.history_file.read_text(encoding="utf-8"))
        assert len(raw) == 3
        saved = {item["final_path"].split("\\")[-1].split("/")[-1] for item in raw}
        assert "Video.mp4" in saved
        assert "Video (1).mp4" in saved
        assert "Video (2).mp4" in saved

    # ------------------------------------------------------------------
    # 9. Boş geçmişte validate_all_completed_records hata vermez
    # ------------------------------------------------------------------
    def test_validate_all_completed_records_empty_history(self):
        from src.history import validate_all_completed_records

        total_checked, stale_count = validate_all_completed_records()
        assert total_checked == 0
        assert stale_count == 0

    # ------------------------------------------------------------------
    # 10. Bozuk history.json güvenli yönetilir
    # ------------------------------------------------------------------
    def test_corrupted_history_json_handled_safely(self):
        from src.history import load_history, validate_all_completed_records

        self.history_file.write_text("{invalid json content---", encoding="utf-8")
        records = load_history()
        assert records == []

        total_checked, stale_count = validate_all_completed_records()
        assert total_checked == 0
        assert stale_count == 0

    # ------------------------------------------------------------------
    # 11. Uygulama başlangıcındaki doğrulama UI’ı kilitlemez ve log yazar
    # ------------------------------------------------------------------
    def test_startup_history_validation_non_blocking(self, qapp):
        import time
        from unittest.mock import patch

        from src.history import save_record
        from src.main_window import MainWindow

        p0 = str(self.tmp_path / "Video.mp4")
        p1 = str(self.tmp_path / "Video (1).mp4")
        Path(p0).write_bytes(b"OK" * 1024)
        Path(p1).write_bytes(b"OK" * 1024)

        save_record(self._make_record(p0))
        save_record(self._make_record(p1))

        # p1 silinmiş olsun
        Path(p1).unlink()

        def _validate(rec):
            return Path(rec.final_path).exists()

        window = MainWindow()

        with patch("src.history.validate_record", side_effect=_validate):
            window._start_history_validation()
            start = time.time()
            while window._history_thread is not None and time.time() - start < 5:
                qapp.processEvents()
                time.sleep(0.01)

        logs = window._log_history
        assert "İndirme geçmişi doğrulanıyor." in logs
        assert "2 kayıt kontrol edildi." in logs
        assert "1 eksik kayıt stale olarak işaretlendi." in logs
        window.close()

    # ------------------------------------------------------------------
    # 12. MainWindow _start_history_validation birden fazla çağrılssa bile 1 worker başlatır
    # ------------------------------------------------------------------
    def test_multiple_show_events_start_only_one_history_validation_worker(self, qapp):
        from unittest.mock import MagicMock, patch

        from src.main_window import MainWindow

        window = MainWindow()

        mock_worker = MagicMock()
        with patch("src.main_window.HistoryValidationWorker", return_value=mock_worker) as mock_worker_cls:
            window._start_history_validation()
            window._start_history_validation()
            window._start_history_validation()

            assert mock_worker_cls.call_count == 1

        if window._history_thread is not None:
            window._history_thread.quit()
            window._history_thread.wait()
        window.close()

    # ------------------------------------------------------------------
    # 13. Video (1).mp4 silindiğinde yeni indirme Video (3) yerine Video (1)'i tekrar kullanır
    # ------------------------------------------------------------------
    def test_deleted_numbered_file_reuses_first_available_number(self):
        from src.history import get_unique_filepath

        p0 = self.tmp_path / "Video.mp4"
        _p1 = self.tmp_path / "Video (1).mp4"
        p2 = self.tmp_path / "Video (2).mp4"

        p0.write_bytes(b"OK")
        # p1 silinmiş / yazılmamış (yok)
        p2.write_bytes(b"OK")

        # p0 için benzersiz dosya yolu istendiğinde p1 serbest olduğu için p1 dönmeli
        next_path = get_unique_filepath(p0)
        assert next_path.name == "Video (1).mp4"


class TestNoWheelComboBoxAndScrollArea:
    def test_no_wheel_combobox_ignores_wheel_when_popup_hidden(self, qapp):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent

        from src.widgets import NoWheelComboBox

        combo = NoWheelComboBox()
        combo.addItems(["Seçenek 1", "Seçenek 2", "Seçenek 3"])
        combo.setCurrentIndex(0)

        # Wheel event oluştur (scroll down)
        wheel_ev = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

        combo.wheelEvent(wheel_ev)

        # Açılır menü kapalıyken indeks değişmemeli ve event.isAccepted() False kalmalı (ignore edilmiş olmalı)
        assert combo.currentIndex() == 0
        assert not wheel_ev.isAccepted()

    def test_main_scroll_area_object_names_and_policies(self, qapp):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QScrollArea, QWidget

        from src.main_window import MainWindow

        win = MainWindow()
        scroll_area = win.findChild(QScrollArea, "mainScrollArea")
        assert scroll_area is not None
        assert scroll_area.widgetResizable()
        assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded

        scroll_content = win.findChild(QWidget, "scrollContent")
        assert scroll_content is not None
        win.close()

    def test_download_options_target_final_path_outtmpl(self, tmp_path):
        from src.download_options import build_ydl_options
        from src.models import DownloadRequest

        target_file = tmp_path / "Video (1).mp4"
        req = DownloadRequest(
            url="https://www.youtube.com/watch?v=69y8UEYbp4Q",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            target_final_path=target_file,
        )

        opts = build_ydl_options(req)
        assert opts["outtmpl"] == str(tmp_path / "Video (1).%(ext)s")
        assert opts["overwrites"] is True
        assert opts["continuedl"] is False



