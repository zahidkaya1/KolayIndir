"""Kolayİndir metin ve log yardımcı fonksiyonları."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QComboBox, QSizePolicy

_ANSI_REGEX = re.compile(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]")


def configure_combo_box(combo: QComboBox) -> None:
    """QComboBox ve açılır menüsünün QPalette renklerini ve yükseklik ayarlarını açık temaya sabitler."""
    combo.setEditable(False)
    combo.setMinimumHeight(40)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    palette = combo.palette()

    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.WindowText, QColor("#172033"))
        palette.setColor(group, QPalette.ColorRole.Text, QColor("#172033"))
        palette.setColor(group, QPalette.ColorRole.ButtonText, QColor("#172033"))
        palette.setColor(group, QPalette.ColorRole.Base, QColor("#FFFFFF"))
        palette.setColor(group, QPalette.ColorRole.Window, QColor("#FFFFFF"))
        palette.setColor(group, QPalette.ColorRole.Button, QColor("#FFFFFF"))
        palette.setColor(
            group, QPalette.ColorRole.AlternateBase, QColor("#FFFFFF")
        )
        palette.setColor(group, QPalette.ColorRole.Highlight, QColor("#E8F0FE"))
        palette.setColor(
            group, QPalette.ColorRole.HighlightedText, QColor("#174EA6")
        )

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor("#667085"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#667085")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#667085"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor("#F2F4F7")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, QColor("#F2F4F7")
    )

    combo.setPalette(palette)
    view = combo.view()
    if view:
        view.setPalette(palette)
        view.setMinimumWidth(max(combo.width(), 180))


def set_combo_value(combo: QComboBox, value: str) -> None:
    """QComboBox içinde verilen metni arar; bulunursa seçer, bulunamazsa index 0 seçer."""
    index = combo.findText(value)
    combo.setCurrentIndex(max(index, 0))



def strip_ansi(text: str) -> str:

    """Metindeki ANSI escape / terminal renk kodlarını temizler."""
    if not text:
        return ""
    return _ANSI_REGEX.sub("", text)


def clean_log_message(text: str) -> str:
    """Metindeki ANSI kodlarını temizler, iç içe geçmiş 'Hata: ERROR:' ön eklerini sadeleştirir ve boşlukları düzenler."""
    cleaned = strip_ansi(text).strip()
    if not cleaned:
        return ""

    pattern = r"^(?:Hata:\s*|ERROR:\s*|Uyarı:\s*|WARNING:\s*)+"
    match = re.match(pattern, cleaned, flags=re.IGNORECASE)
    if match:
        matched_str = match.group(0)
        rest = cleaned[match.end():].strip()
        is_error = "hata" in matched_str.lower() or "error" in matched_str.lower()
        is_warning = "uyarı" in matched_str.lower() or "warning" in matched_str.lower()
        if is_error:
            cleaned = f"Hata: {rest}" if rest else "Hata:"
        elif is_warning:
            cleaned = f"Uyarı: {rest}" if rest else "Uyarı:"

    return cleaned


def is_chrome_cookie_error(text: str) -> bool:
    """Log veya hata mesajında Chrome çerez erişim hatası olup olmadığını denetler."""
    if not text:
        return False
    cleaned = strip_ansi(text).lower()
    return "could not copy chrome cookie database" in cleaned


def clean_tiktok_url(url: str) -> str:
    """Teknik log için URL'deki hassas query parametrelerini, token'ları ve cookie'leri temizler."""
    if not url:
        return ""
    base = url.split("?")[0].split("#")[0].strip()
    return base


HEVC_CODECS = {"hevc", "h265", "hev1", "hvc1", "bytevc1"}
H264_CODECS = {"h264", "avc1", "avc"}


def is_hevc_codec(codec_name: str) -> bool:
    """Video codec adının HEVC/H.265 olup olmadığını denetler."""
    if not codec_name:
        return False
    c = str(codec_name).strip().lower()
    return any(h in c for h in HEVC_CODECS)


def is_h264_codec(codec_name: str) -> bool:
    """Video codec adının H.264/AVC olup olmadığını denetler."""
    if not codec_name:
        return False
    c = str(codec_name).strip().lower()
    return any(h in c for h in H264_CODECS)


def probe_media_codecs(file_path: str | Path) -> dict[str, Any]:
    """ffprobe kullanarak medya dosyasının video/ses codec, çözünürlük, fps ve süre bilgilerini sorgular."""
    import json
    import subprocess

    path = Path(file_path)
    if not path.exists():
        return {
            "video_codec": "unknown",
            "audio_codec": "unknown",
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "duration": 0.0,
        }

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if res.returncode != 0 or not res.stdout:
            return {
                "video_codec": "unknown",
                "audio_codec": "unknown",
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "duration": 0.0,
            }

        data = json.loads(res.stdout)
        video_codec = "none"
        audio_codec = "none"
        width = 0
        height = 0
        fps = 0.0

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_codec == "none":
                video_codec = str(stream.get("codec_name") or "unknown").lower()
                width = int(stream.get("width") or 0)
                height = int(stream.get("height") or 0)
                r_fps = str(stream.get("r_frame_rate") or "0/1")
                if "/" in r_fps:
                    parts = r_fps.split("/")
                    if float(parts[1]) > 0:
                        fps = float(parts[0]) / float(parts[1])
                elif r_fps:
                    fps = float(r_fps)
            elif codec_type == "audio" and audio_codec == "none":
                audio_codec = str(stream.get("codec_name") or "unknown").lower()

        fmt_info = data.get("format", {})
        duration = float(fmt_info.get("duration") or 0.0)

        return {
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "duration": round(duration, 2),
        }
    except Exception:  # noqa: BLE001
        return {
            "video_codec": "unknown",
            "audio_codec": "unknown",
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "duration": 0.0,
        }
