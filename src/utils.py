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
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Window,
        QColor("#F2F4F7"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Button,
        QColor("#F2F4F7"),
    )

    combo.setPalette(palette)


def is_valid_kick_manifest_url(url: str | None) -> bool:
    """
    Kick VOD manifestUrl adresinin geçerli orijinal VOD adresi olduğunu doğrular.
    - None veya boş olamaz
    - http:// veya https:// ile başlamalıdır
    - Path veya query içinde .m3u8 barındırmalıdır
    - MediaTailor SSAI reklam manifesti (web.kick.com/.../manifest.m3u8) kesinlikle olmamalıdır
    """
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        return False
    u_lower = u.lower()
    return ".m3u8" in u_lower and not ("web.kick.com" in u_lower and "manifest.m3u8" in u_lower)


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


INVALID_FINAL_NAMES = {"manifest", "master", "playlist", "index", "chunklist"}
TEMP_FILE_SUFFIXES = (".part", ".ytdl", ".ts", ".temp", ".frag", ".urls", ".m3u8")


def validate_final_download(file_path: str | Path, is_audio_mode: bool = False) -> tuple[bool, str]:
    """
    Final indirilen medya dosyasını doğrular.
    - Dosya mevcut, normal bir dosya olmalı.
    - Dosya adı 'manifest', 'index', 'master', 'playlist', 'chunklist' olmamalı.
    - Dosya uzantısı geçici uzantılar (.part, .ytdl, .ts vb.) veya uzantısız olmamalı.
    - Uzantı beklenen mp4/mp3 uzantısına sahip olmalı.
    - Dosya boyutu 0'dan büyük ve anlamlı olmalı (> 1 KB).
    - ffprobe duration > 0 olmalı.
    - MP4 modunda hem video hem ses codec'i mevcut olmalı. MP3 modunda ses codec'i mevcut olmalı.
    """
    if not file_path:
        return False, "Dosya yolu boş veya geçersiz."

    path = Path(file_path)
    if not path.exists():
        return False, f"Dosya mevcut değil: {path.name}"
    if not path.is_file():
        return False, f"Yol bir dosya değil: {path.name}"

    name_lower = path.name.lower()
    stem_lower = path.stem.lower()

    if stem_lower in INVALID_FINAL_NAMES or name_lower in INVALID_FINAL_NAMES:
        return False, f"Geçersiz dosya adı ({path.name}). 'manifest/index/master' final çıktı olamaz."

    if name_lower.startswith(".kolayindir_") or any(name_lower.endswith(sfx) for sfx in TEMP_FILE_SUFFIXES):
        return False, f"Geçici dosya uzantısı final çıktı olamaz: {path.name}"

    expected_ext = ".mp3" if is_audio_mode else ".mp4"
    if path.suffix.lower() != expected_ext:
        return False, f"Beklenen dosya uzantısı '{expected_ext}' ancak '{path.suffix}' bulundu."

    file_size = path.stat().st_size
    if file_size < 1024:
        return False, f"Dosya boyutu yetersiz ({file_size} bayt)."

    probe = probe_media_codecs(path)
    duration = float(probe.get("duration") or 0.0)
    if duration <= 0.0:
        return False, "ffprobe doğrulaması başarısız: Medya süresi 0 saniye."

    v_codec = str(probe.get("video_codec") or "none").lower()
    a_codec = str(probe.get("audio_codec") or "none").lower()

    if is_audio_mode:
        if a_codec in ("none", "unknown"):
            return False, "ffprobe doğrulaması başarısız: Ses akışı (audio stream) bulunamadı."
    else:
        if v_codec in ("none", "unknown"):
            return False, "ffprobe doğrulaması başarısız: Video akışı (video stream) bulunamadı."
        if a_codec in ("none", "unknown"):
            return False, "ffprobe doğrulaması başarısız: Ses akışı (audio stream) bulunamadı."

    return True, "Doğrulama başarılı."



def extract_available_formats(info: dict[str, Any]) -> tuple[list[int], list[dict[str, Any]]]:
    """
    yt-dlp extract_info sözlüğünden mevcut çözünürlük yüksekliklerini (int)
    ve video formatı listesini çıkarır.
    """
    raw_formats = info.get("formats") or []
    valid_formats: list[dict[str, Any]] = []
    heights_set: set[int] = set()

    for fmt in raw_formats:
        if not isinstance(fmt, dict):
            continue
        vcodec = str(fmt.get("vcodec") or "none")
        height = fmt.get("height")
        if vcodec != "none" and isinstance(height, int) and height > 0:
            valid_formats.append(fmt)
            heights_set.add(height)

    if not heights_set:
        h = info.get("height")
        if isinstance(h, int) and h > 0:
            heights_set.add(h)

    sorted_heights = sorted(heights_set, reverse=True)
    return sorted_heights, valid_formats


