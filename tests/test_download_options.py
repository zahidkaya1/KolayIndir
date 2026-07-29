from pathlib import Path

from src.download_options import build_ydl_options
from src.models import DownloadRequest


def create_request(**overrides):
    values = {
        "url": "https://example.com/video",
        "output_dir": Path("downloads"),
        "media_type": "Video (MP4)",
        "quality": "720p",
        "playlist": False,
        "browser": None,
    }
    values.update(overrides)
    return DownloadRequest(**values)


def test_video_720p_options(tmp_path):
    options = build_ydl_options(create_request(output_dir=tmp_path))
    assert "height<=720" in options["format"]
    assert options["merge_output_format"] == "mp4"
    assert options["noplaylist"] is True


def test_audio_options_include_mp3_postprocessor(tmp_path):
    request = create_request(output_dir=tmp_path, media_type="Ses (MP3)")
    options = build_ydl_options(request)
    assert options["format"] == "bestaudio/best"
    assert options["postprocessors"][0]["preferredcodec"] == "mp3"


def test_playlist_template(tmp_path):
    options = build_ydl_options(create_request(output_dir=tmp_path, playlist=True))
    assert "%(playlist_title,playlist" in options["outtmpl"]
    assert options["noplaylist"] is False



def test_browser_cookie_option(tmp_path):
    options = build_ydl_options(create_request(output_dir=tmp_path, browser="chrome"))
    assert options["cookiesfrombrowser"] == ("chrome",)
