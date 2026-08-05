"""Tests for multi-link download queue functionality."""

from PySide6.QtWidgets import QDialog

from src.models import QueueItem
from src.utils import extract_supported_urls_from_text


def test_url_extraction_rules():
    raw_text = """
    Check out these links:
    https://www.youtube.com/watch?v=video1.
    https://x.com/user/status/123456)
    https://twitter.com/user/status/123456
    https://vt.tiktok.com/ZS123456/
    https://kick.com/streamer
    https://unsupported.com/page
    https://www.youtube.com/watch?v=video1
    """

    urls = extract_supported_urls_from_text(raw_text)

    # Order preserved, trailing dots/parens cleaned, exact dupes removed, Kick and unsupported skipped
    assert len(urls) == 4
    assert urls[0] == "https://www.youtube.com/watch?v=video1"
    assert urls[1] == "https://x.com/user/status/123456"
    assert urls[2] == "https://twitter.com/user/status/123456"
    assert urls[3] == "https://vt.tiktok.com/ZS123456/"


def test_url_extraction_kick_and_unsupported():
    text = "https://kick.com/video/123 https://example.com/foo"
    urls = extract_supported_urls_from_text(text)
    assert urls == []


def test_queue_item_settings_copy_and_duplication(main_window, monkeypatch):
    monkeypatch.setattr(
        "src.main_window.AppMessageDialog.exec",
        lambda self: QDialog.DialogCode.Rejected,
    )

    url = "https://www.youtube.com/watch?v=test1"
    main_window.url_input.setText(url)
    main_window.quality_combo.setCurrentText("1080p'ye kadar")
    main_window.media_combo.setCurrentText("Video (MP4)")

    # Add url to queue
    main_window._on_queue_urls_added([url])
    assert len(main_window._queue_items) == 1
    item1 = main_window._queue_items[0]
    assert item1.url == url
    assert item1.quality == "1080p'ye kadar"
    assert item1.status == "Bekliyor"

    # Adding exact same URL with same settings should be blocked (duplicate)
    main_window._on_queue_urls_added([url])
    assert len(main_window._queue_items) == 1

    # Changing quality and adding same URL should work
    main_window.quality_combo.setCurrentText("720p'ye kadar")
    main_window._on_queue_urls_added([url])
    assert len(main_window._queue_items) == 2
    item2 = main_window._queue_items[1]
    assert item2.quality == "720p'ye kadar"
    assert item1.quality == "1080p'ye kadar"  # Original item settings unchanged


def test_queue_conflict_prevention(main_window, monkeypatch):
    dialog_opened = False

    def mock_exec(self):
        nonlocal dialog_opened
        dialog_opened = True
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr("src.main_window.AppMessageDialog.exec", mock_exec)

    # Fake active queue
    main_window._is_queue_active = True

    main_window.analyze_url()
    assert dialog_opened

    dialog_opened = False
    main_window.start_download()
    assert dialog_opened


def test_retry_failed_queue_items(main_window):
    item1 = QueueItem(
        id="1", url="https://youtube.com/w?v=1", platform="YouTube", status="Tamamlandı"
    )
    item2 = QueueItem(
        id="2",
        url="https://youtube.com/w?v=2",
        platform="YouTube",
        status="Başarısız",
        error_msg="Network Error",
    )
    main_window._queue_items = [item1, item2]

    main_window._retry_failed_queue()

    assert item1.status == "Tamamlandı"
    assert item2.status == "Bekliyor"
    assert item2.error_msg == ""


def test_clear_completed_queue(main_window):
    item1 = QueueItem(
        id="1", url="https://youtube.com/w?v=1", platform="YouTube", status="Tamamlandı"
    )
    item2 = QueueItem(
        id="2", url="https://youtube.com/w?v=2", platform="YouTube", status="Başarısız"
    )
    item3 = QueueItem(
        id="3", url="https://youtube.com/w?v=3", platform="YouTube", status="Bekliyor"
    )
    main_window._queue_items = [item1, item2, item3]

    main_window._clear_completed_queue()

    assert len(main_window._queue_items) == 2
    assert main_window._queue_items[0].id == "2"
    assert main_window._queue_items[1].id == "3"


def test_stop_queue(main_window):
    item = QueueItem(
        id="1",
        url="https://youtube.com/w?v=1",
        platform="YouTube",
        status="İndiriliyor",
    )
    main_window._queue_items = [item]
    main_window._is_queue_active = True

    class FakeWorker:
        def cancel(self):
            pass

    main_window._download_worker = FakeWorker()

    main_window._stop_queue()
    assert not main_window._is_queue_active


def test_queue_dialog_thread_and_flags(main_window):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from src.queue_dialog import DownloadQueueDialog

    app_thread = QApplication.instance().thread()
    dlg = DownloadQueueDialog(main_window)

    assert dlg.thread() == app_thread
    assert dlg.table.thread() == app_thread
    assert dlg.urls_input.thread() == app_thread
    assert dlg.objectName() == "downloadQueueDialog"

    flags = dlg.windowFlags()
    assert bool(flags & Qt.WindowType.WindowCloseButtonHint)
    assert not bool(flags & Qt.WindowType.FramelessWindowHint)

    # Closing dialog does not cancel running queue in main_window
    main_window._is_queue_active = True
    dlg.close()
    assert main_window._is_queue_active is True


