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
