"""Bağlantı önizleme ve detaylı içerik analizi iş parçacığı."""

from __future__ import annotations

import re
from typing import Any
from urllib.request import Request, urlopen

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from src.browser_sessions import (
    analyze_instagram_story_url,
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
    translate_social_error,
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


class MetadataWorker(QObject):
    metadata_ready = Signal(object)
    thumbnail_ready = Signal(bytes)
    story_notice_ready = Signal(str)  # hikaye URL bilgi notu
    status = Signal(str)
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
        story_notice, story_err = analyze_instagram_story_url(self.url)
        if story_err:
            self.failed.emit(story_err)
            self.finished.emit()
            return
        if story_notice:
            self.story_notice_ready.emit(story_notice)
            self.status.emit(story_notice)

        platform = detect_platform_type(self.url)
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

        last_error: Exception | str | None = None
        succeeded = False

        for b_name, p_name, display_name in attempt_order:
            if self._cancel_requested:
                return

            if b_name is None:
                self.status.emit("Oturumsuz deneme: Oturum gerekli mi kontrol ediliyor…")
            else:
                self.status.emit(f"{display_name} oturumu deneniyor…")

            opts: dict[str, Any] = {
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
            err_msg = str(last_error) if last_error else "Bağlantı bilgisi alınamadı."
            err_msg = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", err_msg)
            err_msg = translate_social_error(err_msg, self.url)
            self.failed.emit(err_msg)

        self.finished.emit()

    def _build_metadata(self, info: dict[str, Any]) -> MediaMetadata:
        platform_type = detect_platform_type(self.url)
        raw_entries = info.get("entries")
        entries = list(raw_entries) if raw_entries else []
        is_playlist = info.get("_type") == "playlist" or bool(entries)
        playlist_count = len(entries) if is_playlist else None

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
            or info.get("playlist_title")
            or info.get("id")
            or "İçerik"
        ).strip()
        uploader = str(
            (target_entry.get("uploader") if target_entry else None)
            or info.get("uploader")
            or info.get("channel")
            or info.get("uploader_id")
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

        webpage_url = str(info.get("webpage_url") or self.url).strip()
        media_id = str((target_entry.get("id") if target_entry else None) or info.get("id") or "").strip()

        formats = (target_entry.get("formats") if target_entry else None) or info.get("formats") or []
        max_height = _parse_max_height(formats)

        if max_height is None and not is_playlist:
            if platform_type in (PlatformType.INSTAGRAM_POST, PlatformType.INSTAGRAM_REEL):
                raise ValueError("Bu gönderide indirilebilir video bulunamadı. Fotoğraf indirme desteği henüz eklenmedi.")
            if platform_type == PlatformType.TWITTER_POST:
                raise ValueError("Bu X gönderisinde indirilebilir video bulunamadı.")

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
        )
