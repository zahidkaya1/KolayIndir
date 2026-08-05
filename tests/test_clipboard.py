"""Tests for the clipboard functionality."""

from src.utils import extract_supported_url_from_text


def test_extract_supported_url_empty():
    assert extract_supported_url_from_text("") is None
    assert extract_supported_url_from_text(None) is None


def test_extract_supported_url_plain():
    assert (
        extract_supported_url_from_text("https://youtube.com/watch?v=abc")
        == "https://youtube.com/watch?v=abc"
    )
    assert (
        extract_supported_url_from_text("https://youtu.be/abc")
        == "https://youtu.be/abc"
    )
    assert (
        extract_supported_url_from_text("https://www.instagram.com/reel/abc/")
        == "https://www.instagram.com/reel/abc/"
    )
    assert (
        extract_supported_url_from_text("https://x.com/abc/status/123")
        == "https://x.com/abc/status/123"
    )
    assert (
        extract_supported_url_from_text("https://twitter.com/abc/status/123")
        == "https://twitter.com/abc/status/123"
    )
    assert (
        extract_supported_url_from_text("https://vm.tiktok.com/abc/")
        == "https://vm.tiktok.com/abc/"
    )


def test_extract_supported_url_in_text():
    text = "Şuna bak: https://youtube.com/watch?v=abc çok iyi"
    assert extract_supported_url_from_text(text) == "https://youtube.com/watch?v=abc"


def test_extract_supported_url_trailing_punctuation():
    assert (
        extract_supported_url_from_text("Video: https://youtube.com/watch?v=abc.")
        == "https://youtube.com/watch?v=abc"
    )
    assert (
        extract_supported_url_from_text("(https://www.instagram.com/reel/abc/)")
        == "https://www.instagram.com/reel/abc/"
    )
    assert (
        extract_supported_url_from_text("Link: https://vm.tiktok.com/abc/, baksana")
        == "https://vm.tiktok.com/abc/"
    )
    assert (
        extract_supported_url_from_text("'https://youtube.com/watch?v=abc'")
        == "https://youtube.com/watch?v=abc"
    )
    assert (
        extract_supported_url_from_text('"https://youtube.com/watch?v=abc"')
        == "https://youtube.com/watch?v=abc"
    )


def test_extract_supported_url_unsupported():
    assert extract_supported_url_from_text("https://example.com/test") is None
    assert extract_supported_url_from_text("Sadece normal bir metin") is None


def test_extract_supported_url_kick_rejected():
    assert (
        extract_supported_url_from_text("https://kick.com/test/videos/12345678") is None
    )


def test_extract_supported_url_multiple():
    text = "Önce bu https://example.com/test sonra bu https://youtube.com/watch?v=abc ve bu https://tiktok.com/video/123"
    # Should pick the first SUPPORTED one
    assert extract_supported_url_from_text(text) == "https://youtube.com/watch?v=abc"


def test_ui_paste_button_exists(main_window):
    assert hasattr(main_window, "paste_button")
    assert main_window.paste_button.text() == "Panodan Yapıştır"


def test_ui_paste_valid_url(main_window, qapp, monkeypatch):
    clipboard = qapp.clipboard()
    old_text = clipboard.text()

    try:
        clipboard.setText("https://youtube.com/watch?v=abc")

        # Monkeypatch analyze_url to track if it's called
        analyze_called = False

        def mock_analyze():
            nonlocal analyze_called
            analyze_called = True

        monkeypatch.setattr(main_window, "analyze_url", mock_analyze)

        main_window.paste_button.click()

        # Verify URL is pasted but analysis doesn't auto-start
        assert main_window.url_input.text() == "https://youtube.com/watch?v=abc"
        assert not analyze_called
        assert main_window.status_label.text() == "Bağlantı panodan yapıştırıldı."
    finally:
        clipboard.setText(old_text)


def test_ui_paste_invalid_url_does_not_clear(main_window, qapp):
    clipboard = qapp.clipboard()
    old_text = clipboard.text()

    try:
        main_window.url_input.setText("https://youtube.com/watch?v=old")
        clipboard.setText("https://example.com/unsupported")

        main_window.paste_button.click()

        assert main_window.url_input.text() == "https://youtube.com/watch?v=old"
        assert main_window.status_label.text() == "Bu bağlantı henüz desteklenmiyor."
    finally:
        clipboard.setText(old_text)


def test_ui_paste_empty_clipboard(main_window, qapp):
    clipboard = qapp.clipboard()
    old_text = clipboard.text()

    try:
        clipboard.setText("")
        main_window.paste_button.click()
        assert main_window.status_label.text() == "Panoda bir bağlantı bulunamadı."
    finally:
        clipboard.setText(old_text)
