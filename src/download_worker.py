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
    validate_final_download,
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
            total_bytes = data.get("total_bytes") or 0
            total_estimate = data.get("total_bytes_estimate") or 0
            frag_idx = data.get("fragment_index")
            frag_cnt = data.get("fragment_count")

            # Yüzde hesaplama önceliği:
            # 1. total_bytes 2. total_bytes_estimate 3. fragment_index / fragment_count
            percentage = 0
            if total_bytes > 0:
                percentage = int(downloaded * 100 / total_bytes)
            elif total_estimate > 0:
                percentage = int(downloaded * 100 / total_estimate)
            elif frag_cnt and frag_idx and frag_cnt > 0:
                percentage = int(frag_idx * 100 / frag_cnt)

            percentage = max(0, min(percentage, 100))
            self.progress.emit(percentage)

            raw_speed = data.get("speed")
            speed_str = _human_speed(raw_speed) if raw_speed else "Hız hesaplanıyor…"

            raw_eta = data.get("eta")
            if isinstance(raw_eta, (int, float)) and raw_eta > 0:
                eta_text = f"{int(raw_eta)} sn"
            else:
                eta_text = "Kalan süre hesaplanıyor…"

            # Watchdog için aktivite takibi (downloaded_bytes, fragment_index veya geçici dosya boyutu)
            now = time.time()
            curr_file_size = 0
            target_p = Path(filepath or filename or tmpfilename)
            if target_p.exists() and target_p.is_file():
                try:
                    curr_file_size = target_p.stat().st_size
                except OSError:
                    pass

            last_dl = getattr(self, "_last_downloaded_bytes", 0)
            last_frag = getattr(self, "_last_fragment_index", 0)
            last_size = getattr(self, "_last_file_size", 0)

            if downloaded > last_dl or (frag_idx and frag_idx > last_frag) or curr_file_size > last_size:
                self._last_activity_time = now
                self._last_downloaded_bytes = downloaded
                if frag_idx:
                    self._last_fragment_index = frag_idx
                if curr_file_size > 0:
                    self._last_file_size = curr_file_size

            # Stall denetimi (30 saniye boyunca sıfır aktivite)
            if getattr(self, "_last_activity_time", None) and (now - self._last_activity_time > 30.0):
                raise yt_dlp.utils.DownloadError("STALL_TIMEOUT: Kick indirmesi sırasında veri akışı durdu.")

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

            effective_total = total_bytes or total_estimate

            self.progress_details.emit({
                "phase": phase,
                "percent": percentage,
                "downloaded_bytes": downloaded,
                "total_bytes": effective_total,
                "speed": speed_str,
                "eta": eta_text,
                "filename": filename or self._last_filename,
                "format_id": str(data.get("format_id") or ""),
                "fragment_index": frag_idx,
                "fragment_count": frag_cnt,
            })

            # Status mesajını zenginleştir
            if frag_cnt and frag_idx:
                status_msg = f"HLS parçaları indiriliyor… (Parça {frag_idx} / {frag_cnt}) • Hız: {speed_str} • Kalan: {eta_text}"
            else:
                status_msg = f"İndiriliyor: %{percentage} • Hız: {speed_str} • Kalan: {eta_text}"
            self.status.emit(status_msg)

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
            if "kick.com" in self.request.url.lower():
                self.log.emit("FFmpeg birleştirme işlemi başladı")
            else:
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

    def _resolve_kick_playback_url(self, url: str, retry: bool = False) -> str | None:
        """
        Kick VOD için güncel imzalı m3u8 adresini playback endpoint'ten alır.
        İndirme başında ve 403 sonrası bir kez yenileme için çağrılır.
        Signed URL history/settings içine kaydedilmez.
        """
        import re as _re

        match = _re.search(r"kick\.com/([^/]+)/videos/([a-f0-9\-]{8,})", url, _re.IGNORECASE)
        if not match:
            return None
        uuid = match.group(2)
        try:
            from curl_cffi import requests as cffi_requests

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://kick.com/",
                "Origin": "https://kick.com",
                "Content-Type": "application/json",
            }
            for attempt in range(2):
                try:
                    r = cffi_requests.post(
                        f"https://web.kick.com/api/v1/stream/{uuid}/playback",
                        impersonate="chrome120",
                        headers=headers,
                        json={
                            "video_player": {"player": {}},
                            "video_session": {},
                            "user_session": {"non_personalised_ads": True},
                        },
                        timeout=15,
                    )
                    if r.status_code != 200:
                        return None
                    data = r.json()
                    playback_urls = data.get("playback_url") or {}
                    m3u8 = playback_urls.get("vod") or playback_urls.get("live")
                    return m3u8 or None
                except Exception:  # noqa: BLE001
                    if attempt == 0:
                        continue
                    return None
            return None
        except Exception:  # noqa: BLE001
            return None

    def _run_kick_download(self, platform: PlatformType) -> None:
        """
        Kick VOD için özel indirme akışı.
        - Signed m3u8 üzerinden yt-dlp ile geçici .ts / .part dosyasına indirir.
        - 403 alırsa URL'yi bir kez yeniler, tekrar dener.
        - FFmpeg ile target_final_path (.mp4 / .mp3) dosyasına remux veya dönüştürme yapar.
        - FFprobe (validate_final_download) ile video ve ses akışlarını doğrular.
        - Yalnız doğrulama başarılı ise succeeded sinyalinde gerçek final MP4 dosya yolunu gönderir.
        """
        from yt_dlp.networking.impersonate import ImpersonateTarget

        from src.history import get_unique_filepath, sanitize_filename
        from src.utils import validate_final_download

        is_audio = "MP3" in self.request.media_type or "Ses" in self.request.media_type
        ext = "mp3" if is_audio else "mp4"

        # 1. Target Final Path Belirleme (İndirmeden önce sabitlenir)
        target_final_path = self.request.target_final_path
        if not target_final_path or target_final_path.stem.lower() in {"manifest", "master", "playlist", "index", "chunklist", ""}:
            default_title = "Kick Videosu"
            clean_title = sanitize_filename(default_title)
            target_final_path = get_unique_filepath(self.request.output_dir / f"{clean_title}.{ext}")

        self.log.emit("Kick indirme işlemi başladı")
        self.status.emit("Kick oynatma bağlantısı alınıyor…")
        self.request.output_dir.mkdir(parents=True, exist_ok=True)

        m3u8_url = self._kick_m3u8
        retry_count = 0
        max_retries = 1
        last_error: Exception | str | None = None
        result: Any = None

        # İşe özel geçici medya dosyası (örn: .kolayindir_<job_id>_kick.ts)
        temp_base = self.request.output_dir / f".kolayindir_{self.job_id}_kick"
        temp_ts_path = temp_base.with_suffix(".ts")

        def _build_kick_opts(current_m3u8: str) -> dict[str, Any]:
            from src.download_options import parse_quality_height

            opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": False,
                "outtmpl": str(temp_base) + ".%(ext)s",
                "merge_output_format": None if is_audio else "ts",
                "concurrent_fragment_downloads": 4,
                "retries": 3,
                "fragment_retries": 3,
                "retry_sleep": 1,
                "socket_timeout": 10,
                "windowsfilenames": True,
                "trim_file_name": 180,
                "overwrites": True,
                "continuedl": False,
                "ignoreerrors": False,
                "http_headers": {
                    "Referer": "https://kick.com/",
                    "Origin": "https://kick.com",
                },
                "logger": _YtDlpLogger(self.log),
                "progress_hooks": [self._progress_hook],
                "postprocessor_hooks": [self._postprocessor_hook],
                "hls_prefer_native": True,
                "hls_use_mpegts": True,
            }

            try:
                imp_target = ImpersonateTarget.from_str("chrome")
                opts["impersonate"] = imp_target
            except Exception:  # noqa: BLE001, S110
                pass

            if is_audio:
                opts["format"] = "bestaudio/best"
            else:
                height = parse_quality_height(self.request.quality)
                if height:
                    opts["format"] = f"bv*[height<={height}]+ba/b[height<={height}]/b"
                else:
                    opts["format"] = "bv*+ba/b"

            return opts

        self.status.emit("Video kalitesi hazırlanıyor…")

        while retry_count <= max_retries:
            if self._cancel_requested:
                self.cancelled.emit()
                return

            self._last_activity_time = time.time()
            self._last_downloaded_bytes = 0
            self._last_fragment_index = 0
            self._last_file_size = 0

            opts = _build_kick_opts(m3u8_url)  # type: ignore[arg-type]
            try:
                with yt_dlp.YoutubeDL(opts) as downloader:
                    result = downloader.extract_info(m3u8_url, download=True)

                if self._cancel_requested:
                    self.cancelled.emit()
                    return

                break

            except (DownloadCancelled, Exception) as exc:  # noqa: BLE001
                if self._cancel_requested or isinstance(exc, DownloadCancelled):
                    self.cancelled.emit()
                    return

                err_str = str(exc)
                is_stall = "STALL_TIMEOUT" in err_str or "veri akışı durdu" in err_str.lower()
                is_403 = "403" in err_str

                if (is_403 or is_stall) and retry_count < max_retries:
                    retry_count += 1
                    reason_msg = "bağlantı zaman aşımı" if is_stall else "403 erişim hatası"
                    self.log.emit(f"Kick indirme aksaması ({reason_msg}), oynatma bağlantısı yenileniyor (Deneme {retry_count}/{max_retries})…")
                    self.status.emit("Kick oynatma bağlantısı yenileniyor…")
                    fresh_url = self._resolve_kick_playback_url(self.request.url)
                    if fresh_url:
                        m3u8_url = fresh_url
                        continue
                    else:
                        self.failed.emit("Kick indirmesi sırasında veri akışı durdu. Bağlantıyı yeniden inceleyip tekrar deneyin.")
                        return

                if is_stall:
                    self.failed.emit("Kick indirmesi sırasında veri akışı durdu. Bağlantıyı yeniden inceleyip tekrar deneyin.")
                    return

                last_error = exc
                break

        if self._cancel_requested:
            self.cancelled.emit()
            return

        if not result and last_error:
            err_msg = str(last_error)
            err_msg = re.sub(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]", "", err_msg)
            self.failed.emit(err_msg)
            return

        # 2. İndirilen geçici parçayı tespit et
        downloaded_temp_file: Path | None = None
        for cand in (
            temp_ts_path,
            temp_base.with_suffix(".mp4"),
            temp_base.with_suffix(".m4a"),
            temp_base.with_suffix(""),
        ):
            if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                downloaded_temp_file = cand
                break

        if not downloaded_temp_file and self.request.output_dir.exists():
            for p in self.request.output_dir.glob(f".kolayindir_{self.job_id}_kick*"):
                if p.is_file() and p.stat().st_size > 0 and not p.name.endswith(".part"):
                    downloaded_temp_file = p
                    break

        if not downloaded_temp_file:
            self.failed.emit("Kick HLS segmentleri indirilemedi veya geçici medya dosyası bulunamadı.")
            return

        self._track_file(downloaded_temp_file)

        # 3. FFmpeg Remux (veya MP3 dönüştürme) İşlemi - Non-blocking Pipe Streaming
        self.status.emit("Video dosyası birleştiriliyor…")
        self.log.emit("FFmpeg birleştirme/remux işlemi başladı")

        probe_temp = probe_media_codecs(downloaded_temp_file)
        duration_sec = float(probe_temp.get("duration") or 0.0)

        if is_audio:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(downloaded_temp_file),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(target_final_path),
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(downloaded_temp_file),
                "-map",
                "0",
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                str(target_final_path),
            ]

        self._track_file(target_final_path)

        def _run_ffmpeg_cmd(cmd_args: list[str]) -> int:
            full_cmd = [cmd_args[0], "-y", "-progress", "pipe:1", "-nostats"] + cmd_args[2:]
            proc = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._active_process = proc

            time_pattern = re.compile(r"out_time_ms=(\d+)")
            last_pipe_activity = time.time()

            while True:
                if self._cancel_requested:
                    proc.kill()
                    return -1

                line_raw = proc.stdout.readline() if proc.stdout else ""
                if not line_raw or not isinstance(line_raw, str):
                    if proc.poll() is not None or not isinstance(line_raw, str):
                        break
                    time.sleep(0.05)
                    if time.time() - last_pipe_activity > 30.0:
                        proc.kill()
                        return -2
                    continue

                line = line_raw
                last_pipe_activity = time.time()
                m = time_pattern.search(line)
                if m and duration_sec > 0:
                    curr_ms = float(m.group(1))
                    curr_sec = curr_ms / 1_000_000.0
                    pct = min(99, max(0, int((curr_sec / duration_sec) * 100)))
                    self.progress.emit(pct)
                    self.status.emit(f"Video MP4 olarak hazırlanıyor: %{pct}")
                    self.progress_details.emit({
                        "phase": "merging_video_audio",
                        "percent": pct,
                        "downloaded_bytes": 0,
                        "total_bytes": 0,
                        "speed": "Dosya işleniyor",
                        "eta": "Hesaplanıyor",
                        "filename": target_final_path.name,
                        "format_id": "",
                        "fragment_index": None,
                        "fragment_count": None,
                    })

            proc.wait()
            self._active_process = None
            return proc.returncode

        ret = _run_ffmpeg_cmd(cmd)

        if ret == -2:
            self.failed.emit("Kick indirmesi sırasında veri akışı durdu. Bağlantıyı yeniden inceleyip tekrar deneyin.")
            return

        # Remux başarısızsa safe fallback: Re-encode (Kapsayıcı uyumsuzluğu için)
        if (ret != 0 or not target_final_path.exists() or target_final_path.stat().st_size < 1024) and not is_audio:
            self.log.emit("Remux işlemi başarısız veya uyumsuz, güvenli re-encode fallback uygulanıyor…")
            cmd_fallback = [
                "ffmpeg",
                "-y",
                "-i",
                str(downloaded_temp_file),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(target_final_path),
            ]
            ret_fallback = _run_ffmpeg_cmd(cmd_fallback)
            if ret_fallback == -2:
                self.failed.emit("Kick indirmesi sırasında veri akışı durdu. Bağlantıyı yeniden inceleyip tekrar deneyin.")
                return

        if self._cancel_requested:
            self.cancelled.emit()
            return

        # 4. Sıkı FFprobe Doğrulaması
        self.status.emit("MP4 doğrulanıyor…")
        valid, val_reason = validate_final_download(target_final_path, is_audio_mode=is_audio)
        if not valid:
            self.log.emit(f"Hata: Final Kick dosyası doğrulamadan geçemedi: {val_reason}")
            if target_final_path.exists():
                try:
                    target_final_path.unlink()
                except OSError:
                    pass
            self.failed.emit(f"Kick indirme doğrulaması başarısız: {val_reason}")
            return

        # HEVC dönüştürme kontrolü
        self._handle_post_download_transcode(result)
        if self._cancel_requested:
            self.cancelled.emit()
            return

        # Transcode sonrası 2. doğrulama
        valid, val_reason = validate_final_download(target_final_path, is_audio_mode=is_audio)
        if not valid:
            self.failed.emit(f"Kick indirme doğrulaması başarısız: {val_reason}")
            return

        # 5. Başarılı Tamamlama
        self._save_completed_record(platform, result, override_target_file=target_final_path)
        self.log.emit("Kick videosu başarıyla indirildi")
        final_abs_path = str(target_final_path.resolve())
        self.succeeded.emit(final_abs_path)


    @Slot()
    def run(self) -> None:


        last_error: Exception | str | None = None
        succeeded: bool = False

        try:
            if self._cancel_requested:
                self.cancelled.emit()
                return

            platform = detect_platform_type(self.request.url)

            # --- Kick VOD: İndirme başlamadan güncel playback URL'sini al ---
            if platform == PlatformType.KICK_VIDEO or "kick.com" in self.request.url.lower():
                kick_m3u8 = self._resolve_kick_playback_url(self.request.url)
                if kick_m3u8:
                    self.log.emit("Kick oynatma bağlantısı alındı")
                    # DownloadRequest frozen, self._kick_m3u8 üzerinden kullan
                    self._kick_m3u8 = kick_m3u8
                else:
                    self._kick_m3u8 = None
            else:
                self._kick_m3u8 = None

            # --- Kick VOD: özel indirme akışı ---
            if (platform == PlatformType.KICK_VIDEO or "kick.com" in self.request.url.lower()) and self._kick_m3u8:
                self._run_kick_download(platform)
                return

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
                elif platform == PlatformType.KICK_VIDEO or "kick.com" in self.request.url.lower():
                    self.log.emit("Kick indirme işlemi başladı")
                    self.log.emit("Kick HLS akışı indiriliyor")

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
                    if platform == PlatformType.KICK_VIDEO or "kick.com" in self.request.url.lower():
                        self.log.emit("Kick videosu başarıyla indirildi")
                    else:
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

    def _save_completed_record(self, platform: PlatformType, result: Any, override_target_file: Path | None = None) -> None:
        target_file: Path | None = override_target_file
        if not target_file or not target_file.exists():
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

        if media_id.lower() in ("manifest", "index", "master", "playlist", "chunklist", ""):
            match = re.search(r"videos/([a-f0-9\-]{8,})", self.request.url, re.IGNORECASE)
            if match:
                media_id = match.group(1)

        platform_str = "kick" if platform == PlatformType.KICK_VIDEO else platform.value

        rec = DownloadRecord(
            platform=platform_str,
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
        import gc
        gc.collect()

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

        if self.request.target_final_path:
            try:
                candidates.add(self.request.target_final_path.resolve())
                p_str = str(self.request.target_final_path)
                candidates.add(Path(p_str + ".part").resolve())
                candidates.add(Path(p_str + ".ytdl").resolve())
            except Exception:  # noqa: BLE001, S110
                pass

        if self.request.output_dir.exists():
            for p in self.request.output_dir.glob("*"):
                if p.is_file():
                    try:
                        candidates.add(p.resolve())
                    except Exception:  # noqa: BLE001, S110
                        pass

        temp_suffixes = (".part", ".ytdl", ".temp", ".hevc_temp.mp4", ".ts", ".frag", ".urls")

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

            if not is_cancel and self.request.target_final_path and path_obj.resolve() == self.request.target_final_path.resolve():
                valid, _ = validate_final_download(path_obj, is_audio_mode=("MP3" in self.request.media_type or "Ses" in self.request.media_type))
                if valid:
                    continue

            name_lower = path_obj.name.lower()
            is_temp_ext = (
                name_lower.endswith(temp_suffixes)
                or ".f" in name_lower
                or ".frag" in name_lower
                or name_lower.startswith(".kolayindir_")
                or name_lower in ("manifest", "index", "master", "playlist", "chunklist")
            )

            if is_temp_ext or is_cancel:
                if not self._safe_unlink(path_obj):
                    all_clean = False
            elif not self._last_filename:
                probe = probe_media_codecs(path_obj)
                if probe.get("duration", 0.0) <= 0.0 and not self._safe_unlink(path_obj):
                    all_clean = False

        return all_clean

    def _safe_unlink(self, path_obj: Path, retries: int = 15, delay: float = 0.1) -> bool:
        import gc
        for attempt in range(retries):
            try:
                if not path_obj.exists():
                    return True
                path_obj.unlink()
                return True
            except OSError:
                gc.collect()
                if attempt < retries - 1:
                    time.sleep(delay)
        return False

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
