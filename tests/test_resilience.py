import json
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.dependency_check import (
    check_environment,
    dependency_warnings,
    get_environment_log_lines,
)
from src.dialogs import DownloadCompletedDialog, UpdateAvailableDialog
from src.download_options import build_ydl_options
from src.main_window import MainWindow
from src.models import DownloadRequest
from src.settings import load_settings, save_settings
from src.styles import APP_STYLE
from src.utils import clean_log_message, is_chrome_cookie_error, strip_ansi


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
    assert "%(playlist_title,playlist)s" in playlist_opts["outtmpl"]


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
