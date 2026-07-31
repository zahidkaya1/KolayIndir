"""Uygulama veri modelleri."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
    TIKTOK_VIDEO = "tiktok_video"
    TIKTOK_SHORT_LINK = "tiktok_short_link"
    TIKTOK_PROFILE = "tiktok_profile"
    TIKTOK_LIVE = "tiktok_live"
    TIKTOK_SLIDESHOW = "tiktok_slideshow"
    KICK_VIDEO = "kick_video"
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

    if "tiktok.com" in raw:
        if "vm.tiktok.com" in raw or "vt.tiktok.com" in raw:
            return PlatformType.TIKTOK_SHORT_LINK
        if "/live" in raw or "live.tiktok.com" in raw:
            return PlatformType.TIKTOK_LIVE
        if "/photo/" in raw:
            return PlatformType.TIKTOK_SLIDESHOW
        if "/video/" in raw:
            return PlatformType.TIKTOK_VIDEO
        if re.search(r"tiktok\.com/@[^/]+/?(?:\?.*)?$", raw):
            return PlatformType.TIKTOK_PROFILE
        return PlatformType.TIKTOK_VIDEO

    if "kick.com" in raw:
        if re.search(r"kick\.com/([^/]+)/videos/([a-f0-9\-]{8,})", raw):
            return PlatformType.KICK_VIDEO
        return PlatformType.UNKNOWN

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
        PlatformType.TIKTOK_VIDEO: "TikTok",
        PlatformType.TIKTOK_SHORT_LINK: "TikTok",
        PlatformType.TIKTOK_PROFILE: "TikTok",
        PlatformType.TIKTOK_LIVE: "TikTok",
        PlatformType.TIKTOK_SLIDESHOW: "TikTok Slaytı",
        PlatformType.KICK_VIDEO: "Kick",
        PlatformType.UNKNOWN: "Diğer",
    }
    return badge_map.get(platform, "Diğer")


def is_rehydration_error(error_msg: str) -> bool:
    """TikTok extractor'ının universal data for rehydration hatası verip vermediğini denetler."""
    if not error_msg:
        return False
    msg_lower = error_msg.lower()
    return "universal data for rehydration" in msg_lower or "unable to extract universal data" in msg_lower


def translate_social_error(exc_or_msg: Exception | str, url: str) -> str:
    msg = str(exc_or_msg)
    msg_lower = msg.lower()
    platform = detect_platform_type(url)

    if platform == PlatformType.KICK_VIDEO or "kick.com" in url.lower():
        raw_url = url.strip().lower()
        if "/clips/" in raw_url or "clip=" in raw_url:
            return "Kick klipleri henüz desteklenmiyor. Yalnızca tamamlanmış Kick VOD videoları destekleniyor."
        if re.search(r"kick\.com/[^/]+/videos/?(?:\?.*)?$", raw_url):
            return "Kick kanal videoları listesi desteklenmiyor. Lütfen indirmek istediğiniz tekil VOD videosunun bağlantısını yapıştırın."
        if "/videos/" not in raw_url or "/live" in raw_url:
            return "Kick canlı yayınları henüz desteklenmiyor."
        if any(term in msg_lower for term in ("geçersiz", "invalid")):
            return "Geçersiz Kick video bağlantısı veya UUID."
        if "403" in msg_lower or "forbidden" in msg_lower or "access denied" in msg_lower:
            return "Kick erişim isteğini reddetti. Tarayıcı uyumluluk yöntemi denenemedi veya yeterli olmadı."
        if any(term in msg_lower for term in ("404", "not found", "json metadata", "v1/video", "yeni yapıyı desteklemiyor")):
            return (
                "Kick desteği geçici olarak kullanılamıyor\n\n"
                "Kick, VOD bağlantı sistemini yakın zamanda değiştirdi. Kullanılan yt-dlp sürümü henüz bu yeni yapıyı desteklemiyor.\n\n"
                "Kolayİndir ve yt-dlp güncellendiğinde tekrar deneyin."
            )
        if "m3u8 bulunamadı" in msg_lower or "no formats" in msg_lower or "oynatma url" in msg_lower:
            return "Kick video akış adresi (m3u8) bulunamadı."
        if any(term in msg_lower for term in ("subscriber", "login required", "sign in", "auth", "private")):
            return "Bu video giriş veya abonelik gerektiriyor olabilir."

    if platform in (
        PlatformType.TIKTOK_VIDEO,
        PlatformType.TIKTOK_SHORT_LINK,
        PlatformType.TIKTOK_PROFILE,
        PlatformType.TIKTOK_LIVE,
        PlatformType.TIKTOK_SLIDESHOW,
    ) or "tiktok" in url.lower():
        if is_rehydration_error(msg_lower):
            return (
                "TikTok bağlantısı çözüldü ancak bu videonun verileri şu anda yt-dlp tarafından okunamadı. "
                "Bu sorun bazı TikTok videolarında oluşabilir. Başka bir video deneyin veya yt-dlp güncellemesini kontrol edin."
            )
        if any(term in msg_lower for term in ("impersonation", "impersonate", "curl_cffi")):
            return "TikTok bağlantısını çözmek için gereken tarayıcı taklidi bileşeni bulunamadı."
        if "unable to extract webpage video data" in msg_lower or "unable to extract video data" in msg_lower:
            return "TikTok video bilgileri şu anda alınamadı. TikTok geçici olarak değişmiş olabilir; yt-dlp güncellemesini kontrol edin."
        if "429" in msg_lower or "too many requests" in msg_lower:
            return "TikTok geçici olarak çok fazla istek algıladı. Bir süre bekleyip yeniden deneyin."
        if "ip" in msg_lower and any(term in msg_lower for term in ("block", "banned", "deny", "denied")):
            return "TikTok bu bağlantıya mevcut internet bağlantınızdan erişimi engelledi. Daha sonra yeniden deneyin."
        if any(term in msg_lower for term in ("private", "protected")):
            return "Bu TikTok videosu özel bir hesaba ait. İçeriğe erişebilen bir tarayıcı oturumu gerekiyor."
        if any(term in msg_lower for term in ("login required", "sign in required", "log in", "cookies required", "authentication required")):
            return "TikTok bu içerik için giriş yapılmış bir oturum istiyor."
        if any(term in msg_lower for term in ("not found", "deleted", "404", "video unavailable", "does not exist")):
            return "TikTok videosu bulunamadı, silinmiş veya artık erişilemiyor olabilir."
        if any(term in msg_lower for term in ("short link", "could not resolve")):
            return "TikTok kısa bağlantısı çözümlenemedi. Bağlantıyı TikTok uygulamasından yeniden kopyalayın."

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
    preferred_impersonation: str | None = None
    successful_request_url: str | None = None
    convert_hevc_to_h264: bool = True
    job_id: str = ""
    target_final_path: Path | None = None


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
    is_slideshow: bool = False
    view_count: int | None = None
    like_count: int | None = None
    track_name: str = ""
    preferred_impersonation: str | None = None
    successful_request_url: str | None = None
    successful_attempt_type: str | None = None
    available_heights: list[int] = field(default_factory=list)
    available_formats: list[dict] = field(default_factory=list)
    selected_vcodec: str = ""
    selected_acodec: str = ""
    selected_fps: float | None = None


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
