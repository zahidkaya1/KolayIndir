from __future__ import annotations

import re
from typing import Any

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from src.browser_sessions import (
    build_profile_attempt_order,
    classify_session_error,
    is_authentication_error,
    is_browser_cookie_lock_error,
    is_chromium_encryption_error,
)
from src.download_options import build_ydl_options
from src.models import DownloadRequest, detect_platform_type, translate_social_error
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
        last_error: Exception | str | None = None
        succeeded: bool = False

        platform = detect_platform_type(self.request.url)
        requested_browser = self.request.browser or "auto"
        attempt_order = build_profile_attempt_order(platform, requested_browser)

        if self.request.preferred_profile:
            match_idx = next(
                (
                    i
                    for i, (b, p, _) in enumerate(attempt_order)
                    if (b, p) == self.request.preferred_profile
                ),
                None,
            )
            if match_idx is not None:
                item = attempt_order.pop(match_idx)
                if attempt_order and attempt_order[0][0] is None:
                    attempt_order.insert(1, item)
                else:
                    attempt_order.insert(0, item)

        # preferred_browser / preferred_profile öncelikli deneme
        if self.request.preferred_profile or self.request.preferred_browser:
            b_name_pref: str | None
            p_name_pref: str | None
            if self.request.preferred_profile:
                b_name_pref, p_name_pref = self.request.preferred_profile
            else:
                b_name_pref = self.request.preferred_browser
                p_name_pref = None

            b_label = "Edge" if b_name_pref == "edge" else (b_name_pref or "").capitalize()
            pref_label = f"{b_label} (varsayılan profil)" if p_name_pref is None else f"{b_label} ({p_name_pref})"
            pref_req = DownloadRequest(
                url=self.request.url,
                output_dir=self.request.output_dir,
                media_type=self.request.media_type,
                quality=self.request.quality,
                playlist=self.request.playlist,
                browser=b_name_pref,
                preferred_browser=b_name_pref if not p_name_pref else None,
                preferred_profile=(b_name_pref, p_name_pref) if (b_name_pref and p_name_pref) else None,
            )
            pref_options = build_ydl_options(pref_req)
            pref_options["logger"] = _YtDlpLogger(self.log)
            pref_options["progress_hooks"] = [self._progress_hook]
            pref_options["postprocessor_hooks"] = [self._postprocessor_hook]
            self.status.emit(f"{pref_label} oturumuyla indirme başlatılıyor…")
            try:
                with yt_dlp.YoutubeDL(pref_options) as downloader:
                    result = downloader.extract_info(self.request.url, download=True)
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                title = ""
                if isinstance(result, dict):
                    title = str(result.get("title") or result.get("playlist_title") or result.get("id") or "")
                self.succeeded.emit(title or self._last_filename or "İndirme tamamlandı.")
                self.finished.emit()
                return
            except Exception as exc:  # noqa: BLE001
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                last_error = exc
                err_clean = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", str(exc))
                reason = classify_session_error(err_clean, self.request.url)
                self.status.emit(f"{pref_label}: {reason} — fallback'e geçiliyor…")

        for b_name, p_name, display_name in attempt_order:
            if self._cancel_requested:
                self.cancelled.emit()
                return

            req_copy = DownloadRequest(
                url=self.request.url,
                output_dir=self.request.output_dir,
                media_type=self.request.media_type,
                quality=self.request.quality,
                playlist=self.request.playlist,
                browser=b_name,
                preferred_browser=None,
                preferred_profile=(b_name, p_name) if (b_name and p_name) else None,
            )

            options = build_ydl_options(req_copy)
            options["logger"] = _YtDlpLogger(self.log)
            options["progress_hooks"] = [self._progress_hook]
            options["postprocessor_hooks"] = [self._postprocessor_hook]

            if b_name:
                self.status.emit(f"{display_name} oturumuyla indirme başlatılıyor…")
            else:
                self.status.emit("İndirme başlatılıyor…")

            try:
                with yt_dlp.YoutubeDL(options) as downloader:
                    result = downloader.extract_info(self.request.url, download=True)
                if self._cancel_requested:
                    self.cancelled.emit()
                    return

                title = ""
                if isinstance(result, dict):
                    title = str(result.get("title") or result.get("playlist_title") or result.get("id") or "")
                self.succeeded.emit(title or self._last_filename or "İndirme tamamlandı.")
                succeeded = True
                break

            except Exception as exc:  # noqa: BLE001
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                last_error = exc
                err_clean = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", str(exc))
                reason = classify_session_error(err_clean, self.request.url)
                prefix = display_name if b_name else "Oturumsuz deneme"
                self.status.emit(f"{prefix}: {reason}")

                if requested_browser != "auto":
                    break

                if (
                    is_authentication_error(err_clean)
                    or is_browser_cookie_lock_error(err_clean)
                    or is_chromium_encryption_error(err_clean)
                    or "could not find firefox cookies database" in err_clean.lower()
                    or "could not find" in err_clean.lower()
                ):
                    continue
                else:
                    break

        if not succeeded and not self._cancel_requested:
            err_msg = str(last_error) if last_error else "İndirme başarısız."
            err_msg = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", err_msg)
            translated = translate_social_error(err_msg, self.request.url)
            self.failed.emit(clean_log_message(translated))

        self.finished.emit()
