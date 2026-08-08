"""Ä°ndirme geÃ§miÅŸini saklar ve doÄŸrulama iÅŸlemlerini yÃ¶netir."""

from __future__ import annotations

import datetime
import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.utils import probe_media_codecs


def _history_dir() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    path = base / "KolayÄ°ndir"
    path.mkdir(parents=True, exist_ok=True)
    return path


HISTORY_FILE = _history_dir() / "history.json"


@dataclass
class DownloadRecord:
    platform: str
    media_id: str
    media_type: str
    requested_quality: str
    selected_height: int | None
    final_path: str
    state: str = "completed"
    file_size: int = 0
    completed_at: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    playlist: bool = False
    playlist_id: str = ""
    playlist_title: str = ""
    playlist_index: int = 0
    playlist_count: int = 0
    title: str = ""
    source_url: str = ""

    def display_title(self) -> str:
        if self.title:
            return self.title
        fn = Path(self.final_path).stem if self.final_path else ""
        return fn or self.media_id or "Bilinmeyen Ä°Ã§erik"

    def display_description(self) -> str:
        if self.platform == "youtube_playlist":
            pl_name = self.playlist_title or self.title or self.media_id
            return f"{pl_name} â€” Oynatma Listesi"
        if self.playlist and self.playlist_title:
            idx_str = (
                f" ({self.playlist_index}/{self.playlist_count})"
                if self.playlist_count > 0
                else ""
            )
            return f"{self.display_title()} â€” {self.playlist_title}{idx_str}"
        return self.display_title()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadRecord:
        return cls(
            platform=str(data.get("platform") or ""),
            media_id=str(data.get("media_id") or ""),
            media_type=str(data.get("media_type") or "Video (MP4)"),
            requested_quality=str(data.get("requested_quality") or ""),
            selected_height=data.get("selected_height"),
            final_path=str(data.get("final_path") or ""),
            state=str(data.get("state") or "completed"),
            file_size=int(data.get("file_size") or 0),
            completed_at=str(data.get("completed_at") or ""),
            video_codec=str(data.get("video_codec") or ""),
            audio_codec=str(data.get("audio_codec") or ""),
            playlist=bool(data.get("playlist")),
            playlist_id=str(data.get("playlist_id") or ""),
            playlist_title=str(data.get("playlist_title") or ""),
            playlist_index=int(data.get("playlist_index") or 0),
            playlist_count=int(data.get("playlist_count") or 0),
            title=str(data.get("title") or ""),
            source_url=str(data.get("source_url") or ""),
        )


def load_history() -> list[DownloadRecord]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [
                DownloadRecord.from_dict(item)
                for item in data
                if isinstance(item, dict)
            ]
    except (OSError, json.JSONDecodeError):
        return []
    return []


def save_history(records: list[DownloadRecord]) -> None:
    data = [rec.to_dict() for rec in records]
    temp_file = HISTORY_FILE.with_name(HISTORY_FILE.name + ".tmp")
    try:
        temp_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_file.replace(HISTORY_FILE)
    except OSError:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def normalize_quality(quality: str | int | None) -> str | int:
    """
    Kalite metinlerini/deÄŸerlerini karÅŸÄ±laÅŸtÄ±rma iÃ§in ortak formata dÃ¶nÃ¼ÅŸtÃ¼rÃ¼r.
    Ã–rnek:
    - "1080pâ€™ye kadar" / "1080p'ye kadar" / "1080p" / 1080 -> 1080
    - "720pâ€™ye kadar" / "720p'ye kadar" / "720p" / 720 -> 720
    - "En iyi kullanÄ±labilir kalite" / "En iyi" / "best" / None -> "best"
    """
    if quality is None:
        return "best"
    if isinstance(quality, int):
        return quality
    q_str = str(quality).strip().lower()
    if not q_str or "en iyi" in q_str or "best" in q_str:
        return "best"

    import re

    match = re.search(r"(\d{3,4})", q_str)
    if match:
        return int(match.group(1))

    return q_str


