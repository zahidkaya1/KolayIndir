"""Kick VOD video indirme ve URL analizi birim testleri."""

from unittest.mock import MagicMock, patch

import pytest

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

# ---------------------------------------------------------------------------
# URL Algılama Testleri
# ---------------------------------------------------------------------------


class TestKickURLDetection:
    def test_valid_kick_vod_url_detected(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        assert detect_platform_type(url) == PlatformType.KICK_VIDEO
        assert (
            get_platform_badge_text(PlatformType.KICK_VIDEO)
            == "Kick — Geçici olarak kullanılamıyor"
        )

    def test_www_kick_vod_url_detected(self):
        url = "https://www.kick.com/channelname/videos/12345678-abcd-ef12-3456-567890abcdef"
        assert detect_platform_type(url) == PlatformType.KICK_VIDEO

    def test_kick_url_with_query_params_detected(self):
        url = (
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189?t=120"
        )
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

    def test_valid_kick_vod_analyze_returns_notice(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        notice, err = analyze_kick_url(url)
        assert err is None
        assert notice == "Kick VOD videosu algılandı."


# ---------------------------------------------------------------------------
# Playback Endpoint Testleri (_fetch_kick_playback_m3u8)
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestFetchKickPlaybackM3u8:
    """Playback POST endpoint doğru biçimde çağrılıyor mu?"""

    def test_post_request_correct_url(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with (
            patch("curl_cffi.requests.post") as mock_post,
            patch("curl_cffi.requests.get") as mock_get,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "playback_url": {
                    "vod": "https://example.com/master.m3u8",
                    "vod_session": "https://web.kick.com/api/v1/stream/vod_session",
                },
                "video_session": {"video_title": "Test Başlık"},
            }
            mock_post.return_value = mock_resp

            mock_vs_resp = MagicMock()
            mock_vs_resp.status_code = 200
            mock_vs_resp.json.return_value = {
                "manifestUrl": "https://example.com/master.m3u8"
            }
            mock_get.return_value = mock_vs_resp

            m3u8, code, title = _fetch_kick_playback_m3u8(
                "019fa488-5d20-71c0-a869-8716cf8e8189",
                {"Referer": "https://kick.com/"},
            )

        assert code == 200
        assert m3u8 == "https://example.com/master.m3u8"
        assert title == "Test Başlık"

        # Doğru URL kontrolü
        call_args = mock_post.call_args
        assert (
            "web.kick.com/api/v1/stream/019fa488-5d20-71c0-a869-8716cf8e8189/playback"
            in call_args[0][0]
        )

    def test_post_request_correct_json_body(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "playback_url": {"vod": "https://example.m3u8"},
                "video_session": {},
            }
            mock_post.return_value = mock_resp

            _fetch_kick_playback_m3u8("test-uuid", {})

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["video_player"] == {"player": {}}
        assert call_kwargs["json"]["video_session"] == {}
        assert call_kwargs["json"]["user_session"]["non_personalised_ads"] is True

    def test_impersonation_chrome120_used(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "playback_url": {"vod": "https://example.m3u8"},
                "video_session": {},
            }
            mock_post.return_value = mock_resp

            _fetch_kick_playback_m3u8("test-uuid", {})

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["impersonate"] == "chrome120"

    def test_returns_none_on_404(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_post.return_value = mock_resp

            m3u8, code, title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert code == 404
        assert title is None

    def test_returns_none_on_403(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            mock_post.return_value = mock_resp

            m3u8, code, _title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert code == 403

    def test_returns_none_on_exception(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post", side_effect=Exception("timeout")):
            m3u8, code, _title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert code == "timeout"

    def test_missing_vod_key_returns_none(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"playback_url": {}, "video_session": {}}
            mock_post.return_value = mock_resp

            m3u8, code, _title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert code == "unverified_vod_stream"


# ---------------------------------------------------------------------------
# _extract_kick_vod Fallback Akış Testleri
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestExtractKickVodFallback:
    """Standart extractor başarısız olunca playback endpoint devreye giriyor mu?"""

    @patch("src.metadata_worker._fetch_kick_video_metadata")
    @patch("src.metadata_worker._extract_formats_from_m3u8")
    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_falls_back_to_playback_endpoint_when_ytdlp_fails(
        self, mock_ydl, mock_playback, mock_extract_m3u8, mock_meta
    ):
        from src.metadata_worker import _extract_kick_vod

        # yt-dlp standart extractor başarısız
        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("404 Not Found")
        )

        # Playback endpoint çalışıyor
        mock_playback.return_value = ("https://example.m3u8", 200, "Test Başlık")

        # m3u8 formatları
        mock_extract_m3u8.return_value = {
            "formats": [
                {"height": 1080, "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
                {"height": 720, "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
            ],
        }
        mock_meta.return_value = {}

        meta = _extract_kick_vod(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            "720p'ye kadar",
            "Video (MP4)",
        )

        assert mock_playback.called
        assert meta.platform_type == PlatformType.KICK_VIDEO
        assert meta.selected_height == 720
        assert 1080 in meta.available_heights
        assert 720 in meta.available_heights

    @patch("src.metadata_worker._fetch_kick_video_metadata")
    @patch("src.metadata_worker._extract_formats_from_m3u8")
    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_title_from_playback_when_manifest_title(
        self, mock_ydl, mock_playback, mock_extract_m3u8, mock_meta
    ):
        from src.metadata_worker import _extract_kick_vod

        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("404")
        )
        mock_playback.return_value = (
            "https://example.m3u8",
            200,
            "Gerçek Video Başlığı",
        )
        mock_extract_m3u8.return_value = {
            "title": "manifest",
            "formats": [{"height": 720, "vcodec": "h264", "acodec": "aac"}],
        }
        mock_meta.return_value = {}

        meta = _extract_kick_vod(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            "En iyi kullanılabilir kalite",
            "Video (MP4)",
        )

        assert meta.title == "Gerçek Video Başlığı"

    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_raises_proper_error_on_404_from_playback(self, mock_ydl, mock_playback):
        from src.metadata_worker import _extract_kick_vod

        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("404")
        )
        mock_playback.return_value = (None, 404, None)

        with pytest.raises(
            ValueError, match="Video kaldırılmış veya bağlantı yapısı değişmiş"
        ):
            _extract_kick_vod(
                "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
                "En iyi kullanılabilir kalite",
                "Video (MP4)",
            )

    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_raises_proper_error_on_403_from_playback(self, mock_ydl, mock_playback):
        from src.metadata_worker import _extract_kick_vod

        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("500")
        )
        mock_playback.return_value = (None, 403, None)

        with pytest.raises(ValueError, match="erişim reddedildi"):
            _extract_kick_vod(
                "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
                "En iyi kullanılabilir kalite",
                "Video (MP4)",
            )

    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_raises_proper_error_on_timeout(self, mock_ydl, mock_playback):
        from src.metadata_worker import _extract_kick_vod

        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("network")
        )
        mock_playback.return_value = (None, "timeout", None)

        with pytest.raises(ValueError, match="zamanında yanıt vermedi"):
            _extract_kick_vod(
                "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
                "En iyi kullanılabilir kalite",
                "Video (MP4)",
            )

    @patch("src.metadata_worker._fetch_kick_video_metadata")
    @patch("src.metadata_worker._extract_formats_from_m3u8")
    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_raises_no_formats_error_when_empty(
        self, mock_ydl, mock_playback, mock_extract_m3u8, mock_meta
    ):
        from src.metadata_worker import _extract_kick_vod

        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("404")
        )
        mock_playback.return_value = ("https://example.m3u8", 200, "Başlık")
        mock_extract_m3u8.return_value = {"formats": []}  # boş formatlar
        mock_meta.return_value = {}

        with pytest.raises(ValueError, match="indirilebilir kalite bulunamadı"):
            _extract_kick_vod(
                "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
                "En iyi kullanılabilir kalite",
                "Video (MP4)",
            )

    @patch("src.metadata_worker._fetch_kick_video_metadata")
    @patch("src.metadata_worker._extract_formats_from_m3u8")
    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_successful_request_url_is_original_kick_url(
        self, mock_ydl, mock_playback, mock_extract_m3u8, mock_meta
    ):
        """Signed m3u8 successful_request_url'e kaydedilmemeli."""
        from src.metadata_worker import _extract_kick_vod

        kick_url = (
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        )
        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("404")
        )
        mock_playback.return_value = (
            "https://signed.m3u8?token=secret123",
            200,
            "Başlık",
        )
        mock_extract_m3u8.return_value = {
            "formats": [{"height": 720, "vcodec": "h264", "acodec": "aac"}],
        }
        mock_meta.return_value = {}

        meta = _extract_kick_vod(
            kick_url, "En iyi kullanılabilir kalite", "Video (MP4)"
        )

        # Signed m3u8 kaydedilmemeli
        assert meta.successful_request_url == kick_url
        assert "secret123" not in (meta.successful_request_url or "")

    @patch("src.metadata_worker._fetch_kick_video_metadata")
    @patch("src.metadata_worker._extract_formats_from_m3u8")
    @patch("src.metadata_worker._fetch_kick_playback_m3u8")
    @patch("yt_dlp.YoutubeDL")
    def test_metadata_endpoint_used_for_missing_info(
        self, mock_ydl, mock_playback, mock_extract_m3u8, mock_meta
    ):
        """Başlık/kanal yoksa metadata endpoint devreye giriyor mu?"""
        from src.metadata_worker import _extract_kick_vod

        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
            Exception("404")
        )
        mock_playback.return_value = ("https://example.m3u8", 200, None)  # başlık yok
        mock_extract_m3u8.return_value = {
            "formats": [{"height": 720, "vcodec": "h264", "acodec": "aac"}],
        }
        mock_meta.return_value = {
            "title": "Metadata'dan Başlık",
            "duration": 3600,
        }

        meta = _extract_kick_vod(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            "En iyi kullanılabilir kalite",
            "Video (MP4)",
        )

        assert mock_meta.called
        assert "Metadata'dan Başlık" in meta.title


