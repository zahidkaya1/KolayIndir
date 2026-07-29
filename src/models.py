"""Uygulama veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    url: str
    output_dir: Path
    media_type: str
    quality: str
    playlist: bool
    browser: str | None = None


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