def normalize_platform(platform: Any) -> str:
    """
    Platform isimlerini ortak kategori anahtarÄ±na dÃ¶nÃ¼ÅŸtÃ¼rÃ¼r.
    """
    if not platform:
        return "unknown"
    p_str = str(getattr(platform, "value", platform)).strip().lower()
    if "tiktok" in p_str:
        return "tiktok"
    if "youtube" in p_str:
        return "youtube"
    if "instagram" in p_str:
        return "instagram"
    if "facebook" in p_str or "fb" in p_str:
        return "facebook"
    if "threads" in p_str:
        return "threads"
    if "twitter" in p_str or "x / twitter" in p_str or "x post" in p_str:
        return "twitter"
    return p_str


def normalize_media_type(media_type: str) -> str:
    """
    Medya tÃ¼rÃ¼nÃ¼ 'audio' veya 'video' olarak sadeleÅŸtirir.
    """
    m_str = str(media_type).strip().lower()
    if "mp3" in m_str or "ses" in m_str or "audio" in m_str:
        return "audio"
    return "video"


def _normalize_path(path_str: str) -> str:
    """
    Windows yollarÄ±nÄ± karÅŸÄ±laÅŸtÄ±rma iÃ§in normalleÅŸtirir.
    - BÃ¼yÃ¼k/kÃ¼Ã§Ã¼k harf farkÄ±nÄ± ortadan kaldÄ±rÄ±r (normcase)
    - Ã‡ift eÄŸik Ã§izgi / ileri-geri eÄŸik Ã§izgi farklarÄ±nÄ± giderir (normpath)
    - Path.resolve(strict=False) ile gÃ¼venli ÅŸekilde Ã§Ã¶zer
    """
    if not path_str:
        return ""
    try:
        return os.path.normcase(
            os.path.normpath(str(Path(path_str).resolve(strict=False)))
        )
    except Exception:  # noqa: BLE001
        return os.path.normcase(os.path.normpath(path_str))


def save_record(record: DownloadRecord) -> None:
    """
    KayÄ±t ekleme / gÃ¼ncelleme mantÄ±ÄŸÄ±:

    EÅŸleÅŸme kriteri (Ã¶ncelik sÄ±rasÄ±yla):
    1. NormalleÅŸtirilmiÅŸ final_path aynÄ±ysa â†’ mevcut kaydÄ± gÃ¼ncelle (in-place).
    2. BaÅŸka bir final_path iÃ§in aynÄ± kayÄ±t zaten kayÄ±tlÄ±ysa â†’ yeni kayÄ±t ekle.

    Bu sayede aynÄ± video farklÄ± dosyalara indirildiÄŸinde (Video.mp4, Video (1).mp4 â€¦)
    her biri ayrÄ± bir kayÄ±t olarak saklanÄ±r.
    """
    if not record.completed_at:
        record.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    history = load_history()

    # NormalleÅŸtirilmiÅŸ yol karÅŸÄ±laÅŸtÄ±rmasÄ± iÃ§in hedef path
    rec_norm_path = _normalize_path(record.final_path)

    # Sadece aynÄ± normalleÅŸtirilmiÅŸ final_path'e sahip kaydÄ± gÃ¼ncelle.
    for idx, item in enumerate(history):
        if _normalize_path(item.final_path) == rec_norm_path:
            history[idx] = record
            save_history(history)
            return

    # AynÄ± path yok â†’ her zaman yeni kayÄ±t ekle.
    history.append(record)
    save_history(history)


