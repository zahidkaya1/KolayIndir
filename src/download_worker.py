"""İndirme işlemini arayüz iş parçacığından ayrı yürütür."""

from __future__ import annotations

from typing import Any

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from src.download_options import build_ydl_options
from src.models import DownloadRequest


def _human_speed(value: float | int | None) -> str:
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
            self.signal.emit(message)

    def info(self, message: str) -> None:
        self.signal.emit(message)

    def warning(self, message: str) -> None:
        self.signal.emit(f"Uyarı: {message}")

    def error(self, message: str) -> None:
        self.signal.emit(f"Hata: {message}")


class DownloadWorker(QObject):
    progress = Signal(int)
    status = Signal(str)
    log = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

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
            self.status.emit(
                f"İndiriliyor: %{percentage} • Hız: {_human_speed(data.get('speed'))} • Kalan: {eta_text}"
            )
            if data.get("filename"):
                self._last_filename = str(data["filename"])
        elif state == "finished":
            if data.get("filename"):
                self._last_filename = str(data["filename"])
            self.progress.emit(100)
            self.status.emit("İndirme tamamlandı, dosya hazırlanıyor…")

    def _postprocessor_hook(self, data: dict[str, Any]) -> None:
        if self._cancel_requested:
            raise yt_dlp.utils.DownloadError("İndirme kullanıcı tarafından iptal edildi.")
        if data.get("status") == "started":
            self.status.emit("Ses/video dönüştürülüyor veya birleştiriliyor…")
        elif data.get("status") == "finished":
            info = data.get("info_dict") or {}
            if info.get("filepath"):
                self._last_filename = str(info["filepath"])

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
                self.failed.emit(str(exc))
        except Exception as exc:
            if self._cancel_requested:
                self.cancelled.emit()
            else:
                self.failed.emit(f"Beklenmeyen hata: {exc}")
        finally:
            self.finished.emit()
