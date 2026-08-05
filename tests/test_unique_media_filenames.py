import pytest

from src.history import (
    _reserved_paths,
    release_reserved_path,
    reserve_unique_media_path,
)


@pytest.fixture(autouse=True)
def clean_reservations():
    _reserved_paths.clear()
    yield
    _reserved_paths.clear()


def test_empty_folder(tmp_path):
    # klasör boşken numarasız isim
    res = reserve_unique_media_path(tmp_path, "Video", ".mp4")
    assert res.name == "Video.mp4"
    release_reserved_path(res)


def test_same_extension_only(tmp_path):
    # yalnız aynı uzantı varsa sonraki sıra
    (tmp_path / "Video.mp4").touch()
    res = reserve_unique_media_path(tmp_path, "Video", "mp4")
    assert res.name == "Video (1).mp4"


def test_mixed_mp3_mp4(tmp_path):
    # MP4 varken yeni MP3 sonraki sıra
    (tmp_path / "Sarki.mp4").touch()
    res = reserve_unique_media_path(tmp_path, "Sarki", ".mp3")
    assert res.name == "Sarki (1).mp3"


def test_mixed_mp3_mp4_reverse(tmp_path):
    # MP3 varken yeni MP4 sonraki sıra
    (tmp_path / "Podcast.mp3").touch()
    res = reserve_unique_media_path(tmp_path, "Podcast", ".mp4")
    assert res.name == "Podcast (1).mp4"


def test_complex_shared_counter(tmp_path):
    # mevcut (3).mp4 sonrası yeni MP3 (4).mp3 olur
    (tmp_path / "Belgesel.mp3").touch()
    (tmp_path / "Belgesel.mp4").touch()
    (tmp_path / "Belgesel (1).mp3").touch()
    (tmp_path / "Belgesel (1).mp4").touch()
    (tmp_path / "Belgesel (2).mp3").touch()
    (tmp_path / "Belgesel (2).mp4").touch()
    (tmp_path / "Belgesel (3).mp4").touch()

    res = reserve_unique_media_path(tmp_path, "Belgesel", ".mp3")
    assert res.name == "Belgesel (4).mp3"


def test_gaps_in_counter(tmp_path):
    # sıra numaralarında boşluklar varsa doğru davranır (boşlukları doldurur)
    (tmp_path / "Gaps.mp4").touch()
    (tmp_path / "Gaps (5).mp3").touch()
    res = reserve_unique_media_path(tmp_path, "Gaps", ".mp4")
    assert res.name == "Gaps (6).mp4"


def test_title_with_parentheses_not_counter(tmp_path):
    # başlık içindeki (2025) yanlış sayaç kabul edilmez
    res = reserve_unique_media_path(tmp_path, "Video (2025) Başlık", ".mp4")
    assert res.name == "Video (2025) Başlık.mp4"


def test_title_with_parentheses_at_end(tmp_path):
    # Eğer orijinal isim Film (2025) ise ve klasör boşsa sayaç zannedilmemeli!
    res = reserve_unique_media_path(tmp_path, "Film (2025)", ".mkv")
    assert res.name == "Film (2025).mkv"
    # İkinci kopya Film (2025) (1).mkv olmalı
    (tmp_path / "Film (2025).mkv").touch()
    res2 = reserve_unique_media_path(tmp_path, "Film (2025)", ".mkv")
    assert res2.name == "Film (2025) (1).mkv"


def test_independent_base_names(tmp_path):
    # farklı taban adlar birbirini etkilemez
    (tmp_path / "A.mp4").touch()
    (tmp_path / "A (1).mp4").touch()
    res = reserve_unique_media_path(tmp_path, "B", ".mp4")
    assert res.name == "B.mp4"


def test_case_insensitive_windows(tmp_path):
    # büyük/küçük harf farkı Windows'ta çakışma kabul edilir
    (tmp_path / "test.mp4").touch()
    res = reserve_unique_media_path(tmp_path, "TEST", ".mp3")
    assert res.name.lower() == "test (1).mp3"


def test_ignore_temp_files(tmp_path):
    # .part ve .tmp dosyaları hesaba katılmaz
    (tmp_path / "TempTest.mp4.part").touch()
    (tmp_path / "TempTest.mp3.tmp").touch()
    res = reserve_unique_media_path(tmp_path, "TempTest", ".mp4")
    assert res.name == "TempTest.mp4"


def test_reserved_paths(tmp_path):
    # rezerve final yolları hesaba katılır
    # iki paralel worker farklı yol alır
    res1 = reserve_unique_media_path(tmp_path, "Parallel", ".mp4")
    res2 = reserve_unique_media_path(tmp_path, "Parallel", ".mp3")

    assert res1.name == "Parallel.mp4"
    assert res2.name == "Parallel (1).mp3"


def test_reservation_release(tmp_path):
    # rezervasyon işlem sonunda bırakılır
    res1 = reserve_unique_media_path(tmp_path, "Rel", ".mp4")
    assert res1.name == "Rel.mp4"
    release_reserved_path(res1)

    res2 = reserve_unique_media_path(tmp_path, "Rel", ".mp3")
    # Dosya sisteminde yok ve rezervasyon bırakıldı, yani numarasız alınmalı
    assert res2.name == "Rel.mp3"