def validate_record(record: DownloadRecord) -> bool:
    """
    Ä°ndirme kaydÄ±nÄ±n diskteki gerÃ§ek dosyasÄ±nÄ± doÄŸrular:
    - state == 'completed' olmalÄ±
    - Dosya diskte var ve normal dosya olmalÄ±
    - Boyut > 10KB olmalÄ±
    - ffprobe ile aÃ§Ä±labilmeli:
      * MP4 iÃ§in: video_codec var ve duration > 0
      * MP3 iÃ§in: audio_codec var ve duration > 0
    """
    if record.state != "completed":
        return False

    file_path = Path(record.final_path)
    if not file_path.exists():
        return False

    if file_path.is_dir():
        return True

    try:
        file_size = file_path.stat().st_size
    except OSError:
        return False

    if file_size < 1024:  # 1 KB altÄ± boÅŸ/bozuk sayÄ±lÄ±r
        return False

    probe = probe_media_codecs(file_path)
    duration = float(probe.get("duration") or 0.0)
    if duration <= 0.0:
        return False

    if "MP3" in record.media_type or "Ses" in record.media_type:
        return bool(probe.get("audio_codec"))
    else:
        return bool(probe.get("video_codec"))


def validate_all_completed_records() -> tuple[int, int]:
    """
    TÃ¼m 'completed' kayÄ±tlarÄ± validate eder; geÃ§ersiz olanlarÄ± 'stale' yapar.
    Her kayÄ±t baÄŸÄ±msÄ±z olarak kontrol edilir â€” aynÄ± media_id'ye sahip farklÄ±
    dosyalar birbirini etkilemez.

    Sorumluluk ayrÄ±mÄ±:
    - validate_all_completed_records: TÃ¼m geÃ§miÅŸteki 'completed' kayÄ±tlarÄ±n disk
      durumunu toplu olarak kontrol eder ve silinmiÅŸ/bozuk dosyalarÄ± 'stale'
      olarak gÃ¼nceller.
    - find_completed_record: Belirli bir indirme isteÄŸi iÃ§in diski kontrol ederek
      yalnÄ±zca karÅŸÄ±laÅŸÄ±lan ilk saÄŸlam eÅŸleÅŸmeyi (found) dÃ¶ndÃ¼rÃ¼r. TÃ¼m geÃ§miÅŸ
      kayÄ±tlarÄ±nÄ±n toplu bakÄ±mÄ± bu fonksiyonun sorumluluÄŸunda deÄŸildir.

    DÃ¶ndÃ¼rÃ¼r: (toplam_kontrol_edilen_kayÄ±t_sayÄ±sÄ±, stale_yapÄ±lan_kayÄ±t_sayÄ±sÄ±)
    """
    history = load_history()
    dirty = False
    stale_count = 0
    total_checked = 0

    for item in history:
        if item.state != "completed":
            continue
        total_checked += 1
        if not validate_record(item):
            item.state = "stale"
            dirty = True
            stale_count += 1

    if dirty:
        save_history(history)

    return total_checked, stale_count


class HistoryValidationWorker(QObject):
    finished = Signal(int, int)

    @Slot()
    def run(self) -> None:
        total_checked, stale_count = validate_all_completed_records()
        self.finished.emit(total_checked, stale_count)


def find_completed_record(
    platform: Any,
    media_id: str,
    media_type: str,
    requested_quality: str | int | None,
    playlist: bool,
    output_dir: Path,
) -> tuple[DownloadRecord | None, str]:
    """
    GeÃ§miÅŸte arar. GeÃ§ersiz/silinmiÅŸ/bozuk dosyasÄ± olan kayÄ±tlarÄ±
    otomatik 'stale' olarak iÅŸaretleyip eler.
    DÃ¶ndÃ¼rdÃ¼ÄŸÃ¼ tuple: (DownloadRecord | None, reason_code)
    reason_code: "found", "stale_deleted", "stale_corrupt", "different_quality", "not_found"
    """
    history = load_history()
    dirty = False
    found: DownloadRecord | None = None
    reason = "not_found"

    target_platform = normalize_platform(platform)
    target_media_type = normalize_media_type(media_type)
    target_quality = normalize_quality(requested_quality)

    try:
        target_dir = output_dir.resolve()
    except Exception:  # noqa: BLE001
        target_dir = output_dir

    clean_media_id = str(media_id or "").strip()

    for item in history:
        item_platform = normalize_platform(item.platform)
        item_media_type = normalize_media_type(item.media_type)
        item_quality = normalize_quality(item.requested_quality)

        same_media = (
            item_platform == target_platform
            and (clean_media_id == "" or item.media_id == clean_media_id)
            and item_media_type == target_media_type
            and item.playlist == playlist
        )

        if not same_media:
            continue

        try:
            item_dir = Path(item.final_path).resolve().parent
            if item_dir != target_dir:
                continue
        except Exception:  # noqa: BLE001, S112
            continue

        quality_matches = (
            target_quality == "best"
            or item_quality == "best"
            or item_quality == target_quality
            or (
                isinstance(target_quality, int)
                and item.selected_height == target_quality
            )
        )

        if not quality_matches:
            reason = "different_quality"
            continue

        if validate_record(item):
            found = item
            reason = "found"
            break
        else:
            if item.state == "completed":
                item.state = "stale"
                dirty = True
                file_exists = Path(item.final_path).exists()
                reason = "stale_corrupt" if file_exists else "stale_deleted"

    if dirty:
        save_history(history)

    return found, reason


