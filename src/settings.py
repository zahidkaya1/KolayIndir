"""Kullanıcı ayarlarını JSON biçiminde saklar."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.config import APP_NAME


def _settings_dir() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_FILE = _settings_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    default_dir = str(Path.home() / "Downloads")
    if not SETTINGS_FILE.exists():
        return {"output_dir": default_dir, "auto_open_folder": False}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"output_dir": default_dir, "auto_open_folder": False}

    if not isinstance(data, dict):
        return {"output_dir": default_dir, "auto_open_folder": False}

    data.pop("browser", None)
    data.pop("playlist", None)

    saved_dir = data.get("output_dir")
    if not saved_dir or not Path(saved_dir).exists() or not Path(saved_dir).is_dir():
        data["output_dir"] = default_dir

    QUALITY_MIGRATION = {
        "En iyi kalite": "En iyi kullanılabilir kalite",
        "1080p": "1080p’ye kadar",
        "720p": "720p’ye kadar",
        "480p": "480p’ye kadar",
    }
    VALID_MEDIA_TYPES = {"Video (MP4)", "Ses (MP3)"}
    VALID_QUALITIES = {
        "En iyi kullanılabilir kalite",
        "1080p’ye kadar",
        "720p’ye kadar",
        "480p’ye kadar",
    }

    raw_quality = data.get("quality")
    if raw_quality in QUALITY_MIGRATION:
        data["quality"] = QUALITY_MIGRATION[raw_quality]

    if data.get("media_type") not in VALID_MEDIA_TYPES:
        data["media_type"] = "Video (MP4)"

    if data.get("quality") not in VALID_QUALITIES:
        data["quality"] = "En iyi kullanılabilir kalite"

    if "auto_open_folder" not in data:
        data["auto_open_folder"] = False

    return data




def save_settings(settings: dict[str, Any]) -> None:
    excluded_keys = {"browser", "playlist"}
    sanitized = {
        key: value for key, value in settings.items() if key not in excluded_keys
    }
    temporary = SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(SETTINGS_FILE)