def calculate_format_for_limit(
    available_heights: list[int],
    limit_height: int | None,
) -> int | None:
    """
    Kullanıcının üst sınır seçimine göre (ör. 1080p -> 1080)
    indirilecek gerçek yüksekliği hesaplar.
    Upscale yapmaz.
    """
    if not available_heights:
        return limit_height

    if limit_height is None:
        return available_heights[0]

    for h in available_heights:
        if h <= limit_height:
            return h

    return available_heights[-1]


def calculate_detailed_format_info(
    meta: Any,
    chosen_quality_text: str,
    media_type: str,
    convert_hevc_to_h264: bool = True,
) -> dict[str, Any]:
    """
    Metadata, seçilen kalite ve medya türüne göre:
    - selected_height
    - selected_resolution
    - selected_vcodec
    - selected_acodec
    - selected_fps
    - estimated_size_bytes
    - is_approximate
    - size_display_text
    hesaplar.
    """
    from src.download_options import parse_quality_height
    from src.models import format_bytes

    duration = getattr(meta, "duration_seconds", None) or 0.0
    formats = getattr(meta, "available_formats", []) or []
    heights = getattr(meta, "available_heights", []) or []

    is_audio = "mp3" in media_type.lower() or "ses" in media_type.lower()

    if is_audio:
        audio_bitrate = 192_000  # 192 kbps
        best_abr = 0
        for f in formats:
            if isinstance(f, dict):
                abr = f.get("abr") or f.get("tbr")
                if isinstance(abr, (int, float)) and abr > best_abr:
                    best_abr = float(abr)
        if best_abr > 0:
            audio_bitrate = int(best_abr * 1000)

        est_bytes = int(duration * audio_bitrate / 8) if duration > 0 else 0
        is_approx = True
        size_text = f"Tahmini MP3: yaklaşık {format_bytes(est_bytes)}" if est_bytes > 0 else "Tahmini MP3: 192 kbps"

        return {
            "selected_height": None,
            "selected_resolution": "Ses (MP3)",
            "selected_vcodec": "none",
            "selected_acodec": "mp3",
            "selected_fps": None,
            "estimated_size_bytes": est_bytes,
            "is_approximate": is_approx,
            "size_display_text": size_text,
            "output_codec_text": "MP3 (192 kbps)",
        }

    limit_h = parse_quality_height(chosen_quality_text)
    calc_h = calculate_format_for_limit(heights, limit_h)
    if calc_h is None and getattr(meta, "maximum_available_height", None):
        calc_h = meta.maximum_available_height

    best_v_fmt: dict[str, Any] | None = None
    best_a_fmt: dict[str, Any] | None = None
    best_combo_fmt: dict[str, Any] | None = None

    if formats:
        for f in formats:
            if not isinstance(f, dict):
                continue
            h = f.get("height")
            vcodec = str(f.get("vcodec") or "none")
            acodec = str(f.get("acodec") or "none")

            if calc_h and isinstance(h, int) and h > calc_h:
                continue

            if vcodec != "none" and acodec != "none":
                if not best_combo_fmt or (f.get("height") or 0) > (best_combo_fmt.get("height") or 0):
                    best_combo_fmt = f
            elif vcodec != "none" and acodec == "none":
                if not best_v_fmt or (f.get("height") or 0) > (best_v_fmt.get("height") or 0):
                    best_v_fmt = f
            elif (
                vcodec == "none"
                and acodec != "none"
                and (not best_a_fmt or (f.get("tbr") or 0) > (best_a_fmt.get("tbr") or 0))
            ):
                best_a_fmt = f

    est_bytes = 0
    is_approx = False
    vcodec = getattr(meta, "video_codec", "") or ""
    acodec = getattr(meta, "audio_codec", "") or ""
    fps = None

    if best_combo_fmt:
        vcodec = str(best_combo_fmt.get("vcodec") or vcodec)
        acodec = str(best_combo_fmt.get("acodec") or acodec)
        fps = best_combo_fmt.get("fps")
        sz = best_combo_fmt.get("filesize") or best_combo_fmt.get("filesize_approx")
        if sz:
            est_bytes = int(sz)
        elif duration > 0:
            tbr = best_combo_fmt.get("tbr") or 2000
            est_bytes = int(duration * float(tbr) * 1000 / 8)
            is_approx = True
    elif best_v_fmt:
        vcodec = str(best_v_fmt.get("vcodec") or vcodec)
        fps = best_v_fmt.get("fps")
        v_sz = best_v_fmt.get("filesize") or best_v_fmt.get("filesize_approx")
        if not v_sz and duration > 0:
            tbr = best_v_fmt.get("tbr") or best_v_fmt.get("vbr") or 1500
            v_sz = int(duration * float(tbr) * 1000 / 8)
            is_approx = True

        a_sz = 0
        if best_a_fmt:
            acodec = str(best_a_fmt.get("acodec") or acodec)
            a_sz = best_a_fmt.get("filesize") or best_a_fmt.get("filesize_approx") or 0
            if not a_sz and duration > 0:
                abr = best_a_fmt.get("abr") or 128
                a_sz = int(duration * float(abr) * 1000 / 8)
                is_approx = True
        elif duration > 0:
            a_sz = int(duration * 128_000 / 8)
            is_approx = True

        est_bytes = int((v_sz or 0) + a_sz)

    if est_bytes == 0:
        fallback_sz = getattr(meta, "estimated_size_bytes", 0) or 0
        if fallback_sz > 0:
            est_bytes = fallback_sz
        elif duration > 0:
            bitrate = 2500_000 if (calc_h or 0) >= 1080 else (1500_000 if (calc_h or 0) >= 720 else 800_000)
            est_bytes = int(duration * bitrate / 8)
            is_approx = True

    is_hevc = is_hevc_codec(vcodec) or "vp9" in vcodec.lower() or "av01" in vcodec.lower()
    if convert_hevc_to_h264 and is_hevc:
        is_approx = True
        output_codec_text = "H.264 (Dönüştürülecek)"
    else:
        output_codec_text = vcodec.upper() if vcodec else "H.264"

    if getattr(meta, "is_playlist", False) and (getattr(meta, "playlist_count", 0) or 0) > 1:
        p_count = meta.playlist_count
        total_bytes = est_bytes * p_count
        size_text = f"Tahmini Toplam ({p_count} içerik): yaklaşık {format_bytes(total_bytes)}"
    else:
        if is_approx:
            size_text = f"Tahmini: yaklaşık {format_bytes(est_bytes)}"
        else:
            size_text = f"Tahmini: {format_bytes(est_bytes)}"

    sel_res = f"{calc_h}p" if calc_h else "En iyi"

    return {
        "selected_height": calc_h,
        "selected_resolution": sel_res,
        "selected_vcodec": vcodec,
        "selected_acodec": acodec,
        "selected_fps": fps,
        "estimated_size_bytes": est_bytes,
        "is_approximate": is_approx,
        "size_display_text": size_text,
        "output_codec_text": output_codec_text,
    }