_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitize_filename(
    title: str,
    max_length: int = 180,
    default_name: str = "Video",
) -> str:
    """
    Windows dosya adlarÄ± iÃ§in geÃ§ersiz karakterleri, kontrol karakterlerini (\\n, \\r, \\t),
    ayrÄ±lmÄ±ÅŸ sistem isimlerini ve uzunluk sÄ±nÄ±rlarÄ±nÄ± gÃ¼venli biÃ§imde temizler.
    """
    import re

    if not title:
        return default_name

    # 1. Control characters (\r, \n, \t, \x00-\x1f, \x7f-\x9f) -> space
    cleaned = re.sub(r"[\r\n\t\x00-\x1f\x7f-\x9f]", " ", str(title))

    # 2. Windows invalid filename characters (< > : " / \ | ? *) -> space
    cleaned = re.sub(r'[<>"/:\\|?*]', " ", cleaned)

    # 3. Multiple spaces -> single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 4. Consecutive hyphens and underscores -> single
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned)

    # 5. Strip leading/trailing dots and spaces
    cleaned = cleaned.strip(". ")

    # 6. Fallback if empty
    if not cleaned:
        cleaned = default_name

    # 7. Windows reserved names check
    stem_upper = cleaned.split(".")[0].upper()
    if stem_upper in _WINDOWS_RESERVED_NAMES:
        cleaned = f"{cleaned}_file"

    # 8. Truncate to max_length safely
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")

    return cleaned or default_name


def _is_temp_or_fragment_file(path: Path) -> bool:
    """
    GeÃ§ici veya kÄ±smi (fragment) dosya olup olmadÄ±ÄŸÄ±nÄ± dÃ¶ndÃ¼rÃ¼r.
    Bu dosyalar benzersiz isim hesabÄ±nda tamamlanmÄ±ÅŸ sayÄ±lmaz.
    """
    import re

    name = path.name.lower()
    temp_suffixes = (".part", ".temp", ".ytdl", ".hevc_temp", ".tmp")
    # yt-dlp fragment dosyalarÄ±: video.f137.mp4, audio.f140.m4a
    return (
        any(name.endswith(s) for s in temp_suffixes)
        or name.startswith(".loadvia-")
        or bool(re.search(r"\.f\d{3,}\.(?:mp4|m4a|webm|mkv)$", name))
    )


_reservation_lock = threading.RLock()
_reserved_paths: set[Path] = set()


def release_reserved_path(path: Path) -> None:
    """Rezerve edilmiÅŸ bir yolu serbest bÄ±rakÄ±r."""
    with _reservation_lock:
        _reserved_paths.discard(path)


