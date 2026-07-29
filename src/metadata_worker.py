"""Bağlantı önizleme ve detaylı içerik analizi iş parçacığı."""

from __future__ import annotations

import re
from typing import Any
from urllib.request import Request, urlopen

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from src.config import HTTP_USER_AGENT
from src.download_options import QUALITY_HEIGHTS
from src.models import MediaMetadata, format_duration


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
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        url: str,
        requested_quality: str = "En iyi kullanılabilir kalite",
        media_type: str = "Video (MP4)",
        browser: str | None = None,
    ) -> None:
        super().__init__()
        self.url = url
        self.requested_quality = requested_quality
        self.media_type = media_type
        self.browser = browser

    @Slot()
    def run(self) -> None:
        self.status.emit("Bağlantı inceleniyor…")
        opts: dict[str, Any] = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": False,
        }
        if self.browser:
            opts["cookiesfrombrowser"] = (self.browser,)

        try:
            with yt_dlp.YoutubeDL(opts) as downloader:
                info = downloader.extract_info(self.url, download=False)
            if not isinstance(info, dict):
                raise TypeError("İçerik bilgisi okunamadı.")

            meta = self._build_metadata(info)
            self.metadata_ready.emit(meta)

            if meta.thumbnail_url:
                try:
                    request = Request(
                        meta.thumbnail_url,
                        headers={"User-Agent": HTTP_USER_AGENT},
                    )
                    with urlopen(request, timeout=6) as response:
                        thumb_bytes = response.read()
                    if thumb_bytes:
                        self.thumbnail_ready.emit(thumb_bytes)
                except Exception:  # noqa: BLE001, S110
                    pass


        except Exception as exc:  # noqa: BLE001
            err_msg = str(exc)
            err_msg = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", err_msg)
            self.failed.emit(err_msg if err_msg else "Bağlantı bilgisi alınamadı.")
        finally:
            self.finished.emit()

    def _build_metadata(self, info: dict[str, Any]) -> MediaMetadata:
        is_playlist = info.get("_type") == "playlist" or bool(info.get("entries"))
        entries = info.get("entries") or []
        playlist_count = len(entries) if is_playlist else None

        title = str(
            info.get("title")
            or info.get("playlist_title")
            or info.get("id")
            or "İçerik"
        ).strip()
        uploader = str(
            info.get("uploader")
            or info.get("channel")
            or info.get("uploader_id")
            or ""
        ).strip()
        source_name = str(info.get("extractor_key") or info.get("extractor") or "").strip()

        duration = info.get("duration")
        duration_sec = float(duration) if isinstance(duration, (int, float)) else None
        duration_text = format_duration(duration_sec) if duration_sec else ""

        thumbnail_url = str(info.get("thumbnail") or "").strip()
        if not thumbnail_url and is_playlist and entries:
            first = entries[0]
            if isinstance(first, dict):
                thumbnail_url = str(first.get("thumbnail") or "").strip()

        webpage_url = str(info.get("webpage_url") or self.url).strip()
        media_id = str(info.get("id") or "").strip()

        formats = info.get("formats") or []
        max_height = _parse_max_height(formats)

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
        )