# ---------------------------------------------------------------------------
# Format Tekilleştirme Testleri
# ---------------------------------------------------------------------------


class TestKickFormatDeduplication:
    def test_duplicate_heights_deduplicated(self):
        """Aynı yükseklikte birden fazla format olduğunda tekilleştiriliyor mu?"""
        from src.utils import extract_available_formats

        info_dict = {
            "formats": [
                {"height": 1080, "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
                {
                    "height": 1080,
                    "vcodec": "h264",
                    "acodec": "aac",
                    "ext": "ts",
                },  # duplicate
                {"height": 720, "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
                {"height": 360, "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
            ],
        }

        heights, _formats = extract_available_formats(info_dict)

        assert heights.count(1080) == 1
        assert heights.count(720) == 1
        assert heights == sorted(set(heights), reverse=True)

    def test_audio_only_formats_excluded_from_height_list(self):
        """Ses-only formatlar kalite listesine eklenmiyor mu?"""
        from src.utils import extract_available_formats

        info_dict = {
            "formats": [
                {"height": 720, "vcodec": "h264", "acodec": "aac"},
                {"height": None, "vcodec": "none", "acodec": "aac"},  # audio-only
            ],
        }

        heights, _ = extract_available_formats(info_dict)

        assert None not in heights
        # Audio-only format yükseklik listesine eklenmiyor
        assert all(h is not None and h > 0 for h in heights)

    def test_heights_sorted_descending(self):
        """Kalite listesi büyükten küçüğe sıralı mı?"""
        from src.utils import extract_available_formats

        info_dict = {
            "formats": [
                {"height": 360, "vcodec": "h264", "acodec": "aac"},
                {"height": 1080, "vcodec": "h264", "acodec": "aac"},
                {"height": 480, "vcodec": "h264", "acodec": "aac"},
                {"height": 720, "vcodec": "h264", "acodec": "aac"},
            ],
        }

        heights, _ = extract_available_formats(info_dict)

        assert heights == sorted(heights, reverse=True)


# ---------------------------------------------------------------------------
# İndirme Seçenekleri Testleri
# ---------------------------------------------------------------------------


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


class TestKickFilenameSanitization:
    def test_kick_title_with_newlines_and_backslash_sanitized(self):
        from src.history import sanitize_filename

        raw_title = (
            "Bu sefer gerçekten döndüm-Çok haber var _ Gündem-Haberler\n\n\\wraith"
        )
        cleaned = sanitize_filename(raw_title)
        assert "\n" not in cleaned
        assert "\r" not in cleaned
        assert "\\" not in cleaned
        assert (
            cleaned
            == "Bu sefer gerçekten döndüm-Çok haber var _ Gündem-Haberler wraith"
        )

    def test_kick_target_final_path_sanitized(self, tmp_path):
        from src.history import (
            reserve_unique_media_path,
            sanitize_filename,
        )

        raw_title = (
            "Bu sefer gerçekten döndüm-Çok haber var _ Gündem-Haberler\n\n\\wraith"
        )
        clean = sanitize_filename(raw_title)
        initial_path = tmp_path / f"{clean}.mp4"
        target_path = reserve_unique_media_path(
            (initial_path).parent, (initial_path).stem, (initial_path).suffix
        )

        assert "\n" not in str(target_path)
        assert "\\" not in target_path.name
        assert target_path.suffix == ".mp4"

    def test_kick_ytdl_path_valid(self, tmp_path):
        from pathlib import Path

        from src.history import (
            reserve_unique_media_path,
            sanitize_filename,
        )

        raw_title = "Bu sefer gerçekten döndüm\n\n\\wraith"
        clean = sanitize_filename(raw_title)
        target_path = reserve_unique_media_path(
            (tmp_path / f"{clean}.mp4").parent,
            (tmp_path / f"{clean}.mp4").stem,
            (tmp_path / f"{clean}.mp4").suffix,
        )
        ytdl_path = target_path.with_suffix(".mp4.ytdl")

        assert "\n" not in str(ytdl_path)
        assert ytdl_path.name.endswith(".mp4.ytdl")
        assert isinstance(ytdl_path, Path)


# ---------------------------------------------------------------------------
# DownloadWorker Kick: Playback URL Yenileme Testleri
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestKickDownloadWorkerPlaybackRefresh:
    def test_resolve_kick_playback_url_calls_correct_endpoint(self):
        """_resolve_kick_playback_url doğru URL'ye POST yapıyor mu?"""
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        with (
            patch("src.download_worker.DownloadWorker._save_completed_record"),
            patch("src.download_worker.DownloadWorker._cleanup_job_files"),
        ):
            pass  # sınıfı import etmek yeterli

        with (
            patch("curl_cffi.requests.post") as mock_post,
            patch("curl_cffi.requests.get") as mock_get,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "playback_url": {
                    "vod": "https://fresh.m3u8",
                    "vod_session": "https://web.kick.com/api/v1/stream/vod_session",
                }
            }
            mock_post.return_value = mock_resp

            mock_vs_resp = MagicMock()
            mock_vs_resp.status_code = 200
            mock_vs_resp.json.return_value = {"manifestUrl": "https://fresh.m3u8"}
            mock_get.return_value = mock_vs_resp

            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                req = DownloadRequest(
                    url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
                    output_dir=Path(tmpdir),
                    media_type="Video (MP4)",
                    quality="720p'ye kadar",
                    playlist=False,
                )
                worker = DownloadWorker(req)
                result = worker._resolve_kick_playback_url(req.url)

        assert result == "https://fresh.m3u8"
        call_args = mock_post.call_args
        assert "019fa488-5d20-71c0-a869-8716cf8e8189" in call_args[0][0]
        assert call_args[1]["impersonate"] == "chrome120"
        assert call_args[1]["json"]["user_session"]["non_personalised_ads"] is True

    def test_resolve_returns_none_on_non_200(self):
        import tempfile
        from pathlib import Path

        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            mock_post.return_value = mock_resp

            with tempfile.TemporaryDirectory() as tmpdir:
                req = DownloadRequest(
                    url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
                    output_dir=Path(tmpdir),
                    media_type="Video (MP4)",
                    quality="720p'ye kadar",
                    playlist=False,
                )
                worker = DownloadWorker(req)
                result = worker._resolve_kick_playback_url(req.url)

        assert result is None


# ---------------------------------------------------------------------------
# Hata Mesajı Sınıflandırma Testleri
# ---------------------------------------------------------------------------


class TestKickErrorTranslations:
    def test_403_error_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("HTTP Error 403: Forbidden", url)
        assert "Kick desteği geçici olarak kullanılamıyor" in msg

    def test_invalid_url_error_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("invalid uuid format", url)
        assert "Kick desteği geçici olarak kullanılamıyor" in msg

    def test_subscriber_only_vod_translation(self):
        url = "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        msg = translate_social_error("subscriber only content", url)
        assert "Kick desteği geçici olarak kullanılamıyor" in msg

    def test_kick_clip_url_rejected(self):
        url = "https://kick.com/jahrein/clips/abc123"
        _, err = analyze_kick_url(url)
        assert err is not None
        assert "klip" in err.lower()

    def test_kick_live_url_rejected(self):
        url = "https://kick.com/jahrein"
        _, err = analyze_kick_url(url)
        assert err is not None
        assert "canlı" in err.lower()


# ---------------------------------------------------------------------------
# MediaMetadata Yapı Testleri
# ---------------------------------------------------------------------------


class TestKickMetadataStructure:
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

    def test_kick_source_name_always_kick(self):
        """Platform rozeti Generic/HLS değil, Kick görünmeli."""
        meta = MediaMetadata(
            source_name="Kick",
            platform_type=PlatformType.KICK_VIDEO,
        )
        from src.models import get_platform_badge_text

        assert (
            get_platform_badge_text(meta.platform_type)
            == "Kick — Geçici olarak kullanılamıyor"
        )
        assert meta.source_name == "Kick"


# ---------------------------------------------------------------------------
# Kick İndirme İptali ve Otomatik Temizlik Testleri
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestKickDownloadCancellationAndCleanup:
    def test_cancellation_emits_cancelled_and_finished_signals(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)

        cancelled_emitted = False
        finished_emitted = False

        def on_cancelled():
            nonlocal cancelled_emitted
            cancelled_emitted = True

        def on_finished():
            nonlocal finished_emitted
            finished_emitted = True

        worker.cancelled.connect(on_cancelled)
        worker.finished.connect(on_finished)

        worker.cancel()

        with (
            patch.object(
                worker,
                "_resolve_kick_playback_url",
                return_value="https://example.com/stream.m3u8",
            ),
            patch("yt_dlp.YoutubeDL") as mock_ydl,
        ):
            mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
                Exception("Cancelled")
            )
            worker.run()

        assert cancelled_emitted is True
        assert finished_emitted is True

    def test_cancellation_signal_counts_exact(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)

        cancelled_count = 0
        finished_count = 0
        succeeded_count = 0
        failed_count = 0

        def on_cancelled():
            nonlocal cancelled_count
            cancelled_count += 1

        def on_finished():
            nonlocal finished_count
            finished_count += 1

        def on_succeeded(_):
            nonlocal succeeded_count
            succeeded_count += 1

        def on_failed(_):
            nonlocal failed_count
            failed_count += 1

        worker.cancelled.connect(on_cancelled)
        worker.finished.connect(on_finished)
        worker.succeeded.connect(on_succeeded)
        worker.failed.connect(on_failed)

        worker.cancel()
        with (
            patch.object(
                worker,
                "_resolve_kick_playback_url",
                return_value="https://example.com/stream.m3u8",
            ),
            patch("yt_dlp.YoutubeDL") as mock_ydl,
        ):
            mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
                Exception("Cancelled")
            )
            worker.run()

        assert cancelled_count == 1
        assert finished_count == 1
        assert succeeded_count == 0
        assert failed_count == 0

    def test_success_signal_counts_exact(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        target_file = tmp_path / "Test Kick.mp4"
        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            target_final_path=target_file,
        )
        worker = DownloadWorker(req)

        succeeded_count = 0
        finished_count = 0
        cancelled_count = 0
        failed_count = 0

        def on_succeeded(_):
            nonlocal succeeded_count
            succeeded_count += 1

        def on_finished():
            nonlocal finished_count
            finished_count += 1

        def on_cancelled():
            nonlocal cancelled_count
            cancelled_count += 1

        def on_failed(_):
            nonlocal failed_count
            failed_count += 1

        worker.succeeded.connect(on_succeeded)
        worker.finished.connect(on_finished)
        worker.cancelled.connect(on_cancelled)
        worker.failed.connect(on_failed)

        def mock_extract(url, download=True):
            temp_ts = tmp_path / f".kolayindir_{worker.job_id}_kick.ts"
            temp_ts.write_text("ts content" * 100, encoding="utf-8")
            return {"title": "Test Kick"}

        def mock_ffmpeg(cmd, **kwargs):
            target_file.write_text("mp4 content" * 100, encoding="utf-8")
            m = MagicMock()
            m.returncode = 0
            m.wait.return_value = 0
            m.stdout = None
            return m

        with (
            patch.object(
                worker,
                "_resolve_kick_playback_url",
                return_value="https://example.com/stream.m3u8",
            ),
            patch("yt_dlp.YoutubeDL") as mock_ydl,
            patch("subprocess.Popen", side_effect=mock_ffmpeg),
            patch(
                "src.utils.probe_media_codecs",
                return_value={
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "duration": 100.0,
                    "height": 720,
                },
            ),
            patch.object(worker, "_save_completed_record"),
            patch.object(worker, "_handle_post_download_transcode"),
        ):
            mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
                mock_extract
            )
            worker.run()

        assert succeeded_count == 1
        assert finished_count == 1
        assert cancelled_count == 0
        assert failed_count == 0

    def test_failure_signal_counts_exact(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)

        failed_count = 0
        finished_count = 0
        cancelled_count = 0
        succeeded_count = 0

        def on_failed(_):
            nonlocal failed_count
            failed_count += 1

        def on_finished():
            nonlocal finished_count
            finished_count += 1

        def on_cancelled():
            nonlocal cancelled_count
            cancelled_count += 1

        def on_succeeded(_):
            nonlocal succeeded_count
            succeeded_count += 1

        worker.failed.connect(on_failed)
        worker.finished.connect(on_finished)
        worker.cancelled.connect(on_cancelled)
        worker.succeeded.connect(on_succeeded)

        with patch.object(worker, "_resolve_kick_playback_url", return_value=None):
            worker.run()

        assert failed_count == 1
        assert finished_count == 1
        assert cancelled_count == 0
        assert succeeded_count == 0

    def test_cleanup_deletes_job_temp_files_and_preserves_existing_user_files(
        self, tmp_path
    ):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        # Önceden var olan kullanıcı dosyası
        user_file = tmp_path / "user_document.txt"
        user_file.write_text("Önemli kullanıcı belgesi", encoding="utf-8")

        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)

        # İndirme sırasında oluşan geçici dosyalar
        part_file = tmp_path / "video.mp4.part"
        ytdl_file = tmp_path / "video.mp4.ytdl"
        ts_file = tmp_path / "segment_001.ts"
        frag_file = tmp_path / "video.frag1"
        half_mp4 = tmp_path / "video.mp4"

        for f in (part_file, ytdl_file, ts_file, frag_file, half_mp4):
            f.write_text("temporary data", encoding="utf-8")

        # İptal durumunda temizlik çalıştır
        clean_ok = worker._cleanup_job_files(is_cancel=True)

        assert clean_ok is True
        # Kullanıcı dosyası durmalı
        assert user_file.exists()
        # İşe ait tüm geçici ve yarım dosyalar silinmeli
        assert not part_file.exists()
        assert not ytdl_file.exists()
        assert not ts_file.exists()
        assert not frag_file.exists()
        assert not half_mp4.exists()

    def test_cleanup_preserves_completed_final_mp4_on_success(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        final_mp4 = tmp_path / "Kick Yayın.mp4"
        final_mp4.write_text("complete mp4 data", encoding="utf-8")

        req = DownloadRequest(
            url="https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            target_final_path=final_mp4,
        )
        worker = DownloadWorker(req)
        worker._last_filename = str(final_mp4)

        with patch(
            "src.download_worker.probe_media_codecs", return_value={"duration": 120.0}
        ):
            clean_ok = worker._cleanup_job_files(is_cancel=False)

        assert clean_ok is True
        assert final_mp4.exists()


# ---------------------------------------------------------------------------
# Playback Hata Ayrıştırma Testleri
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestPlaybackErrorReasonPreservation:
    def test_timeout_reason_preserved(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch(
            "curl_cffi.requests.post", side_effect=Exception("Connection timed out")
        ):
            m3u8, reason, _title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert reason == "timeout"

    def test_connection_error_reason_preserved(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch(
            "curl_cffi.requests.post", side_effect=Exception("Failed to resolve host")
        ):
            m3u8, reason, _title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert reason == "connection_error"

    def test_missing_playback_url_reason_preserved(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        with patch("curl_cffi.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"playback_url": {}}
            mock_post.return_value = mock_resp

            m3u8, reason, _title = _fetch_kick_playback_m3u8("test-uuid", {})

        assert m3u8 is None
        assert reason == "unverified_vod_stream"


# ---------------------------------------------------------------------------
# Manifest Önleme ve Sıkı Doğrulama Testleri
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestKickManifestPreventionAndValidation:
    def test_validate_final_download_rejects_manifest_stem(self, tmp_path):
        from src.utils import validate_final_download

        manifest_file = tmp_path / "manifest.mp4"
        manifest_file.write_text("x" * 2000, encoding="utf-8")

        valid, reason = validate_final_download(manifest_file, is_audio_mode=False)
        assert valid is False
        assert "Geçersiz dosya adı" in reason

    def test_validate_final_download_rejects_temp_ts_extension(self, tmp_path):
        from src.utils import validate_final_download

        ts_file = tmp_path / "video.ts"
        ts_file.write_text("x" * 2000, encoding="utf-8")

        valid, reason = validate_final_download(ts_file, is_audio_mode=False)
        assert valid is False
        assert "Beklenen dosya uzantısı" in reason or "Geçici dosya" in reason

    def test_validate_final_download_rejects_duration_zero(self, tmp_path):
        from src.utils import validate_final_download

        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_text("x" * 2000, encoding="utf-8")

        with patch(
            "src.utils.probe_media_codecs",
            return_value={"video_codec": "h264", "audio_codec": "aac", "duration": 0.0},
        ):
            valid, reason = validate_final_download(mp4_file, is_audio_mode=False)

        assert valid is False
        assert "Medya süresi 0 saniye" in reason

    def test_validate_final_download_rejects_missing_video_codec(self, tmp_path):
        from src.utils import validate_final_download

        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_text("x" * 2000, encoding="utf-8")

        with patch(
            "src.utils.probe_media_codecs",
            return_value={
                "video_codec": "none",
                "audio_codec": "aac",
                "duration": 10.0,
            },
        ):
            valid, reason = validate_final_download(mp4_file, is_audio_mode=False)

        assert valid is False
        assert "Video akışı (video stream) bulunamadı" in reason

    def test_validate_final_download_rejects_missing_audio_codec(self, tmp_path):
        from src.utils import validate_final_download

        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_text("x" * 2000, encoding="utf-8")

        with patch(
            "src.utils.probe_media_codecs",
            return_value={
                "video_codec": "h264",
                "audio_codec": "none",
                "duration": 10.0,
            },
        ):
            valid, reason = validate_final_download(mp4_file, is_audio_mode=False)

        assert valid is False
        assert "Ses akışı (audio stream) bulunamadı" in reason

    def test_validate_final_download_accepts_valid_mp4(self, tmp_path):
        from src.utils import validate_final_download

        mp4_file = tmp_path / "valid_video.mp4"
        mp4_file.write_text("x" * 2000, encoding="utf-8")

        with patch(
            "src.utils.probe_media_codecs",
            return_value={
                "video_codec": "h264",
                "audio_codec": "aac",
                "duration": 120.5,
            },
        ):
            valid, reason = validate_final_download(mp4_file, is_audio_mode=False)

        assert valid is True
        assert reason == "Doğrulama başarılı."

    def test_succeeded_signal_emits_real_mp4_path_even_if_extractor_title_is_manifest(
        self, tmp_path
    ):
        from pathlib import Path

        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        target_file = tmp_path / "Güvenli Kick Video Başlığı.mp4"
        temp_ts = tmp_path / ".kolayindir_testjob_kick.ts"
        temp_ts.write_text("temp ts data" * 100, encoding="utf-8")

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            target_final_path=target_file,
            job_id="testjob",
        )
        worker = DownloadWorker(req)
        worker._kick_m3u8 = "https://example.com/manifest.m3u8"

        emitted_path = ""

        def on_succeeded(path_str: str):
            nonlocal emitted_path
            emitted_path = path_str

        worker.succeeded.connect(on_succeeded)

        def mock_ffmpeg_run(cmd, **kwargs):
            # Target file yaz
            target_file.write_text("valid mp4 content" * 100, encoding="utf-8")
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.wait.return_value = 0
            return mock_proc

        with (
            patch("yt_dlp.YoutubeDL") as mock_ydl,
            patch("subprocess.Popen", side_effect=mock_ffmpeg_run),
            patch(
                "src.utils.probe_media_codecs",
                return_value={
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "duration": 300.0,
                    "height": 720,
                },
            ),
            patch.object(worker, "_save_completed_record") as mock_save_rec,
        ):
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = {
                "title": "manifest",
                "id": "manifest",
            }
            worker._run_kick_download(req.url)

        assert emitted_path == str(target_file.resolve())
        assert "manifest" not in Path(emitted_path).name
        assert mock_save_rec.called

    def test_history_record_sanitizes_manifest_media_id(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest, PlatformType

        target_file = tmp_path / "Kick Video.mp4"
        target_file.write_text("valid video content" * 100, encoding="utf-8")

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
            target_final_path=target_file,
        )
        worker = DownloadWorker(req)

        with (
            patch("src.download_worker.save_record") as mock_save,
            patch(
                "src.utils.probe_media_codecs",
                return_value={
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "height": 720,
                },
            ),
        ):
            worker._save_completed_record(
                PlatformType.KICK_VIDEO,
                {"id": "manifest"},
                override_target_file=target_file,
            )

        assert mock_save.called
        saved_rec = mock_save.call_args[0][0]
        assert saved_rec.media_id == "019faef9-eeb8-755e-a9b3-fb974cc7769e"
        assert saved_rec.final_path == str(target_file.resolve())

    def test_download_completed_dialog_sanitizes_manifest_display(self):
        from src.dialogs import DownloadCompletedDialog

        dlg = DownloadCompletedDialog(
            result_summary="manifest",
            filepath="C:\\Downloads\\manifest",
            video_codec="h264",
            audio_codec="aac",
            resolution="720p",
            filesize_text="10 MB",
        )
        label_text = dlg.message_label.text()
        assert "Tamamlanan: manifest" not in label_text
        assert "Dosya: manifest" not in label_text
        assert "Kick Videosu" in label_text


# ---------------------------------------------------------------------------
# Progress Hook, Safe UI Text ve Stall Watchdog Testleri
# ---------------------------------------------------------------------------


@pytest.mark.kick_experimental
class TestKickProgressAndStallWatchdog:
    def test_progress_percent_priority(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)

        emitted_pcts = []
        emitted_details = []

        worker.progress.connect(lambda p: emitted_pcts.append(p))
        worker.progress_details.connect(lambda d: emitted_details.append(d))

        # 1. total_bytes ile yüzde
        worker._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 50,
                "total_bytes": 100,
                "speed": 1000,
                "eta": 5,
            }
        )
        assert emitted_pcts[-1] == 50

        # 2. total_bytes_estimate ile yüzde
        worker._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 30,
                "total_bytes": 0,
                "total_bytes_estimate": 100,
                "speed": None,
                "eta": None,
            }
        )
        assert emitted_pcts[-1] == 30
        assert emitted_details[-1]["speed"] == "Hız hesaplanıyor…"
        assert emitted_details[-1]["eta"] == "Kalan süre hesaplanıyor…"

        # 3. fragment_index/fragment_count ile yüzde
        worker._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 1000,
                "total_bytes": 0,
                "total_bytes_estimate": 0,
                "fragment_index": 25,
                "fragment_count": 100,
                "speed": None,
                "eta": None,
            }
        )
        assert emitted_pcts[-1] == 25

    def test_watchdog_resets_on_activity(self, tmp_path):
        import time

        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._last_activity_time = time.time() - 25.0  # 25 saniye geçmiş

        # Aktivite gerçekleşti: downloaded_bytes arttı
        worker._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 500,
                "fragment_index": 1,
                "fragment_count": 10,
            }
        )

        # last_activity_time sıfırlanmış olmalı (güncel zaman)
        assert time.time() - worker._last_activity_time < 2.0

    def test_watchdog_raises_stall_timeout_after_30s_inactivity(self, tmp_path):
        import time

        import yt_dlp

        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._last_activity_time = time.time() - 31.0  # 31 saniye hareketsiz
        worker._last_downloaded_bytes = 500
        worker._last_fragment_index = 5

        # Aktivite yok (aynı downloaded_bytes ve fragment_index)
        with pytest.raises(yt_dlp.utils.DownloadError) as exc_info:
            worker._progress_hook(
                {
                    "status": "downloading",
                    "downloaded_bytes": 500,
                    "fragment_index": 5,
                    "fragment_count": 10,
                }
            )

        assert "STALL_TIMEOUT" in str(exc_info.value)

    def test_single_retry_on_stall_and_fail_on_second_stall(self, tmp_path):
        import yt_dlp

        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._kick_m3u8 = "https://example.com/stream.m3u8"

        failed_msg = ""
        worker.failed.connect(lambda err: nonlocal_failed(err))

        def nonlocal_failed(err):
            nonlocal failed_msg
            failed_msg = err

        extract_calls = 0

        def mock_extract(url, download=True):
            nonlocal extract_calls
            extract_calls += 1
            raise yt_dlp.utils.DownloadError(
                "STALL_TIMEOUT: Kick indirmesi sırasında veri akışı durdu."
            )

        with (
            patch("yt_dlp.YoutubeDL") as mock_ydl,
            patch.object(
                worker,
                "_resolve_kick_playback_url",
                return_value="https://example.com/fresh.m3u8",
            ) as mock_resolve,
        ):
            mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = (
                mock_extract
            )
            worker._run_kick_download(req.url)

        # 1 baslangic cozümleme + 1 stall retry = 2 resolve cagirisi
        assert extract_calls == 2
        assert mock_resolve.call_count == 2
        assert "Kick indirmesi sırasında veri akışı durdu." in failed_msg

    def test_vod_session_manifest_url_retrieval(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        mock_pb_resp = MagicMock()
        mock_pb_resp.status_code = 200
        mock_pb_resp.json.return_value = {
            "playback_url": {
                "vod": "https://web.kick.com/api/v1/stream/manifest.m3u8",
                "vod_session": "https://web.kick.com/api/v1/stream/vod_session",
            },
            "video_session": {"video_title": "Test Kick Stream"},
        }

        mock_vs_resp = MagicMock()
        mock_vs_resp.status_code = 200
        mock_vs_resp.json.return_value = {
            "manifestUrl": "https://d26yk4zpyhjeeq.cloudfront.net/v1/master/real_ivs_master.m3u8"
        }

        def mock_cffi_get(url, **kwargs):
            if "vod_session" in url:
                return mock_vs_resp
            return MagicMock(status_code=404)

        with (
            patch("curl_cffi.requests.post", return_value=mock_pb_resp),
            patch("curl_cffi.requests.get", side_effect=mock_cffi_get),
        ):
            m3u8_url, status, title = _fetch_kick_playback_m3u8(
                "019faef9-eeb8-755e-a9b3-fb974cc7769e", {}
            )

        assert (
            m3u8_url
            == "https://d26yk4zpyhjeeq.cloudfront.net/v1/master/real_ivs_master.m3u8"
        )
        assert status == 200
        assert title == "Test Kick Stream"

    def test_invalid_content_rejection_emits_unverified_turkish_error(self, tmp_path):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="360p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._kick_m3u8 = "https://example.com/stream.m3u8"

        failed_msg = ""
        succeeded_emitted = False

        worker.failed.connect(lambda err: nonlocal_failed(err))
        worker.succeeded.connect(lambda p: nonlocal_succeeded())

        def nonlocal_failed(err):
            nonlocal failed_msg
            failed_msg = err

        def nonlocal_succeeded():
            nonlocal succeeded_emitted
            succeeded_emitted = True

        fake_ts = tmp_path / f".kolayindir_{worker.job_id}_kick.ts"
        fake_ts.write_bytes(b"dummy ts data")

        with (
            patch("yt_dlp.YoutubeDL"),
            patch("subprocess.Popen") as mock_popen,
            patch(
                "src.download_worker.validate_final_download",
                return_value=(False, "Geçersiz içerik veya reklam akışı"),
            ),
            patch.object(worker, "_save_completed_record") as mock_save_history,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout.readline.side_effect = ["", ""]
            mock_popen.return_value = mock_proc

            worker._run_kick_download(req.url)

        assert not succeeded_emitted
        assert mock_save_history.call_count == 0
        assert (
            "Kick tarafından döndürülen akışın orijinal VOD olduğu doğrulanamadı."
            in failed_msg
        )

    def test_is_valid_kick_manifest_url_rejects_ssai_and_invalid_urls(self):
        from src.utils import is_valid_kick_manifest_url

        assert is_valid_kick_manifest_url(
            "https://d26yk4zpyhjeeq.cloudfront.net/v1/master/stream.m3u8"
        )
        assert not is_valid_kick_manifest_url(
            "https://web.kick.com/api/v1/stream/manifest.m3u8"
        )
        assert not is_valid_kick_manifest_url("https://example.com/stream.mp4")
        assert not is_valid_kick_manifest_url("not_a_url")
        assert not is_valid_kick_manifest_url("")
        assert not is_valid_kick_manifest_url(None)

    def test_fetch_kick_playback_m3u8_rejects_playback_url_vod_fallback(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        mock_pb_resp = MagicMock()
        mock_pb_resp.status_code = 200
        mock_pb_resp.json.return_value = {
            "playback_url": {
                "vod": "https://web.kick.com/api/v1/stream/manifest.m3u8",
            },
            "video_session": {"video_title": "Test Kick Stream"},
        }

        with patch("curl_cffi.requests.post", return_value=mock_pb_resp):
            m3u8_url, status, title = _fetch_kick_playback_m3u8(
                "019faef9-eeb8-755e-a9b3-fb974cc7769e", {}
            )

        assert m3u8_url is None
        assert status == "unverified_vod_stream"
        assert title == "Test Kick Stream"

    def test_fetch_kick_playback_m3u8_handles_vod_session_403_and_timeout(self):
        from src.metadata_worker import _fetch_kick_playback_m3u8

        mock_pb_resp = MagicMock()
        mock_pb_resp.status_code = 200
        mock_pb_resp.json.return_value = {
            "playback_url": {
                "vod": "https://web.kick.com/api/v1/stream/manifest.m3u8",
                "vod_session": "https://web.kick.com/api/v1/stream/vod_session",
            },
        }

        mock_vs_resp = MagicMock(status_code=403)

        with (
            patch("curl_cffi.requests.post", return_value=mock_pb_resp),
            patch("curl_cffi.requests.get", return_value=mock_vs_resp),
        ):
            m3u8_url, status, _title = _fetch_kick_playback_m3u8(
                "019faef9-eeb8-755e-a9b3-fb974cc7769e", {}
            )

        assert m3u8_url is None
        assert status == "unverified_vod_stream"

    def test_download_worker_start_gets_fresh_manifest_and_fails_if_unverified(
        self, tmp_path
    ):
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://kick.com/konsoloyun/videos/019faef9-eeb8-755e-a9b3-fb974cc7769e",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="360p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._kick_m3u8 = "https://web.kick.com/api/v1/stream/manifest.m3u8"

        failed_msg = ""
        worker.failed.connect(lambda err: nonlocal_failed(err))

        def nonlocal_failed(err):
            nonlocal failed_msg
            failed_msg = err

        with patch.object(worker, "_resolve_kick_playback_url", return_value=None):
            worker._run_kick_download(req.url)

        assert "Kick’in gerçek VOD bağlantısı alınamadı." in failed_msg


# ---------------------------------------------------------------------------
# Kick Geçici Devre Dışı Bırakma Testleri
# ---------------------------------------------------------------------------


class TestKickDisabledUnitTests:
    """QApplication veya MainWindow oluşturmadan Kick'in geçici devre dışı durumunu doğrulayan saf birim testler."""

    def test_kick_platform_is_temporarily_disabled(self):
        from src.models import PlatformType, is_platform_temporarily_disabled

        assert (
            is_platform_temporarily_disabled(
                PlatformType.KICK_VIDEO,
                "https://kick.com/user/videos/12345678-abcd-ef12-3456-567890abcdef",
            )
            is True
        )
        assert is_platform_temporarily_disabled(PlatformType.KICK_VIDEO) is True

    def test_kick_disabled_title_and_message(self):
        from src.models import KICK_DISABLED_MESSAGE, KICK_DISABLED_TITLE

        assert KICK_DISABLED_TITLE == "Kick Desteği Geçici Olarak Kullanılamıyor"
        assert (
            "Kick’in orijinal yayın akışı güvenilir biçimde doğrulanamadığı için Kick VOD indirme özelliği geçici olarak devre dışı bırakıldı."
            in KICK_DISABLED_MESSAGE
        )

    def test_other_platforms_not_disabled(self):
        from src.models import PlatformType, is_platform_temporarily_disabled

        assert (
            is_platform_temporarily_disabled(
                PlatformType.YOUTUBE_VIDEO, "https://www.youtube.com/watch?v=123"
            )
            is False
        )
        assert (
            is_platform_temporarily_disabled(
                PlatformType.INSTAGRAM_REEL, "https://instagram.com/reel/123"
            )
            is False
        )
        assert (
            is_platform_temporarily_disabled(
                PlatformType.TWITTER_POST, "https://twitter.com/user/status/123"
            )
            is False
        )
        assert (
            is_platform_temporarily_disabled(
                PlatformType.TIKTOK_VIDEO, "https://tiktok.com/@user/video/123"
            )
            is False
        )

    def test_kick_badge_text_indicates_disabled(self):
        from src.models import PlatformType, get_platform_badge_text

        assert (
            get_platform_badge_text(PlatformType.KICK_VIDEO)
            == "Kick — Geçici olarak kullanılamıyor"
        )

    def test_youtube_single_video_kick_watchdog_bypassed(self, tmp_path):
        """YouTube tek video indirmesinde Kick watchdog çalıştırılmaz ve stall hatası üretilmez."""
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="720p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._last_activity_time = 100.0  # 30 saniyeden uzun süre önce
        with patch("time.time", return_value=200.0):
            # _progress_hook çağrısı STALL_TIMEOUT fırlatmamalı
            worker._progress_hook(
                {"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000}
            )

    def test_youtube_playlist_kick_watchdog_bypassed(self, tmp_path):
        """YouTube playlist indirmesinde Kick watchdog çalıştırılmaz."""
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://www.youtube.com/playlist?list=PL6F_cmvZa0pF4IOzeMekeUNp_QAxKOqcX",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="480p'ye kadar",
            playlist=True,
        )
        worker = DownloadWorker(req)
        worker._last_activity_time = 100.0
        with patch("time.time", return_value=200.0):
            worker._progress_hook(
                {"status": "downloading", "downloaded_bytes": 100, "total_bytes": 1000}
            )

    def test_youtube_playlist_item_pause_over_30s_no_kick_timeout(self, tmp_path):
        """Playlist öğeleri arasındaki 30 saniyeyi aşan beklemede Kick STALL_TIMEOUT üretilmez."""
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://www.youtube.com/playlist?list=PL6F_cmvZa0pF4IOzeMekeUNp_QAxKOqcX",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="480p'ye kadar",
            playlist=True,
        )
        worker = DownloadWorker(req)
        # Önce 1. video sonlandırıldı
        worker._progress_hook(
            {"status": "downloading", "downloaded_bytes": 1000, "total_bytes": 1000}
        )
        import time as _time

        # 40 saniye sonra 2. video indirmesi başladı
        with patch("time.time", return_value=_time.time() + 40.0):
            worker._progress_hook(
                {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 500}
            )

    def test_ffmpeg_postprocessing_no_kick_timeout(self, tmp_path):
        """FFmpeg işleme sırasında ilerleme sabit kalsa bile Kick timeout üretilmez."""
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="1080p'ye kadar",
            playlist=False,
        )
        worker = DownloadWorker(req)
        worker._last_activity_time = 100.0
        with patch("time.time", return_value=200.0):
            worker._postprocessor_hook(
                {"postprocessor": "FFmpegMerger", "status": "started"}
            )

    def test_instagram_download_no_kick_error(self):
        """Instagram indirme hatalarında Kick hata mesajı gösterilmez."""
        from src.models import translate_social_error

        err = "STALL_TIMEOUT: Kick indirmesi sırasında veri akışı durdu."
        translated = translate_social_error(
            err, "https://www.instagram.com/reel/C123456789/"
        )
        assert "Kick" not in translated
        assert "İndirme sırasında uzun süre veri alınamadı" in translated

    def test_twitter_download_no_kick_error(self):
        """X/Twitter indirme hatalarında Kick hata mesajı gösterilmez."""
        from src.models import translate_social_error

        err = "STALL_TIMEOUT: Kick indirmesi sırasında veri akışı durdu."
        translated = translate_social_error(
            err, "https://twitter.com/user/status/1234567890"
        )
        assert "Kick" not in translated
        assert "İndirme sırasında uzun süre veri alınamadı" in translated

    def test_tiktok_download_no_kick_error(self):
        """TikTok indirme hatalarında Kick hata mesajı gösterilmez."""
        from src.models import translate_social_error

        err = "STALL_TIMEOUT: Kick indirmesi sırasında veri akışı durdu."
        translated = translate_social_error(
            err, "https://www.tiktok.com/@user/video/1234567890"
        )
        assert "Kick" not in translated
        assert "İndirme sırasında uzun süre veri alınamadı" in translated

    def test_kick_vod_disabled_on_main(self):
        """Kick VOD main dalında geçici olarak devre dışıdır."""
        from src.models import PlatformType, is_platform_temporarily_disabled

        assert (
            is_platform_temporarily_disabled(
                PlatformType.KICK_VIDEO,
                "https://kick.com/user/videos/12345678-abcd-ef12-3456-567890abcdef",
            )
            is True
        )

    def test_kick_stall_message_isolation(self):
        """Kullanıcıya gösterilen Kick stall mesajı yalnız Kick platformunda üretilir veya genel mesaja dönüştürülür."""
        from src.models import translate_social_error

        yt_err = translate_social_error(
            "STALL_TIMEOUT", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert (
            yt_err
            == "İndirme sırasında uzun süre veri alınamadı. İnternet bağlantınızı kontrol edip yeniden deneyin."
        )

    def test_playlist_worker_cancel_clean_shutdown(self, tmp_path):
        """Playlist worker iptal edildiğinde temiz kapama bayrağı ve durum güncellenir."""
        from src.download_worker import DownloadWorker
        from src.models import DownloadRequest

        req = DownloadRequest(
            url="https://www.youtube.com/playlist?list=PL6F_cmvZa0pF4IOzeMekeUNp_QAxKOqcX",
            output_dir=tmp_path,
            media_type="Video (MP4)",
            quality="480p'ye kadar",
            playlist=True,
        )
        worker = DownloadWorker(req)
        worker.cancelled.connect(
            lambda: setattr(worker, "_cancelled_signal_seen", True)
        )
        worker.cancel()
        assert worker._cancel_requested is True


@pytest.mark.qt_integration
class TestKickDisabledBehavior:
    """Kick VOD özelliğinin geçici olarak devre dışı bırakılmasını ve diğer platformların etkilenmediğini doğrular."""

    def test_kick_url_metadata_worker_not_started(self, main_window):
        main_window.url_input.setText(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        )
        with patch("src.main_window.AppMessageDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = None
            main_window.analyze_url()
        assert main_window._metadata_thread is None
        assert main_window._metadata_worker is None

    def test_kick_url_download_worker_not_started(self, main_window):
        main_window.url_input.setText(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        )
        with patch("src.main_window.AppMessageDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = None
            main_window.start_download()
        assert main_window._download_thread is None
        assert main_window._download_worker is None

    def test_kick_url_download_button_remains_disabled(self, main_window):
        main_window.url_input.setText(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        )
        with patch("src.main_window.AppMessageDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = None
            main_window.analyze_url()
        assert not main_window.download_button.isEnabled()

    def test_kick_url_shows_correct_disabled_message(self, main_window):
        main_window.url_input.setText(
            "https://kick.com/jahrein/videos/019fa488-5d20-71c0-a869-8716cf8e8189"
        )
        captured = {}

        def mock_dialog_constructor(
            title, message, icon_type="info", parent=None, buttons=None
        ):
            captured["title"] = title
            captured["message"] = message
            captured["icon_type"] = icon_type
            mock_inst = MagicMock()
            mock_inst.exec.return_value = None
            return mock_inst

        with patch(
            "src.main_window.AppMessageDialog", side_effect=mock_dialog_constructor
        ):
            main_window.analyze_url()

        assert captured["title"] == "Kick Desteği Geçici Olarak Kullanılamıyor"
        assert (
            "Kick’in orijinal yayın akışı güvenilir biçimde doğrulanamadığı için Kick VOD indirme özelliği geçici olarak devre dışı bırakıldı."
            in captured["message"]
        )
        assert captured["title"] != "İnceleme Başarısız"

    def test_youtube_inspection_unaffected(self, main_window):
        main_window.url_input.setText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        with patch("src.main_window.MetadataWorker") as mock_worker_cls:
            mock_worker = MagicMock()
            mock_worker_cls.return_value = mock_worker
            with patch("PySide6.QtCore.QThread"):
                main_window.analyze_url()
        assert main_window.analyze_button.text() == "İnceleniyor…"

    def test_instagram_inspection_unaffected(self, main_window):
        main_window.url_input.setText("https://www.instagram.com/reel/C123456789/")
        with patch("src.main_window.MetadataWorker") as mock_worker_cls:
            mock_worker = MagicMock()
            mock_worker_cls.return_value = mock_worker
            with patch("PySide6.QtCore.QThread"):
                main_window.analyze_url()
        assert main_window.analyze_button.text() == "İnceleniyor…"

    def test_twitter_inspection_unaffected(self, main_window):
        main_window.url_input.setText(
            "https://twitter.com/user/status/1234567890123456789"
        )
        with patch("src.main_window.MetadataWorker") as mock_worker_cls:
            mock_worker = MagicMock()
            mock_worker_cls.return_value = mock_worker
            with patch("PySide6.QtCore.QThread"):
                main_window.analyze_url()
        assert main_window.analyze_button.text() == "İnceleniyor…"

    def test_tiktok_inspection_unaffected(self, main_window):
        main_window.url_input.setText(
            "https://www.tiktok.com/@user/video/1234567890123456789"
        )
        with patch("src.main_window.MetadataWorker") as mock_worker_cls:
            mock_worker = MagicMock()
            mock_worker_cls.return_value = mock_worker
            with patch("PySide6.QtCore.QThread"):
                main_window.analyze_url()
        assert main_window.analyze_button.text() == "İnceleniyor…"
