"""Bağlantı önizleme ve detaylı içerik analizi iş parçacığı."""

from __future__ import annotations

import re
from typing import Any
from urllib.request import Request, urlopen

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from src.browser_sessions import (
    analyze_instagram_story_url,
    analyze_kick_url,
    analyze_tiktok_url,
    build_profile_attempt_order,
    classify_session_error,
    is_authentication_error,
    is_browser_cookie_lock_error,
    is_chromium_encryption_error,
)
from src.config import HTTP_USER_AGENT
from src.download_options import QUALITY_HEIGHTS
from src.models import (
    MediaMetadata,
    PlatformType,
    detect_platform_type,
    format_duration,
    is_rehydration_error,
    translate_social_error,
)
from src.utils import clean_log_message, clean_tiktok_url


def _extract_kick_vod(url: str, requested_quality: str, media_type: str) -> MediaMetadata:
    match = re.search(r"kick\.com/([^/]+)/videos/([a-f0-9\-]{8,})", url, re.IGNORECASE)
    if not match:
        raise ValueError("Geçersiz Kick VOD bağlantısı.")

    channel = match.group(1)
    uuid = match.group(2)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://kick.com/",
        "Origin": "https://kick.com",
    }

    title = f"Kick VOD ({channel})"
    thumbnail = ""
    m3u8_url = None
    duration_sec = None

    # Try fetching channel videos list first for stream.kick.com URL & exact metadata
    try:
        from curl_cffi import requests

        r_api = requests.get(
            f"https://kick.com/api/v2/channels/{channel}/videos",
            impersonate="chrome110",
            headers=headers,
            timeout=6,
        )
        if r_api.status_code == 200:
            for v in r_api.json():
                v_obj = v.get("video") or {}
                if v_obj.get("uuid") == uuid or v.get("slug") == uuid or str(v.get("id")) == uuid:
                    m3u8_url = v.get("source")
                    if v.get("session_title"):
                        title = v.get("session_title")
                    if isinstance(v.get("thumbnail"), dict) and v["thumbnail"].get("src"):
                        thumbnail = v["thumbnail"]["src"]
                    elif isinstance(v.get("thumbnail"), str):
                        thumbnail = v["thumbnail"]
                    if v.get("duration"):
                        duration_sec = float(v["duration"]) / 1000.0
                    break
    except Exception:  # noqa: BLE001, S110
        pass

    # Fetch webpage HTML via curl_cffi for fallback / title
    try:
        from curl_cffi import requests

        r_page = requests.get(url, impersonate="chrome110", headers=headers, timeout=6)
        if r_page.status_code == 404 and not m3u8_url:
            raise ValueError("Bu Kick videosu artık mevcut olmayabilir.")
        if r_page.status_code == 403 and not m3u8_url:
            raise ValueError("Kick video bilgilerine erişilemedi. Tarayıcı oturumu veya güncel yt-dlp gerekebilir.")
        if r_page.status_code == 200:
            html = r_page.text
            title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']', html)
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html)
            thumb_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\'](.*?)["\']', html)

            if not thumbnail and thumb_match:
                thumbnail = thumb_match.group(1)

            if not title or title.startswith("Kick VOD"):
                raw_t = title_match.group(1) if title_match else ""
                if raw_t.endswith("- Watch the VOD on Kick"):
                    raw_t = raw_t[:-len("- Watch the VOD on Kick")].strip()
                desc_t = desc_match.group(1) if desc_match else ""
                title = desc_t or raw_t or f"Kick VOD {uuid}"

            if not m3u8_url:
                vod_m3u8s = re.findall(
                    r'https?://[^\s\"\',\\<>]*(?:stream\.kick\.com|media/hls/master\.m3u8)[^\s\"\',\\<>]*',
                    html,
                )
                if vod_m3u8s:
                    m3u8_url = vod_m3u8s[0]
    except Exception:
        if not m3u8_url:
            raise

    if not m3u8_url:
        raise ValueError("Kick video akış adresi (m3u8) bulunamadı.")

    # Extract formats from m3u8 using yt-dlp
    ydl_opts = {
        "quiet": True,
        "http_headers": headers,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(m3u8_url, download=False)

    info_dict = info if isinstance(info, dict) else {}
    if not duration_sec and info_dict.get("duration"):
        duration_sec = float(info_dict["duration"])

    from src.utils import extract_available_formats

    available_heights, valid_formats = extract_available_formats(info_dict)

    max_height = max(available_heights) if available_heights else None
    requested_limit = QUALITY_HEIGHTS.get(requested_quality)
    selected_height = None
    if max_height is not None:
        if requested_limit is None:
            selected_height = max_height
        else:
            selected_height = min(max_height, requested_limit)

    vcodec = str(info_dict.get("vcodec") or "h264")
    acodec = str(info_dict.get("acodec") or "aac")

    return MediaMetadata(
        title=title,
        uploader=channel,
        source_name="Kick",
        duration_seconds=duration_sec,
        duration_text=format_duration(duration_sec),
        thumbnail_url=thumbnail,
        webpage_url=url,
        media_id=uuid,
        requested_quality=requested_quality,
        maximum_available_height=max_height,
        selected_height=selected_height,
        selected_resolution=f"{selected_height}p" if selected_height else "En iyi",
        selected_extension="mp3" if ("MP3" in media_type or "Ses" in media_type) else "mp4",
        video_codec=vcodec,
        audio_codec=acodec,
        platform_type=PlatformType.KICK_VIDEO,
        successful_request_url=m3u8_url,
        available_heights=available_heights,
        available_formats=valid_formats,
    )


def _parse_max_height(formats: list[dict[str, Any]]) -> int | None:
    heights = []
    for fmt in formats:
        vcodec = str(fmt.get("vcodec", ""))
        height = fmt.get("height")
        if vcodec != "none" and isinstance(height, int) and height > 0:
            heights.append(height)
    return max(heights) if heights else None


def _calculate_estimated_size(info: dict[str, Any]) -> int | None:
    filesize = info.get("filesize") or info.get("filesize_approx")
    if isinstance(filesize, (int, float)) and filesize > 0:
        return int(filesize)

    requested_formats = info.get("requested_formats") or []
    if requested_formats:
        total = 0
        found_any = False
        for fmt in requested_formats:
            fmt_size = fmt.get("filesize") or fmt.get("filesize_approx")
            if isinstance(fmt_size, (int, float)) and fmt_size > 0:
                total += int(fmt_size)
                found_any = True
        if found_any:
            return total

    requested_downloads = info.get("requested_downloads") or []
    if requested_downloads:
        total = 0
        found_any = False
        for item in requested_downloads:
            item_size = item.get("filesize") or item.get("filesize_approx")
            if isinstance(item_size, (int, float)) and item_size > 0:
                total += int(item_size)
                found_any = True
        if found_any:
            return total

    return None


def resolve_tiktok_short_link(url: str) -> tuple[str, str | None]:
    """Kısa TikTok URL'sini (vm.tiktok.com / vt.tiktok.com) HTTP yönlendirmesiyle çözer."""
    if "vm.tiktok.com" not in url.lower() and "vt.tiktok.com" not in url.lower():
        return clean_tiktok_url(url), None
    try:
        req = Request(url, headers={"User-Agent": HTTP_USER_AGENT})
        with urlopen(req, timeout=8) as res:
            final_url = res.geturl()
            return clean_tiktok_url(final_url), None
    except Exception as exc:  # noqa: BLE001
        return url, str(exc)


def _make_impersonate_target(target_name: str) -> Any:
    """yt_dlp impersonate target nesnesi oluşturur."""
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str(target_name.lower())
    except Exception:  # noqa: BLE001
        return None


class MetadataWorker(QObject):
    metadata_ready = Signal(object)
    thumbnail_ready = Signal(bytes)
    story_notice_ready = Signal(str)  # hikaye/tiktok URL bilgi notu
    status = Signal(str)
    log = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        url: str,
        requested_quality: str = "En iyi kullanılabilir kalite",
        media_type: str = "Video (MP4)",
        browser: str | None = "auto",
        preferred_browser: str | None = None,
        preferred_profile: tuple[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.url = url
        self.requested_quality = requested_quality
        self.media_type = media_type
        self.browser = browser
        self.preferred_browser = preferred_browser
        self.preferred_profile = preferred_profile
        self._cancel_requested = False

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True
        self.status.emit("İnceleme iptal ediliyor…")

    @Slot()
    def run(self) -> None:
        try:
            self._do_run()
        finally:
            self.finished.emit()

    def _do_run(self) -> None:
        story_notice, story_err = analyze_instagram_story_url(self.url)
        if story_err:
            self.failed.emit(story_err)
            self.finished.emit()
            return
        if story_notice:
            self.story_notice_ready.emit(story_notice)
            self.status.emit(story_notice)

        tiktok_notice, tiktok_err = analyze_tiktok_url(self.url)
        if tiktok_err:
            self.failed.emit(tiktok_err)
            self.finished.emit()
            return
        if tiktok_notice:
            self.story_notice_ready.emit(tiktok_notice)
            self.status.emit(tiktok_notice)

        kick_notice, kick_err = analyze_kick_url(self.url)
        if kick_err:
            self.failed.emit(kick_err)
            self.finished.emit()
            return
        if kick_notice:
            self.story_notice_ready.emit(kick_notice)
            self.status.emit(kick_notice)

        platform = detect_platform_type(self.url)
        is_kick = platform == PlatformType.KICK_VIDEO or "kick.com" in self.url.lower()

        if is_kick:
            self.log.emit("Kick VOD bağlantısı algılandı")
            self.log.emit("Kick metadata isteği başlatıldı")
            try:
                meta = _extract_kick_vod(self.url, self.requested_quality, self.media_type)
                self.log.emit("Kick metadata bilgileri alındı")
                if not self._cancel_requested:
                    self.metadata_ready.emit(meta)

                if meta.thumbnail_url and not self._cancel_requested:
                    try:
                        request = Request(
                            meta.thumbnail_url,
                            headers={"User-Agent": HTTP_USER_AGENT},
                        )
                        with urlopen(request, timeout=6) as response:
                            thumb_bytes = response.read()
                        if thumb_bytes and not self._cancel_requested:
                            self.thumbnail_ready.emit(thumb_bytes)
                    except Exception:  # noqa: BLE001, S110
                        pass
                return
            except Exception as exc:  # noqa: BLE001
                self.log.emit("Standart bağlantı denemesi başarısız oldu")
                self.log.emit("Tarayıcı uyumluluk yöntemi deneniyor")
                err_clean = clean_log_message(str(exc))
                err_msg = translate_social_error(err_clean, self.url)
                self.failed.emit(err_msg)
                return
        is_tiktok = platform in (
            PlatformType.TIKTOK_VIDEO,
            PlatformType.TIKTOK_SHORT_LINK,
            PlatformType.TIKTOK_PROFILE,
            PlatformType.TIKTOK_LIVE,
            PlatformType.TIKTOK_SLIDESHOW,
        ) or "tiktok" in self.url.lower()

        is_short_link = "vm.tiktok.com" in self.url.lower() or "vt.tiktok.com" in self.url.lower()

        if is_tiktok:
            real_target_url = clean_tiktok_url(self.url)
            if is_short_link:
                self.log.emit("TikTok kısa bağlantısı algılandı")
                self.log.emit("Yönlendirme başladı…")
                self.status.emit("TikTok kısa bağlantısı çözümleniyor…")
                resolved_url, _ = resolve_tiktok_short_link(self.url)
                if resolved_url and resolved_url != self.url and ("tiktok.com" in resolved_url or "/video/" in resolved_url):
                    self.log.emit("TikTok yönlendirmesi başarılı.")
                    self.log.emit(f"Gerçek video bağlantısı bulundu: {clean_tiktok_url(resolved_url)}")
                    real_target_url = resolved_url

            candidates: list[tuple[str, str | None, str | None, Any, str]] = []
            candidates.append((self.url, None, None, None, "Oturumsuz (Orijinal URL)"))

            if real_target_url != self.url:
                candidates.append((real_target_url, None, None, None, "Oturumsuz (Gerçek URL)"))

            imp_chrome = _make_impersonate_target("chrome")
            if imp_chrome:
                candidates.append((real_target_url, None, None, imp_chrome, "Chrome Impersonation"))
                candidates.append((real_target_url, "firefox", None, imp_chrome, "Firefox Oturumu + Chrome Impersonation"))

            last_error: Exception | str | None = None
            succeeded = False

            for target_url, b_name, p_name, imp_target, label in candidates:
                if self._cancel_requested:
                    return

                self.status.emit(f"TikTok sayfası inceleniyor ({label})…")
                opts: dict[str, Any] = {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": False,
                }
                if b_name and p_name:
                    opts["cookiesfrombrowser"] = (b_name, p_name)
                elif b_name:
                    opts["cookiesfrombrowser"] = (b_name,)

                if imp_target is not None:
                    opts["impersonate"] = imp_target

                try:
                    with yt_dlp.YoutubeDL(opts) as downloader:
                        info = downloader.extract_info(target_url, download=False)

                    if self._cancel_requested:
                        return

                    if not isinstance(info, dict):
                        raise TypeError("İçerik bilgisi okunamadı.")

                    self.log.emit("TikTok video verisi alındı")
                    meta = self._build_metadata(info)
                    meta.webpage_url = real_target_url
                    meta.session_browser = b_name
                    meta.session_profile = (b_name, p_name) if (b_name and p_name) else None
                    meta.preferred_impersonation = "chrome" if imp_target is not None else None
                    meta.successful_request_url = target_url
                    meta.successful_attempt_type = label

                    if not self._cancel_requested:
                        self.metadata_ready.emit(meta)

                    if meta.thumbnail_url and not self._cancel_requested:
                        try:
                            request = Request(
                                meta.thumbnail_url,
                                headers={"User-Agent": HTTP_USER_AGENT},
                            )
                            with urlopen(request, timeout=6) as response:
                                thumb_bytes = response.read()
                            if thumb_bytes and not self._cancel_requested:
                                self.thumbnail_ready.emit(thumb_bytes)
                        except Exception:  # noqa: BLE001, S110
                            pass

                    succeeded = True
                    break

                except Exception as exc:  # noqa: BLE001
                    if self._cancel_requested:
                        return
                    last_error = exc
                    err_clean = clean_log_message(str(exc))

                    if is_rehydration_error(err_clean):
                        self.log.emit("TikTok extractor video verisini çıkaramadı: universal data for rehydration bulunamadı.")
                        continue
                    elif is_authentication_error(err_clean):
                        continue
                    else:
                        break

            if not succeeded and not self._cancel_requested:
                self.log.emit("TikTok video verisi çıkarılamadı")
                err_clean = clean_log_message(str(last_error) if last_error else "")
                err_msg = translate_social_error(err_clean, self.url)
                self.failed.emit(err_msg)

            self.finished.emit()
            return

        attempt_order = build_profile_attempt_order(platform, self.browser)

        if self.preferred_profile:
            match_idx = next(
                (
                    i
                    for i, (b, p, _) in enumerate(attempt_order)
                    if (b, p) == self.preferred_profile
                ),
                None,
            )
            if match_idx is not None:
                item = attempt_order.pop(match_idx)
                if attempt_order and attempt_order[0][0] is None:
                    attempt_order.insert(1, item)
                else:
                    attempt_order.insert(0, item)

        last_error = None
        succeeded = False

        for b_name, p_name, display_name in attempt_order:
            if self._cancel_requested:
                return

            if b_name is None:
                self.status.emit("Oturumsuz deneme: Oturum gerekli mi kontrol ediliyor…")
            else:
                self.status.emit(f"{display_name} oturumu deneniyor…")

            opts = {
                "extract_flat": "in_playlist",
                "skip_download": True,
                "quiet": True,
                "no_warnings": False,
            }

            if b_name and p_name:
                opts["cookiesfrombrowser"] = (b_name, p_name)
            elif b_name:
                opts["cookiesfrombrowser"] = (b_name,)

            try:
                with yt_dlp.YoutubeDL(opts) as downloader:
                    info = downloader.extract_info(self.url, download=False)

                if self._cancel_requested:
                    return

                if not isinstance(info, dict):
                    raise TypeError("İçerik bilgisi okunamadı.")

                meta = self._build_metadata(info)
                if b_name:
                    meta.session_browser = b_name
                    if b_name and p_name:
                        meta.session_profile = (b_name, p_name)
                        self.status.emit(f"{display_name}: Oturum doğrulandı")
                    else:
                        meta.session_profile = None
                        self.status.emit(f"{display_name}: Oturum doğrulandı")

                if not self._cancel_requested:
                    self.metadata_ready.emit(meta)

                if meta.thumbnail_url and not self._cancel_requested:
                    try:
                        request = Request(
                            meta.thumbnail_url,
                            headers={"User-Agent": HTTP_USER_AGENT},
                        )
                        with urlopen(request, timeout=6) as response:
                            thumb_bytes = response.read()
                        if thumb_bytes and not self._cancel_requested:
                            self.thumbnail_ready.emit(thumb_bytes)
                    except Exception:  # noqa: BLE001, S110
                        pass

                succeeded = True
                break

            except Exception as exc:  # noqa: BLE001
                if self._cancel_requested:
                    return
                last_error = exc
                err_clean = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", str(exc))
                reason = classify_session_error(err_clean, self.url)
                prefix = display_name if b_name else "Oturumsuz deneme"
                self.status.emit(f"{prefix}: {reason}")

                if self.browser and self.browser != "auto":
                    break

                if (
                    is_authentication_error(err_clean)
                    or is_browser_cookie_lock_error(err_clean)
                    or is_chromium_encryption_error(err_clean)
                    or "could not find firefox cookies database" in err_clean.lower()
                    or "could not find" in err_clean.lower()
                ):
                    continue
                else:
                    break

        if not succeeded and not self._cancel_requested:
            err_raw = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", str(last_error) if last_error else "")
            err_msg = translate_social_error(err_raw, self.url)
            self.failed.emit(err_msg)

    def _build_metadata(self, info: dict[str, Any]) -> MediaMetadata:
        platform_type = detect_platform_type(self.url)
        raw_entries = info.get("entries")
        entries = list(raw_entries) if raw_entries else []
        is_playlist = info.get("_type") == "playlist" or bool(entries)
        playlist_count = len(entries) if is_playlist else None

        webpage_url = str(info.get("webpage_url") or info.get("original_url") or self.url).strip()
        if platform_type == PlatformType.TIKTOK_SHORT_LINK and ("/video/" in webpage_url or "tiktok.com" in webpage_url):
            platform_type = PlatformType.TIKTOK_VIDEO

        # Instagram story için özel ID arama
        target_entry: dict[str, Any] | None = None
        if is_playlist and entries:
            story_match = re.search(r"instagram\.com/stories/[^/]+/(\d+)", self.url)
            if story_match:
                target_id = story_match.group(1)
                for entry in entries:
                    if isinstance(entry, dict) and str(entry.get("id")) == target_id:
                        target_entry = entry
                        break
            if target_entry is None and isinstance(entries[0], dict):
                target_entry = entries[0]

        title = str(
            (target_entry.get("title") if target_entry else None)
            or info.get("title")
            or info.get("description")
            or info.get("playlist_title")
            or info.get("id")
            or "İçerik"
        ).strip()
        uploader = str(
            (target_entry.get("uploader") if target_entry else None)
            or info.get("uploader")
            or info.get("channel")
            or info.get("uploader_id")
            or info.get("creator")
            or ""
        ).strip()
        source_name = str(info.get("extractor_key") or info.get("extractor") or "").strip()

        duration = (target_entry.get("duration") if target_entry else None) or info.get("duration")
        duration_sec = float(duration) if isinstance(duration, (int, float)) else None
        duration_text = format_duration(duration_sec) if duration_sec else ""

        thumbnail_url = str(
            (target_entry.get("thumbnail") if target_entry else None) or info.get("thumbnail") or ""
        ).strip()
        if not thumbnail_url and is_playlist and entries:
            for e in entries:
                if isinstance(e, dict) and e.get("thumbnail"):
                    thumbnail_url = str(e["thumbnail"]).strip()
                    break

        media_id = str((target_entry.get("id") if target_entry else None) or info.get("id") or "").strip()

        formats = (target_entry.get("formats") if target_entry else None) or info.get("formats") or []
        max_height = _parse_max_height(formats)

        is_tiktok = platform_type in (
            PlatformType.TIKTOK_VIDEO,
            PlatformType.TIKTOK_SHORT_LINK,
            PlatformType.TIKTOK_PROFILE,
            PlatformType.TIKTOK_LIVE,
            PlatformType.TIKTOK_SLIDESHOW,
        ) or "tiktok" in self.url.lower()

        # Slideshow / photo post tespiti
        is_slideshow = (
            info.get("_type") == "slideshow"
            or platform_type == PlatformType.TIKTOK_SLIDESHOW
            or (
                is_tiktok
                and formats
                and not any(
                    isinstance(f, dict) and f.get("vcodec") not in (None, "none")
                    for f in formats
                )
            )
        )

        if is_tiktok and is_slideshow:
            if "MP3" not in self.media_type and "Ses" not in self.media_type:
                raise ValueError("Bu TikTok gönderisi fotoğraf veya slayt içeriği. Görselleri indirme desteği henüz eklenmedi.")
            else:
                self.story_notice_ready.emit("Bu slayt gönderisinin yalnızca ses parçası indirilecek.")

        if max_height is None and not is_playlist and not is_slideshow:
            if platform_type in (PlatformType.INSTAGRAM_POST, PlatformType.INSTAGRAM_REEL):
                raise ValueError("Bu gönderide indirilebilir video bulunamadı. Fotoğraf indirme desteği henüz eklenmedi.")
            if platform_type == PlatformType.TWITTER_POST:
                raise ValueError("Bu X gönderisinde indirilebilir video bulunamadı.")

        from src.utils import extract_available_formats
        available_heights, valid_formats = extract_available_formats(info)

        requested_limit = QUALITY_HEIGHTS.get(self.requested_quality)
        selected_height = None
        if max_height is not None:
            if requested_limit is None:
                selected_height = max_height
            else:
                selected_height = min(max_height, requested_limit)

        if "MP3" in self.media_type or "Ses" in self.media_type:
            selected_res = "Ses (MP3)"
            selected_ext = "mp3"
        else:
            selected_res = f"{selected_height}p" if selected_height else "En iyi"
            selected_ext = str(info.get("ext") or "mp4").strip()

        vcodec = str(info.get("vcodec") or "").strip()
        acodec = str(info.get("acodec") or "").strip()
        est_size = _calculate_estimated_size(info)

        track_name = str(info.get("track") or info.get("track_name") or info.get("music") or "").strip()
        view_count = info.get("view_count") if isinstance(info.get("view_count"), int) else None
        like_count = info.get("like_count") if isinstance(info.get("like_count"), int) else None

        return MediaMetadata(
            title=title,
            uploader=uploader,
            source_name=source_name,
            duration_seconds=duration_sec,
            duration_text=duration_text,
            thumbnail_url=thumbnail_url,
            webpage_url=webpage_url,
            media_id=media_id,
            requested_quality=self.requested_quality,
            maximum_available_height=max_height,
            selected_height=selected_height,
            selected_resolution=selected_res,
            selected_extension=selected_ext,
            video_codec=vcodec,
            audio_codec=acodec,
            estimated_size_bytes=est_size,
            playlist_count=playlist_count,
            is_playlist=is_playlist,
            platform_type=platform_type,
            is_slideshow=is_slideshow,
            view_count=view_count,
            like_count=like_count,
            track_name=track_name,
            available_heights=available_heights,
            available_formats=valid_formats,
        )
