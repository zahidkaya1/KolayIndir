"""Tests for download rate limiting functionality."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.download_options import build_ydl_options
from src.download_worker import DownloadWorker
from src.models import DownloadRequest, QueueItem
from src.queue_dialog import DownloadQueueDialog, QueueItemEditDialog
from src.settings import load_settings, save_settings
from src.utils import (
    format_rate_limit,
    parse_rate_limit_setting,
    rate_limit_to_bps,
)


class TestRateLimitConversions:
    """Test rate limit conversion and formatting utilities."""

    def test_rate_limit_to_bps_presets(self):
        assert rate_limit_to_bps(512, "KB/sn") == 524288
        assert rate_limit_to_bps(1, "MB/sn") == 1048576
        assert rate_limit_to_bps(2, "MB/sn") == 2097152
        assert rate_limit_to_bps(5, "MB/sn") == 5242880
        assert rate_limit_to_bps(10, "MB/sn") == 10485760

    def test_rate_limit_to_bps_custom(self):
        assert rate_limit_to_bps(2.5, "MB/sn") == int(2.5 * 1024 * 1024)
        assert rate_limit_to_bps(750, "KB/sn") == 750 * 1024

    def test_rate_limit_to_bps_invalid_or_zero(self):
        assert rate_limit_to_bps(0, "MB/sn") is None
        assert rate_limit_to_bps(-5, "MB/sn") is None
        assert rate_limit_to_bps(10, "INVALID") is None
        assert rate_limit_to_bps(None, "MB/sn") is None

    def test_format_rate_limit(self):
        assert format_rate_limit(None) == "Sınırsız"
        assert format_rate_limit(0) == "Sınırsız"
        assert format_rate_limit(524288) == "512 KB/sn"
        assert format_rate_limit(1048576) == "1 MB/sn"
        assert format_rate_limit(2097152) == "2 MB/sn"
        assert format_rate_limit(5242880) == "5 MB/sn"
        assert format_rate_limit(10485760) == "10 MB/sn"
        assert format_rate_limit(int(2.5 * 1024 * 1024)) == "2,5 MB/sn"
        assert format_rate_limit(750 * 1024) == "750 KB/sn"

    def test_parse_rate_limit_setting(self):
        assert parse_rate_limit_setting(1048576) == 1048576
        assert parse_rate_limit_setting(None) is None
        assert parse_rate_limit_setting(0) is None
        assert parse_rate_limit_setting(-100) is None
        assert parse_rate_limit_setting("invalid") is None


class TestRateLimitDownloadOptions:
    """Test yt-dlp options generation with rate limit."""

    def test_build_ydl_options_with_rate_limit(self, tmp_path):
        req = DownloadRequest(
            url="https://example.com/watch?v=123",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="1080p'ye kadar",
            playlist=False,
            browser=None,
            rate_limit_bps=2097152,
        )
        opts = build_ydl_options(req)
        assert opts["ratelimit"] == 2097152
        assert opts.get("concurrent_fragment_downloads") == 4

    def test_build_ydl_options_unlimited(self, tmp_path):
        req = DownloadRequest(
            url="https://example.com/watch?v=123",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="1080p'ye kadar",
            playlist=False,
            browser=None,
            rate_limit_bps=None,
        )
        opts = build_ydl_options(req)
        assert "ratelimit" not in opts
        assert opts.get("concurrent_fragment_downloads") == 4

    def test_download_worker_preserves_rate_limit(self, tmp_path):
        req = DownloadRequest(
            url="https://kick.com/video/123",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            browser=None,
            rate_limit_bps=1048576,
        )
        worker = DownloadWorker(req)
        assert worker.request.rate_limit_bps == 1048576
        opts = build_ydl_options(worker.request)
        assert opts["ratelimit"] == 1048576


class TestRateLimitSettingsPersistence:
    """Test saving and restoring rate limit in settings."""

    def test_save_and_load_rate_limit(self, tmp_path, monkeypatch):
        fake_settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("src.settings.SETTINGS_FILE", fake_settings_file)

        save_settings({"rate_limit_bps": 5242880})
        loaded = load_settings()
        assert loaded.get("rate_limit_bps") == 5242880

    def test_save_and_load_unlimited(self, tmp_path, monkeypatch):
        fake_settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("src.settings.SETTINGS_FILE", fake_settings_file)

        save_settings({"rate_limit_bps": None})
        loaded = load_settings()
        assert loaded.get("rate_limit_bps") is None


class TestRateLimitMainWindowUI:
    """Test MainWindow rate limit controls and interactions."""

    def test_rate_limit_controls_exist(self, main_window):
        assert hasattr(main_window, "rate_limit_combo")
        assert main_window.rate_limit_combo.objectName() == "rateLimitCombo"
        assert hasattr(main_window, "custom_rate_limit_spin")
        assert main_window.custom_rate_limit_spin.objectName() == "customRateLimitSpin"
        assert hasattr(main_window, "custom_rate_limit_unit_combo")
        assert (
            main_window.custom_rate_limit_unit_combo.objectName()
            == "customRateLimitUnitCombo"
        )

    def test_rate_limit_combo_presets(self, main_window):
        # Select 1 MB/sn
        idx = -1
        for i in range(main_window.rate_limit_combo.count()):
            if main_window.rate_limit_combo.itemData(i) == 1048576:
                idx = i
                break
        assert idx >= 0
        main_window.rate_limit_combo.setCurrentIndex(idx)
        assert main_window.get_current_rate_limit_bps() == 1048576
        assert main_window.custom_rate_limit_container.isHidden()

        # Select Sınırsız
        main_window.rate_limit_combo.setCurrentIndex(0)
        assert main_window.get_current_rate_limit_bps() is None
        assert main_window.custom_rate_limit_container.isHidden()

    def test_rate_limit_custom_selection(self, main_window):
        main_window.show()
        # Select Özel...
        idx = -1
        for i in range(main_window.rate_limit_combo.count()):
            if main_window.rate_limit_combo.itemData(i) == "custom":
                idx = i
                break
        assert idx >= 0
        main_window.rate_limit_combo.setCurrentIndex(idx)
        assert not main_window.custom_rate_limit_container.isHidden()

        main_window.custom_rate_limit_unit_combo.setCurrentText("MB/sn")
        main_window.custom_rate_limit_spin.setValue(3.5)
        assert main_window.get_current_rate_limit_bps() == int(3.5 * 1024 * 1024)

        main_window.custom_rate_limit_unit_combo.setCurrentText("KB/sn")
        main_window.custom_rate_limit_spin.setValue(750)
        assert main_window.get_current_rate_limit_bps() == 750 * 1024

    def test_rate_limit_restore_setting(self, main_window):
        # Preset restore
        main_window._restore_rate_limit_setting(2097152)
        assert main_window.rate_limit_combo.currentData() == 2097152
        assert main_window.custom_rate_limit_container.isHidden()

        # Custom MB restore
        main_window._restore_rate_limit_setting(int(4.5 * 1024 * 1024))
        assert main_window.rate_limit_combo.currentData() == "custom"
        assert not main_window.custom_rate_limit_container.isHidden()
        assert main_window.custom_rate_limit_unit_combo.currentText() == "MB/sn"
        assert main_window.custom_rate_limit_spin.value() == 4.5

        # Unlimited restore
        main_window._restore_rate_limit_setting(None)
        assert main_window.rate_limit_combo.currentData() is None
        assert main_window.custom_rate_limit_container.isHidden()


class TestRateLimitQueueIntegration:
    """Test queue item rate limiting and dialogs."""

    def test_queue_item_model_rate_limit(self):
        item = QueueItem(
            id="test-1",
            url="https://youtube.com/watch?v=123",
            platform="YouTube",
            media_type="Video (MP4)",
            quality="1080p'ye kadar",
            playlist=False,
            output_dir=Path("C:/Downloads"),
            browser=None,
            rate_limit_bps=1048576,
        )
        assert item.rate_limit_bps == 1048576

    def test_queue_dialog_table_columns(self, qapp):
        dialog = DownloadQueueDialog(default_folder=Path.home() / "Downloads")
        assert dialog.table.columnCount() == 8
        headers = [dialog.table.horizontalHeaderItem(i).text() for i in range(8)]
        assert "Hız Sınırı" in headers
        assert headers[4] == "Hız Sınırı"

        item = QueueItem(
            id="q1",
            url="https://youtube.com/watch?v=123",
            platform="YouTube",
            media_type="Video (MP4)",
            quality="1080p'ye kadar",
            playlist=False,
            output_dir=Path.home() / "Downloads",
            browser=None,
            rate_limit_bps=2097152,
        )
        dialog.refresh_table([item])
        rate_item = dialog.table.item(0, 4)
        assert rate_item is not None
        assert rate_item.text() == "2 MB/sn"

        dialog.close()
        dialog.deleteLater()
        QApplication.processEvents()

    def test_queue_edit_dialog_rate_limit(self, qapp):
        item = QueueItem(
            id="q2",
            url="https://youtube.com/watch?v=456",
            platform="YouTube",
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            output_dir=Path.home() / "Downloads",
            browser=None,
            rate_limit_bps=524288,
        )
        edit_dlg = QueueItemEditDialog(item)
        assert edit_dlg.rate_limit_combo.currentData() == 524288

        # Change to 5 MB/sn
        idx = -1
        for i in range(edit_dlg.rate_limit_combo.count()):
            if edit_dlg.rate_limit_combo.itemData(i) == 5242880:
                idx = i
                break
        edit_dlg.rate_limit_combo.setCurrentIndex(idx)
        edit_dlg._save()
        assert item.rate_limit_bps == 5242880

        edit_dlg.close()
        edit_dlg.deleteLater()
        QApplication.processEvents()
