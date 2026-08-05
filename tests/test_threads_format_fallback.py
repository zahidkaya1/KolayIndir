from unittest.mock import MagicMock, patch

from src.download_options import _video_format, build_ydl_options
from src.download_worker import DownloadWorker
from src.models import DownloadRequest


def test_threads_video_format_no_strict_codec():
    """Threads (ve genel kullanım) için üretilen _video_format içinde katı vcodec^=avc1 gibi filtrelerin olmadığını doğrular."""
    fmt = _video_format("1080p'ye kadar")
    assert "[vcodec^=avc1]" not in fmt
    assert "[vcodec^=h264]" not in fmt
    assert "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b" in fmt


def test_threads_ydl_options_format_sort():
    """Threads indirmelerinde format_sort'un yt-dlp'ye verilmediğini (boş bırakıldığını) doğrular."""
    req = DownloadRequest(
        url="https://www.threads.net/@sueermurat/post/DbnFT1TjdLL",
        output_dir=MagicMock(),
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
    )
    opts = build_ydl_options(req)
    assert "format_sort" not in opts


@patch("src.download_worker.create_ytdl")
@patch("src.download_worker.patch_subprocess_for_hidden_console")
def test_download_worker_fallback_on_format_not_available(mock_patch, mock_create_ytdl):
    """
    Requested format is not available hatası alındığında, DownloadWorker'ın
    'bv*+ba/b' selector ile ikinci bir deneme yaptığını doğrular.
    """
    req = DownloadRequest(
        url="https://www.threads.net/@user/post/123",
        output_dir=MagicMock(),
        media_type="Video (MP4)",
        quality="1080p'ye kadar",
        playlist=False,
    )

    worker = DownloadWorker(req)
    worker.log = MagicMock()
    worker.status = MagicMock()
    worker.succeeded = MagicMock()
    worker.failed = MagicMock()

    # Mocking yt-dlp instance
    mock_ydl_first = MagicMock()
    mock_ydl_second = MagicMock()

    # First extraction passes, but processing fails
    mock_ydl_first.extract_info.return_value = {
        "id": "123",
        "title": "Test",
        "ext": "mp4",
    }
    mock_ydl_first.prepare_filename.return_value = "C:\\temp\\dummy.mp4"
    mock_ydl_first.params = {"merge_output_format": "mp4"}

    # Simulate first process_ie_result raising "Requested format is not available"
    mock_ydl_first.process_ie_result.side_effect = Exception(
        "ERROR: [threads] 123: Requested format is not available"
    )

    # Second processing passes
    mock_ydl_second.process_ie_result.return_value = {
        "id": "123",
        "title": "Test",
        "ext": "mp4",
    }
    mock_ydl_second.params = {"merge_output_format": "mp4"}

    mock_create_ytdl.side_effect = [
        MagicMock(
            __enter__=MagicMock(return_value=mock_ydl_first), __exit__=MagicMock()
        ),
        MagicMock(
            __enter__=MagicMock(return_value=mock_ydl_second), __exit__=MagicMock()
        ),
    ]

    # Prevent transcode logic from failing the test
    worker._handle_post_download_transcode = MagicMock()
    worker._save_completed_record = MagicMock()

    worker.run()

    # We should have created ytdl twice (original and fallback)
    assert mock_create_ytdl.call_count == 2

    # Check that fallback options contained the fallback format
    fallback_args = mock_create_ytdl.call_args_list[1][0][0]
    assert fallback_args["format"] == "bv*+ba/b"

    # Check log message
    worker.log.emit.assert_any_call(
        "İstenen kalite formatı bulunamadı, güvenli genel seçici ile yeniden deneniyor…"
    )

    # Verify success was emitted
    worker.succeeded.emit.assert_called_once()
