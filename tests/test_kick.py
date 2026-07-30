"""Kick VOD video indirme ve URL analizi birim testleri."""

from unittest.mock import MagicMock, patch

from src.browser_sessions import analyze_kick_url
from src.download_options import build_ydl_options
from src.models import (
    DownloadRequest,
    MediaMetadata,
    PlatformType,
    detect_platform_type,
    get_platform_badge_text,
    translate_social_error,
)


class TestKickURLDetection:
    def test_valid_kick_vod_url_detected(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        assert detect_platform_type(url) == PlatformType.KICK_VIDEO
        assert get_platform_badge_text(PlatformType.KICK_VIDEO) == "Kick"

    def test_www_kick_vod_url_detected(self):
        url = "https://www.kick.com/channelname/videos/12345678-abcd-efgh-1234-567890abcdef"
        assert detect_platform_type(url) == PlatformType.KICK_VIDEO

    def test_kick_url_with_query_params_cleaned(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189?t=120"
        assert detect_platform_type(url) == PlatformType.KICK_VIDEO

    def test_kick_live_stream_not_detected_as_vod(self):
        url = "https://kick.com/jahrein"
        assert detect_platform_type(url) == PlatformType.UNKNOWN
        notice, err = analyze_kick_url(url)
        assert notice is None
        assert "canlı yayınları henüz desteklenmiyor" in err

    def test_kick_clips_not_detected_as_vod(self):
        url = "https://kick.com/jahrein/clips/clip_123456"
        assert detect_platform_type(url) == PlatformType.UNKNOWN
        notice, err = analyze_kick_url(url)
        assert notice is None
        assert "klipleri henüz desteklenmiyor" in err

    def test_kick_channel_videos_list_not_detected_as_vod(self):
        url = "https://kick.com/jahrein/videos"
        assert detect_platform_type(url) == PlatformType.UNKNOWN
        notice, err = analyze_kick_url(url)
        assert notice is None
        assert "kanal videoları listesi desteklenmiyor" in err

    def test_invalid_kick_uuid_rejected(self):
        url = "https://kick.com/jahrein/videos/123"
        assert detect_platform_type(url) == PlatformType.UNKNOWN
        notice, err = analyze_kick_url(url)
        assert notice is None
        assert "Geçersiz Kick video" in err


class TestKickMetadataExtraction:
    def test_kick_metadata_structure(self):
        meta = MediaMetadata(
            title="Örnek Yayın",
            uploader="jahrein",
            source_name="Kick",
            media_id="019fa488-5d20-71c0-a869-8716cf8e8189",
            platform_type=PlatformType.KICK_VIDEO,
            available_heights=[1080, 720, 480, 360],
            selected_height=720,
            selected_resolution="720p",
            video_codec="h264",
            audio_codec="aac",
        )
        assert meta.platform_type == PlatformType.KICK_VIDEO
        assert meta.media_id == "019fa488-5d20-71c0-a869-8716cf8e8189"
        assert meta.available_heights == [1080, 720, 480, 360]
        assert meta.selected_height == 720

    @patch("curl_cffi.requests.get")
    @patch("yt_dlp.YoutubeDL")
    def test_extract_kick_vod_helper(self, mock_ydl, mock_requests, tmp_path):
        from src.metadata_worker import _extract_kick_vod

        mock_resp_api = MagicMock()
        mock_resp_api.status_code = 200
        mock_resp_api.json.return_value = [
            {
                "id": 119395398,
                "session_title": "Test Kick Yod",
                "source": "https://stream.kick.com/test/master.m3u8",
                "duration": 5000,
                "thumbnail": {"src": "https://images.kick.com/thumb.webp"},
                "video": {"uuid": "019fa488-5d20-71c0-a869-8716cf8e8189"},
            }
        ]

        mock_requests.return_value = mock_resp_api

        mock_ydl_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.return_value = {
            "duration": 5.0,
            "vcodec": "h264",
            "acodec": "aac",
            "formats": [
                {"height": 1080, "vcodec": "h264", "acodec": "aac"},
                {"height": 720, "vcodec": "h264", "acodec": "aac"},
            ],
        }

        meta = _extract_kick_vod(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            "720p'ye kadar",
            "Video (MP4)",
        )

        assert meta.title == "Test Kick Yod"
        assert meta.uploader == "jahrein"
        assert meta.media_id == "019fa488-5d20-71c0-a869-8716cf8e8189"
        assert meta.selected_height == 720
        assert meta.platform_type == PlatformType.KICK_VIDEO


class TestKickDownloadOptionsAndHeaders:
    def test_build_ydl_options_contains_kick_headers(self, tmp_path):
        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )

        opts = build_ydl_options(req)
        assert "http_headers" in opts
        assert opts["http_headers"]["Referer"] == "https://kick.com/"
        assert opts["http_headers"]["Origin"] == "https://kick.com"
        assert opts["merge_output_format"] == "mp4"

    def test_target_final_path_no_double_extension(self, tmp_path):
        target = tmp_path / "Kick Yayın (1).mp4"
        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            target_final_path=target,
        )

        opts = build_ydl_options(req)
        assert opts["outtmpl"] == str(tmp_path / "Kick Yayın (1).%(ext)s")
        assert not opts["outtmpl"].endswith(".mp4.%(ext)s")


class TestKickErrorTranslations:
    def test_metadata_403_error_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("HTTP Error 403: Forbidden", url)
        assert "Kick video bilgilerine erişilemedi" in msg

    def test_hls_stream_403_error_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("403 Forbidden on HLS stream playlist", url)
        assert "Kick video akışına erişim reddedildi" in msg

    def test_deleted_vod_404_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("404 Not Found: Video unavailable", url)
        assert "Bu Kick videosu artık mevcut olmayabilir" in msg

    def test_subscriber_only_vod_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("subscriber only content, authentication required", url)
        assert "Bu video giriş veya abonelik gerektiriyor olabilir" in msg
