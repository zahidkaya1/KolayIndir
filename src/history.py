"""İndirme geçmişini saklar ve doğrulama işlemlerini yönetir."""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.utils import probe_media_codecs


def _history_dir() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    path = base / "Kolayİndir"
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
        return fn or self.media_id or "Bilinmeyen İçerik"

    def display_description(self) -> str:
        if self.platform == "youtube_playlist":
            pl_name = self.playlist_title or self.title or self.media_id
            return f"{pl_name} — Oynatma Listesi"
        if self.playlist and self.playlist_title:
            idx_str = f" ({self.playlist_index}/{self.playlist_count})" if self.playlist_count > 0 else ""
            return f"{self.display_title()} — {self.playlist_title}{idx_str}"
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
            return [DownloadRecord.from_dict(item) for item in data if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError):
        return []
    return []


def save_history(records: list[DownloadRecord]) -> None:
    data = [rec.to_dict() for rec in records]
    temp_file = HISTORY_FILE.with_name(HISTORY_FILE.name + ".tmp")
    try:
        temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_file.replace(HISTORY_FILE)
    except OSError:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def normalize_quality(quality: str | int | None) -> str | int:
    """
    Kalite metinlerini/değerlerini karşılaştırma için ortak formata dönüştürür.
    Örnek:
    - "1080p’ye kadar" / "1080p'ye kadar" / "1080p" / 1080 -> 1080
    - "720p’ye kadar" / "720p'ye kadar" / "720p" / 720 -> 720
    - "En iyi kullanılabilir kalite" / "En iyi" / "best" / None -> "best"
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
    Platform isimlerini ortak kategori anahtarına dönüştürür.
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
    Medya türünü 'audio' veya 'video' olarak sadeleştirir.
    """
    m_str = str(media_type).strip().lower()
    if "mp3" in m_str or "ses" in m_str or "audio" in m_str:
        return "audio"
    return "video"


def _normalize_path(path_str: str) -> str:
    """
    Windows yollarını karşılaştırma için normalleştirir.
    - Büyük/küçük harf farkını ortadan kaldırır (normcase)
    - Çift eğik çizgi / ileri-geri eğik çizgi farklarını giderir (normpath)
    - Path.resolve(strict=False) ile güvenli şekilde çözer
    """
    if not path_str:
        return ""
    try:
        return os.path.normcase(os.path.normpath(str(Path(path_str).resolve(strict=False))))
    except Exception:  # noqa: BLE001
        return os.path.normcase(os.path.normpath(path_str))


def save_record(record: DownloadRecord) -> None:
    """
    Kayıt ekleme / güncelleme mantığı:

    Eşleşme kriteri (öncelik sırasıyla):
    1. Normalleştirilmiş final_path aynıysa → mevcut kaydı güncelle (in-place).
    2. Başka bir final_path için aynı kayıt zaten kayıtlıysa → yeni kayıt ekle.

    Bu sayede aynı video farklı dosyalara indirildiğinde (Video.mp4, Video (1).mp4 …)
    her biri ayrı bir kayıt olarak saklanır.
    """
    if not record.completed_at:
        record.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    history = load_history()

    # Normalleştirilmiş yol karşılaştırması için hedef path
    rec_norm_path = _normalize_path(record.final_path)

    # Sadece aynı normalleştirilmiş final_path'e sahip kaydı güncelle.
    for idx, item in enumerate(history):
        if _normalize_path(item.final_path) == rec_norm_path:
            history[idx] = record
            save_history(history)
            return

    # Aynı path yok → her zaman yeni kayıt ekle.
    history.append(record)
    save_history(history)


