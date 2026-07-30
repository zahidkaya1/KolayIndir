import datetime
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

try:
    from yt_dlp.utils import DownloadCancelled
except ImportError:
    class DownloadCancelled(Exception):  # type: ignore[no-redef]
        pass


from src.browser_sessions import (
    build_profile_attempt_order,
    classify_session_error,
    is_authentication_error,
    is_browser_cookie_lock_error,
    is_chromium_encryption_error,
)
from src.download_options import build_ydl_options
from src.history import DownloadRecord, save_record
from src.models import (
    DownloadRequest,
    PlatformType,
    detect_platform_type,
    translate_social_error,
)
from src.utils import (
    clean_log_message,
    is_hevc_codec,
    probe_media_codecs,
)


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
        self._active_process: subprocess.Popen | None = None
        self.job_id = request.job_id or f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self._created_files: set[Path] = set()
        self._initial_files: dict[Path, tuple[int, float]] = {}

        if request.output_dir.exists():
            for p in request.output_dir.glob("*"):
                if p.is_file():
                    try:
                        self._initial_files[p.resolve()] = (p.stat().st_size, p.stat().st_mtime)
                    except OSError:
                        pass

    def _track_file(self, raw_path: Any) -> None:
        if not raw_path:
            return
        p_str = str(raw_path).strip()
        if not p_str:
            return
        try:
            path_obj = Path(p_str).resolve()
            self._created_files.add(path_obj)
        except Exception:  # noqa: BLE001, S110
            pass

    @Slot()
    def cancel(self) -> None:
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.status.emit("İndirme iptal ediliyor…")
        if self._active_process:
            try:
                self._active_process.terminate()
                self._active_process.poll()
                if self._active_process.returncode is None:
                    self._active_process.kill()
            except Exception:  # noqa: BLE001, S110
                pass

    def _progress_hook(self, data: dict[str, Any]) -> None:
        if self._cancel_requested:
            raise DownloadCancelled("İndirme kullanıcı tarafından iptal edildi.")

        filename = str(data.get("filename") or "")
        filepath = str(data.get("filepath") or "")
        tmpfilename = str(data.get("tmpfilename") or "")
        self._track_file(filename)
        self._track_file(filepath)
        self._track_file(tmpfilename)

        state = data.get("status")
        if state == "downloading":
            if not getattr(self, "_data_downloading_logged", False):
                self._data_downloading_logged = True
                self.log.emit("İndirme verisi alınmaya başladı.")
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
        if not getattr(self, "_ffmpeg_logged", False):
            self._ffmpeg_logged = True
            self.log.emit("FFmpeg işleme başladı.")
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

        try:
            if self._cancel_requested:
                self.cancelled.emit()
                return

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

            # preferred_browser / preferred_profile / preferred_impersonation öncelikli deneme
            if self.request.preferred_profile or self.request.preferred_browser or self.request.preferred_impersonation:
                b_name_pref: str | None = None
                p_name_pref: str | None = None
                if self.request.preferred_profile:
                    b_name_pref, p_name_pref = self.request.preferred_profile
                elif self.request.preferred_browser:
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
                    preferred_impersonation=self.request.preferred_impersonation,
                    successful_request_url=self.request.successful_request_url,
                    convert_hevc_to_h264=self.request.convert_hevc_to_h264,
                    job_id=self.job_id,
                    target_final_path=self.request.target_final_path,
                )
                pref_options = build_ydl_options(pref_req)
                pref_options["logger"] = _YtDlpLogger(self.log)
                pref_options["progress_hooks"] = [self._progress_hook]
                pref_options["postprocessor_hooks"] = [self._postprocessor_hook]

                if platform in (
                    PlatformType.TIKTOK_VIDEO,
                    PlatformType.TIKTOK_SHORT_LINK,
                    PlatformType.TIKTOK_PROFILE,
                    PlatformType.TIKTOK_LIVE,
                    PlatformType.TIKTOK_SLIDESHOW,
                ):
                    url_type = "kısa bağlantı" if ("vm.tiktok.com" in self.request.url or "vt.tiktok.com" in self.request.url) else "çözülmüş bağlantı"
                    imp_text = self.request.preferred_impersonation or "Yok"
                    sess_text = b_name_pref or "Oturumsuz"
                    self.log.emit(f"TikTok indirme başlatılıyor (URL Türü: {url_type} | Oturum: {sess_text} | Impersonation: {imp_text})…")

                self.status.emit(f"{pref_label} oturumuyla indirme başlatılıyor…" if b_name_pref else "İndirme başlatılıyor…")
                self.log.emit("yt-dlp işlemi başladı.")
                try:
                    with yt_dlp.YoutubeDL(pref_options) as downloader:
                        result = downloader.extract_info(self.request.url, download=True)
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return
                    self._handle_post_download_transcode(result)
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return
                    title = ""
                    if isinstance(result, dict):
                        title = str(result.get("title") or result.get("playlist_title") or result.get("id") or "")
                    self._save_completed_record(platform, result)
                    self.log.emit("İndirme tamamlandı.")
                    self.succeeded.emit(title or self._last_filename or "İndirme tamamlandı.")
                    succeeded = True
                    return
                except (DownloadCancelled, Exception) as exc:  # noqa: BLE001
                    if self._cancel_requested or isinstance(exc, DownloadCancelled):
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
                    preferred_impersonation=self.request.preferred_impersonation,
                    successful_request_url=self.request.successful_request_url,
                    convert_hevc_to_h264=self.request.convert_hevc_to_h264,
                    job_id=self.job_id,
                    target_final_path=self.request.target_final_path,
                )

                options = build_ydl_options(req_copy)
                options["logger"] = _YtDlpLogger(self.log)
                options["progress_hooks"] = [self._progress_hook]
                options["postprocessor_hooks"] = [self._postprocessor_hook]

                if b_name:
                    self.status.emit(f"{display_name} oturumuyla indirme başlatılıyor…")
                elif platform in (
                    PlatformType.TIKTOK_VIDEO,
                    PlatformType.TIKTOK_SHORT_LINK,
                    PlatformType.TIKTOK_PROFILE,
                    PlatformType.TIKTOK_LIVE,
                    PlatformType.TIKTOK_SLIDESHOW,
                ):
                    if "MP3" in self.request.media_type or "Ses" in self.request.media_type:
                        self.status.emit("TikTok sesi indiriliyor…")
                    else:
                        self.status.emit("TikTok videosu indiriliyor…")
                else:
                    self.status.emit("İndirme başlatılıyor…")

                try:
                    with yt_dlp.YoutubeDL(options) as downloader:
                        result = downloader.extract_info(self.request.url, download=True)
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return

                    self._handle_post_download_transcode(result)
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return

                    title = ""
                    if isinstance(result, dict):
                        title = str(result.get("title") or result.get("playlist_title") or result.get("id") or "")
                    self._save_completed_record(platform, result)
                    self.succeeded.emit(title or self._last_filename or "İndirme tamamlandı.")
                    succeeded = True
                    break

                except (DownloadCancelled, Exception) as exc:  # noqa: BLE001
                    if self._cancel_requested or isinstance(exc, DownloadCancelled):
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

            if not succeeded:
                if self._cancel_requested:
                    self.cancelled.emit()
                else:
                    err_msg = str(last_error) if last_error else "İndirme başarısız."
                    err_msg = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", err_msg)
                    translated = translate_social_error(err_msg, self.request.url)
                    self.failed.emit(clean_log_message(translated))
        except (DownloadCancelled, Exception) as exc:  # noqa: BLE001
            if self._cancel_requested or isinstance(exc, DownloadCancelled) or "iptal" in str(exc).lower():
                self.cancelled.emit()
            else:
                err_msg = str(exc)
                err_msg = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", err_msg)
                translated = translate_social_error(err_msg, self.request.url)
                self.failed.emit(clean_log_message(translated))
        finally:
            clean_ok = self._cleanup_job_files(is_cancel=self._cancel_requested)
            if self._cancel_requested:
                if clean_ok:
                    self.status.emit("İndirme iptal edildi. Yarım dosyalar temizlendi.")
                else:
                    self.status.emit("İndirme iptal edildi ancak bazı geçici dosyalar silinemedi.")
            self.finished.emit()

    def _save_completed_record(self, platform: PlatformType, result: Any) -> None:
        target_file: Path | None = None
        if self.request.target_final_path and self.request.target_final_path.exists():
            target_file = self.request.target_final_path
        elif self._last_filename and Path(self._last_filename).exists():
            target_file = Path(self._last_filename)
        elif isinstance(result, dict):
            fn = result.get("_filename") or result.get("filepath")
            if fn and Path(fn).exists():
                target_file = Path(fn)

        if not target_file and self.request.output_dir.exists():
            files = [f for f in self.request.output_dir.glob("*") if f.is_file() and not f.name.endswith((".part", ".ytdl", ".temp"))]
            if files:
                target_file = max(files, key=lambda f: f.stat().st_mtime)

        if not target_file or not target_file.exists():
            return

        if self.request.target_final_path and target_file != self.request.target_final_path:
            try:
                if not self.request.target_final_path.exists():
                    target_file.rename(self.request.target_final_path)
                    target_file = self.request.target_final_path
            except OSError:
                pass

        probe = probe_media_codecs(target_file)
        media_id = ""
        if isinstance(result, dict):
            media_id = str(result.get("id") or "")

        rec = DownloadRecord(
            platform=platform.value,
            media_id=media_id,
            media_type=self.request.media_type,
            requested_quality=self.request.quality,
            selected_height=probe.get("height"),
            final_path=str(target_file.resolve()),
            state="completed",
            file_size=target_file.stat().st_size,
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            video_codec=probe.get("video_codec", ""),
            audio_codec=probe.get("audio_codec", ""),
            playlist=self.request.playlist,
        )
        save_record(rec)

    def _cleanup_job_files(self, is_cancel: bool) -> bool:
        if self._active_process:
            try:
                self._active_process.terminate()
                self._active_process.poll()
                if self._active_process.returncode is None:
                    self._active_process.kill()
            except Exception:  # noqa: BLE001, S110
                pass
            self._active_process = None

        all_clean = True
        candidates: set[Path] = set(self._created_files)

        if self.request.output_dir.exists():
            for p in self.request.output_dir.glob("*"):
                name = p.name.lower()
                if (
                    name.endswith((".part", ".ytdl", ".temp", ".hevc_temp.mp4"))
                    or ".f" in name
                    or name.startswith(".kolayindir_")
                ):
                    try:
                        candidates.add(p.resolve())
                    except Exception:  # noqa: BLE001, S110
                        pass

        temp_suffixes = (".part", ".ytdl", ".temp", ".hevc_temp.mp4")

        for path_obj in candidates:
            if not path_obj.exists() or not path_obj.is_file():
                continue

            try:
                res_path = path_obj.resolve()
                if res_path in self._initial_files:
                    init_size, init_mtime = self._initial_files[res_path]
                    curr_size = path_obj.stat().st_size
                    curr_mtime = path_obj.stat().st_mtime
                    if curr_size == init_size and abs(curr_mtime - init_mtime) < 1.0:
                        continue
            except OSError:
                pass

            name_lower = path_obj.name.lower()
            is_temp_ext = name_lower.endswith(temp_suffixes) or ".f" in name_lower or name_lower.startswith(".kolayindir_")

            if is_temp_ext:
                try:
                    path_obj.unlink()
                except OSError:
                    all_clean = False
            elif is_cancel or not self._last_filename:
                probe = probe_media_codecs(path_obj)
                if probe.get("duration", 0.0) <= 0.0:
                    try:
                        path_obj.unlink()
                    except OSError:
                        all_clean = False

        return all_clean

    def _handle_post_download_transcode(self, result: Any) -> None:
        if self._cancel_requested or self.request.media_type == "Ses (MP3)":
            return

        target_file: Path | None = None
        if self._last_filename and Path(self._last_filename).exists():
            target_file = Path(self._last_filename)
        elif isinstance(result, dict):
            fn = result.get("_filename") or result.get("filepath")
            if fn and Path(fn).exists():
                target_file = Path(fn)

        if not target_file:
            files = [f for f in self.request.output_dir.glob("*") if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".temp")]
            if files:
                target_file = max(files, key=lambda f: f.stat().st_mtime)

        if not target_file or not target_file.exists():
            return

        self.status.emit("Video codec'i kontrol ediliyor…")
        probe = probe_media_codecs(target_file)
        v_codec = probe.get("video_codec", "")

        if is_hevc_codec(v_codec) and self.request.convert_hevc_to_h264:
            self.log.emit("İndirilen video HEVC/H.265 biçiminde. Windows uyumlu H.264 MP4'e dönüştürülüyor…")
            self.status.emit("Video Windows uyumlu H.264 biçimine dönüştürülüyor…")

            temp_hevc = target_file.with_name(target_file.stem + ".hevc_temp" + target_file.suffix)
            try:
                if temp_hevc.exists():
                    temp_hevc.unlink()
                target_file.rename(temp_hevc)
            except OSError as exc:
                self.log.emit(f"Geçici dosya oluşturulamadı: {exc}")
                return

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(temp_hevc),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(target_file),
            ]

            duration = float(probe.get("duration") or 0.0)
            process = None
            try:
                process = subprocess.Popen(
                    cmd,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self._active_process = process
                time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

                while True:
                    if self._cancel_requested:
                        if process:
                            process.kill()
                        if temp_hevc.exists():
                            temp_hevc.unlink()
                        if target_file.exists():
                            target_file.unlink()
                        return

                    line = process.stderr.readline() if process.stderr else ""
                    if not line and process.poll() is not None:
                        break

                    if line:
                        m = time_pattern.search(line)
                        if m and duration > 0:
                            h, m_m, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
                            curr_sec = h * 3600 + m_m * 60 + s
                            pct = min(99, max(0, int((curr_sec / duration) * 100)))
                            self.status.emit(f"Video Windows uyumlu H.264 biçimine dönüştürülüyor… (%{pct})")

                process.wait()

                if process.returncode == 0 and target_file.exists() and target_file.stat().st_size > 0:
                    if temp_hevc.exists():
                        temp_hevc.unlink()
                    self.status.emit("Video ve ses hazırlanıyor…")
                    self.log.emit("H.264 MP4 dönüştürmesi tamamlandı.")
                else:
                    if temp_hevc.exists() and not target_file.exists():
                        temp_hevc.rename(target_file)
                    self.log.emit("Video indirildi ancak Windows uyumlu H.264 biçimine dönüştürülemedi.")
                    self.status.emit("H.264 dönüştürmesi tamamlanamadı (orijinal dosya korundu).")
            except Exception as exc:  # noqa: BLE001
                if process:
                    process.kill()
                if temp_hevc.exists() and not target_file.exists():
                    temp_hevc.rename(target_file)
                self.log.emit(f"Dönüştürme hatası: {exc}")
                self.status.emit("H.264 dönüştürmesi başarısız (orijinal dosya korundu).")
