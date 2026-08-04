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
    FACEBOOK_VIDEO = "facebook_video"
    FACEBOOK_REEL = "facebook_reel"
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

    # Facebook
    try:
        from urllib.parse import urlparse
        url_to_parse = url.strip()
        if "://" not in url_to_parse:
            url_to_parse = f"https://{url_to_parse}"
        parsed = urlparse(url_to_parse)
        host = (parsed.hostname or "").lower()
    except (ValueError, TypeError, AttributeError, UnicodeError):
        host = ""
        parsed = None

    if parsed and host:
        is_fb_host = (
            host in (
                "facebook.com",
                "www.facebook.com",
                "m.facebook.com",
                "web.facebook.com",
                "mbasic.facebook.com",
                "touch.facebook.com",
                "fb.watch",
                "www.fb.watch",
            )
            or host.endswith((".facebook.com", ".fb.watch"))
        )
        if is_fb_host:
            path = parsed.path.lower().strip("/")
            query = parsed.query.lower()

            if not path:
                if "v=" in query:
                    return PlatformType.FACEBOOK_VIDEO
                return PlatformType.UNKNOWN

            blocked_pages = (
                "login",
                "login.php",
                "marketplace",
                "notifications",
                "messages",
                "settings",
                "help",
                "groups",
                "pages",
                "events",
                "gaming",
                "friends",
                "saved",
                "memories",
                "recover",
                "checkpoint",
            )
            first_segment = path.split("/")[0]
            if first_segment in blocked_pages or path in blocked_pages:
                return PlatformType.UNKNOWN

            if (
                path.startswith(("reel/", "reels/", "share/r/"))
                or "/reel/" in path
                or "/reels/" in path
            ):
                return PlatformType.FACEBOOK_REEL

            if path == "watch" or path.startswith("watch/"):
                return PlatformType.FACEBOOK_VIDEO

            if "fb.watch" in host:
                return PlatformType.FACEBOOK_VIDEO if path else PlatformType.UNKNOWN

            if path.startswith(("share/v/", "share/p/", "share/")):
                return PlatformType.FACEBOOK_VIDEO

            if "/videos/" in path or path.startswith("videos/") or path.endswith("/videos"):
                return PlatformType.FACEBOOK_VIDEO

            if (
                "/posts/" in path
                or path.startswith(
                    ("posts/", "story.php", "permalink.php", "video.php", "photo.php")
                )
                or "/photos/" in path
            ):
                return PlatformType.FACEBOOK_VIDEO

            segments = [s for s in path.split("/") if s]
            if len(segments) >= 2:
                return PlatformType.FACEBOOK_VIDEO

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
        PlatformType.KICK_VIDEO: "Kick — Geçici olarak kullanılamıyor",
        PlatformType.FACEBOOK_VIDEO: "Facebook",
        PlatformType.FACEBOOK_REEL: "Facebook",
        PlatformType.UNKNOWN: "Diğer",
    }
    return badge_map.get(platform, "Diğer")


KICK_DISABLED_TITLE = "Kick Desteği Geçici Olarak Kullanılamıyor"
KICK_DISABLED_MESSAGE = (
    "Kick’in orijinal yayın akışı güvenilir biçimde doğrulanamadığı için Kick VOD indirme özelliği geçici olarak devre dışı bırakıldı."
)


def is_platform_temporarily_disabled(platform: PlatformType, url: str = "") -> bool:
    """Belirtilen platformun veya URL'in geçici olarak devre dışı bırakılıp bırakılmadığını kontrol eder."""
    return platform == PlatformType.KICK_VIDEO or "kick.com" in url.lower()


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

    if is_platform_temporarily_disabled(platform, url):
        return f"Kick desteği geçici olarak kullanılamıyor\n\n{KICK_DISABLED_MESSAGE}"

    if platform in (PlatformType.FACEBOOK_VIDEO, PlatformType.FACEBOOK_REEL) or "facebook" in url.lower() or "fb.watch" in url.lower():
        if "cannot parse data" in msg_lower:
            return "Facebook video bilgileri alınamadı. Facebook sayfa yapısını değiştirmiş olabilir veya bu bağlantı şu anda desteklenmiyor."
        if any(term in msg_lower for term in ("no video formats", "no video format", "no downloadable video", "there is no video", "there's no video")):
            return "Bu Facebook bağlantısında indirilebilir video bulunamadı."
        if any(term in msg_lower for term in ("only photo", "only photos", "photo post", "contains photo", "no media")):
            return "Bu Facebook gönderisinde indirilebilir bir video bulunamadı."
        if any(term in msg_lower for term in ("login required", "sign in required", "log in", "registered users", "this content isn't available", "private", "must log in", "cookies required", "authentication required")):
            return "Bu Facebook içeriğini görüntülemek için tarayıcı oturumu gerekebilir. Oturumla Tekrar Dene seçeneğini kullanabilirsiniz."
        if any(term in msg_lower for term in ("unavailable", "removed", "deleted", "does not exist", "not found", "404", "content is not available")):
            return "Facebook videosu kaldırılmış, gizlenmiş veya kullanılamıyor olabilir."
        if any(term in msg_lower for term in ("rate limit", "429", "too many requests", "temporarily blocked", "temporary block", "ip block", "banned")):
            return "Facebook isteği geçici olarak sınırlandırdı. Bir süre sonra yeniden deneyin."
        if any(term in msg_lower for term in ("unable to extract", "extractor")):
            return "Facebook video bilgileri şu anda alınamadı. Facebook sayfa yapısını değiştirmiş olabilir veya bu bağlantı şu anda desteklenmiyor."

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

    if any(term in msg_lower for term in ("stall_timeout", "veri akışı durdu", "read timed out", "socket timeout", "connection timed out", "download timeout")):
        if platform == PlatformType.KICK_VIDEO:
            return "Kick indirmesi sırasında veri akışı durdu. Bağlantıyı yeniden inceleyip tekrar deneyin."
        return "İndirme sırasında uzun süre veri alınamadı. İnternet bağlantınızı kontrol edip yeniden deneyin."

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
    rate_limit_bps: int | None = None


@dataclass(slots=True)
class QueueItem:
    id: str
    url: str
    platform: str
    title: str = "Video"
    media_type: str = "Video (MP4)"
    quality: str = "1080p'ye kadar"
    playlist: bool = False
    output_dir: Path | None = None
    browser: str | None = None
    status: str = "Bekliyor"
    error_msg: str = ""
    progress_percent: int = 0
    progress_text: str = ""
    rate_limit_bps: int | None = None


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
