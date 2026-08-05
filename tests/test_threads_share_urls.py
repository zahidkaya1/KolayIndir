from unittest.mock import MagicMock, patch

import pytest
from yt_dlp.utils import ExtractorError

from src.models import PlatformType, detect_platform_type
from src.threads_extractor import ThreadsIE


def test_threads_share_url_detection():
    # Valid urls
    assert (
        detect_platform_type("https://threads.com/share/BBYbNlJBF3")
        == PlatformType.THREADS
    )
    assert (
        detect_platform_type("https://www.threads.com/share/BBYbNlJBF3/")
        == PlatformType.THREADS
    )
    assert (
        detect_platform_type("https://threads.net/share/TOKEN123")
        == PlatformType.THREADS
    )
    assert (
        detect_platform_type("https://www.threads.net/share/TOKEN_123?abc=1")
        == PlatformType.THREADS
    )

    # Invalid urls
    assert detect_platform_type("https://threads.com/share/") == PlatformType.UNKNOWN
    assert (
        detect_platform_type("https://threads.com/share/invalid!@#")
        == PlatformType.UNKNOWN
    )


@patch("src.threads_extractor.ThreadsIE._download_webpage_handle")
def test_threads_share_url_extractor_redirect(mock_download):
    # Simulate a successful HTTP redirect without parsing HTML
    mock_urlh = MagicMock()
    mock_urlh.geturl.return_value = "https://www.threads.net/@user/post/12345"
    mock_download.return_value = ("", mock_urlh)

    ydl = MagicMock()
    ie = ThreadsIE(ydl)

    result = ie._real_extract("https://www.threads.net/share/BBYbNlJBF3")
    assert result["_type"] == "url"
    assert result["url"] == "https://www.threads.net/@user/post/12345"
    assert result["ie_key"] == "Threads"


@patch("src.threads_extractor.ThreadsIE._download_webpage_handle")
def test_threads_share_url_extractor_canonical_meta(mock_download):
    # Simulate no redirect, but HTML has canonical URL
    mock_urlh = MagicMock()
    mock_urlh.geturl.return_value = "https://www.threads.net/share/BBYbNlJBF3"

    html = """
    <html>
        <head>
            <meta property="og:url" content="https://www.threads.net/@user/post/12345" />
        </head>
    </html>
    """
    mock_download.return_value = (html, mock_urlh)

    ydl = MagicMock()
    ie = ThreadsIE(ydl)

    result = ie._real_extract("https://www.threads.net/share/BBYbNlJBF3")
    assert result["_type"] == "url"
    assert result["url"] == "https://www.threads.net/@user/post/12345"


@patch("src.threads_extractor.ThreadsIE._download_webpage_handle")
def test_threads_share_url_extractor_canonical_link(mock_download):
    # Simulate no redirect, no og:url, but <link rel="canonical">
    mock_urlh = MagicMock()
    mock_urlh.geturl.return_value = "https://www.threads.net/share/BBYbNlJBF3"

    html = """
    <html>
        <head>
            <link rel="canonical" href="https://www.threads.net/@user/post/12345" />
        </head>
    </html>
    """
    mock_download.return_value = (html, mock_urlh)

    ydl = MagicMock()
    ie = ThreadsIE(ydl)

    result = ie._real_extract("https://www.threads.net/share/BBYbNlJBF3")
    assert result["_type"] == "url"
    assert result["url"] == "https://www.threads.net/@user/post/12345"


@patch("src.threads_extractor.ThreadsIE._download_webpage_handle")
def test_threads_share_url_extractor_rate_limit(mock_download):
    mock_download.side_effect = ExtractorError("HTTP Error 429: Too Many Requests")

    ydl = MagicMock()
    ie = ThreadsIE(ydl)

    with pytest.raises(ExtractorError) as exc_info:
        ie._real_extract("https://www.threads.net/share/BBYbNlJBF3")

    assert "geçici olarak sınırlandırdı" in str(exc_info.value)


@patch("src.threads_extractor.ThreadsIE._download_webpage_handle")
def test_threads_share_url_extractor_login_required(mock_download):
    mock_urlh = MagicMock()
    mock_urlh.geturl.return_value = "https://www.threads.net/login/"
    mock_download.return_value = (
        "<html><title>Threads • Log In</title></html>",
        mock_urlh,
    )

    ydl = MagicMock()
    ie = ThreadsIE(ydl)

    with pytest.raises(ExtractorError) as exc_info:
        ie._real_extract("https://www.threads.net/share/BBYbNlJBF3")

    assert "tarayıcı oturumu gerekebilir" in str(exc_info.value)


@patch("src.threads_extractor.ThreadsIE._download_webpage_handle")
def test_threads_share_url_extractor_external_domain(mock_download):
    # Simulate redirect to external domain
    mock_urlh = MagicMock()
    mock_urlh.geturl.return_value = "https://www.google.com"
    mock_download.return_value = ("", mock_urlh)

    ydl = MagicMock()
    ie = ThreadsIE(ydl)

    with pytest.raises(ExtractorError) as exc_info:
        ie._real_extract("https://www.threads.net/share/BBYbNlJBF3")

    assert "silinmiş veya kullanılamıyor" in str(exc_info.value)
