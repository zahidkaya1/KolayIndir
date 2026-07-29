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
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict[str, Any]) -> None:
    temporary = SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(SETTINGS_FILE)
