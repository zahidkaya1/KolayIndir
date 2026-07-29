"""yt-dlp seçeneklerini tek bir yerde üretir."""

from __future__ import annotations

from typing import Any

from src.models import DownloadRequest, PlatformType, detect_platform_type

QUALITY_HEIGHTS: dict[str, int | None] = {
    "En iyi kullanılabilir kalite": None,
    "En iyi kalite": None,
    "1080p'ye kadar": 1080,
    "1080p": 1080,
    "720p'ye kadar": 720,
    "720p": 720,
    "480p'ye kadar": 480,
    "480p": 480,
}


def _video_format(quality: str) -> str:
    height = QUALITY_HEIGHTS.get(quality)
    if height is None:
        return (
            "bv*[vcodec^=avc1]+ba/bv*[vcodec^=h264]+ba/"
            "b[vcodec^=avc1]/b[vcodec^=h264]/"
            "bv*+ba/b"
        )
    return (
        f"bv*[vcodec^=avc1][height<={height}]+ba/"
        f"bv*[vcodec^=h264][height<={height}]+ba/"
        f"b[vcodec^=avc1][height<={height}]/"
        f"b[vcodec^=h264][height<={height}]/"
        f"bv*[height<={height}]+ba/b[height<={height}]/b"
    )


def _make_cookies_from_browser(
    browser_name: str | None,
    profile_name: str | None,
) -> tuple | None:
    """
    yt-dlp cookiesfrombrowser tuple'ını üretir.
    Tuple biçimi: (browser_name, profile, keyring, container)
    profile=None → yt-dlp kendi en son Firefox profilini seçer;
    CLI --cookies-from-browser firefox ile aynı davranış.
    """
    if not browser_name or browser_name in ("auto", "none", "disabled", "off"):
        return None
    if profile_name:
        return (browser_name, profile_name, None, None)
    return (browser_name,)


def _make_impersonate_target(target_name: str) -> Any:
    """yt_dlp impersonate target nesnesi oluşturur."""
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str(target_name.lower())
    except Exception:  # noqa: BLE001
        return None


def build_tiktok_attempt_options(
    browser: str | None = None,
    profile: tuple[str, str] | None = None,
    impersonation: str | None = None,
) -> dict[str, Any]:
    """TikTok deneme seçeneği üreten ortak yardımcı fonksiyon."""
    opts: dict[str, Any] = {}
    if profile:
        opts["cookiesfrombrowser"] = profile
    elif browser:
        opts["cookiesfrombrowser"] = (browser,)

    if impersonation:
        imp_target = _make_impersonate_target(impersonation)
        if imp_target is not None:
            opts["impersonate"] = imp_target

    return opts


def build_ydl_options(request: DownloadRequest) -> dict[str, Any]:
    request.output_dir.mkdir(parents=True, exist_ok=True)

    platform = detect_platform_type(request.url)
    is_instagram_story = platform in (
        PlatformType.INSTAGRAM_STORY,
        PlatformType.INSTAGRAM_HIGHLIGHT,
    )
    is_tiktok = platform in (
        PlatformType.TIKTOK_VIDEO,
        PlatformType.TIKTOK_SHORT_LINK,
        PlatformType.TIKTOK_PROFILE,
        PlatformType.TIKTOK_LIVE,
        PlatformType.TIKTOK_SLIDESHOW,
    )

    if is_tiktok:
        template = "TikTok - %(uploader,uploader_id,channel|TikTok_Kullanicisi)s - %(title,id)s [%(id)s].%(ext)s"
    elif request.playlist:
        if is_instagram_story:
            template = "%(uploader,uploader_id,playlist_title,playlist|Instagram_Hikayeleri)s/%(playlist_index)03d - %(title,id)s [%(id)s].%(ext)s"
        else:
            template = "%(playlist_title,playlist,title,id)s/%(playlist_index)03d - %(title,id)s [%(id)s].%(ext)s"
    else:
        template = "%(title)s [%(id)s].%(ext)s"

    options: dict[str, Any] = {
        "outtmpl": str(request.output_dir / template),
        "noplaylist": not request.playlist,
        "ignoreerrors": False,
        "continuedl": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "windowsfilenames": True,
        "trim_file_name": 180,
        "quiet": True,
        "no_warnings": False,
    }

    if not request.playlist:
        options["playlist_items"] = "1"

    if request.media_type == "Ses (MP3)":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        options.update({
            "format": _video_format(request.quality),
            "merge_output_format": "mp4",
        })

    # --- Çerez / oturum seçenekleri ---
    cookies_tuple: tuple | None = None

    if request.preferred_profile:
        b_name, p_name = request.preferred_profile
        cookies_tuple = _make_cookies_from_browser(b_name, p_name)
    elif request.preferred_browser:
        cookies_tuple = _make_cookies_from_browser(request.preferred_browser, None)
    elif isinstance(request.browser, tuple):
        cookies_tuple = request.browser
    elif request.browser and request.browser not in ("auto", "none", "disabled", "off"):
        cookies_tuple = _make_cookies_from_browser(request.browser, None)

    if cookies_tuple is not None:
        options["cookiesfrombrowser"] = cookies_tuple

    if request.preferred_impersonation:
        imp_target = _make_impersonate_target(request.preferred_impersonation)
        if imp_target is not None:
            options["impersonate"] = imp_target

    return options