def validate_record(record: DownloadRecord) -> bool:
    """
    İndirme kaydının diskteki gerçek dosyasını doğrular:
    - state == 'completed' olmalı
    - Dosya diskte var ve normal dosya olmalı
    - Boyut > 10KB olmalı
    - ffprobe ile açılabilmeli:
      * MP4 için: video_codec var ve duration > 0
      * MP3 için: audio_codec var ve duration > 0
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

    if file_size < 1024:  # 1 KB altı boş/bozuk sayılır
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
    Tüm 'completed' kayıtları validate eder; geçersiz olanları 'stale' yapar.
    Her kayıt bağımsız olarak kontrol edilir — aynı media_id'ye sahip farklı
    dosyalar birbirini etkilemez.

    Sorumluluk ayrımı:
    - validate_all_completed_records: Tüm geçmişteki 'completed' kayıtların disk
      durumunu toplu olarak kontrol eder ve silinmiş/bozuk dosyaları 'stale'
      olarak günceller.
    - find_completed_record: Belirli bir indirme isteği için diski kontrol ederek
      yalnızca karşılaşılan ilk sağlam eşleşmeyi (found) döndürür. Tüm geçmiş
      kayıtlarının toplu bakımı bu fonksiyonun sorumluluğunda değildir.

    Döndürür: (toplam_kontrol_edilen_kayıt_sayısı, stale_yapılan_kayıt_sayısı)
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
    Geçmişte arar. Geçersiz/silinmiş/bozuk dosyası olan kayıtları
    otomatik 'stale' olarak işaretleyip eler.
    Döndürdüğü tuple: (DownloadRecord | None, reason_code)
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
            or (isinstance(target_quality, int) and item.selected_height == target_quality)
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
    Windows dosya adları için geçersiz karakterleri, kontrol karakterlerini (\\n, \\r, \\t),
    ayrılmış sistem isimlerini ve uzunluk sınırlarını güvenli biçimde temizler.
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
    Geçici veya kısmi (fragment) dosya olup olmadığını döndürür.
    Bu dosyalar benzersiz isim hesabında tamamlanmış sayılmaz.
    """
    import re

    name = path.name.lower()
    temp_suffixes = (".part", ".temp", ".ytdl", ".hevc_temp")
    # yt-dlp fragment dosyaları: video.f137.mp4, audio.f140.m4a
    return any(name.endswith(s) for s in temp_suffixes) or bool(
        re.search(r"\.f\d{3,}\.(?:mp4|m4a|webm|mkv)$", name)
    )


def get_unique_filepath(target_path: Path) -> Path:
    """
    Tarayıcılar gibi tamamlanmış dosya adı çakışmalarında otomatik benzersiz dosya adı üretir.
    Örnekler:
    - İlk indirme: Video.mp4
    - İkinci indirme: Video (1).mp4
    - Üçüncü indirme: Video (2).mp4
    - Belgesel (Final).mp4 -> Belgesel (Final) (1).mp4

    Yalnızca tamamlanmış dosyalar numaralandırmayı tetikler.
    .part, .temp, .ytdl, .hevc_temp ve .f137.mp4 tarzı geçici dosyalar yok sayılır.

    Ayrıca tam yolun Windows sınırına (~230 karakter) yaklaşmaması için dosya adını güvenli şekilde kısaltır.
    """
    directory = target_path.parent
    original_stem = target_path.stem
    suffix = target_path.suffix

    import re

    # Windows MAX_PATH koruması:
    # 230 karakter limit, dizin uzunluğu, suffix (.mp4) ve potansiyel (999) + .ytdl ekleri için pay
    try:
        dir_len = len(str(directory.resolve()))
    except Exception:  # noqa: BLE001
        dir_len = len(str(directory))

    # Pay: \ (1) + (999) (6) + suffix (5) + .ytdl (5) + güvenlik (10) = ~27 karakter
    max_stem_len = max(30, 230 - dir_len - 27)

    match = re.match(r"^(.*?)\s*\((\d+)\)$", original_stem)
    if match:
        base_stem = match.group(1).strip()
    else:
        base_stem = original_stem

    base_stem = sanitize_filename(base_stem, max_length=max_stem_len)

    candidate = directory / f"{base_stem}{suffix}"
    if not candidate.exists() or _is_temp_or_fragment_file(candidate):
        return candidate

    counter = 1
    while True:
        candidate = directory / f"{base_stem} ({counter}){suffix}"
        if not candidate.exists() or _is_temp_or_fragment_file(candidate):
            return candidate
        counter += 1

def clear_history() -> None:
    """
    History kayıtlarını tamamen temizler ve boş liste yazar.
    Diskteki hiçbir fiziksel medyayı silmez.
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
    Oynatma listeleri için benzersiz klasör adı üretir.
    Örnek:
    - İlk indirme: Python Dersleri
    - İkinci indirme: Python Dersleri (1)
    - Üçüncü indirme: Python Dersleri (2)
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

