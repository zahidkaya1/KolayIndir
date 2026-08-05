"""Tests for failed download retry functionality."""

from pathlib import Path

from PySide6.QtWidgets import QDialog

from src.models import DownloadRequest


def create_fake_request():
    return DownloadRequest(
        url="https://youtube.com/watch?v=fake",
        output_dir=Path("fake_dir"),
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
        browser="none",
    )


def test_retry_state_retention(main_window, monkeypatch):
    assert main_window._last_failed_request is None

    # Fake download failure
    fake_req = create_fake_request()

    class FakeWorker:
        request = fake_req

        def cancel(self):
            pass

    main_window._download_worker = FakeWorker()

    # Mock AppMessageDialog to prevent UI blocking
    monkeypatch.setattr(
        "src.main_window.AppMessageDialog.exec",
        lambda self: QDialog.DialogCode.Rejected,
    )

    main_window._on_download_failed("Test error")

    assert main_window._last_failed_request is not None
    assert main_window._last_failed_request.url == "https://youtube.com/watch?v=fake"


def test_retry_state_cleared_on_success(main_window):
    main_window._last_failed_request = create_fake_request()

    main_window._on_download_succeeded("test_file.mp4")

    assert main_window._last_failed_request is None


def test_retry_state_cleared_on_url_change(main_window):
    main_window._last_failed_request = create_fake_request()

    main_window.url_input.setText("https://youtube.com/watch?v=new")

    assert main_window._last_failed_request is None


def test_retry_download_behavior(main_window, monkeypatch):
    fake_req = create_fake_request()
    main_window._last_failed_request = fake_req

    # Monkeypatch start_download to just verify state
    start_called = False

    def mock_start():
        nonlocal start_called
        start_called = True
        assert main_window.url_input.text() == fake_req.url
        assert main_window.media_combo.currentText() == fake_req.media_type
        assert main_window.quality_combo.currentText() == fake_req.quality

    monkeypatch.setattr(main_window, "start_download", mock_start)

    main_window._retry_download()

    assert start_called


def test_retry_download_blocked_if_active(main_window):
    main_window._last_failed_request = create_fake_request()
    main_window._download_worker = object()  # Fake active worker

    main_window._retry_download()

    assert (
        main_window.status_label.text()
        == "Devam eden işlem tamamlanmadan yeniden deneme başlatılamaz."
    )


def test_retry_with_session_switches_to_auto(main_window, monkeypatch):
    fake_req = create_fake_request()
    main_window._last_failed_request = fake_req

    retry_called = False

    def mock_retry():
        nonlocal retry_called
        retry_called = True

    monkeypatch.setattr(main_window, "_retry_download", mock_retry)

    main_window._retry_with_session()

    assert retry_called
    assert main_window.browser_combo.currentData() == "auto"
    assert main_window._preferred_profile is None
    assert main_window._preferred_browser is None


def test_retry_with_session_stops_if_already_auto(main_window, monkeypatch):
    fake_req = DownloadRequest(
        url="https://youtube.com/watch?v=fake",
        output_dir=Path("fake_dir"),
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
        browser="auto",  # Already tried auto
    )
    main_window._last_failed_request = fake_req

    dialog_shown = False

    def mock_exec(self):
        nonlocal dialog_shown
        dialog_shown = True
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("src.main_window.AppMessageDialog.exec", mock_exec)

    retry_called = False

    def mock_retry():
        nonlocal retry_called
        retry_called = True

    monkeypatch.setattr(main_window, "_retry_download", mock_retry)

    main_window._retry_with_session()

    assert dialog_shown
    assert not retry_called
    assert (
        main_window.status_label.text()
        == "Kullanılabilir bir tarayıcı oturumu bulunamadı veya oturum doğrulanamadı."
    )


def test_edit_url_behavior(main_window):
    fake_req = create_fake_request()
    main_window._last_failed_request = fake_req

    main_window._edit_url_after_failure()

    assert main_window.url_input.isEnabled()
    assert main_window.url_input.text() == "https://youtube.com/watch?v=fake"
    assert main_window._last_failed_request is None
    assert main_window.preview_frame.isHidden()
