"""İndirme geçmişi, dinamik kalite ve geçici dosya temizliği birim testleri."""

import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.dialogs import LeftoverJobsDialog
from src.download_options import _video_format
from src.download_worker import DownloadWorker
from src.history import (
    DownloadRecord,
    find_completed_record,
    get_unique_filepath,
    load_history,
    save_record,
)
from src.main_window import MainWindow
from src.models import DownloadRequest, MediaMetadata, PlatformType
from src.utils import calculate_format_for_limit, extract_available_formats


def test_history_record_missing_file_allows_redownload(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    missing_path = tmp_path / "NonExistent.mp4"
    rec = DownloadRecord(
        platform="youtube_video",
        media_id="dQw4w9WgXcQ",
        media_type="Video (MP4)",
        requested_quality="1080p'ye kadar",
        selected_height=1080,
        final_path=str(missing_path),
        state="completed",
        file_size=102400,
        completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    save_record(rec)

    # Dosya diskte olmadığı için find_completed_record None döndürmeli
    found, reason = find_completed_record(
        "youtube_video", "dQw4w9WgXcQ", "Video (MP4)", "1080p'ye kadar", False, tmp_path
    )
    assert found is None
    assert reason == "stale_deleted"

    # Stale olarak işaretlenmiş olmalı
    loaded = load_history()
    assert loaded[0].state == "stale"


def test_history_record_corrupted_file_allows_redownload(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    corrupt_file = tmp_path / "Corrupt.mp4"
    corrupt_file.write_bytes(b"0123456789")  # Bozuk/çok küçük dosya

    rec = DownloadRecord(
        platform="youtube_video",
        media_id="dQw4w9WgXcQ",
        media_type="Video (MP4)",
        requested_quality="1080p'ye kadar",
        selected_height=1080,
        final_path=str(corrupt_file),
        state="completed",
        file_size=10,
        completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    save_record(rec)

    found, reason = find_completed_record(
        "youtube_video", "dQw4w9WgXcQ", "Video (MP4)", "1080p'ye kadar", False, tmp_path
    )
    assert found is None
    assert reason == "stale_corrupt"


def test_history_intact_file_triggers_completed_record(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    intact_file = tmp_path / "Intact.mp4"
    intact_file.write_bytes(b"A" * 20000)

    # Mock ffprobe validation
    with patch("src.history.probe_media_codecs") as mock_probe:
        mock_probe.return_value = {
            "video_codec": "h264",
            "audio_codec": "aac",
            "width": 1920,
            "height": 1080,
            "duration": 60.0,
        }

        rec = DownloadRecord(
            platform="youtube_video",
            media_id="dQw4w9WgXcQ",
            media_type="Video (MP4)",
            requested_quality="1080p'ye kadar",
            selected_height=1080,
            final_path=str(intact_file),
            state="completed",
            file_size=20000,
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        save_record(rec)

        found, reason = find_completed_record(
            "youtube_video",
            "dQw4w9WgXcQ",
            "Video (MP4)",
            "1080p'ye kadar",
            False,
            tmp_path,
        )
        assert found is not None
        assert found.final_path == str(intact_file)
        assert reason == "found"


def test_get_unique_filepath_suffixes(tmp_path):
    existing = tmp_path / "Sample.mp4"
    existing.write_text("dummy")

    new_path = get_unique_filepath(existing)
    # Numbering starts at (1)
    assert new_path.name == "Sample (1).mp4"

    new_path.write_text("dummy")
    newer_path = get_unique_filepath(existing)
    assert newer_path.name == "Sample (2).mp4"


def test_different_formats_and_qualities_are_separate_records(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    mp4_file = tmp_path / "Video.mp4"
    mp4_file.write_bytes(b"A" * 20000)

    with patch("src.history.probe_media_codecs") as mock_probe:
        mock_probe.return_value = {
            "video_codec": "h264",
            "audio_codec": "aac",
            "duration": 60.0,
        }

        rec_mp4 = DownloadRecord(
            platform="youtube_video",
            media_id="dQw4w9WgXcQ",
            media_type="Video (MP4)",
            requested_quality="1080p'ye kadar",
            selected_height=1080,
            final_path=str(mp4_file),
            state="completed",
            file_size=20000,
        )
        save_record(rec_mp4)

        # MP3 araması MP4 kaydına takılmamalı
        found_mp3, _ = find_completed_record(
            "youtube_video",
            "dQw4w9WgXcQ",
            "Ses (MP3)",
            "En iyi kullanılabilir kalite",
            False,
            tmp_path,
        )
        assert found_mp3 is None

        # 720p araması 1080p kaydına takılmamalı
        found_720, reason_720 = find_completed_record(
            "youtube_video",
            "dQw4w9WgXcQ",
            "Video (MP4)",
            "720p'ye kadar",
            False,
            tmp_path,
        )
        assert found_720 is None
        assert reason_720 == "different_quality"


def test_extract_available_formats_sorting():
    info = {
        "formats": [
            {"vcodec": "avc1", "height": 360},
            {"vcodec": "vp9", "height": 2160},
            {"vcodec": "avc1", "height": 1080},
            {
                "vcodec": "none",
                "height": 1080,
            },  # audio only format ignored for height list
            {"vcodec": "avc1", "height": 720},
        ]
    }
    heights, formats = extract_available_formats(info)
    assert heights == [2160, 1080, 720, 360]
    assert len(formats) == 4


def test_calculate_format_for_limit():
    heights = [2160, 1080, 720, 360]

    # Limit 1080 -> 1080
    assert calculate_format_for_limit(heights, 1080) == 1080

    # Limit 720 -> 720
    assert calculate_format_for_limit(heights, 720) == 720

    # Limit 1440 -> 1080 (highest height <= 1440)
    assert calculate_format_for_limit(heights, 1440) == 1080

    # Limit 240 (lower than 360) -> 360 (no upscale/returns lowest available)
    assert calculate_format_for_limit(heights, 240) == 360

    # Limit None -> 2160 (highest available)
    assert calculate_format_for_limit(heights, None) == 2160


def test_video_format_filter_contains_limit_height():
    fmt_1080 = _video_format("1080p'ye kadar")
    assert "height<=1080" in fmt_1080

    fmt_720 = _video_format("720p'ye kadar")
    assert "height<=720" in fmt_720


def test_instant_quality_change_updates_preview(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    _app = QApplication.instance() or QApplication([])
    win = MainWindow()

    meta = MediaMetadata(
        title="Quality Test Video",
        uploader="channel",
        maximum_available_height=2160,
        selected_height=2160,
        selected_resolution="2160p",
        selected_extension="mp4",
        available_heights=[2160, 1080, 720, 360],
        platform_type=PlatformType.YOUTUBE_VIDEO,
    )
    win._on_metadata_ready(meta)

    # 1080p seç
    index_1080 = win.quality_combo.findText("1080p'ye kadar")
    assert index_1080 >= 0
    win.quality_combo.setCurrentIndex(index_1080)

    assert "Kaynak: 2160p" in win.meta_badges_label.text()
    assert "İndirilecek: 1080p" in win.meta_badges_label.text()
    assert meta.selected_height == 1080

    # 720p seç
    index_720 = win.quality_combo.findText("720p'ye kadar")
    assert index_720 >= 0
    win.quality_combo.setCurrentIndex(index_720)

    assert "İndirilecek: 720p" in win.meta_badges_label.text()
    assert meta.selected_height == 720


def test_download_worker_job_file_cleanup_on_cancel(tmp_path):
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="En iyi",
        playlist=False,
    )
    worker = DownloadWorker(req)

    # Create temporary files during simulated job
    part_file = tmp_path / "sample.mp4.part"
    ytdl_file = tmp_path / "sample.mp4.ytdl"
    hevc_temp = tmp_path / "sample.hevc_temp.mp4"
    part_file.write_bytes(b"PART DATA")
    ytdl_file.write_bytes(b"YTDL DATA")
    hevc_temp.write_bytes(b"HEVC DATA")

    # Call cleanup with cancel=True
    clean_ok = worker._cleanup_job_files(is_cancel=True)

    assert clean_ok is True
    assert not part_file.exists()
    assert not ytdl_file.exists()
    assert not hevc_temp.exists()


def test_download_worker_preserves_pre_existing_files(tmp_path):
    # Pre-existing file before job
    pre_file = tmp_path / "PreExisting.mp4"
    pre_file.write_bytes(b"PRE EXISTING CONTENT")

    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="En iyi",
        playlist=False,
    )
    worker = DownloadWorker(req)

    # Temporary file created during job
    part_file = tmp_path / "downloading.part"
    part_file.write_bytes(b"PART")

    worker._cleanup_job_files(is_cancel=True)

    # Pre-existing file must NOT be deleted
    assert pre_file.exists()
    assert pre_file.read_bytes() == b"PRE EXISTING CONTENT"
    # Temporary part file must be deleted
    assert not part_file.exists()


def test_leftover_jobs_dialog_clean():
    _app = QApplication.instance() or QApplication([])
    dlg = LeftoverJobsDialog(count=3)
    dlg._choose("clean")
    assert dlg.clicked_button_id == "clean"


def test_normalization_functions():
    from src.history import normalize_media_type, normalize_platform, normalize_quality

    # Quality normalization
    assert normalize_quality("1080p’ye kadar") == 1080
    assert normalize_quality("1080p'ye kadar") == 1080
    assert normalize_quality("720p") == 720
    assert normalize_quality("En iyi kullanılabilir kalite") == "best"
    assert normalize_quality(None) == "best"

    # Platform normalization
    assert normalize_platform("TikTok Video") == "tiktok"
    assert normalize_platform("youtube_video") == "youtube"
    assert normalize_platform("Instagram Reel") == "instagram"

    # Media type normalization
    assert normalize_media_type("Video (MP4)") == "video"
    assert normalize_media_type("Ses (MP3)") == "audio"


def test_calculate_detailed_format_info():
    from src.utils import calculate_detailed_format_info

    meta = MediaMetadata(
        title="Sample Video",
        uploader="User",
        duration_seconds=120.0,
        maximum_available_height=1080,
        available_heights=[1080, 720],
        available_formats=[
            {
                "vcodec": "avc1.640028",
                "acodec": "mp4a.40.2",
                "height": 1080,
                "filesize": 50_000_000,
                "fps": 30,
            },
            {
                "vcodec": "avc1.64001f",
                "acodec": "mp4a.40.2",
                "height": 720,
                "filesize": 20_000_000,
                "fps": 30,
            },
        ],
    )

    # Video calculation for 720p limit
    info = calculate_detailed_format_info(
        meta, "720p'ye kadar", "Video (MP4)", convert_hevc_to_h264=True
    )
    assert info["selected_height"] == 720
    assert info["estimated_size_bytes"] == 20_000_000
    assert "19,1 MB" in info["size_display_text"]

    # Audio MP3 calculation
    info_mp3 = calculate_detailed_format_info(
        meta, "En iyi", "Ses (MP3)", convert_hevc_to_h264=True
    )
    assert info_mp3["selected_resolution"] == "Ses (MP3)"
    assert info_mp3["estimated_size_bytes"] > 0
    assert "Tahmini MP3" in info_mp3["size_display_text"]


def test_pointing_hand_cursor_filter():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    from src.utils import apply_pointing_hand_cursor

    _app = QApplication.instance() or QApplication([])
    btn = QPushButton("Test")
    apply_pointing_hand_cursor(btn)

    assert btn.cursor().shape() == Qt.CursorShape.PointingHandCursor
    btn.setEnabled(False)
    assert btn.cursor().shape() == Qt.CursorShape.ArrowCursor
    btn.setEnabled(True)
    assert btn.cursor().shape() == Qt.CursorShape.PointingHandCursor


import pytest


@pytest.mark.qt_integration
def test_main_window_playlist_480p_request_qt_integration(tmp_path):
    _app = QApplication.instance() or QApplication([])
    window = MainWindow()
    meta = MediaMetadata(
        title="Test Playlist",
        uploader="User",
        duration_seconds=300.0,
        is_playlist=True,
        playlist_count=3,
        webpage_url="https://www.youtube.com/playlist?list=PL6F_cmvZa0pF4IOzeMekeUNp_QAxKOqcX",
        successful_request_url="https://www.youtube.com/playlist?list=PL6F_cmvZa0pF4IOzeMekeUNp_QAxKOqcX",
    )
    window.url_input.setText(
        "https://www.youtube.com/playlist?list=PL6F_cmvZa0pF4IOzeMekeUNp_QAxKOqcX"
    )
    window._on_metadata_ready(meta)
    window.playlist_checkbox.setChecked(True)
    window.media_combo.setCurrentText("Video (MP4)")
    window.quality_combo.setCurrentText("480p'ye kadar")
    window.folder_input.setText(str(tmp_path))

    captured_request = None

    original_init = DownloadWorker.__init__

    def mock_init(self, request):
        nonlocal captured_request
        captured_request = request
        original_init(self, request)

    with (
        patch("src.main_window.AppMessageDialog"),
        patch.object(DownloadWorker, "__init__", mock_init),
        patch("PySide6.QtCore.QThread"),
    ):
        window.start_download()

    assert captured_request is not None
    assert captured_request.playlist is True
    assert "480p" in captured_request.quality

    window._stop_all_threads()
    window.close()


@pytest.mark.qt_integration
def test_main_window_mp3_request_qt_integration(tmp_path):
    _app = QApplication.instance() or QApplication([])
    window = MainWindow()
    url = "https://www.youtube.com/watch?v=tVlcKp3bWH8"
    meta = MediaMetadata(
        title="Test MP3 Video",
        uploader="User",
        duration_seconds=78.0,
        webpage_url=url,
        successful_request_url=url,
    )
    window.url_input.setText(url)
    window._on_metadata_ready(meta)
    window.media_combo.setCurrentText("Ses (MP3)")
    window.folder_input.setText(str(tmp_path))

    captured_request = None

    original_init = DownloadWorker.__init__

    def mock_init(self, request):
        nonlocal captured_request
        captured_request = request
        original_init(self, request)

    with (
        patch("src.main_window.AppMessageDialog"),
        patch.object(DownloadWorker, "__init__", mock_init),
        patch("PySide6.QtCore.QThread"),
    ):
        window.start_download()

    assert captured_request is not None
    assert captured_request.playlist is False
    assert captured_request.media_type == "Ses (MP3)"
    assert captured_request.url == url
    assert captured_request.output_dir == tmp_path

    window._stop_all_threads()
    window.close()


def test_playlist_individual_and_summary_history_records(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    pl_dir = tmp_path / "TestPlaylistFolder"
    pl_dir.mkdir()

    v1 = pl_dir / "001 - Video 1 [vid1].mp4"
    v2 = pl_dir / "002 - Video 2 [vid2].mp4"
    v3 = pl_dir / "003 - Video 3 [vid3].mp4"

    v1.write_bytes(b"A" * 5000)
    v2.write_bytes(b"B" * 6000)
    v3.write_bytes(b"C" * 7000)

    request = DownloadRequest(
        url="https://www.youtube.com/playlist?list=PL123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="480p'ye kadar",
        playlist=True,
    )
    worker = DownloadWorker(request)

    result_dict = {
        "_type": "playlist",
        "id": "PL123",
        "title": "Test Playlist Title",
        "playlist_count": 3,
        "entries": [
            {
                "id": "vid1",
                "title": "Video 1",
                "filepath": str(v1),
                "height": 360,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "playlist_index": 1,
                "playlist_count": 3,
            },
            {
                "id": "vid2",
                "title": "Video 2",
                "filepath": str(v2),
                "height": 480,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "playlist_index": 2,
                "playlist_count": 3,
            },
            {
                "id": "vid3",
                "title": "Video 3",
                "filepath": str(v3),
                "height": 360,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "playlist_index": 3,
                "playlist_count": 3,
            },
        ],
    }

    with patch("src.download_worker.probe_media_codecs") as mock_probe:
        mock_probe.side_effect = [
            {
                "height": 360,
                "video_codec": "h264",
                "audio_codec": "aac",
                "duration": 10.0,
            },
            {
                "height": 480,
                "video_codec": "h264",
                "audio_codec": "aac",
                "duration": 20.0,
            },
            {
                "height": 360,
                "video_codec": "h264",
                "audio_codec": "aac",
                "duration": 30.0,
            },
        ]
        worker._save_completed_record(PlatformType.YOUTUBE_PLAYLIST, result_dict)

    records = load_history()
    assert len(records) == 4

    video_records = [r for r in records if r.platform == "youtube_video"]
    summary_records = [r for r in records if r.platform == "youtube_playlist"]

    assert len(video_records) == 3
    assert len(summary_records) == 1

    summary = summary_records[0]
    assert summary.media_id == "PL123"
    assert summary.playlist is True
    assert summary.requested_quality == "480p'ye kadar"
    assert summary.selected_height == 480
    assert summary.final_path == str(pl_dir.resolve())
    assert summary.final_path != str(v3.resolve())
    assert summary.display_description() == "Test Playlist Title — Oynatma Listesi"

    for idx, (rec, expected_id) in enumerate(
        zip(video_records, ["vid1", "vid2", "vid3"]), start=1
    ):
        assert rec.platform == "youtube_video"
        assert rec.media_id == expected_id
        assert rec.playlist_id == "PL123"
        assert rec.playlist_title == "Test Playlist Title"
        assert rec.playlist_index == idx
        assert rec.playlist_count == 3
        assert rec.requested_quality == "480p'ye kadar"
        assert rec.playlist is True
        assert Path(rec.final_path).exists()
        assert f"({idx}/3)" in rec.display_description()


def test_cancelled_or_missing_files_not_added_to_history(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    request = DownloadRequest(
        url="https://www.youtube.com/playlist?list=PL123",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="480p'ye kadar",
        playlist=True,
    )
    worker = DownloadWorker(request)
    worker.cancel()

    worker._save_completed_record(PlatformType.YOUTUBE_PLAYLIST, {"entries": []})
    assert len(load_history()) == 0


def test_part_files_and_duplicate_paths_ignored(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    v1 = tmp_path / "Video1.mp4"
    part_file = tmp_path / "Video2.mp4.part"
    v1.write_bytes(b"A" * 5000)
    part_file.write_bytes(b"B" * 5000)

    request = DownloadRequest(
        url="https://www.youtube.com/watch?v=v1",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="720p'ye kadar",
        playlist=False,
    )
    worker = DownloadWorker(request)

    with patch(
        "src.download_worker.probe_media_codecs",
        return_value={
            "height": 720,
            "video_codec": "h264",
            "audio_codec": "aac",
            "duration": 10.0,
        },
    ):
        worker._save_completed_record(
            PlatformType.YOUTUBE_VIDEO, {"id": "v1"}, override_target_file=v1
        )
        worker._save_completed_record(
            PlatformType.YOUTUBE_VIDEO, {"id": "v1"}, override_target_file=v1
        )

    records = load_history()
    assert len(records) == 1
    assert records[0].media_id == "v1"


def test_backward_compatibility_old_history_json(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)

    old_data = [
        {
            "platform": "youtube_video",
            "media_id": "old_id_1",
            "media_type": "Video (MP4)",
            "requested_quality": "1080p'ye kadar",
            "selected_height": 1080,
            "final_path": str(tmp_path / "old.mp4"),
            "state": "completed",
            "file_size": 1024,
            "completed_at": "2026-01-01T00:00:00Z",
            "video_codec": "h264",
            "audio_codec": "aac",
            "playlist": False,
        }
    ]
    import json

    history_file.write_text(json.dumps(old_data), encoding="utf-8")

    records = load_history()
    assert len(records) == 1
    r = records[0]
    assert r.media_id == "old_id_1"
    assert r.playlist_id == ""
    assert r.playlist_title == ""
    assert r.playlist_index == 0
    assert r.playlist_count == 0
    assert r.title == ""
    assert r.display_title() == "old"


def test_redownload_behavior_unique_paths_and_history(tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("src.history.HISTORY_FILE", history_file)
    monkeypatch.setattr(
        "src.download_worker.probe_media_codecs",
        lambda p: {"video_codec": "h264", "audio_codec": "aac", "duration": 10.0},
    )

    class MockYDL:
        def __init__(self, params=None):
            self.params = params or {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download=False):
            return {"id": "mock1", "title": "Mock Video", "ext": "mp4"}

        def prepare_filename(self, info):
            return str(tmp_path / "Mock Video [mock1].mp4")

        def process_ie_result(self, info, download=False):
            out_tmpl = self.params.get("outtmpl", {})
            if isinstance(out_tmpl, dict):
                out = out_tmpl.get(
                    "default", str(tmp_path / "Mock Video [mock1].%(ext)s")
                )
            else:
                out = str(tmp_path / "Mock Video [mock1].mp4")
            final_path = out.replace("%(ext)s", "mp4")
            Path(final_path).write_bytes(b"DATA")
            return {
                "id": "mock1",
                "title": "Mock Video",
                "filepath": final_path,
                "_filename": final_path,
            }

    # 1. İlk indirme (temel ad)
    req1 = DownloadRequest(
        "https://youtube.com/watch?v=mock1", tmp_path, "Video (MP4)", "En iyi", False
    )
    worker1 = DownloadWorker(req1)

    succeeded_path1 = []
    worker1.succeeded.connect(lambda p: succeeded_path1.append(p))

    with patch("yt_dlp.YoutubeDL", MockYDL):
        worker1.run()

    assert len(succeeded_path1) == 1
    assert Path(succeeded_path1[0]).name == "Mock Video [mock1].mp4"
    assert Path(succeeded_path1[0]).exists()

    records = load_history()
    assert len(records) == 1
    assert records[0].media_id == "mock1"
    assert records[0].final_path == succeeded_path1[0]

    # 2. İkinci indirme (1) numarası almalı
    req2 = DownloadRequest(
        "https://youtube.com/watch?v=mock1", tmp_path, "Video (MP4)", "En iyi", False
    )
    worker2 = DownloadWorker(req2)
    succeeded_path2 = []
    worker2.succeeded.connect(lambda p: succeeded_path2.append(p))

    with patch("yt_dlp.YoutubeDL", MockYDL):
        worker2.run()

    assert len(succeeded_path2) == 1
    assert Path(succeeded_path2[0]).name == "Mock Video [mock1] (1).mp4"
    assert Path(succeeded_path2[0]).exists()

    records2 = load_history()
    assert len(records2) == 2
    assert records2[1].media_id == "mock1"
    assert records2[1].final_path == succeeded_path2[0]
    assert records2[0].final_path != records2[1].final_path
