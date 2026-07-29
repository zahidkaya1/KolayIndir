"""İndirme işlemini arayüz iş parçacığından ayrı yürütür."""

from __future__ import annotations

from typing import Any

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from src.download_options import build_ydl_options
from src.models import DownloadRequest
from src.utils import clean_log_message


def _human_speed(value: float | None) -> str:
    if not value:
        return "—"
    units = ("B/sn", "KB/sn", "MB/sn", "GB/sn")
    size = float(value)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024 or candidate == units[-1]:
            break
        size /= 1024
    return f"{size:.1f} {unit}"


class _YtDlpLogger:
    def __init__(self, signal: Signal) -> None:
        self.signal = signal

    def debug(self, message: str) -> None:
        if not message.startswith("[debug]"):
            clean = clean_log_message(message)
            if clean:
                self.signal.emit(clean)

    def info(self, message: str) -> None:
        clean = clean_log_message(message)
        if clean:
            self.signal.emit(clean)

    def warning(self, message: str) -> None:
        clean = clean_log_message(message)
        if clean:
            if not clean.startswith(("Uyarı:", "Hata:")):
                clean = f"Uyarı: {clean}"
            self.signal.emit(clean)

    def error(self, message: str) -> None:
        clean = clean_log_message(message)
        if clean:
            if not clean.startswith(("Hata:", "Uyarı:")):
                clean = f"Hata: {clean}"
            self.signal.emit(clean)




class DownloadWorker(QObject):
    progress = Signal(int)
    status = Signal(str)
    log = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()
    progress_details = Signal(dict)

    def __init__(self, request: DownloadRequest) -> None:
        super().__init__()
        self.request = request
        self._cancel_requested = False
        self._last_filename = ""

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True
        self.status.emit("İndirme iptal ediliyor…")

    def _progress_hook(self, data: dict[str, Any]) -> None:
        if self._cancel_requested:
            raise yt_dlp.utils.DownloadError("İndirme kullanıcı tarafından iptal edildi.")
        state = data.get("status")
        if state == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            percentage = int(downloaded * 100 / total) if total else 0
            self.progress.emit(max(0, min(percentage, 100)))

            eta = data.get("eta")
            eta_text = f"{eta} sn" if isinstance(eta, int) else "—"
            speed_str = _human_speed(data.get("speed"))
            self.status.emit(
                f"İndiriliyor: %{percentage} • Hız: {speed_str} • Kalan: {eta_text}"
            )

            filename = str(data.get("filename") or "")
            if filename:
                self._last_filename = filename

            vcodec = str(data.get("info_dict", {}).get("vcodec", "") if isinstance(data.get("info_dict"), dict) else "")
            acodec = str(data.get("info_dict", {}).get("acodec", "") if isinstance(data.get("info_dict"), dict) else "")
            if "MP3" in self.request.media_type or "Ses" in self.request.media_type:
                phase = "audio_downloading"
            elif vcodec != "none" and acodec == "none":
                phase = "video_downloading"
            elif vcodec == "none" and acodec != "none":
                phase = "audio_downloading"
            else:
                phase = "downloading"

            self.progress_details.emit({
                "phase": phase,
                "percent": max(0, min(percentage, 100)),
                "downloaded_bytes": downloaded,
                "total_bytes": total,
                "speed": speed_str,
                "eta": eta_text,
                "filename": filename or self._last_filename,
                "format_id": str(data.get("format_id") or ""),
                "fragment_index": data.get("fragment_index"),
                "fragment_count": data.get("fragment_count"),
            })

        elif state == "finished":
            filename = str(data.get("filename") or "")
            if filename:
                self._last_filename = filename
            self.progress.emit(100)
            self.status.emit("İndirme tamamlandı, dosya hazırlanıyor…")
            self.progress_details.emit({
                "phase": "finished",
                "percent": 100,
                "downloaded_bytes": data.get("downloaded_bytes") or 0,
                "total_bytes": data.get("total_bytes") or 0,
                "speed": "—",
                "eta": "0 sn",
                "filename": self._last_filename,
                "format_id": str(data.get("format_id") or ""),
                "fragment_index": None,
                "fragment_count": None,
            })

    def _postprocessor_hook(self, data: dict[str, Any]) -> None:
        if self._cancel_requested:
            raise yt_dlp.utils.DownloadError("İndirme kullanıcı tarafından iptal edildi.")
        postprocessor_key = str(data.get("postprocessor") or "")
        status = str(data.get("status") or "")

        if "FFmpegExtractAudio" in postprocessor_key:
            phase = "preparing_mp3"
            msg = "MP3 dosyası hazırlanıyor…"
        elif "Merger" in postprocessor_key or "FFmpegMerger" in postprocessor_key:
            phase = "merging_video_audio"
            msg = "Video ve ses birleştiriliyor…"
        elif status == "started":
            phase = "converting"
            msg = "Ses/video dönüştürülüyor veya birleştiriliyor…"
        else:
            phase = "preparing_file"
            msg = "Dosya hazırlanıyor…"

        self.status.emit(msg)
        info = data.get("info_dict") or {}
        if isinstance(info, dict) and info.get("filepath"):
            self._last_filename = str(info["filepath"])

        self.progress_details.emit({
            "phase": phase,
            "percent": 100,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed": "—",
            "eta": "—",
            "filename": self._last_filename,
            "format_id": "",
            "fragment_index": None,
            "fragment_count": None,
        })


    @Slot()
    def run(self) -> None:
        options = build_ydl_options(self.request)
        options["logger"] = _YtDlpLogger(self.log)
        options["progress_hooks"] = [self._progress_hook]
        options["postprocessor_hooks"] = [self._postprocessor_hook]
        try:
            self.status.emit("Bağlantı inceleniyor…")
            with yt_dlp.YoutubeDL(options) as downloader:
                result = downloader.extract_info(self.request.url, download=True)
            if self._cancel_requested:
                self.cancelled.emit()
                return
            title = ""
            if isinstance(result, dict):
                title = str(result.get("title") or result.get("playlist_title") or result.get("id") or "")
            self.succeeded.emit(title or self._last_filename or "İndirme tamamlandı.")
        except yt_dlp.utils.DownloadError as exc:
            if self._cancel_requested:
                self.cancelled.emit()
            else:
                self.failed.emit(clean_log_message(str(exc)))
        except Exception as exc:  # noqa: BLE001
            if self._cancel_requested:
                self.cancelled.emit()
            else:
                self.failed.emit(clean_log_message(f"Beklenmeyen hata: {exc}"))
        finally:
            self.finished.emit()

