"""Kullanıcı ayarlarını JSON biçiminde saklar."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _settings_dir() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    path = base / "Kolayİndir"
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_FILE = _settings_dir() / "settings.json"


def get_default_download_dir() -> str:
    """Yeni kurulumlar için varsayılan indirme klasörünü döndürür (Downloads/Loadvia)."""
    old_default = Path.home() / "Downloads" / "Kolayİndir"
    if old_default.exists() and old_default.is_dir():
        return str(old_default)
    return str(Path.home() / "Downloads" / "Loadvia")


def load_settings() -> dict[str, Any]:
    from src.utils import parse_rate_limit_setting

    default_dir = get_default_download_dir()
    if not SETTINGS_FILE.exists():
        return {
            "output_dir": default_dir,
            "auto_open_folder": False,
            "rate_limit_bps": None,
        }
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "output_dir": default_dir,
            "auto_open_folder": False,
            "rate_limit_bps": None,
        }

    if not isinstance(data, dict):
        return {
            "output_dir": default_dir,
            "auto_open_folder": False,
            "rate_limit_bps": None,
        }

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
        "1080p'ye kadar",
        "1080p’ye kadar",
        "720p'ye kadar",
        "720p’ye kadar",
        "480p'ye kadar",
        "480p’ye kadar",
        "360p'ye kadar",
        "360p’ye kadar",
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

    if "convert_hevc_to_h264" not in data:
        data["convert_hevc_to_h264"] = True

    data["rate_limit_bps"] = parse_rate_limit_setting(data.get("rate_limit_bps"))

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
