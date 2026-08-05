import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.download_worker import DownloadWorker
from src.main_window import MainWindow
from src.models import DownloadRequest, SessionMethod


@pytest.fixture
def mock_request(tmp_path):
    return DownloadRequest(
        url="https://www.youtube.com/watch?v=test",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
        session_method=SessionMethod.AUTO,
    )


def test_video_format_fallback(tmp_path):
    # It should prioritize h264 and aac via format_sort without failing
    from src.download_options import build_ydl_options

    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=test",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
    )
    opts = build_ydl_options(req)
    assert opts.get("format_sort") == ["vcodec:h264", "acodec:aac", "ext:mp4"]


def test_ui_has_no_video_compat_combo(qapp):
    main_window = MainWindow()
    assert not hasattr(main_window, "video_compat_combo"), (
        "videoCompatibilityCombo should be removed from UI"
    )


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_mp4_trigger_compatibility_check(mock_popen, mock_probe, mock_request):
    mock_probe.return_value = {
        "video_codec": "vp9",
        "audio_codec": "opus",
        "pix_fmt": "yuv420p",
        "width": 1920,
        "height": 1080,
        "channels": 2,
    }

    # Mock subprocess process
    process_mock = MagicMock()
    process_mock.poll.return_value = 0
    process_mock.returncode = 0
    process_mock.stderr.readline.return_value = ""
    mock_popen.return_value = process_mock

    worker = DownloadWorker(mock_request)
    # Simulate an already downloaded file
    target = mock_request.output_dir / "test.mp4"
    target.touch()
    worker._last_filename = str(target)

    # Mock rename to not actually fail on Windows if exists
    with patch.object(Path, "rename") as mock_rename:
        temp_file = target.with_name(target.stem + ".wa_temp.mp4")
        temp_file.touch()
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 100
            worker._handle_post_download_transcode({"_filename": str(target)})

        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args

        # Verify NO shell=True
        assert kwargs.get("shell") is not True

        # Verify CREATE_NO_WINDOW is set
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            assert kwargs.get("creationflags") == subprocess.CREATE_NO_WINDOW

        cmd = args[0]
        assert "ffmpeg" in cmd[0]
        assert "libx264" in cmd
        assert "aac" in cmd

        temp_file = target.with_name(target.stem + ".wa_temp.mp4")
        assert str(temp_file) in cmd
        mock_rename.assert_called_once()


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_no_transcode_for_already_compatible(mock_popen, mock_probe, mock_request):
    mock_probe.return_value = {
        "video_codec": "h264",
        "audio_codec": "aac",
        "pix_fmt": "yuv420p",
        "width": 1920,
        "height": 1080,
        "channels": 2,
    }

    worker = DownloadWorker(mock_request)
    target = mock_request.output_dir / "test.mp4"
    target.touch()
    worker._last_filename = str(target)

    worker._handle_post_download_transcode({"_filename": str(target)})
    mock_popen.assert_not_called()


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_no_transcode_for_no_audio_compatible(mock_popen, mock_probe, mock_request):
    mock_probe.return_value = {
        "video_codec": "h264",
        "audio_codec": "none",
        "pix_fmt": "yuv420p",
        "width": 1920,
        "height": 1080,
        "channels": 0,
    }

    worker = DownloadWorker(mock_request)
    target = mock_request.output_dir / "test.mp4"
    target.touch()
    worker._last_filename = str(target)

    worker._handle_post_download_transcode({"_filename": str(target)})
    mock_popen.assert_not_called()


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_transcode_odd_resolutions(mock_popen, mock_probe, mock_request):
    mock_probe.return_value = {
        "video_codec": "h264",
        "audio_codec": "aac",
        "pix_fmt": "yuv420p",
        "width": 1921,  # odd width
        "height": 1080,
        "channels": 2,
    }

    process_mock = MagicMock()
    process_mock.poll.return_value = 0
    process_mock.returncode = 0
    process_mock.stderr.readline.return_value = ""
    mock_popen.return_value = process_mock

    worker = DownloadWorker(mock_request)
    target = mock_request.output_dir / "test.mp4"
    target.touch()
    worker._last_filename = str(target)

    with patch.object(Path, "rename") as mock_rename:
        temp_file = target.with_name(target.stem + ".wa_temp.mp4")
        temp_file.touch()
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 100
            worker._handle_post_download_transcode({"_filename": str(target)})
        mock_popen.assert_called_once()
        mock_rename.assert_called_once()


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_mp3_not_transcoded(mock_popen, mock_probe, tmp_path):
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=test",
        output_dir=tmp_path,
        media_type="Ses (MP3)",
        quality="1080p'ye kadar",
        playlist=False,
        session_method=SessionMethod.AUTO,
    )
    worker = DownloadWorker(req)

    target = req.output_dir / "test.mp3"
    target.touch()
    worker._last_filename = str(target)

    worker._handle_post_download_transcode({"_filename": str(target)})
    mock_probe.assert_not_called()
    mock_popen.assert_not_called()


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_transcode_failure_preserves_original(mock_popen, mock_probe, mock_request):
    mock_probe.return_value = {
        "video_codec": "hevc",
        "audio_codec": "aac",
        "pix_fmt": "yuv420p",
        "width": 1920,
        "height": 1080,
        "channels": 2,
    }

    process_mock = MagicMock()
    process_mock.poll.return_value = 0
    process_mock.returncode = 1  # Failure!
    process_mock.stderr.readline.return_value = ""
    mock_popen.return_value = process_mock

    worker = DownloadWorker(mock_request)
    target = mock_request.output_dir / "test.mp4"
    target.touch()
    worker._last_filename = str(target)

    temp_file = target.with_name(target.stem + ".wa_temp.mp4")
    # Simulate ffmpeg leaving a temp file
    temp_file.touch()

    with patch.object(Path, "unlink") as mock_unlink:
        worker._handle_post_download_transcode({"_filename": str(target)})
        mock_popen.assert_called_once()
        mock_unlink.assert_called_with()  # We check it's called for the temp file

    assert target.exists()  # original file preserved


@patch("src.download_worker.probe_media_codecs")
@patch("subprocess.Popen")
def test_transcode_cancellation(mock_popen, mock_probe, mock_request):
    mock_probe.return_value = {
        "video_codec": "vp9",
        "audio_codec": "opus",
        "pix_fmt": "yuv420p",
        "width": 1920,
        "height": 1080,
        "channels": 2,
    }

    worker = DownloadWorker(mock_request)

    def side_effect(*args, **kwargs):
        worker._cancel_requested = True
        return ""

    process_mock = MagicMock()
    process_mock.poll.return_value = None
    process_mock.stderr.readline.side_effect = side_effect
    mock_popen.return_value = process_mock
    target = mock_request.output_dir / "test.mp4"
    target.touch()
    worker._last_filename = str(target)

    temp_file = target.with_name(target.stem + ".wa_temp.mp4")
    temp_file.touch()

    worker._handle_post_download_transcode({"_filename": str(target)})

    process_mock.kill.assert_called_once()
    assert not temp_file.exists()  # Temp file is unlinked during cancel
