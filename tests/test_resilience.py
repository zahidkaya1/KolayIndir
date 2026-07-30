import json
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox

from src.dependency_check import (
    check_environment,
    dependency_warnings,
    get_environment_log_lines,
)
from src.dialogs import (
    AppMessageDialog,
    DownloadCompletedDialog,
    UpdateAvailableDialog,
)
from src.download_options import build_ydl_options
from src.main_window import MainWindow
from src.models import DownloadRequest
from src.settings import load_settings, save_settings
from src.styles import APP_STYLE
from src.utils import (
    clean_log_message,
    is_chrome_cookie_error,
    set_combo_value,
    strip_ansi,
)


def test_strip_ansi():
    ansi_text = "\x1b[0;31mERROR:\x1b[0m \033[32mDownload failed\033[0m"
    cleaned = strip_ansi(ansi_text)
    assert cleaned == "ERROR: Download failed"


def test_clean_log_message_nested_prefixes():
    raw_message = "\x1b[31mHata: ERROR: ERROR: [youtube] Could not copy Chrome cookie database\x1b[0m"
    cleaned = clean_log_message(raw_message)
    assert cleaned == "Hata: [youtube] Could not copy Chrome cookie database"


def test_clean_log_message_empty():
    assert clean_log_message("   \x1b[0m   ") == ""


def test_chrome_cookie_error_detection():
    err1 = "[youtube] Could not copy Chrome cookie database"
    err2 = "Uyarı: \x1b[0;31mCould not copy Chrome cookie database\x1b[0m"
    err3 = "Normal indirme hatası: HTTP 404"

    assert is_chrome_cookie_error(err1) is True
    assert is_chrome_cookie_error(err2) is True
    assert is_chrome_cookie_error(err3) is False


@patch("shutil.which")
def test_ffmpeg_missing_check(mock_which):
    mock_which.side_effect = (
        lambda cmd: None if cmd in {"ffmpeg", "ffprobe"} else "/usr/bin/" + cmd
    )

    env = check_environment()
    assert env["ffmpeg"] is False
    assert env["ffprobe"] is False

    warnings = dependency_warnings()
    assert any("FFmpeg" in w for w in warnings)


