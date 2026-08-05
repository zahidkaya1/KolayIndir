"""
Geçmiş (History) arayüzü ve entegrasyon testleri.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from src.history import DownloadRecord, save_history
from src.history_dialog import HistoryCard, HistoryDialog, _get_platform_display_name
from src.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def main_window_factory(monkeypatch, qapp):
    from PySide6.QtCore import QCoreApplication, QEvent

    windows = []

    # Disable dependency status modal globally for this fixture
    monkeypatch.setattr(
        MainWindow,
        "_show_dependency_status",
        lambda self: None,
    )

    def create(*args, **kwargs):
        window = MainWindow(*args, **kwargs)
        windows.append(window)
        return window

    yield create

    for window in reversed(windows):
        try:
            window.close()
        finally:
            window.deleteLater()

    QCoreApplication.sendPostedEvents(
        None,
        QEvent.Type.DeferredDelete,
    )
    qapp.processEvents()


@pytest.fixture(autouse=True)
def setup_history(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)
    yield history_file


def _make_record(
    tmp_path,
    name="video.mp4",
    platform="youtube_video",
    media_id="123",
    playlist=False,
    playlist_title="",
    playlist_index=0,
    playlist_count=0,
    source_url="https://youtube.com/watch?v=123",
    is_dir=False,
    title=None,
    media_type="Video (MP4)",
    completed_at="",
    state="completed",
):
    p = tmp_path / name
    if name:
        if is_dir:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.write_bytes(b"OK" * 2048)

    return DownloadRecord(
        platform=platform,
        media_id=media_id,
        media_type=media_type,
        requested_quality="1080p",
        selected_height=1080,
        final_path=str(p) if name else "",
        file_size=2048,
        playlist=playlist,
        playlist_title=playlist_title,
        playlist_index=playlist_index,
        playlist_count=playlist_count,
        source_url=source_url,
        title=title if title is not None else (name or "Unknown"),
        state=state,
        completed_at=completed_at,
    )


class TestHistoryUI:
    def test_main_window_has_history_button(self, main_window_factory):
        win = main_window_factory()
        assert hasattr(win, "history_button")
        assert win.history_button.text() == "Geçmiş"

    def test_history_dialog_empty_state(self, qapp):
        # Varsayılan history_file boştur (setup_history'de unlink edilmediği sürece)
        dlg = HistoryDialog()
        assert not dlg.empty_label.isHidden()
        assert dlg.scroll_layout.count() == 2  # empty_label + stretch
        dlg.close()

    def test_history_dialog_shows_records_newest_first(self, qapp, tmp_path):
        rec1 = _make_record(tmp_path, "1.mp4", media_id="v1")
        rec2 = _make_record(tmp_path, "2.mp4", media_id="v2")
        save_history([rec1, rec2])

        dlg = HistoryDialog()
        # count = cards + empty_label + stretch (if empty_label is hidden it's still in layout)
        # However _filter_records inserts cards before empty_label and stretch.
        # Actually it takes them out and rebuilds. Let's just check the cards.
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
        ]
        cards = [c for c in cards if isinstance(c, HistoryCard)]
        assert len(cards) == 2
        # rec2 is newer (at the end of list), so it should be first
        assert cards[0].record.media_id == "v2"
        assert cards[1].record.media_id == "v1"
        dlg.close()

    def test_history_card_single_video(self, qapp, tmp_path):
        rec = _make_record(tmp_path, "single.mp4", platform="youtube_video")
        card = HistoryCard(rec)
        assert _get_platform_display_name(rec.platform) == "YouTube"
        assert card.open_file_btn.isEnabled()
        assert card.open_folder_btn.isEnabled()
        assert card.redownload_btn.isEnabled()

    def test_history_card_missing_file_disables_open_file(self, qapp, tmp_path):
        rec = _make_record(tmp_path, "missing.mp4")
        Path(rec.final_path).unlink()  # Dosyayı sil
        card = HistoryCard(rec)
        assert not card.open_file_btn.isEnabled()
        assert card.open_folder_btn.isEnabled()  # Parent exists

    def test_history_card_playlist_summary_disables_open_file(self, qapp, tmp_path):
        rec = _make_record(
            tmp_path,
            "My Playlist",
            platform="youtube_playlist",
            playlist=True,
            playlist_index=0,
            is_dir=True,
        )
        card = HistoryCard(rec)
        assert not card.open_file_btn.isVisible()
        assert card.open_folder_btn.isEnabled()

    def test_history_card_playlist_item_shows_index(self, qapp, tmp_path):
        rec = _make_record(
            tmp_path,
            "item.mp4",
            playlist=True,
            playlist_title="My Pl",
            playlist_index=2,
            playlist_count=5,
        )
        card = HistoryCard(rec)
        # Başlıkta sıra bilgisi olmalı
        assert "(2/5)" in card.record.display_description()

    def test_search_filters_records(self, qapp, tmp_path):
        save_history(
            [_make_record(tmp_path, "apple.mp4"), _make_record(tmp_path, "banana.mp4")]
        )
        dlg = HistoryDialog()
        dlg.search_input.setText("apple")

        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
        ]
        cards = [c for c in cards if isinstance(c, HistoryCard)]
        assert len(cards) == 1
        assert "apple.mp4" in cards[0].record.final_path
        dlg.close()

    def test_redownload_signal(self, qapp, tmp_path):
        rec = _make_record(tmp_path, "test.mp4", source_url="https://x.com/abc")
        HistoryCard(rec)

        signal_received = []
        dlg = HistoryDialog()
        dlg.redownload_requested.connect(lambda url: signal_received.append(url))
        dlg._on_redownload(rec)

        assert signal_received == ["https://x.com/abc"]
        dlg.close()

    def test_empty_source_url_disables_redownload(self, qapp, tmp_path):
        rec = _make_record(tmp_path, "old.mp4", source_url="")
        card = HistoryCard(rec)
        assert not card.redownload_btn.isEnabled()

    def test_platform_names(self):
        assert _get_platform_display_name("youtube_video") == "YouTube"
        assert _get_platform_display_name("instagram_reel") == "Instagram"
        assert _get_platform_display_name("x_com") == "X / Twitter"
        assert _get_platform_display_name("tiktok_video") == "TikTok"
        assert _get_platform_display_name("kick_video") == "Kick"

    def test_history_dialog_close_flag(self, qapp):
        from PySide6.QtCore import Qt

        dlg = HistoryDialog()
        # Verify the help button hint is removed
        assert not (dlg.windowFlags() & Qt.WindowType.WindowContextHelpButtonHint)
        dlg.close()

    def test_redownload_active_download_shows_warning(
        self, monkeypatch, main_window_factory
    ):
        # active download prevents analyze

        win = main_window_factory()
        win._download_thread = "fake_thread"

        warn_shown = []

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                warn_shown.append(True)

        monkeypatch.setattr("src.main_window.AppMessageDialog", FakeDialog)
        win._on_history_redownload_requested("http://test")

        assert len(warn_shown) == 1
        assert win.url_input.text() != "http://test"

    def test_redownload_fills_url_and_analyzes(self, monkeypatch, main_window_factory):

        win = main_window_factory()
        analyzed = []
        monkeypatch.setattr(win, "analyze_url", lambda: analyzed.append(True))

        win._on_history_redownload_requested("http://test2")

        assert win.url_input.text() == "http://test2"
        assert len(analyzed) == 1

    def test_clear_history_writes_empty_list(self, tmp_path, monkeypatch):
        from src.history import HISTORY_FILE, clear_history, load_history

        HISTORY_FILE.write_text('[{"platform": "youtube_video"}]', encoding="utf-8")
        assert len(load_history()) == 1
        clear_history()
        assert HISTORY_FILE.read_text(encoding="utf-8") == "[]"
        assert len(load_history()) == 0

    def test_clear_history_does_not_fail_if_missing(self, tmp_path, monkeypatch):
        from src.history import HISTORY_FILE, clear_history

        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        clear_history()
        assert HISTORY_FILE.read_text(encoding="utf-8") == "[]"

    def test_clear_history_dialog_cancel_does_not_clear(
        self, qapp, tmp_path, monkeypatch
    ):
        save_history([_make_record(tmp_path, "1.mp4")])
        dlg = HistoryDialog()
        assert len(dlg._all_records) == 1

        class FakeDialogCancel:
            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                pass

            @property
            def clicked_button_id(self):
                return "cancel"

        monkeypatch.setattr("src.dialogs.AppMessageDialog", FakeDialogCancel)
        dlg._on_clear_history()

        assert len(dlg._all_records) == 1
        dlg.close()

    def test_clear_history_dialog_clear_removes_records(
        self, qapp, tmp_path, monkeypatch
    ):
        save_history([_make_record(tmp_path, "1.mp4")])
        dlg = HistoryDialog()
        assert len(dlg._all_records) == 1

        class FakeDialogClear:
            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                pass

            @property
            def clicked_button_id(self):
                return "clear"

        monkeypatch.setattr("src.dialogs.AppMessageDialog", FakeDialogClear)
        dlg._on_clear_history()

        assert len(dlg._all_records) == 0
        assert not dlg.empty_label.isHidden()
        dlg.close()


class TestHistoryFiltersAndSearch:
    @pytest.fixture(autouse=True)
    def disable_validation(self, monkeypatch):
        monkeypatch.setattr(
            "src.history_dialog.validate_all_completed_records", lambda: (0, 0)
        )

    def test_search_by_title_and_filename(self, qapp, tmp_path):
        from src.history import save_history

        save_history(
            [
                _make_record(tmp_path, "video_Işık.mp4", title="IŞIK Title"),
                _make_record(tmp_path, "İstanbul.mp4", title="Normal Title"),
            ]
        )
        dlg = HistoryDialog()

        dlg.search_input.setText("ışık")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1

        dlg.search_input.setText("istanbul")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1

        dlg.search_input.setText("İSTANBUL")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        dlg.close()

    def test_search_empty_shows_all(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, "1.mp4"), _make_record(tmp_path, "2.mp4")])
        dlg = HistoryDialog()
        dlg.search_input.setText("xxx")
        assert not dlg.empty_label.isHidden()

        dlg.search_input.setText("")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 2
        dlg.close()

    def test_platform_filter_youtube_instagram_x_tiktok(self, qapp, tmp_path):
        from src.history import save_history

        save_history(
            [
                _make_record(tmp_path, "1.mp4", platform="youtube_video"),
                _make_record(tmp_path, "2.mp4", platform="instagram_reel"),
                _make_record(tmp_path, "3.mp4", platform="twitter"),
                _make_record(tmp_path, "4.mp4", platform="tiktok_video"),
                _make_record(tmp_path, "5.mp4", platform="x_com"),
            ]
        )
        dlg = HistoryDialog()

        dlg.platform_combo.setCurrentText("YouTube")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert _get_platform_display_name(cards[0].record.platform) == "YouTube"

        dlg.platform_combo.setCurrentText("X / Twitter")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 2

        dlg.platform_combo.setCurrentText("Instagram")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert _get_platform_display_name(cards[0].record.platform) == "Instagram"

        dlg.platform_combo.setCurrentText("TikTok")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert _get_platform_display_name(cards[0].record.platform) == "TikTok"
        dlg.close()

    def test_type_filter_video_audio(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "vid.mp4")
        r2 = _make_record(tmp_path, "aud.mp3", media_type="Ses (MP3)")
        save_history([r1, r2])

        dlg = HistoryDialog()

        dlg.type_combo.setCurrentText("Video")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.media_type == "Video (MP4)"

        dlg.type_combo.setCurrentText("Ses")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.media_type == "Ses (MP3)"
        dlg.close()

    def test_status_filter_missing_and_playlist(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "ok.mp4")
        r2 = _make_record(tmp_path, "missing.mp4")
        Path(r2.final_path).unlink()
        r3 = _make_record(
            tmp_path,
            "playlist",
            platform="youtube_playlist",
            playlist=True,
            playlist_index=0,
            is_dir=True,
        )

        save_history([r1, r2, r3])

        dlg = HistoryDialog()

        dlg.status_combo.setCurrentText("Dosya Mevcut")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 2

        dlg.status_combo.setCurrentText("Dosya Eksik")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.title == "missing.mp4"

        dlg.status_combo.setCurrentText("Playlist")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.title == "playlist"
        dlg.close()

    def test_sorting_options(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(
            tmp_path,
            "C.mp4",
            platform="youtube",
            completed_at="2023-01-01T10:00:00Z",
            title="C Title",
        )
        r2 = _make_record(
            tmp_path,
            "A.mp4",
            platform="instagram",
            completed_at="2024-01-01T10:00:00Z",
            title="A Title",
        )
        r3 = _make_record(
            tmp_path,
            "B.mp4",
            platform="twitter",
            completed_at="2022-01-01T10:00:00Z",
            title="B Title",
        )

        save_history([r1, r2, r3])
        dlg = HistoryDialog()

        # En Yeni (default) -> r2, r1, r3
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].record.title == "A Title"

        # En Eski -> r3, r1, r2
        dlg.sort_combo.setCurrentText("En Eski")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].record.title == "B Title"

        # Başlık A-Z -> A, B, C
        dlg.sort_combo.setCurrentText("Başlık A-Z")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].record.title == "A Title"
        assert cards[1].record.title == "B Title"

        # Başlık Z-A -> C, B, A
        dlg.sort_combo.setCurrentText("Başlık Z-A")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].record.title == "C Title"
        assert cards[1].record.title == "B Title"

        # Platform A-Z -> Instagram, Twitter, YouTube
        dlg.sort_combo.setCurrentText("Platform A-Z")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert _get_platform_display_name(cards[0].record.platform) == "Instagram"
        dlg.close()

    def test_clear_filters_button_state_and_action(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, "1.mp4")])
        dlg = HistoryDialog()

        assert not dlg.clear_filters_btn.isEnabled()
        dlg.search_input.setText("test")
        assert dlg.clear_filters_btn.isEnabled()

        dlg.clear_filters_btn.click()
        assert not dlg.clear_filters_btn.isEnabled()
        assert dlg.search_input.text() == ""
        assert dlg.platform_combo.currentText() == "Tüm Platformlar"

        # verify it resets sorting to En Yeni
        dlg.sort_combo.setCurrentText("En Eski")
        dlg.clear_filters_btn.click()
        assert dlg.sort_combo.currentText() == "En Yeni"
        dlg.close()

    def test_result_count_badge_update(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, "1.mp4"), _make_record(tmp_path, "2.mp4")])
        dlg = HistoryDialog()
        assert dlg.badge_label.text() == "2 kayıt"

        dlg.search_input.setText("non_existent")
        assert dlg.badge_label.text() == "0 / 2 kayıt"

        dlg.search_input.setText("1.mp4")
        assert dlg.badge_label.text() == "1 / 2 kayıt"
        dlg.close()

    def test_search_and_platform_filter_combined(self, qapp, tmp_path):
        from src.history import save_history

        save_history(
            [
                _make_record(tmp_path, "1.mp4", platform="youtube", title="Cat Video"),
                _make_record(
                    tmp_path, "2.mp4", platform="instagram", title="Cat Video"
                ),
                _make_record(tmp_path, "3.mp4", platform="youtube", title="Dog Video"),
            ]
        )
        dlg = HistoryDialog()
        dlg.search_input.setText("cat")
        dlg.platform_combo.setCurrentText("YouTube")

        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.title == "Cat Video"
        assert _get_platform_display_name(cards[0].record.platform) == "YouTube"
        dlg.close()

    def test_platform_type_status_combined(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "1.mp4", platform="youtube", media_type="Video")
        r2 = _make_record(tmp_path, "2.mp3", platform="youtube", media_type="Ses")
        r3 = _make_record(tmp_path, "3.mp3", platform="instagram", media_type="Ses")
        Path(r2.final_path).unlink()  # make it missing
        save_history([r1, r2, r3])

        dlg = HistoryDialog()
        dlg.platform_combo.setCurrentText("YouTube")
        dlg.type_combo.setCurrentText("Ses")
        dlg.status_combo.setCurrentText("Dosya Eksik")

        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.title == "2.mp3"
        dlg.close()

    def test_filtering_does_not_mutate_all_records_or_json(self, qapp, tmp_path):
        from src.history import load_history, save_history

        save_history([_make_record(tmp_path, "1.mp4"), _make_record(tmp_path, "2.mp4")])
        dlg = HistoryDialog()
        dlg.search_input.setText("non_existent")

        assert len(dlg._all_records) == 2
        assert len(load_history()) == 2
        dlg.close()

    def test_refresh_preserves_filters(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, "1.mp4")])
        dlg = HistoryDialog()

        dlg.search_input.setText("1")
        dlg.platform_combo.setCurrentText("YouTube")
        dlg.type_combo.setCurrentText("Video")
        dlg.status_combo.setCurrentText("Dosya Mevcut")
        dlg.sort_combo.setCurrentText("Başlık A-Z")

        dlg.refresh_btn.click()

        assert dlg.search_input.text() == "1"
        assert dlg.platform_combo.currentText() == "YouTube"
        assert dlg.type_combo.currentText() == "Video"
        assert dlg.status_combo.currentText() == "Dosya Mevcut"
        assert dlg.sort_combo.currentText() == "Başlık A-Z"
        dlg.close()

    def test_empty_final_path_not_dosya_mevcut(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, name="", title="Empty")])
        dlg = HistoryDialog()
        dlg.status_combo.setCurrentText("Dosya Mevcut")

        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 0
        dlg.close()

    def test_empty_final_path_does_not_crash(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, name="", title="Empty")])
        dlg = HistoryDialog()
        dlg.search_input.setText("Empty")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        dlg.close()

    def test_missing_old_record_fields_does_not_crash(self, qapp, tmp_path):
        from src.history import HISTORY_FILE

        # Write directly to simulate old record
        HISTORY_FILE.write_text(
            '[{"platform": "youtube_video", "media_id": "123"}]', encoding="utf-8"
        )
        dlg = HistoryDialog()
        dlg.type_combo.setCurrentText("Video")
        dlg.search_input.setText("x")
        # Should not crash
        dlg.close()

    def test_no_date_is_last_in_newest(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "A.mp4", completed_at="2023-01-01T10:00:00Z")
        r2 = _make_record(tmp_path, "B.mp4", completed_at="")
        save_history([r1, r2])
        dlg = HistoryDialog()

        dlg.sort_combo.setCurrentText("En Yeni")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[-1].record.title == "B.mp4"
        dlg.close()

    def test_no_date_is_last_in_oldest(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "A.mp4", completed_at="2023-01-01T10:00:00Z")
        r2 = _make_record(tmp_path, "B.mp4", completed_at="")
        save_history([r1, r2])
        dlg = HistoryDialog()

        dlg.sort_combo.setCurrentText("En Eski")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[-1].record.title == "B.mp4"
        dlg.close()

    def test_corrupted_date_is_last(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "A.mp4", completed_at="2023-01-01T10:00:00Z")
        r2 = _make_record(tmp_path, "B.mp4", completed_at="invalid_date")
        save_history([r1, r2])
        dlg = HistoryDialog()

        dlg.sort_combo.setCurrentText("En Yeni")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[-1].record.title == "B.mp4"
        dlg.close()

    def test_playlist_item_filter(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(
            tmp_path, "p_item.mp4", playlist=True, playlist_index=1, playlist_count=2
        )
        r2 = _make_record(tmp_path, "single.mp4", playlist=False)
        save_history([r1, r2])
        dlg = HistoryDialog()

        dlg.status_combo.setCurrentText("Playlist")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].record.title == "p_item.mp4"
        dlg.close()

    def test_no_filter_results_message(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, "1.mp4")])
        dlg = HistoryDialog()
        dlg.search_input.setText("notfound")
        assert not dlg.empty_label.isHidden()
        assert "Filtrelere uygun" in dlg.empty_label.text()
        dlg.close()

    def test_true_empty_history_message(self, qapp, tmp_path):
        dlg = HistoryDialog()
        assert not dlg.empty_label.isHidden()
        assert "Henüz indirilen" in dlg.empty_label.text()
        dlg.close()

    def test_filter_does_not_spawn_thread_or_network(self, qapp, tmp_path, monkeypatch):
        from src.history import save_history

        save_history([_make_record(tmp_path, "1.mp4")])
        dlg = HistoryDialog()

        # intercept QThread start and network requests if any
        thread_started = False

        def fake_start(*args, **kwargs):
            nonlocal thread_started
            thread_started = True

        monkeypatch.setattr("PySide6.QtCore.QThread.start", fake_start, raising=False)

        dlg.search_input.setText("x")
        assert not thread_started
        dlg.close()

    def test_dialog_closure_leaves_no_windows(self, qapp):
        dlg = HistoryDialog()
        dlg.close()
        # QApplication.topLevelWidgets() shouldn't contain dlg
        assert dlg not in qapp.topLevelWidgets() or dlg.isHidden()

    def test_no_horizontal_overflow_at_1366_768(self, qapp, tmp_path):
        from src.history import save_history

        # A very long title, but keep filename reasonable to avoid Windows MAX_PATH (260) limit
        long_title = "x" * 200
        long_name = "x" * 100 + ".mp4"
        save_history([_make_record(tmp_path, long_name, title=long_title)])
        dlg = HistoryDialog()
        dlg.resize(1366, 768)

        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        card = cards[0]
        assert card.minimumSizeHint().width() < 1366
        dlg.close()

    def test_empty_final_path_shows_dosya_bulunamadi(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, name="", title="Empty")])
        dlg = HistoryDialog()
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        assert cards[0].findChild(QLabel, "historyStatusMissing") is not None
        dlg.close()

    def test_empty_final_path_disables_open_file(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, name="", title="Empty")])
        dlg = HistoryDialog()
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert not cards[0].open_file_btn.isEnabled()
        dlg.close()

    def test_empty_final_path_disables_open_folder(self, qapp, tmp_path):
        from src.history import save_history

        save_history([_make_record(tmp_path, name="", title="Empty")])
        dlg = HistoryDialog()
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert not cards[0].open_folder_btn.isEnabled()
        dlg.close()

    def test_open_folder_empty_path_does_not_call_desktop_services(
        self, qapp, tmp_path, monkeypatch
    ):
        from src.history import save_history

        save_history([_make_record(tmp_path, name="", title="Empty")])
        dlg = HistoryDialog()
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        card = cards[0]

        called = False

        def fake_openUrl(*args, **kwargs):
            nonlocal called
            called = True

        monkeypatch.setattr(
            "PySide6.QtGui.QDesktopServices.openUrl", fake_openUrl, raising=False
        )
        card._open_folder()
        assert not called

        card._open_file()
        assert not called
        dlg.close()

    def test_no_title_last_in_a_to_z(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "B.mp4", title="B Title")
        r2 = _make_record(tmp_path, "A.mp4", title="A Title")
        r3 = _make_record(tmp_path, name="", title="")  # completely empty
        save_history([r1, r2, r3])
        dlg = HistoryDialog()

        dlg.sort_combo.setCurrentText("Başlık A-Z")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].record.title == "A Title"
        assert cards[1].record.title == "B Title"
        assert cards[2].record.title == ""
        dlg.close()

    def test_no_title_last_in_z_to_a(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "B.mp4", title="B Title")
        r2 = _make_record(tmp_path, "A.mp4", title="A Title")
        r3 = _make_record(tmp_path, name="", title="")
        save_history([r1, r2, r3])
        dlg = HistoryDialog()

        dlg.sort_combo.setCurrentText("Başlık Z-A")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].record.title == "B Title"
        assert cards[1].record.title == "A Title"
        assert cards[2].record.title == ""
        dlg.close()

    def test_playlist_summary_shows_correctly_when_exists(self, qapp, tmp_path):
        from src.history import save_history

        r = _make_record(
            tmp_path,
            "my_pl_dir",
            platform="youtube_playlist",
            playlist=True,
            playlist_index=0,
            is_dir=True,
        )
        save_history([r])
        dlg = HistoryDialog()
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].findChild(QLabel, "historyStatusInfo") is not None
        assert (
            cards[0].findChild(QLabel, "historyStatusInfo").text() == "Playlist Özeti"
        )
        dlg.close()

    def test_playlist_summary_shows_missing_when_empty_path(self, qapp, tmp_path):
        from src.history import save_history

        r = _make_record(
            tmp_path, "", platform="youtube_playlist", playlist=True, playlist_index=0
        )
        save_history([r])
        dlg = HistoryDialog()
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert cards[0].findChild(QLabel, "historyStatusMissing") is not None
        assert (
            cards[0].findChild(QLabel, "historyStatusMissing").text()
            == "Dosya bulunamadı"
        )
        dlg.close()

    def test_x_alias_values_all_match_x_twitter_filter(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "1.mp4", platform="twitter")
        r2 = _make_record(tmp_path, "2.mp4", platform="x")
        r3 = _make_record(tmp_path, "3.mp4", platform="x_com")
        r4 = _make_record(tmp_path, "4.mp4", platform="X / Twitter")
        save_history([r1, r2, r3, r4])

        dlg = HistoryDialog()
        dlg.platform_combo.setCurrentText("X / Twitter")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 4
        dlg.close()

    def test_none_or_empty_platform_does_not_crash(self, qapp, tmp_path):
        from src.history import save_history

        r1 = _make_record(tmp_path, "1.mp4", platform=None)
        r2 = _make_record(tmp_path, "2.mp4", platform="")
        save_history([r1, r2])
        dlg = HistoryDialog()
        dlg.platform_combo.setCurrentText("YouTube")
        # should just show 0 cards, no crash
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 0
        dlg.close()

    def test_none_media_type_and_platform_safe(self, qapp):
        from src.history import DownloadRecord
        from src.history_dialog import HistoryCard

        record = DownloadRecord(
            media_id="1",
            title="Safe Test",
            source_url="http://example.com",
            platform=None,
            media_type=None,
            requested_quality=None,
            selected_height=0,
            final_path="",
            file_size=0,
            state="completed",
            playlist=False,
            playlist_index=0,
            playlist_count=0,
        )

        # Should not crash
        card = HistoryCard(record)
        badge = card.findChild(QLabel, "platformBadge")
        assert badge is not None
        assert badge.text() == "Bilinmiyor"
        assert "background-color: #f1f5f9;" in badge.styleSheet()
        card.close()

    def test_history_dialog_shows_records_newest_first_with_same_date(
        self, qapp, tmp_path
    ):
        from src.history import save_history

        r1 = _make_record(
            tmp_path, "1.mp4", media_id="v1", completed_at="2024-01-01T10:00:00Z"
        )
        r2 = _make_record(
            tmp_path, "2.mp4", media_id="v2", completed_at="2024-01-01T10:00:00Z"
        )
        r3 = _make_record(
            tmp_path, "3.mp4", media_id="v3", completed_at="2024-01-01T10:00:00Z"
        )
        save_history([r1, r2, r3])
        dlg = HistoryDialog()

        dlg.sort_combo.setCurrentText("En Yeni")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert [c.record.media_id for c in cards] == ["v3", "v2", "v1"]

        dlg.sort_combo.setCurrentText("En Eski")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert [c.record.media_id for c in cards] == ["v1", "v2", "v3"]
        dlg.close()

    def test_platform_alias_parametric(self, qapp, tmp_path):
        from src.history import save_history

        aliases = [
            "instagram",
            "instagram_reel",
            "instagram_post",
            "instagram_story",
            "youtube_video",
            "youtube_playlist",
            "twitter",
            "twitter_video",
            "x",
            "x_com",
            "tiktok_video",
        ]
        records = []
        for i, alias in enumerate(aliases):
            records.append(_make_record(tmp_path, f"{i}.mp4", platform=alias))
        save_history(records)
        dlg = HistoryDialog()

        # Instagram count
        dlg.platform_combo.setCurrentText("Instagram")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 4

        # YouTube count
        dlg.platform_combo.setCurrentText("YouTube")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 2

        # X / Twitter count
        dlg.platform_combo.setCurrentText("X / Twitter")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 4

        # TikTok count
        dlg.platform_combo.setCurrentText("TikTok")
        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        assert len(cards) == 1
        dlg.close()

    def test_long_title_and_filename_overflow_with_1366_768(self, qapp, tmp_path):
        from src.history import save_history

        long_title = "A" * 500
        long_name = "B" * 100 + ".mp4"
        save_history([_make_record(tmp_path, long_name, title=long_title)])

        dlg = HistoryDialog()
        dlg.resize(1366, 768)
        dlg.show()
        qapp.processEvents()

        cards = [
            dlg.scroll_layout.itemAt(i).widget()
            for i in range(dlg.scroll_layout.count())
            if isinstance(dlg.scroll_layout.itemAt(i).widget(), HistoryCard)
        ]
        card = cards[0]

        assert card.minimumSizeHint().width() < 1366
        assert card.width() <= 1366
        assert card.record.title == long_title
        dlg.close()


class TestHistoryBackgroundRegression:
    def _is_light_color(self, color_str: str) -> bool:
        """Helper to determine if a hex color is 'light' (e.g. #F7F9FC)."""
        color_str = color_str.strip().strip(";")
        if not color_str.startswith("#"):
            return False
        # Simplistic check: #F7... is very light. We expect #F7F9FC or similar
        return color_str.lower() in {"#f7f9fc", "#ffffff"}

    def test_history_dialog_main_background_is_light(self, qapp, tmp_path):
        from src.history_dialog import HistoryDialog

        dlg = HistoryDialog()
        qss = dlg.styleSheet()
        assert (
            "background-color: #F7F9FC" in qss
            or "background-color: #f7f9fc" in qss.lower()
        )

    def test_scroll_area_viewport_background_is_light(self, qapp):
        from src.history_dialog import HistoryDialog

        dlg = HistoryDialog()
        qss = dlg.styleSheet()
        assert "QWidget#historyScrollViewport" in qss
        # Checking that WA_StyledBackground is True
        from PySide6.QtCore import Qt

        assert dlg.scroll_area.viewport().testAttribute(
            Qt.WidgetAttribute.WA_StyledBackground
        )

    def test_scroll_content_background_is_light(self, qapp):
        from src.history_dialog import HistoryDialog

        dlg = HistoryDialog()
        from PySide6.QtCore import Qt

        assert dlg.scroll_content.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def test_no_black_background_when_history_empty(self, qapp):
        from src.history import clear_history
        from src.history_dialog import HistoryDialog

        clear_history()
        dlg = HistoryDialog()
        dlg.show()
        dlg.resize(1100, 700)
        qapp.processEvents()

        # Test the visual rendering by capturing a pixel from the empty area (bottom)
        pixmap = dlg.grab()
        image = pixmap.toImage()
        # Sample a pixel near the bottom middle where there should be empty space
        color = image.pixelColor(dlg.width() // 2, dlg.height() - 50)
        # Should not be black/dark. Check lightness/value > 200
        assert color.lightness() > 200

    def test_light_background_under_cards_with_single_record(self, qapp, tmp_path):
        import datetime

        from src.history import DownloadRecord, save_history
        from src.history_dialog import HistoryDialog

        save_history(
            [
                DownloadRecord(
                    platform="youtube",
                    media_id="test",
                    media_type="Video",
                    requested_quality="720p",
                    selected_height=720,
                    final_path=str(tmp_path / "1.mp4"),
                    state="completed",
                    file_size=1024,
                    completed_at=datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    video_codec="h264",
                    audio_codec="aac",
                )
            ]
        )
        dlg = HistoryDialog()
        dlg.show()
        dlg.resize(1100, 700)
        qapp.processEvents()

        pixmap = dlg.grab()
        image = pixmap.toImage()
        color = image.pixelColor(dlg.width() // 2, dlg.height() - 50)
        assert color.lightness() > 200

    def test_viewport_light_when_filter_results_zero(self, qapp, tmp_path):
        import datetime

        from src.history import DownloadRecord, save_history
        from src.history_dialog import HistoryDialog

        save_history(
            [
                DownloadRecord(
                    platform="youtube",
                    media_id="test",
                    media_type="Video",
                    requested_quality="720p",
                    selected_height=720,
                    final_path=str(tmp_path / "1.mp4"),
                    state="completed",
                    file_size=1024,
                    completed_at=datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    video_codec="h264",
                    audio_codec="aac",
                )
            ]
        )
        dlg = HistoryDialog()
        dlg.platform_combo.setCurrentText("TikTok")
        dlg.show()
        dlg.resize(1100, 700)
        qapp.processEvents()

        pixmap = dlg.grab()
        image = pixmap.toImage()
        color = image.pixelColor(dlg.width() // 2, dlg.height() - 50)
        assert color.lightness() > 200
