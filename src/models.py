"""Uygulama veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PlatformType(Enum):
    YOUTUBE_VIDEO = "youtube_video"
    YOUTUBE_PLAYLIST = "youtube_playlist"
    TWITTER_POST = "twitter_post"
    INSTAGRAM_REEL = "instagram_reel"
    INSTAGRAM_POST = "instagram_post"
    INSTAGRAM_STORY = "instagram_story"
    INSTAGRAM_HIGHLIGHT = "instagram_highlight"
    UNKNOWN = "unknown"


def detect_platform_type(url: str) -> PlatformType:
    if not url or not isinstance(url, str):
        return PlatformType.UNKNOWN

    raw = url.strip().lower()

    if "youtube.com" in raw or "youtu.be" in raw:
        if "list=" in raw or "/playlist" in raw:
            return PlatformType.YOUTUBE_PLAYLIST
        return PlatformType.YOUTUBE_VIDEO

    if "twitter.com" in raw or "x.com" in raw:
        return PlatformType.TWITTER_POST

    if "instagram.com" in raw:
        if "/stories/highlights/" in raw:
            return PlatformType.INSTAGRAM_HIGHLIGHT
        if "/stories/" in raw:
            return PlatformType.INSTAGRAM_STORY
        if "/reel/" in raw or "/reels/" in raw:
            return PlatformType.INSTAGRAM_REEL
        if "/p/" in raw or "/tv/" in raw:
            return PlatformType.INSTAGRAM_POST
        return PlatformType.INSTAGRAM_POST

    return PlatformType.UNKNOWN


def get_platform_badge_text(platform: PlatformType) -> str:
    badge_map = {
        PlatformType.YOUTUBE_VIDEO: "YouTube",
        PlatformType.YOUTUBE_PLAYLIST: "YouTube Oynatma Listesi",
        PlatformType.TWITTER_POST: "X / Twitter",
        PlatformType.INSTAGRAM_REEL: "Instagram Reel",
        PlatformType.INSTAGRAM_POST: "Instagram Gönderisi",
        PlatformType.INSTAGRAM_STORY: "Instagram Hikâyesi",
        PlatformType.INSTAGRAM_HIGHLIGHT: "Instagram Öne Çıkan",
        PlatformType.UNKNOWN: "Diğer",
    }
    return badge_map.get(platform, "Diğer")


def translate_social_error(exc_or_msg: Exception | str, url: str) -> str:
    msg = str(exc_or_msg)
    msg_lower = msg.lower()
    platform = detect_platform_type(url)

    if platform == PlatformType.TWITTER_POST:
        if any(term in msg_lower for term in ("protected", "private account", "not authorized", "this tweet is from a protected account")):
            return "Bu gönderi korumalı bir hesaba ait. İçeriğe tarayıcıda erişebildiğiniz bir oturum gerekebilir."
        if any(term in msg_lower for term in ("no video", "there's no video", "no media", "no downloadable video", "unsupported url", "did not find any video")):
            return "Bu X gönderisinde indirilebilir video bulunamadı."
        if any(term in msg_lower for term in ("extractor", "unable to extract", "twitter", "x.com")):
            return "X bağlantısı şu anda çözümlenemedi. yt-dlp güncellemesi gerekebilir."

    if platform in (PlatformType.INSTAGRAM_STORY, PlatformType.INSTAGRAM_HIGHLIGHT):
        if any(term in msg_lower for term in ("login", "cookie", "log in", "redirect", "private")):
            return "Bu hikâyeye erişmek için Instagram oturumu gerekiyor."
        if any(term in msg_lower for term in ("expired", "not available", "404", "does not exist", "unavailable")):
            return "Instagram hikâyesi artık erişilebilir değil veya hesabınızın erişimi bulunmuyor."

    if platform in (PlatformType.INSTAGRAM_REEL, PlatformType.INSTAGRAM_POST):
        if any(term in msg_lower for term in ("no video", "there is no video", "there's no video", "only photo", "only photos", "contains photo", "photo post", "no media")):
            return "Bu gönderide indirilebilir video bulunamadı. Fotoğraf indirme desteği henüz eklenmedi."
        if any(term in msg_lower for term in ("login", "cookie", "log in", "redirect", "private", "require")):
            return "Instagram bu içerik için oturum isteyebilir. Firefox oturumunu seçip yeniden deneyin."

    if any(term in msg_lower for term in ("no video", "there is no video", "only photo", "only photos", "contains photo")):
        if "instagram" in url.lower():
            return "Bu gönderide indirilebilir video bulunamadı. Fotoğraf indirme desteği henüz eklenmedi."
        if "twitter" in url.lower() or "x.com" in url.lower():
            return "Bu X gönderisinde indirilebilir video bulunamadı."


    return msg


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    url: str
    output_dir: Path
    media_type: str
    quality: str
    playlist: bool
    browser: str | None = None
    preferred_browser: str | None = None
    preferred_profile: tuple[str, str] | None = None


@dataclass
class MediaMetadata:
    title: str = ""
    uploader: str = ""
    source_name: str = ""
    duration_seconds: float | None = None
    duration_text: str = ""
    thumbnail_url: str = ""
    webpage_url: str = ""
    media_id: str = ""
    requested_quality: str = ""
    maximum_available_height: int | None = None
    selected_height: int | None = None
    selected_resolution: str = ""
    selected_extension: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    estimated_size_bytes: int | None = None
    playlist_count: int | None = None
    is_playlist: bool = False
    platform_type: PlatformType = PlatformType.UNKNOWN
    session_browser: str | None = None
    session_profile: tuple[str, str] | None = None





def format_bytes(size: float | None) -> str:
    """Byte değerini Türkçe ondalık gösterimle KB/MB/GB biçimine dönüştürür."""
    if size is None or size <= 0:
        return "Hesaplanamadı"
    size_float = float(size)
    if size_float < 1024 * 1024:
        kb = size_float / 1024
        return f"{kb:.0f} KB"
    if size_float < 1024 * 1024 * 1024:
        mb = size_float / (1024 * 1024)
        formatted_mb = f"{mb:.1f}".replace(".", ",")
        return f"{formatted_mb} MB"
    gb = size_float / (1024 * 1024 * 1024)
    formatted_gb = f"{gb:.2f}".replace(".", ",")
    return f"{formatted_gb} GB"


def format_duration(seconds: float | None) -> str:

    """Saniyeyi MM:SS veya HH:MM:SS biçimine dönüştürür."""
    if seconds is None or seconds < 0:
        return ""
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