@patch("shutil.which")
def test_environment_log_lines(mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd
    lines = get_environment_log_lines()
    assert any("FFmpeg: Hazır" in l for l in lines)
    assert any("yt-dlp:" in l for l in lines)


def test_browser_and_playlist_settings_not_persisted(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    settings_file.write_text(
        '{"output_dir": "'
        + str(tmp_path).replace("\\", "\\\\")
        + '", "browser": "chrome", "playlist": true}',
        encoding="utf-8",
    )

    loaded = load_settings()
    assert "browser" not in loaded
    assert "playlist" not in loaded

    save_settings({
        "output_dir": str(tmp_path),
        "browser": "chrome",
        "playlist": True,
        "media_type": "Video (MP4)",
    })
    reloaded_dict = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "chrome" not in reloaded_dict.values()
    assert "browser" not in reloaded_dict
    assert "playlist" not in reloaded_dict


def test_default_folder_is_downloads(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    loaded = load_settings()
    assert loaded["output_dir"] == str(Path.home() / "Downloads")


def test_non_existent_folder_falls_back_to_downloads(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    invalid_path = tmp_path / "non_existent_folder_12345"
    settings_file.write_text(
        '{"output_dir": "' + str(invalid_path).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )

    loaded = load_settings()
    assert loaded["output_dir"] == str(Path.home() / "Downloads")


def test_save_and_load_auto_open_folder(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    save_settings({"output_dir": str(tmp_path), "auto_open_folder": True})
    loaded = load_settings()
    assert loaded["auto_open_folder"] is True
    assert loaded["output_dir"] == str(tmp_path)


def test_single_video_vs_playlist_output_template(tmp_path):
    single_req = DownloadRequest(
        url="https://example.com/watch?v=123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p",
        playlist=False,
        browser=None,
    )
    single_opts = build_ydl_options(single_req)
    assert (
        single_opts["outtmpl"]
        == str(tmp_path / "%(title)s [%(id)s].%(ext)s")
    )

    playlist_req = DownloadRequest(
        url="https://example.com/playlist?list=123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p",
        playlist=True,
        browser=None,
    )
    playlist_opts = build_ydl_options(playlist_req)
    assert "%(playlist_title,playlist" in playlist_opts["outtmpl"]



def test_download_request_retry_without_browser(tmp_path):
    initial_request = DownloadRequest(
        url="https://example.com/watch?v=123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p",
        playlist=True,
        browser="chrome",
    )

    initial_options = build_ydl_options(initial_request)
    assert initial_options.get("cookiesfrombrowser") == ("chrome",)

    retry_request = DownloadRequest(
        url=initial_request.url,
        output_dir=initial_request.output_dir,
        media_type=initial_request.media_type,
        quality=initial_request.quality,
        playlist=initial_request.playlist,
        browser=None,
    )

    retry_options = build_ydl_options(retry_request)
    assert "cookiesfrombrowser" not in retry_options
    assert retry_request.url == initial_request.url
    assert retry_request.output_dir == initial_request.output_dir
    assert retry_request.media_type == initial_request.media_type
    assert retry_request.quality == initial_request.quality
    assert retry_request.playlist == initial_request.playlist


def test_dialog_and_menu_style_selectors_exist():
    required_selectors = [
        "QMenu#folderMenu",
        "QMenu",
        "QDialog#downloadCompletedDialog",
        "QDialog#updateDialog",
        "QLabel#dialogTitleLabel",
        "QLabel#dialogMessageLabel",
        "QPushButton#dialogPrimaryButton",
        "QPushButton#dialogSecondaryButton",
        "QPushButton#updateButton",
        "QLabel#updateDialogTitle",
        "QLabel#updateDialogMessage",
    ]
    for selector in required_selectors:
        assert selector in APP_STYLE


def test_download_completed_dialog_texts():
    _app = QApplication.instance() or QApplication([])
    dlg = DownloadCompletedDialog("Örnek Video [123]")

    assert dlg.objectName() == "downloadCompletedDialog"
    assert dlg.windowTitle() == "İndirme tamamlandı"
    assert dlg.title_label.objectName() == "dialogTitleLabel"
    assert dlg.title_label.text() == "İçerik başarıyla indirildi."
    assert dlg.message_label.objectName() == "dialogMessageLabel"
    assert "İndirme klasörünü açmak ister misiniz?" in dlg.message_label.text()
    assert dlg.primary_button.objectName() == "dialogPrimaryButton"
    assert dlg.primary_button.text() == "Klasörü Aç"
    assert dlg.secondary_button.objectName() == "dialogSecondaryButton"
    assert dlg.secondary_button.text() == "Kapat"


def test_update_available_dialog_texts():
    _app = QApplication.instance() or QApplication([])
    dlg = UpdateAvailableDialog("v2.0.0", "Hata düzeltmeleri eklendi.")

    assert dlg.objectName() == "updateDialog"
    assert dlg.windowTitle() == "Yeni Sürüm Bulundu"
    assert dlg.title_label.objectName() == "updateDialogTitle"
    assert dlg.primary_button.objectName() == "dialogPrimaryButton"
    assert dlg.primary_button.text() == "Güncelleme sayfasını aç"
    assert dlg.secondary_button.objectName() == "dialogSecondaryButton"
    assert dlg.secondary_button.text() == "Kapat"


def test_main_window_object_names():
    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    assert win.folder_button.menu().objectName() == "folderMenu"
    assert win.update_button.objectName() == "updateButton"


def test_http_user_agent_ascii_only():
    from src.config import APP_NAME, HTTP_USER_AGENT

    assert APP_NAME == "Kolayİndir"
    assert "İ" not in HTTP_USER_AGENT
    assert HTTP_USER_AGENT.isascii() is True


@patch("src.updater.urlopen")
def test_updater_release_not_found_404(mock_urlopen):
    from urllib.error import HTTPError

    from src.updater import UpdateWorker

    mock_urlopen.side_effect = HTTPError("url", 404, "Not Found", {}, None)

    worker = UpdateWorker()
    no_release_signal_received = False

    def handler():
        nonlocal no_release_signal_received
        no_release_signal_received = True

    worker.no_release_found.connect(handler)
    worker.run()

    assert no_release_signal_received is True


def test_combo_boxes_object_names_and_defaults(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    assert win.media_combo.objectName() == "mediaTypeCombo"
    assert win.quality_combo.objectName() == "qualityCombo"
    assert win.browser_combo.objectName() == "browserCombo"

    assert win.media_combo.currentText() == "Video (MP4)"
    assert win.quality_combo.currentText() == "En iyi kullanılabilir kalite"
    assert win.browser_combo.currentText() == "Otomatik oturum"



def test_invalid_settings_media_and_quality_fallback(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    settings_file.write_text(
        '{"media_type": "GeçersizTÜR", "quality": "GeçersizKalite"}',
        encoding="utf-8",
    )

    loaded = load_settings()
    assert loaded["media_type"] == "Video (MP4)"
    assert loaded["quality"] == "En iyi kullanılabilir kalite"


def test_app_style_contains_combobox_selectors():
    assert "QComboBox" in APP_STYLE
    assert "QComboBox QAbstractItemView" in APP_STYLE
    assert "selection-color" in APP_STYLE
    assert "selection-background-color" in APP_STYLE
    assert "min-height: 38px;" in APP_STYLE
    assert "QLineEdit, QTextEdit" in APP_STYLE
    assert "QLineEdit, QComboBox, QTextEdit" not in APP_STYLE


def test_fusion_style_and_combo_box_heights(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    assert app.style().objectName().lower() == "fusion"

    win = MainWindow()
    for combo in (win.media_combo, win.quality_combo, win.browser_combo):
        assert combo.minimumHeight() >= 38
        assert combo.currentIndex() >= 0
        assert bool(combo.currentText()) is True


def test_set_combo_value_fallback():
    _app = QApplication.instance() or QApplication([])
    combo = QComboBox()
    combo.addItems(["A", "B", "C"])

    set_combo_value(combo, "B")
    assert combo.currentIndex() == 1

    set_combo_value(combo, "GEÇERSİZ")
    assert combo.currentIndex() == 0


def test_fixed_window_structure_and_dimensions(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    flags = win.windowFlags()
    assert bool(flags & Qt.WindowType.WindowCloseButtonHint) is True
    assert bool(flags & Qt.WindowType.WindowMinimizeButtonHint) is True
    assert bool(flags & Qt.WindowType.WindowTitleHint) is True
    assert bool(flags & Qt.WindowType.WindowSystemMenuHint) is True
    assert bool(flags & Qt.WindowType.FramelessWindowHint) is False
    assert bool(flags & Qt.WindowType.WindowMaximizeButtonHint) is False
    assert win.width() == 710
    assert win.height() == 650
    assert win.minimumWidth() == 710
    assert win.minimumHeight() == 650
    assert hasattr(win, "tech_details_button") is True




def test_dialogs_max_width_constraints():
    _app = QApplication.instance() or QApplication([])
    dlg1 = DownloadCompletedDialog("Summary")
    dlg2 = UpdateAvailableDialog("v1.0.0", "Notes")
    dlg3 = AppMessageDialog("Title", "Message")

    assert dlg1.maximumWidth() <= 600
    assert dlg2.maximumWidth() <= 600
    assert dlg3.maximumWidth() <= 600


@patch("src.main_window.check_environment")
def test_download_worker_log_signal_and_main_window_connections(
    mock_check_env, tmp_path, monkeypatch
):
    from src.download_worker import DownloadWorker
    from src.models import DownloadRequest

    mock_check_env.return_value = {
        "ffmpeg": True,
        "ffprobe": True,
        "deno": True,
        "yt_dlp": True,
    }

    req = DownloadRequest(
        url="https://example.com/watch?v=123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p",
        playlist=False,
        browser=None,
    )
    worker = DownloadWorker(req)

    assert hasattr(worker, "log") is True
    assert hasattr(worker, "log_message") is False
    assert hasattr(worker, "succeeded") is True
    assert hasattr(worker, "failed") is True
    assert hasattr(worker, "cancelled") is True
    assert hasattr(worker, "status") is True
    assert hasattr(worker, "progress") is True

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.url_input.setText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    win.folder_input.setText(str(tmp_path))

    with patch.object(DownloadWorker, "run"):
        win.start_download()
        assert win._download_worker is not None
        assert hasattr(win._download_worker, "log") is True
        if win._download_thread:
            win._download_thread.quit()
            win._download_thread.wait(1000)


def test_format_bytes_and_duration():
    from src.models import format_bytes, format_duration

    assert format_bytes(None) == "Hesaplanamadı"
    assert format_bytes(0) == "Hesaplanamadı"
    assert format_bytes(512 * 1024) == "512 KB"
    assert format_bytes(18.4 * 1024 * 1024) == "18,4 MB"
    assert format_bytes(1.25 * 1024 * 1024 * 1024) == "1,25 GB"

    assert format_duration(None) == ""
    assert format_duration(45) == "00:45"
    assert format_duration(163) == "02:43"
    assert format_duration(3665) == "01:01:05"


def test_parse_max_height_and_estimated_size():
    from src.metadata_worker import _calculate_estimated_size, _parse_max_height

    formats = [
        {"vcodec": "none", "height": 720},
        {"vcodec": "avc1.4d401f", "height": 480},
        {"vcodec": "vp9", "height": 360},
    ]
    assert _parse_max_height(formats) == 480

    info_direct = {"filesize": 18400000}
    assert _calculate_estimated_size(info_direct) == 18400000

    info_req_formats = {
        "requested_formats": [
            {"filesize": 15000000},
            {"filesize": 3400000},
        ]
    }
    assert _calculate_estimated_size(info_req_formats) == 18400000

    info_none = {}
    assert _calculate_estimated_size(info_none) is None


def test_metadata_worker_quality_selection_logic():
    from src.metadata_worker import MetadataWorker

    mw = MetadataWorker("https://example.com/watch?v=123", "1080p’ye kadar")
    raw_info = {
        "title": "Örnek Video",
        "uploader": "Test Kanalı",
        "extractor": "youtube",
        "duration": 120,
        "formats": [
            {"vcodec": "avc1.4d401f", "height": 480},
            {"vcodec": "avc1.4d4015", "height": 360},
        ],
    }
    meta = mw._build_metadata(raw_info)
    assert meta.maximum_available_height == 480
    assert meta.selected_height == 480
    assert meta.selected_resolution == "480p"


def test_quality_settings_migration(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    settings_file.write_text(
        '{"quality": "1080p", "media_type": "Video (MP4)"}',
        encoding="utf-8",
    )

    loaded = load_settings()
    assert loaded["quality"] == "1080p’ye kadar"


def test_metadata_worker_signals():
    from src.metadata_worker import MetadataWorker

    mw = MetadataWorker("https://example.com")
    assert hasattr(mw, "metadata_ready") is True
    assert hasattr(mw, "thumbnail_ready") is True
    assert hasattr(mw, "status") is True
    assert hasattr(mw, "failed") is True
    assert hasattr(mw, "finished") is True


def test_download_worker_progress_details_signal(tmp_path):
    from src.download_worker import DownloadWorker
    from src.models import DownloadRequest

    req = DownloadRequest(
        url="https://example.com/watch?v=123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p’ye kadar",
        playlist=False,
    )
    worker = DownloadWorker(req)
    assert hasattr(worker, "progress_details") is True

    received_details = []
    worker.progress_details.connect(lambda d: received_details.append(d))

    worker._progress_hook({
        "status": "downloading",
        "downloaded_bytes": 500000,
        "total_bytes": 1000000,
        "speed": 100000,
        "eta": 5,
        "filename": "video.mp4",
    })

    assert len(received_details) == 1
    assert received_details[0]["percent"] == 50
    assert received_details[0]["downloaded_bytes"] == 500000
    assert received_details[0]["total_bytes"] == 1000000


def test_option_cards_structure_and_clicking(tmp_path, monkeypatch):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    assert win.playlist_card.objectName() == "playlistOptionCard"
    assert win.auto_open_card.objectName() == "autoOpenOptionCard"

    assert win.playlist_checkbox.objectName() == "playlistCheckBox"
    assert win.auto_open_checkbox.objectName() == "autoOpenCheckBox"

    assert bool(win.playlist_checkbox.text()) is True
    assert bool(win.auto_open_checkbox.text()) is True

    assert "playlistOptionCard" in APP_STYLE
    assert "autoOpenOptionCard" in APP_STYLE
    assert 'optionCard="true"' in APP_STYLE

    assert win.playlist_checkbox.isChecked() is False
    click_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        QPointF(5, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    win.playlist_card.mousePressEvent(click_event)
    assert win.playlist_checkbox.isChecked() is True

    win.auto_open_checkbox.setChecked(True)
    loaded = load_settings()
    assert loaded.get("auto_open_folder") is True
    assert "playlist" not in loaded


def test_close_event_when_idle(tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    event = QCloseEvent()
    win.closeEvent(event)
    assert event.isAccepted() is True


@patch.object(AppMessageDialog, "exec")
def test_close_event_when_active_and_canceled(mock_dialog_exec, tmp_path, monkeypatch):
    from PySide6.QtCore import QThread
    from PySide6.QtGui import QCloseEvent

    from src.dialogs import AppMessageDialog
    from src.download_worker import DownloadWorker
    from src.models import DownloadRequest

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    req = DownloadRequest(
        url="https://example.com/watch?v=123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p’ye kadar",
        playlist=False,
    )
    win._download_worker = DownloadWorker(req)
    win._download_thread = QThread()

    def mock_exec_no(*args, **kwargs):
        for widget in win.findChildren(AppMessageDialog):
            widget.clicked_button_id = "no"
        return 0

    def mock_exec_yes(*args, **kwargs):
        for widget in win.findChildren(AppMessageDialog):
            widget.clicked_button_id = "yes"
        return 1


    mock_dialog_exec.side_effect = mock_exec_no
    event = QCloseEvent()
    win.closeEvent(event)
    assert event.isAccepted() is False
    assert win._close_requested is False

    mock_dialog_exec.side_effect = mock_exec_yes
    event2 = QCloseEvent()
    win.closeEvent(event2)
    assert event2.isAccepted() is False
    assert win._close_requested is True



def test_reset_after_successful_download(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    win.url_input.setText("https://www.youtube.com/watch?v=123")
    win.preview_frame.show()
    win.progress_bar.setValue(80)
    win.status_label.setText("İndiriliyor")
    win.stats_label.setText("10 MB / 20 MB")
    win.playlist_checkbox.setChecked(True)
    win.browser_combo.setCurrentIndex(1)
    folder_before = win.folder_input.text()

    win._reset_after_successful_download()

    assert win.url_input.text() == ""
    assert win.preview_frame.isHidden() is True
    assert win.progress_bar.value() == 0
    assert win.status_label.text() == "Hazır"
    assert win.stats_label.text() == ""
    assert win.playlist_checkbox.isChecked() is False
    assert win.browser_combo.currentIndex() == 0
    assert win.folder_input.text() == folder_before
    assert win.media_combo.currentText() == "Video (MP4)"


@patch.object(AppMessageDialog, "exec")
def test_error_preserves_url_and_preview(mock_dialog_exec, tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    win.url_input.setText("https://www.youtube.com/watch?v=123")
    win.preview_frame.show()

    win._on_download_failed("HTTP 404")

    assert win.url_input.text() == "https://www.youtube.com/watch?v=123"
    assert win.preview_frame.isHidden() is False
    assert "İndirme başarısız" in win.status_label.text()
    assert win.download_button.isEnabled() is True
    assert win.cancel_button.isEnabled() is False


def test_platform_type_detection():
    from src.models import PlatformType, detect_platform_type, get_platform_badge_text

    assert detect_platform_type("https://twitter.com/user/status/123") == PlatformType.TWITTER_POST
    assert detect_platform_type("https://x.com/user/status/456") == PlatformType.TWITTER_POST
    assert detect_platform_type("https://www.instagram.com/reel/C123456/") == PlatformType.INSTAGRAM_REEL
    assert detect_platform_type("https://www.instagram.com/p/B98765/") == PlatformType.INSTAGRAM_POST
    assert detect_platform_type("https://www.instagram.com/stories/username/123456/") == PlatformType.INSTAGRAM_STORY
    assert detect_platform_type("https://www.instagram.com/stories/highlights/987654/") == PlatformType.INSTAGRAM_HIGHLIGHT
    assert detect_platform_type("https://www.youtube.com/watch?v=abc") == PlatformType.YOUTUBE_VIDEO

    assert get_platform_badge_text(PlatformType.TWITTER_POST) == "X / Twitter"
    assert get_platform_badge_text(PlatformType.INSTAGRAM_REEL) == "Instagram Reel"
    assert get_platform_badge_text(PlatformType.INSTAGRAM_POST) == "Instagram Gönderisi"
    assert get_platform_badge_text(PlatformType.INSTAGRAM_STORY) == "Instagram Hikâyesi"
    assert get_platform_badge_text(PlatformType.INSTAGRAM_HIGHLIGHT) == "Instagram Öne Çıkan"


def test_translate_social_error():
    from src.models import translate_social_error

    err1 = translate_social_error("This tweet is from a protected account.", "https://x.com/user/status/123")
    assert "korumalı bir hesaba ait" in err1

    err2 = translate_social_error("Did not find any video stream", "https://x.com/user/status/456")
    assert "indirilebilir video bulunamadı" in err2

    err3 = translate_social_error("Instagram error: Please log in to view this story", "https://www.instagram.com/stories/user/123")
    assert "Instagram oturumu gerekiyor" in err3

    err4 = translate_social_error("This post only contains photos", "https://www.instagram.com/p/123")
    assert "Fotoğraf indirme desteği henüz eklenmedi" in err4

    err5 = translate_social_error("Login required to view this reel", "https://www.instagram.com/reel/123")
    assert "Firefox oturumunu seçip yeniden deneyin" in err5


def test_multi_media_auto_check_playlist(tmp_path, monkeypatch):
    from src.models import MediaMetadata, PlatformType

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    meta = MediaMetadata(
        title="Carousel Post",
        uploader="insta_user",
        is_playlist=True,
        playlist_count=3,
        platform_type=PlatformType.INSTAGRAM_POST,
    )
    win._on_metadata_ready(meta)

    assert win.platform_badge_label.text() == "Instagram Gönderisi"
    assert win.playlist_checkbox.isChecked() is True
    assert "3 indirilebilir video var" in win.meta_badges_label.text()


def test_720p_source_limit_display(tmp_path, monkeypatch):
    from src.models import MediaMetadata, PlatformType

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    meta = MediaMetadata(
        title="Sample Video",
        uploader="x_user",
        maximum_available_height=720,
        selected_height=720,
        selected_resolution="720p",
        selected_extension="mp4",
        platform_type=PlatformType.TWITTER_POST,
    )
    win._on_metadata_ready(meta)

    assert win.platform_badge_label.text() == "X / Twitter"
    assert "Kaynak: 720p" in win.meta_badges_label.text()
    assert "İndirilecek: 720p" in win.meta_badges_label.text()


def test_download_worker_cancel_raises_download_cancelled(tmp_path):
    from src.download_worker import DownloadCancelled, DownloadWorker

    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="En iyi",
        playlist=False,
    )
    worker = DownloadWorker(req)

    # Test initial state
    assert worker._cancel_requested is False
    assert worker._active_process is None

    # Call cancel
    worker.cancel()
    assert worker._cancel_requested is True

    # Calling cancel again should be idempotent
    worker.cancel()
    assert worker._cancel_requested is True

    # Progress hook should raise DownloadCancelled
    import pytest
    with pytest.raises(DownloadCancelled):
        worker._progress_hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})


def test_cancel_download_idempotent(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    # Before start
    assert win._cancel_requested is False

    # Calling cancel when idle
    win.cancel_download()
    assert win._cancel_requested is True

    # Repeat call
    win.cancel_download()
    assert win._cancel_requested is True


def test_close_event_asynchronous_with_timer(tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    # Mock active thread
    win._download_thread = "fake_thread"

    # Mock user accepting dialog
    with patch("src.main_window.AppMessageDialog") as mock_dlg_cls:
        mock_dlg = mock_dlg_cls.return_value
        mock_dlg.exec.return_value = 1  # Accepted
        mock_dlg.clicked_button_id = "yes"

        event = QCloseEvent()
        win.closeEvent(event)

        assert event.isAccepted() is False
        assert win._pending_close is True
        assert win._shutdown_in_progress is True
        assert win._force_close_timer is not None
        win._force_close_timer.stop()








