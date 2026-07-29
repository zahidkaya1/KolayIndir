"""yt-dlp seçeneklerini tek bir yerde üretir."""

from __future__ import annotations

from typing import Any

from src.models import DownloadRequest

QUALITY_HEIGHTS: dict[str, int | None] = {
    "En iyi kalite": None,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
}


def _video_format(quality: str) -> str:
    height = QUALITY_HEIGHTS.get(quality)
    if height is None:
        return "bv*+ba/b"
    return f"bv*[height<={height}]+ba/b[height<={height}]"


def build_ydl_options(request: DownloadRequest) -> dict[str, Any]:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    if request.playlist:
        template = "%(playlist_title,playlist)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
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

    if request.browser:
        options["cookiesfrombrowser"] = (request.browser,)
    return options