def test_queue_download_start_exception_and_signal_transition(main_window, monkeypatch):
    from src.models import MediaMetadata

    item = QueueItem(
        id="q1",
        url="https://youtube.com/watch?v=abc",
        platform="YouTube",
        status="Analiz ediliyor",
    )
    main_window._queue_items = [item]
    main_window._is_queue_active = True

    meta = MediaMetadata(
        title="Test Video", webpage_url="https://youtube.com/watch?v=abc"
    )
    main_window._on_queue_metadata_ready(meta)

    assert main_window._pending_queue_download_item_id == "q1"
    assert main_window._pending_queue_metadata == meta

    # Simulate thread finish triggering pending download start safely
    start_called = False

    def mock_start_download(target_item, target_meta):
        nonlocal start_called
        start_called = True
        assert target_item.id == "q1"
        assert target_meta.title == "Test Video"

    monkeypatch.setattr(main_window, "_start_queue_download", mock_start_download)

    main_window._on_metadata_finished()
    assert start_called is True
    assert main_window._pending_queue_download_item_id is None
    assert main_window._pending_queue_metadata is None


def test_download_succeeded_signal_slot_compatibility(main_window):
    item1 = QueueItem(
        id="s1",
        url="https://youtube.com/watch?v=s1",
        platform="YouTube",
        status="İndiriliyor",
    )
    item2 = QueueItem(
        id="s2",
        url="https://youtube.com/watch?v=s2",
        platform="YouTube",
        status="Bekliyor",
    )
    main_window._queue_items = [item1, item2]
    main_window._active_queue_item_id = "s1"
    main_window._is_queue_active = True

    # Calling succeeded slot ONLY updates item status to Tamamlandı
    main_window._on_queue_download_succeeded("C:/path/to/video.mp4")

    assert item1.status == "Tamamlandı"
    assert item1.progress_percent == 100
    assert item1.progress_text == "Başarılı"

    # Item 2 has NOT started yet (waiting for thread finished)
    assert item2.status == "Bekliyor"


def test_thread_finished_advances_queue_and_respects_stop(main_window, monkeypatch):
    item1 = QueueItem(
        id="t1",
        url="https://youtube.com/watch?v=t1",
        platform="YouTube",
        status="Tamamlandı",
    )
    item2 = QueueItem(
        id="t2",
        url="https://youtube.com/watch?v=t2",
        platform="YouTube",
        status="Bekliyor",
    )
    main_window._queue_items = [item1, item2]
    main_window._active_queue_item_id = "t1"
    main_window._is_queue_active = True

    next_started = False

    def mock_start_metadata(item):
        nonlocal next_started
        next_started = True
        assert item.id == "t2"

    monkeypatch.setattr(main_window, "_start_queue_metadata", mock_start_metadata)

    # When thread finished fires and queue is active, it starts next item
    main_window._on_queue_download_thread_finished()
    assert next_started is True
    assert main_window._active_queue_item_id is None

    # When queue is stopped (_is_queue_active = False), thread finished does NOT advance
    next_started = False
    main_window._is_queue_active = False
    main_window._on_queue_download_thread_finished()
    assert next_started is False


def test_queue_settings_controls_and_item_editing(main_window, monkeypatch):
    from pathlib import Path

    from src.queue_dialog import DownloadQueueDialog

    folder_a = Path.home() / "Downloads" / "FolderA"
    folder_b = Path.home() / "Downloads" / "FolderB"

    dlg = DownloadQueueDialog(default_folder=folder_a, parent=main_window)
    dlg.urls_added.connect(main_window._on_queue_urls_added)

    assert dlg.media_combo is not None
    assert dlg.quality_combo is not None
    assert dlg.folder_input is not None
    assert dlg.playlist_checkbox is not None

    # Set custom settings in queue dialog
    dlg.media_combo.setCurrentText("Ses (MP3)")
    dlg.quality_combo.setCurrentText("320 kbps (En iyi)")
    dlg.folder_input.setText(str(folder_a))

    # Add URL using queue dialog settings
    dlg.urls_input.setText("https://www.youtube.com/watch?v=video1")
    dlg._on_add_urls_clicked()

    # Verify QueueItem in main_window acquired these settings
    assert len(main_window._queue_items) == 1
    item1 = main_window._queue_items[0]
    assert item1.media_type == "Ses (MP3)"
    assert item1.quality == "320 kbps (En iyi)"
    assert item1.output_dir == folder_a

    # Now change queue dialog settings and add second URL
    dlg.media_combo.setCurrentText("Video (MP4)")
    dlg.quality_combo.setCurrentText("720p'ye kadar")
    dlg.folder_input.setText(str(folder_b))

    dlg.urls_input.setText("https://www.youtube.com/watch?v=video2")
    dlg._on_add_urls_clicked()

    assert len(main_window._queue_items) == 2
    item2 = main_window._queue_items[1]
    assert item2.media_type == "Video (MP4)"
    assert item2.quality == "720p'ye kadar"
    assert item2.output_dir == folder_b

    # Item 1 original settings must remain unchanged
    assert item1.media_type == "Ses (MP3)"
    assert item1.output_dir == folder_a

    # Edit blocked for active / completed item
    item2.status = "İndiriliyor"
    warn_shown = False

    def mock_warning(*args, **kwargs):
        nonlocal warn_shown
        warn_shown = True

    monkeypatch.setattr("src.queue_dialog.AppMessageDialog.exec", mock_warning)

    dlg.refresh_table(main_window._queue_items)
    dlg.table.selectRow(1)
    dlg._on_edit_clicked()
    assert warn_shown is True