from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class PointingHandEventFilter(QObject):
    """
    Widget'ın enabled durum değişikliklerini izler ve cursor'ı dinamik günceller:
    - enabled=True -> PointingHandCursor
    - enabled=False -> ArrowCursor
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.EnabledChange, QEvent.Type.Show) and isinstance(watched, QWidget):
            if watched.isEnabled():
                watched.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                watched.setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(watched, event)


_hand_event_filter: PointingHandEventFilter | None = None


def apply_pointing_hand_cursor(widget: QWidget) -> None:
    """
    Verilen widget'a PointingHandCursor uygular ve enabled değiştiğinde el imlecini dinamik günceller.
    """
    global _hand_event_filter
    if _hand_event_filter is None:
        _hand_event_filter = PointingHandEventFilter()

    if widget.isEnabled():
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
    else:
        widget.setCursor(Qt.CursorShape.ArrowCursor)

    widget.installEventFilter(_hand_event_filter)


def extract_supported_url_from_text(text: str) -> str | None:
    """Metin içerisinden desteklenen ilk URL'yi çıkarır ve temizler."""
    if not text:
        return None

    import re

    from src.models import (
        PlatformType,
        detect_platform_type,
        is_platform_temporarily_disabled,
    )

    # HTTP veya HTTPS ile başlayan URL adaylarını bul
    url_pattern = re.compile(r'https?://[^\s]+')
    matches = url_pattern.findall(text)

    for match in matches:
        # URL sonuna yapışan noktalama işaretlerini temizle
        cleaned = re.sub(r'[\.\,\)\'\"\;\:\]]+$', '', match)

        platform = detect_platform_type(cleaned)
        if platform != PlatformType.UNKNOWN and not is_platform_temporarily_disabled(
            platform, cleaned
        ):
            return cleaned

    return None
