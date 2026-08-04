"""Facebook video, reel, kısa bağlantı ve hata yönetimi testleri."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.browser_sessions import build_profile_attempt_order, classify_session_error
from src.download_options import build_ydl_options
from src.history import normalize_platform
from src.history_dialog import (
    _canonical_platform,
    _get_platform_badge_style,
    _get_platform_display_name,
)
from src.metadata_worker import MetadataWorker
from src.models import (
    DownloadRequest,
    PlatformType,
    QueueItem,
    detect_platform_type,
    get_platform_badge_text,
    translate_social_error,
)
from src.utils import (
    extract_supported_url_from_text,
    extract_supported_urls_from_text,
)

# -----------------------------------------------------------------------------
# 1. URL Doğrulama Testleri
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("url", "expected_platform"),
    [
        ("https://www.facebook.com/watch/?v=123456", PlatformType.FACEBOOK_VIDEO),
        ("https://facebook.com/watch/?v=123456", PlatformType.FACEBOOK_VIDEO),
        ("https://www.facebook.com/user/videos/123456", PlatformType.FACEBOOK_VIDEO),
        ("https://www.facebook.com/user/videos/title/123456", PlatformType.FACEBOOK_VIDEO),
        ("https://www.facebook.com/reel/123456", PlatformType.FACEBOOK_REEL),
        ("https://m.facebook.com/watch/?v=123456", PlatformType.FACEBOOK_VIDEO),
        ("https://m.facebook.com/user/videos/123456", PlatformType.FACEBOOK_VIDEO),
        ("https://web.facebook.com/watch/?v=123456", PlatformType.FACEBOOK_VIDEO),
        ("https://fb.watch/abc123", PlatformType.FACEBOOK_VIDEO),
        ("https://www.facebook.com/share/v/abc123", PlatformType.FACEBOOK_VIDEO),
        ("https://www.facebook.com/share/r/abc123", PlatformType.FACEBOOK_REEL),
        ("https://www.facebook.com/permalink.php?story_fbid=123456&id=789", PlatformType.FACEBOOK_VIDEO),
        ("https://m.facebook.com/story.php?story_fbid=123456&id=789", PlatformType.FACEBOOK_VIDEO),
        ("https://www.facebook.com/username/posts/123456", PlatformType.FACEBOOK_VIDEO),
    ],
)
def test_facebook_valid_url_detection(url: str, expected_platform: PlatformType):
    platform = detect_platform_type(url)
    assert platform == expected_platform
    assert get_platform_badge_text(platform) == "Facebook"


@pytest.mark.parametrize(
    "invalid_url",
    [
        "https://facebook.com",
        "https://www.facebook.com/",
        "https://facebook.com/login",
        "https://facebook.com/login.php",
        "https://facebook.com/marketplace",
        "https://facebook.com/notifications",
        "https://facebook.com.evil.example/watch/?v=123",
        "https://evil.example/?url=facebook.com/reel/123",
        "https://fb.watch",
        "https://fb.watch/",
        "https://facebook.com/username",
        "",
        "not_a_valid_url",
    ],
)
def test_facebook_invalid_url_detection(invalid_url: str):
    platform = detect_platform_type(invalid_url)
    assert platform == PlatformType.UNKNOWN


# -----------------------------------------------------------------------------
# 2. Metadata Eşleme Testleri
# -----------------------------------------------------------------------------

def test_facebook_watch_metadata_conversion():
    worker = MetadataWorker("https://www.facebook.com/watch/?v=123456")
    info = {
        "title": "Muhteşem Doğa Belgeseli &amp; Manzaralar",
        "uploader": "Doğa Sayfası",
        "duration": 120,
        "thumbnail": "https://example.com/fb_thumb.jpg",
        "webpage_url": "https://www.facebook.com/watch/?v=123456",
        "id": "123456",
        "ext": "mp4",
        "view_count": 85000,
        "like_count": 4200,
        "formats": [
            {"vcodec": "h264", "height": 720, "acodec": "aac"},
            {"vcodec": "h264", "height": 1080, "acodec": "aac"},
        ],
    }
    meta = worker._build_metadata(info)
    # HTML entity unescaped
    assert meta.title == "Muhteşem Doğa Belgeseli & Manzaralar"
    assert meta.uploader == "Doğa Sayfası"
    assert meta.duration_seconds == 120.0
    assert meta.duration_text == "02:00"
    assert meta.maximum_available_height == 1080
    assert meta.view_count == 85000
    assert meta.like_count == 4200
    assert meta.platform_type == PlatformType.FACEBOOK_VIDEO
    assert get_platform_badge_text(meta.platform_type) == "Facebook"


def test_facebook_reel_metadata_conversion():
    worker = MetadataWorker("https://www.facebook.com/reel/7891011")
    info = {
        "title": "Hızlı Tarif &#39;Lezzetli Yemekler&#39;",
        "uploader": "Şef Ahmet",
        "duration": 45,
        "thumbnail": "https://example.com/reel_thumb.jpg",
        "webpage_url": "https://www.facebook.com/reel/7891011",
        "id": "7891011",
        "ext": "mp4",
        "formats": [
            {"vcodec": "h264", "height": 1080, "acodec": "aac"},
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Hızlı Tarif 'Lezzetli Yemekler'"
    assert meta.uploader == "Şef Ahmet"
    assert meta.duration_seconds == 45.0
    assert meta.maximum_available_height == 1080
    assert meta.platform_type == PlatformType.FACEBOOK_REEL
    assert get_platform_badge_text(meta.platform_type) == "Facebook"


def test_facebook_photo_only_raises_error():
    worker = MetadataWorker("https://www.facebook.com/user/posts/12345")
    info = {
        "title": "Fotoğraf Gönderisi",
        "uploader": "Kullanıcı",
        "id": "12345",
        "formats": [],
    }
    with pytest.raises(ValueError, match="Bu Facebook gönderisinde indirilebilir bir video bulunamadı."):
        worker._build_metadata(info)


def test_facebook_playlist_no_top_level_formats_entries_accepted():
    worker = MetadataWorker("https://www.facebook.com/watch/?v=123456")
    info = {
        "_type": "playlist",
        "title": "Facebook Playlist Title",
        "id": "pl_123",
        "entries": [
            {
                "id": "entry_1",
                "title": "Video in Playlist",
                "uploader": "Page Name",
                "formats": [
                    {"vcodec": "h264", "height": 720, "acodec": "aac"},
                    {"vcodec": "h264", "height": 1080, "acodec": "aac"},
                ],
            }
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Video in Playlist"
    assert meta.uploader == "Page Name"
    assert meta.maximum_available_height == 1080
    assert meta.is_playlist is True


def test_facebook_multi_video_accepted():
    worker = MetadataWorker("https://www.facebook.com/watch/?v=123456")
    info = {
        "_type": "multi_video",
        "title": "Facebook Multi Video",
        "id": "mv_123",
        "entries": [
            {
                "id": "mv_sub_1",
                "title": "Multi Video Sub 1",
                "formats": [
                    {"vcodec": "h264", "height": 1080, "acodec": "aac"},
                ],
            }
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Multi Video Sub 1"
    assert meta.maximum_available_height == 1080
    assert meta.is_playlist is True


def test_facebook_first_entry_none_second_entry_video_accepted():
    worker = MetadataWorker("https://www.facebook.com/watch/?v=123456")
    info = {
        "_type": "playlist",
        "title": "Facebook Broken First Entry",
        "id": "pl_none_first",
        "entries": [
            None,
            {
                "id": "entry_2",
                "title": "Valid Video After None",
                "formats": [
                    {"vcodec": "h264", "height": 720, "acodec": "aac"},
                ],
            },
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Valid Video After None"
    assert meta.maximum_available_height == 720
    assert meta.is_playlist is True
    assert meta.playlist_count == 1


def test_facebook_entry_with_requested_downloads_accepted():
    worker = MetadataWorker("https://www.facebook.com/watch/?v=123456")
    info = {
        "_type": "playlist",
        "title": "Facebook With Requested Downloads",
        "id": "pl_req_dl",
        "entries": [
            {
                "id": "entry_req_dl",
                "title": "Requested Download Video",
                "requested_downloads": [
                    {"url": "https://fbcdn.net/video.mp4", "ext": "mp4", "filesize": 5000000}
                ],
            }
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Requested Download Video"
    assert meta.is_playlist is True


def test_facebook_no_formats_and_no_valid_entries_raises_error():
    worker = MetadataWorker("https://www.facebook.com/watch/?v=123456")
    info = {
        "_type": "playlist",
        "title": "Empty/Photo Album",
        "id": "pl_empty",
        "entries": [
            None,
            {
                "id": "entry_text_only",
                "title": "Text Entry",
                "formats": [],
            },
        ],
    }
    with pytest.raises(ValueError, match="Bu Facebook gönderisinde indirilebilir bir video bulunamadı."):
        worker._build_metadata(info)


def test_facebook_url_transparent_accepted():
    worker = MetadataWorker("https://www.facebook.com/share/v/1BE1p2ZPKS/")
    info = {
        "_type": "url_transparent",
        "title": "Redirect Video",
        "url": "https://facebook.com/watch/?v=12345",
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Redirect Video"


def test_facebook_single_video_requested_formats_accepted():
    worker = MetadataWorker("https://fb.watch/j3RI-T3VOA/")
    info = {
        "title": "Single FB Video With Requested Formats",
        "requested_formats": [
            {"vcodec": "h264", "height": 1080},
            {"acodec": "aac"},
        ],
        "formats": [],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Single FB Video With Requested Formats"
    assert meta.maximum_available_height == 1080


# -----------------------------------------------------------------------------
# 3. Kalite ve Format Seçim Testleri
# -----------------------------------------------------------------------------

def test_facebook_quality_selection_best():
    worker = MetadataWorker(
        "https://www.facebook.com/watch/?v=123",
        requested_quality="En iyi kullanılabilir kalite",
    )
    info = {
        "title": "Facebook 1080p Video",
        "uploader": "User",
        "formats": [
            {"vcodec": "h264", "height": 720, "acodec": "aac"},
            {"vcodec": "h264", "height": 1080, "acodec": "aac"},
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.maximum_available_height == 1080
    assert meta.selected_height == 1080


def test_facebook_quality_selection_downscale():
    worker = MetadataWorker(
        "https://www.facebook.com/watch/?v=123",
        requested_quality="720p'ye kadar",
    )
    info = {
        "title": "Facebook 1080p Video",
        "uploader": "User",
        "formats": [
            {"vcodec": "h264", "height": 720, "acodec": "aac"},
            {"vcodec": "h264", "height": 1080, "acodec": "aac"},
        ],
    }
    meta = worker._build_metadata(info)
    assert meta.maximum_available_height == 1080
    assert meta.selected_height == 720


def test_facebook_audio_download_options(tmp_path: Path):
    req = DownloadRequest(
        url="https://www.facebook.com/watch/?v=123",
        media_type="Ses (MP3)",
        quality="En iyi kullanılabilir kalite",
        playlist=False,
        output_dir=tmp_path,
    )
    opts = build_ydl_options(req)
    assert opts["format"] == "bestaudio/best"
    assert any(pp.get("key") == "FFmpegExtractAudio" for pp in opts.get("postprocessors", []))


# -----------------------------------------------------------------------------
# 4. Hata Mesajı Çeviri Testleri
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw_error", "expected_snippet"),
    [
        ("Cannot parse data from facebook page", "Facebook video bilgileri alınamadı"),
        ("No video formats found on this page", "Bu Facebook bağlantısında indirilebilir video bulunamadı"),
        ("Login required to view this video", "Bu Facebook içeriğini görüntülemek için tarayıcı oturumu gerekebilir"),
        ("This video has been removed or is unavailable", "Facebook videosu kaldırılmış, gizlenmiş veya kullanılamıyor olabilir"),
        ("Post contains only photos and no video", "Bu Facebook gönderisinde indirilebilir bir video bulunamadı"),
        ("HTTP Error 429: Too Many Requests / Rate limit", "Facebook isteği geçici olarak sınırlandırdı"),
    ],
)
def test_facebook_error_translations(raw_error: str, expected_snippet: str):
    msg = translate_social_error(raw_error, "https://www.facebook.com/watch/?v=123456")
    assert expected_snippet in msg


# -----------------------------------------------------------------------------
# 5. Platform Badge, Geçmiş ve Kuyruk Testleri
# -----------------------------------------------------------------------------

def test_facebook_badge_text():
    assert get_platform_badge_text(PlatformType.FACEBOOK_VIDEO) == "Facebook"
    assert get_platform_badge_text(PlatformType.FACEBOOK_REEL) == "Facebook"


def test_facebook_history_canonical_and_display():
    assert normalize_platform("facebook_video") == "facebook"
    assert normalize_platform("facebook_reel") == "facebook"
    assert normalize_platform("facebook") == "facebook"

    assert _canonical_platform("facebook_video") == "facebook"
    assert _canonical_platform("facebook_reel") == "facebook"
    assert _canonical_platform("Facebook") == "facebook"

    assert _get_platform_display_name("facebook_video") == "Facebook"
    assert _get_platform_display_name("facebook_reel") == "Facebook"
    assert _get_platform_display_name("facebook") == "Facebook"

    badge_style = _get_platform_badge_style("facebook", "Video (MP4)")
    assert "#eff6ff" in badge_style
    assert "#1d4ed8" in badge_style


def test_facebook_queue_item_creation(tmp_path: Path):
    item = QueueItem(
        id="fb_item_1",
        url="https://www.facebook.com/reel/123456",
        platform=PlatformType.FACEBOOK_REEL.value,
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
        output_dir=tmp_path,
    )
    assert item.platform == "facebook_reel"
    assert item.url == "https://www.facebook.com/reel/123456"


# -----------------------------------------------------------------------------
# 6. Tarayıcı Oturumu ve Fallback Testleri
# -----------------------------------------------------------------------------

def test_facebook_session_attempt_order():
    order = build_profile_attempt_order(PlatformType.FACEBOOK_VIDEO, "auto")
    # Oturumsuz deneme ilk sırada olmalı
    assert len(order) >= 1
    assert order[0] == (None, None, "Oturumsuz")


def test_facebook_browser_failure_reason():
    reason = classify_session_error("Sign in required / Cookies needed", "https://www.facebook.com/watch/?v=123")
    assert "Facebook oturumu" in reason or "oturum" in reason.lower()


# -----------------------------------------------------------------------------
# 7. Clipboard URL Çıkarma Testleri
# -----------------------------------------------------------------------------

def test_facebook_clipboard_extraction():
    text = "Şu Facebook videosuna göz at: https://www.facebook.com/watch/?v=987654 harika görünüyor!"
    url = extract_supported_url_from_text(text)
    assert url == "https://www.facebook.com/watch/?v=987654"


def test_facebook_clipboard_extraction_multiple():
    text = (
        "1. https://www.facebook.com/watch/?v=111\n"
        "2. https://www.facebook.com/reel/222\n"
        "3. https://fb.watch/333\n"
        "4. https://facebook.com/marketplace (desteklenmeyen)\n"
    )
    urls = extract_supported_urls_from_text(text)
    assert urls == [
        "https://www.facebook.com/watch/?v=111",
        "https://www.facebook.com/reel/222",
        "https://fb.watch/333",
    ]


def test_facebook_clipboard_rejects_homepage_and_evil():
    assert extract_supported_url_from_text("https://facebook.com/") is None
    assert extract_supported_url_from_text("https://facebook.com.evil.example/watch/?v=123") is None
