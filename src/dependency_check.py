"""Çalışma zamanı bağımlılıklarını denetler."""

from __future__ import annotations

import importlib.util
import shutil
from typing import Any

import yt_dlp


def check_environment() -> dict[str, Any]:
    """Çalışma zamanı araçlarını ve yt-dlp sürümünü denetler."""
    ytdlp_ver = getattr(yt_dlp.version, "__version__", "Bilinmiyor")
    has_curl_cffi = importlib.util.find_spec("curl_cffi") is not None
    return {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "deno": shutil.which("deno") is not None,
        "git": shutil.which("git") is not None,
        "curl_cffi": has_curl_cffi,
        "ytdlp_version": ytdlp_ver,
    }


def get_environment_log_lines() -> list[str]:
    """Log box için her bir aracın durumunu liste halinde döndürür."""
    env = check_environment()
    return [
        f"FFmpeg: {'Hazır' if env['ffmpeg'] else 'Eksik'}",
        f"FFprobe: {'Hazır' if env['ffprobe'] else 'Eksik'}",
        f"Deno: {'Hazır' if env['deno'] else 'Eksik'}",
        f"Git: {'Hazır' if env['git'] else 'Eksik'}",
        f"TikTok tarayıcı taklidi: {'Hazır' if env['curl_cffi'] else 'Eksik'}",
        f"yt-dlp: {env['ytdlp_version']}",
    ]


def dependency_warnings() -> list[str]:
    """Eksik araçlar için kullanıcı dostu Türkçe uyarıları döndürür."""
    env = check_environment()
    warnings: list[str] = []
    if not env["ffmpeg"] or not env["ffprobe"]:
        warnings.append(
            "FFmpeg veya FFprobe bulunamadı. Video ve ses birleştirme işlemi yapılabilmesi için FFmpeg kurulmalıdır."
        )
    if not env["deno"]:
        warnings.append(
            "Deno (JavaScript çalışma zamanı) bulunamadı. YouTube desteği bazı bağlantılarda veya formatlarda sınırlı kalabilir."
        )
    return warnings
