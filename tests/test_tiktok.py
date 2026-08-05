"""TikTok video, kısa bağlantı, slayt, canlı yayın ve hata yönetimi testleri."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.browser_sessions import analyze_tiktok_url, build_profile_attempt_order
from src.download_options import build_ydl_options
from src.metadata_worker import MetadataWorker
from src.models import (
    DownloadRequest,
    PlatformType,
    detect_platform_type,
    get_platform_badge_text,
    translate_social_error,
)


def test_tiktok_normal_video_url_detection():
    url = "https://www.tiktok.com/@user/video/1234567890123456789"
    assert detect_platform_type(url) == PlatformType.TIKTOK_VIDEO
    assert get_platform_badge_text(detect_platform_type(url)) == "TikTok"


def test_tiktok_vm_short_url_detection():
    url = "https://vm.tiktok.com/ZM8xXXXXX/"
    assert detect_platform_type(url) == PlatformType.TIKTOK_SHORT_LINK
    assert get_platform_badge_text(detect_platform_type(url)) == "TikTok"


def test_tiktok_vt_short_url_detection():
    url = "https://vt.tiktok.com/ZS8xXXXXX/"
    assert detect_platform_type(url) == PlatformType.TIKTOK_SHORT_LINK
    assert get_platform_badge_text(detect_platform_type(url)) == "TikTok"


def test_tiktok_query_param_url_detection():
    url = "https://www.tiktok.com/@user/video/1234567890123456789?is_from_webapp=1&sender_device=pc"
    assert detect_platform_type(url) == PlatformType.TIKTOK_VIDEO


def test_tiktok_profile_url_detection():
    url = "https://www.tiktok.com/@user"
    assert detect_platform_type(url) == PlatformType.TIKTOK_PROFILE
    notice, err = analyze_tiktok_url(url)
    assert notice is None
    assert err is not None
    assert "profil bağlantısı" in err.lower()


def test_tiktok_live_url_detection():
    url = "https://www.tiktok.com/@user/live"
    assert detect_platform_type(url) == PlatformType.TIKTOK_LIVE
    notice, err = analyze_tiktok_url(url)
    assert notice is None
    assert err is not None
    assert "canlı yayın" in err.lower()


def test_tiktok_metadata_conversion():
    worker = MetadataWorker("https://www.tiktok.com/@user/video/123")
    info = {
        "title": "Test TikTok Title",
        "uploader": "testuser",
        "duration": 45,
        "thumbnail": "https://example.com/thumb.jpg",
        "webpage_url": "https://www.tiktok.com/@user/video/123",
        "id": "123",
        "ext": "mp4",
        "view_count": 50000,
        "like_count": 12000,
        "track": "Original Sound - testuser",
        "formats": [{"vcodec": "h264", "height": 720, "acodec": "aac"}],
    }
    meta = worker._build_metadata(info)
    assert meta.title == "Test TikTok Title"
    assert meta.uploader == "testuser"
    assert meta.duration_seconds == 45.0
    assert meta.duration_text == "00:45"
    assert meta.maximum_available_height == 720
    assert meta.view_count == 50000
    assert meta.like_count == 12000
    assert meta.track_name == "Original Sound - testuser"


def test_tiktok_720p_source_limit_selection():
    worker = MetadataWorker(
        "https://www.tiktok.com/@user/video/123",
        requested_quality="1080p'ye kadar",
    )
    info = {
        "title": "TikTok 720p",
        "uploader": "testuser",
        "formats": [{"vcodec": "h264", "height": 720, "acodec": "aac"}],
    }
    meta = worker._build_metadata(info)
    assert meta.maximum_available_height == 720
    assert meta.selected_height == 720
    assert meta.selected_resolution == "720p"


def test_tiktok_mp4_download_options():
    req = DownloadRequest(
        url="https://www.tiktok.com/@user/video/123",
        output_dir=Path("downloads"),
        media_type="Video (MP4)",
        quality="720p",
        playlist=False,
    )
    opts = build_ydl_options(req)
    assert "TikTok" in opts["outtmpl"]
    assert opts["merge_output_format"] == "mp4"


def test_tiktok_mp3_download_options():
    req = DownloadRequest(
        url="https://www.tiktok.com/@user/video/123",
        output_dir=Path("downloads"),
        media_type="Ses (MP3)",
        quality="En iyi kullanılabilir kalite",
        playlist=False,
    )
    opts = build_ydl_options(req)
    assert opts["format"] == "bestaudio/best"
    assert opts["postprocessors"][0]["preferredcodec"] == "mp3"


def test_tiktok_error_translation_private():
    url = "https://www.tiktok.com/@user/video/123"
    msg = "This video is private"
    tr = translate_social_error(msg, url)
    assert "özel bir hesaba ait" in tr.lower()


def test_tiktok_error_translation_ip_blocked():
    url = "https://www.tiktok.com/@user/video/123"
    msg = "HTTP Error 403: IP address blocked"
    tr = translate_social_error(msg, url)
    assert "internet bağlantınızdan erişimi engelledi" in tr.lower()


def test_tiktok_error_translation_rate_limit():
    url = "https://www.tiktok.com/@user/video/123"
    msg = "HTTP Error 429: Too Many Requests"
    tr = translate_social_error(msg, url)
    assert "geçici olarak çok fazla istek" in tr.lower()


def test_tiktok_error_translation_impersonation():
    url = "https://www.tiktok.com/@user/video/123"
    msg = "Impersonation target chrome is not available"
    tr = translate_social_error(msg, url)
    assert "tarayıcı taklidi bileşeni bulunamadı" in tr.lower()


def test_tiktok_error_translation_unable_to_extract():
    url = "https://www.tiktok.com/@user/video/123"
    msg = "Unable to extract webpage video data"
    tr = translate_social_error(msg, url)
    assert "video bilgileri şu anda alınamadı" in tr.lower()


def test_tiktok_slideshow_video_type_rejection():
    worker = MetadataWorker(
        "https://www.tiktok.com/@user/photo/123",
        media_type="Video (MP4)",
    )
    info = {
        "title": "Photo Post",
        "uploader": "user",
        "_type": "slideshow",
        "formats": [{"vcodec": "none", "acodec": "mp3"}],
    }
    with pytest.raises(ValueError) as exc_info:
        worker._build_metadata(info)
    assert "fotoğraf veya slayt içeriği" in str(exc_info.value)


def test_tiktok_slideshow_mp3_allowed():
    worker = MetadataWorker(
        "https://www.tiktok.com/@user/photo/123",
        media_type="Ses (MP3)",
    )
    info = {
        "title": "Photo Post",
        "uploader": "user",
        "_type": "slideshow",
        "formats": [{"vcodec": "none", "acodec": "mp3"}],
    }
    meta = worker._build_metadata(info)
    assert meta.is_slideshow is True
    assert meta.selected_resolution == "Ses (MP3)"


@patch("src.browser_sessions.detect_available_browser_profiles", return_value=[])
def test_tiktok_attempt_order_first_unauthenticated(mock_profiles):
    order = build_profile_attempt_order(PlatformType.TIKTOK_VIDEO, "auto")
    assert order[0] == (None, None, "Oturumsuz")
    assert order[1][0] == "firefox"
    assert order[1][1] is None


def test_tiktok_short_url_passed_as_is_to_ytdlp():
    url_vm = "https://vm.tiktok.com/ZM8xXXXXX/"
    url_vt = "https://vt.tiktok.com/ZS8xXXXXX/"
    worker_vm = MetadataWorker(url_vm)
    worker_vt = MetadataWorker(url_vt)
    assert worker_vm.url == url_vm
    assert worker_vt.url == url_vt


def test_tiktok_short_url_resolution_updates_platform_to_video():
    worker = MetadataWorker("https://vm.tiktok.com/ZM8xXXXXX/")
    info = {
        "title": "Resolved TikTok Video",
        "uploader": "tiktok_user",
        "webpage_url": "https://www.tiktok.com/@tiktok_user/video/9876543210",
        "id": "9876543210",
        "ext": "mp4",
        "formats": [{"vcodec": "h264", "height": 1080, "acodec": "aac"}],
    }
    meta = worker._build_metadata(info)
    assert meta.platform_type == PlatformType.TIKTOK_VIDEO
    assert meta.webpage_url == "https://www.tiktok.com/@tiktok_user/video/9876543210"
    assert meta.title == "Resolved TikTok Video"


def test_tiktok_short_url_success_logs_and_preview(monkeypatch):
    url = "https://vm.tiktok.com/ZM8xXXXXX/"
    worker = MetadataWorker(url)

    logs = []
    worker.log.connect(logs.append)

    fake_info = {
        "title": "Short Link Resolved",
        "uploader": "user",
        "webpage_url": "https://www.tiktok.com/@user/video/111222333",
        "id": "111222333",
        "formats": [{"vcodec": "h264", "height": 720, "acodec": "aac"}],
    }

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, target_url, download=False):
            return fake_info

    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDL)
    monkeypatch.setattr(
        "src.metadata_worker.resolve_tiktok_short_link",
        lambda u: ("https://www.tiktok.com/@user/video/111222333", "video"),
    )

    meta_received = []
    worker.metadata_ready.connect(meta_received.append)

    worker.run()

    assert len(meta_received) == 1
    assert meta_received[0].title == "Short Link Resolved"
    assert "TikTok kısa bağlantısı algılandı" in logs
    assert "Yönlendirme başladı…" in logs
    assert any("Gerçek video bağlantısı bulundu" in log for log in logs)


def test_tiktok_short_url_failed_logs_turkish_error(monkeypatch):
    url = "https://vm.tiktok.com/ZM8xXXXXX/"
    worker = MetadataWorker(url)

    logs = []
    worker.log.connect(logs.append)

    failed_msg = []
    worker.failed.connect(failed_msg.append)

    def fake_resolve_fail(u):
        return u, "Could not resolve"

    monkeypatch.setattr(
        "src.metadata_worker.resolve_tiktok_short_link", fake_resolve_fail
    )

    class FakeYDLFail:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, target_url, download=False):
            raise ValueError("Unable to extract webpage video data")

    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDLFail)

    worker.run()

    assert len(failed_msg) == 1
    assert "TikTok video bilgileri şu anda alınamadı" in failed_msg[0]


def test_tiktok_rehydration_error_turkish_translation():
    url = "https://vt.tiktok.com/ZSXgEmedA/"
    msg = "ERROR: [TikTok] 7664960339628313864: Unable to extract universal data for rehydration"
    tr = translate_social_error(msg, url)
    assert (
        "TikTok bağlantısı çözüldü ancak bu videonun verileri şu anda yt-dlp tarafından okunamadı"
        in tr
    )
    assert "yt-dlp güncellemesini kontrol edin" in tr


def test_tiktok_rehydration_error_does_not_show_short_link_failed_msg(monkeypatch):
    url = "https://vt.tiktok.com/ZSXgEmedA/"
    worker = MetadataWorker(url)

    logs = []
    worker.log.connect(logs.append)

    def fake_resolve(u):
        return "https://www.tiktok.com/@teus.54/video/7664960339628313864", None

    monkeypatch.setattr("src.metadata_worker.resolve_tiktok_short_link", fake_resolve)

    class FakeYDLRehydrationFail:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, target_url, download=False):
            raise ValueError("Unable to extract universal data for rehydration")

    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDLRehydrationFail)

    failed_msgs = []
    worker.failed.connect(failed_msgs.append)

    worker.run()

    assert len(failed_msgs) == 1
    assert "TikTok bağlantısı çözüldü ancak bu videonun verileri" in failed_msgs[0]

    assert "TikTok yönlendirmesi başarılı." in logs
    assert any("Gerçek video bağlantısı bulundu:" in log for log in logs)
    assert (
        "TikTok extractor video verisini çıkaramadı: universal data for rehydration bulunamadı."
        in logs
    )
    assert not any("Kısa bağlantı çözümlenemedi" in log for log in logs)


def test_clean_tiktok_url_removes_tokens_and_query_params():
    from src.utils import clean_tiktok_url

    raw_url = "https://www.tiktok.com/@teus.54/video/7664960339628313864?_r=1&_t=ZS-98FKvxrMzEm#token=123"
    cleaned = clean_tiktok_url(raw_url)
    assert cleaned == "https://www.tiktok.com/@teus.54/video/7664960339628313864"
    assert "_r=1" not in cleaned
    assert "token" not in cleaned


def test_tiktok_rehydration_error_does_not_trigger_full_browser_loop():
    from src.browser_sessions import classify_session_error, is_authentication_error

    msg = "Unable to extract universal data for rehydration"
    url = "https://www.tiktok.com/@user/video/123"
    assert not is_authentication_error(msg)
    assert (
        classify_session_error(msg, url)
        == "TikTok video verisi çıkarılamadı (rehydration)"
    )


def test_tiktok_metadata_stores_successful_attempt_strategy(monkeypatch):
    url = "https://vm.tiktok.com/ZMMY5XSe8/"
    worker = MetadataWorker(url)

    fake_info = {
        "title": "Strategy Test",
        "uploader": "user",
        "webpage_url": "https://www.tiktok.com/@user/video/123",
        "id": "123",
        "formats": [{"vcodec": "h264", "height": 1080, "acodec": "aac"}],
    }

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, target_url, download=False):
            return fake_info

    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDL)

    meta_received = []
    worker.metadata_ready.connect(meta_received.append)
    worker.run()

    assert len(meta_received) == 1
    meta = meta_received[0]
    assert meta.successful_request_url is not None
    assert meta.successful_attempt_type is not None


def test_build_ydl_options_uses_preferred_impersonation():
    req = DownloadRequest(
        url="https://www.tiktok.com/@user/video/123",
        output_dir=Path("downloads"),
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
        preferred_browser="firefox",
        preferred_impersonation="chrome",
        successful_request_url="https://www.tiktok.com/@user/video/123",
    )
    opts = build_ydl_options(req)
    assert opts.get("cookiesfrombrowser") == ("firefox",)
    assert "impersonate" in opts


def test_build_tiktok_attempt_options_combinations():
    from src.download_options import build_tiktok_attempt_options

    o1 = build_tiktok_attempt_options()
    assert o1 == {}

    o2 = build_tiktok_attempt_options(browser="firefox")
    assert o2 == {"cookiesfrombrowser": ("firefox",)}

    o3 = build_tiktok_attempt_options(impersonation="chrome")
    assert "impersonate" in o3

    o4 = build_tiktok_attempt_options(browser="firefox", impersonation="chrome")
    assert o4.get("cookiesfrombrowser") == ("firefox",)
    assert "impersonate" in o4


def test_preferred_impersonation_none_does_not_break_other_platforms():
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=123",
        output_dir=Path("downloads"),
        media_type="Video (MP4)",
        quality="720p",
        playlist=False,
        preferred_impersonation=None,
    )
    opts = build_ydl_options(req)
    assert "impersonate" not in opts


def test_hevc_and_h264_codec_detection():
    from src.utils import is_h264_codec, is_hevc_codec

    for c in ("bytevc1", "bytevc1_1080p", "hev1", "hvc1", "hevc", "h265", "HEVC"):
        assert is_hevc_codec(c), f"{c} should be detected as HEVC"
        assert not is_h264_codec(c), f"{c} should not be detected as H264"

    for c in ("avc1", "avc1.64002a", "h264", "AVC", "H264"):
        assert is_h264_codec(c), f"{c} should be detected as H264"
        assert not is_hevc_codec(c), f"{c} should not be detected as HEVC"


def test_video_format_prioritizes_h264():
    from pathlib import Path

    from src.download_options import build_ydl_options
    from src.models import DownloadRequest

    req = DownloadRequest(
        url="https://www.tiktok.com/@user/video/123",
        output_dir=Path("."),
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
    )
    opts = build_ydl_options(req)
    assert opts.get("format_sort") == ["vcodec:h264", "acodec:aac", "ext:mp4"]


def test_handle_post_download_transcode_h264_no_reencode(tmp_path, monkeypatch):
    from src.download_worker import DownloadWorker

    test_file = tmp_path / "test_h264.mp4"
    test_file.write_bytes(b"fake_video")

    req = DownloadRequest(
        url="https://www.tiktok.com/@user/video/123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
    )
    worker = DownloadWorker(req)
    worker._last_filename = str(test_file)

    def fake_probe(path):
        return {
            "video_codec": "h264",
            "audio_codec": "aac",
            "height": 1080,
            "width": 1920,
            "pix_fmt": "yuv420p",
            "channels": 2,
        }

    monkeypatch.setattr("src.download_worker.probe_media_codecs", fake_probe)

    logs = []
    worker.log.connect(logs.append)
    worker._handle_post_download_transcode({})

    assert test_file.exists()
    assert not any("dönüştürülüyor" in log for log in logs)
