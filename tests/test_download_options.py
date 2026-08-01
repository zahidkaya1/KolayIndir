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


def test_playlist_480p_format_selector(tmp_path):
    req = create_request(output_dir=tmp_path, quality="480p'ye kadar", playlist=True)
    options = build_ydl_options(req)
    assert "height<=480" in options["format"]
    assert not options["format"].endswith("/b")


def test_playlist_720p_format_selector(tmp_path):
    req = create_request(output_dir=tmp_path, quality="720p'ye kadar", playlist=True)
    options = build_ydl_options(req)
    assert "height<=720" in options["format"]
    assert not options["format"].endswith("/b")


def test_playlist_1080p_format_selector(tmp_path):
    req = create_request(output_dir=tmp_path, quality="1080p'ye kadar", playlist=True)
    options = build_ydl_options(req)
    assert "height<=1080" in options["format"]
    assert not options["format"].endswith("/b")


def test_playlist_best_quality_no_height_limit(tmp_path):
    req = create_request(output_dir=tmp_path, quality="En iyi kullanılabilir kalite", playlist=True)
    options = build_ydl_options(req)
    assert "height<=" not in options["format"]


def test_playlist_true_does_not_override_quality(tmp_path):
    req = create_request(output_dir=tmp_path, quality="480p'ye kadar", playlist=True)
    assert req.quality == "480p'ye kadar"
    options = build_ydl_options(req)
    assert "height<=480" in options["format"]


def test_both_apostrophe_styles_parsed_correctly(tmp_path):
    req_straight = create_request(output_dir=tmp_path, quality="480p'ye kadar")
    req_curly = create_request(output_dir=tmp_path, quality="480p’ye kadar")
    opts_straight = build_ydl_options(req_straight)
    opts_curly = build_ydl_options(req_curly)
    assert "height<=480" in opts_straight["format"]
    assert "height<=480" in opts_curly["format"]