def reserve_unique_media_path(
    output_dir: Path, base_name: str, target_extension: str
) -> Path:
    """
    Ã‡eÅŸitli medya uzantÄ±larÄ± (mp3, mp4 vb.) iÃ§in ortak sayaÃ§ kullanarak
    Ã§akÄ±ÅŸmalarÄ± Ã¶nleyen benzersiz bir dosya yolu rezerve eder.
    Paralel indirmelere karÅŸÄ± kilitleme (RLock) kullanÄ±r.

    KullanÄ±m sonrasÄ± release_reserved_path ile bÄ±rakÄ±lmalÄ±dÄ±r.
    """
    if not target_extension.startswith("."):
        target_extension = "." + target_extension

    supported_extensions = (".mp4", ".mp3", ".webm", ".m4a", ".mkv", ".opus", ".wav")

    with _reservation_lock:
        match = re.match(r"^(.*?)\s*\((\d+)\)$", base_name)
        if match:
            potential_base = match.group(1).strip()
            base_exists = False
            for ext in supported_extensions:
                check_path = output_dir / f"{potential_base}{ext}"
                if (
                    check_path.exists() and not _is_temp_or_fragment_file(check_path)
                ) or check_path in _reserved_paths:
                    base_exists = True
                    break

            if base_exists:
                base_stem = potential_base
            else:
                base_stem = base_name
        else:
            base_stem = base_name

        base_stem = sanitize_filename(base_stem, max_length=150)

        max_counter = 0
        has_base_file = False

        if output_dir.exists() and output_dir.is_dir():
            for child in output_dir.iterdir():
                if _is_temp_or_fragment_file(child):
                    continue
                if child.suffix.lower() not in supported_extensions:
                    continue

                name_no_ext = child.stem
                if name_no_ext.lower() == base_stem.lower():
                    has_base_file = True
                else:
                    pat = re.compile(
                        r"^" + re.escape(base_stem) + r"\s*\((\d+)\)$", re.IGNORECASE
                    )
                    m = pat.match(name_no_ext)
                    if m:
                        has_base_file = True
                        num = int(m.group(1))
                        max_counter = max(max_counter, num)

        for res_path in _reserved_paths:
            if (
                res_path.parent == output_dir
                and res_path.suffix.lower() in supported_extensions
            ):
                name_no_ext = res_path.stem
                if name_no_ext.lower() == base_stem.lower():
                    has_base_file = True
                else:
                    pat = re.compile(
                        r"^" + re.escape(base_stem) + r"\s*\((\d+)\)$", re.IGNORECASE
                    )
                    m = pat.match(name_no_ext)
                    if m:
                        has_base_file = True
                        num = int(m.group(1))
                        max_counter = max(max_counter, num)

        if not has_base_file:
            final_path = output_dir / f"{base_stem}{target_extension}"
        else:
            next_num = max(1, max_counter + 1)
            final_path = output_dir / f"{base_stem} ({next_num}){target_extension}"

        _reserved_paths.add(final_path)
        return final_path


def clear_history() -> None:
    """
    History kayÄ±tlarÄ±nÄ± tamamen temizler ve boÅŸ liste yazar.
    Diskteki hiÃ§bir fiziksel medyayÄ± silmez.
    """
    temp_file = HISTORY_FILE.with_name(HISTORY_FILE.name + ".tmp")
    try:
        temp_file.write_text("[]", encoding="utf-8")
        temp_file.replace(HISTORY_FILE)
    except OSError:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def get_unique_directory_path(target_dir: Path) -> Path:
    """
    Oynatma listeleri iÃ§in benzersiz klasÃ¶r adÄ± Ã¼retir.
    Ã–rnek:
    - Ä°lk indirme: Python Dersleri
    - Ä°kinci indirme: Python Dersleri (1)
    - ÃœÃ§Ã¼ncÃ¼ indirme: Python Dersleri (2)
    """
    directory = target_dir.parent
    original_name = target_dir.name

    import re

    match = re.match(r"^(.*?)\s*\((\d+)\)$", original_name)
    if match:
        base_name = match.group(1).strip()
    else:
        base_name = original_name

    base_name = sanitize_filename(base_name, max_length=150)

    candidate = directory / base_name
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = directory / f"{base_name} ({counter})"
        if not candidate.exists():
            return candidate
        counter += 1
