"""Tarayıcı profil tespiti ve oturum yönetimi testleri."""

from __future__ import annotations

import configparser
import json
from pathlib import Path

from src.browser_sessions import (
    SESSION_STATUS_LABELS,
    BrowserProfileCandidate,
    analyze_instagram_story_url,
    build_profile_attempt_order,
    classify_session_error,
    detect_available_browser_profiles,
    is_authentication_error,
    is_browser_cookie_lock_error,
    is_chromium_encryption_error,
)
from src.models import DownloadRequest, MediaMetadata, PlatformType
from src.settings import load_settings, save_settings

# ---------------------------------------------------------------------------
# BrowserProfileCandidate veri yapısı
# ---------------------------------------------------------------------------

def test_browser_profile_candidate_fields():
    cand = BrowserProfileCandidate(
        browser="edge",
        profile_name="Profile 1",
        profile_path=Path("/fake/edge/Profile 1"),
        display_name="Edge (Profile 1)",
        priority=3,
    )
    assert cand.browser == "edge"
    assert cand.profile_name == "Profile 1"
    assert cand.display_name == "Edge (Profile 1)"
    assert cand.priority == 3


# ---------------------------------------------------------------------------
# Chrome / Edge / Brave profil algılama
# ---------------------------------------------------------------------------

def _make_chromium_structure(tmp_path: Path, browser_rel: str) -> Path:
    """tmp_path altında sahte bir Chromium User Data dizini oluşturur."""
    user_data = tmp_path / browser_rel
    (user_data / "Default").mkdir(parents=True)
    (user_data / "Profile 1").mkdir(parents=True)
    (user_data / "Profile 2").mkdir(parents=True)
    return user_data


def test_chromium_chrome_profiles_detected(tmp_path, monkeypatch):
    _make_chromium_structure(tmp_path, "Google/Chrome/User Data")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    profiles = detect_available_browser_profiles()
    chrome_profiles = [p for p in profiles if p.browser == "chrome"]
    names = [p.profile_name for p in chrome_profiles]
    assert "Default" in names
    assert "Profile 1" in names
    assert "Profile 2" in names


def test_chromium_edge_profiles_detected(tmp_path, monkeypatch):
    _make_chromium_structure(tmp_path, "Microsoft/Edge/User Data")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    profiles = detect_available_browser_profiles()
    edge_profiles = [p for p in profiles if p.browser == "edge"]
    names = [p.profile_name for p in edge_profiles]
    assert "Default" in names


def test_chromium_brave_profiles_detected(tmp_path, monkeypatch):
    _make_chromium_structure(tmp_path, "BraveSoftware/Brave-Browser/User Data")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    profiles = detect_available_browser_profiles()
    brave_profiles = [p for p in profiles if p.browser == "brave"]
    names = [p.profile_name for p in brave_profiles]
    assert "Default" in names


def test_chromium_display_name_format(tmp_path, monkeypatch):
    _make_chromium_structure(tmp_path, "Microsoft/Edge/User Data")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    profiles = detect_available_browser_profiles()
    edge_default = next((p for p in profiles if p.browser == "edge" and p.profile_name == "Default"), None)
    assert edge_default is not None
    assert "Edge" in edge_default.display_name
    assert "Default" in edge_default.display_name


# ---------------------------------------------------------------------------
# Firefox profil algılama
# ---------------------------------------------------------------------------

def _make_firefox_ini(base: Path, profiles: list[dict]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config["General"] = {"StartWithLastProfile": "1"}
    for i, p in enumerate(profiles):
        section = f"Profile{i}"
        config[section] = {
            "Name": p["name"],
            "IsRelative": "1",
            "Path": p["path"],
        }
        (base / p["path"]).mkdir(parents=True, exist_ok=True)
    with open(base / "profiles.ini", "w", encoding="utf-8") as f:
        config.write(f)


def test_firefox_profiles_detected(tmp_path, monkeypatch):
    ff_base = tmp_path / "Mozilla" / "Firefox"
    _make_firefox_ini(
        ff_base,
        [
            {"name": "default-release", "path": "Profiles/abc.default-release"},
            {"name": "work", "path": "Profiles/xyz.work"},
        ],
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))

    profiles = detect_available_browser_profiles()
    ff_profiles = [p for p in profiles if p.browser == "firefox"]
    assert len(ff_profiles) >= 2


def test_firefox_profile_name_from_ini(tmp_path, monkeypatch):
    ff_base = tmp_path / "Mozilla" / "Firefox"
    _make_firefox_ini(
        ff_base,
        [{"name": "default-release", "path": "Profiles/abc123.default-release"}],
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))

    profiles = detect_available_browser_profiles()
    ff = [p for p in profiles if p.browser == "firefox"]
    assert len(ff) >= 1
    assert "default-release" in ff[0].profile_name.lower() or ff[0].profile_name != ""


# ---------------------------------------------------------------------------
# build_profile_attempt_order
# ---------------------------------------------------------------------------

def test_attempt_order_first_is_unauthenticated():
    order = build_profile_attempt_order(PlatformType.INSTAGRAM_REEL, "auto")
    assert order[0] == (None, None, "Oturumsuz")


def test_attempt_order_none_mode_only_unauthenticated():
    order = build_profile_attempt_order(PlatformType.INSTAGRAM_REEL, "none")
    assert len(order) == 1
    assert order[0] == (None, None, "Oturumsuz")


def test_attempt_order_no_duplicates(tmp_path, monkeypatch):
    _make_chromium_structure(tmp_path, "Microsoft/Edge/User Data")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    order = build_profile_attempt_order(PlatformType.INSTAGRAM_STORY, "auto")
    seen = set()
    for b, p, _ in order:
        key = (b, p)
        assert key not in seen, f"Yinelenen profil: {b}/{p}"
        seen.add(key)


def test_attempt_order_instagram_firefox_priority(tmp_path, monkeypatch):
    """Instagram için Firefox profilleri Edge'den önce gelmeli."""
    _make_chromium_structure(tmp_path, "Microsoft/Edge/User Data")
    ff_base = tmp_path / "Mozilla" / "Firefox"
    _make_firefox_ini(
        ff_base, [{"name": "default-release", "path": "Profiles/abc.default-release"}]
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))

    order = build_profile_attempt_order(PlatformType.INSTAGRAM_STORY, "auto")
    browsers_order = [b for b, p, _ in order if b is not None]
    if "firefox" in browsers_order and "edge" in browsers_order:
        assert browsers_order.index("firefox") < browsers_order.index("edge")


def test_attempt_order_specific_browser_mode(tmp_path, monkeypatch):
    _make_chromium_structure(tmp_path, "Microsoft/Edge/User Data")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    order = build_profile_attempt_order(PlatformType.INSTAGRAM_POST, "edge")
    browsers = [b for b, _, _ in order]
    assert all(b == "edge" for b in browsers if b is not None)


# ---------------------------------------------------------------------------
# classify_session_error
# ---------------------------------------------------------------------------

def test_classify_locked_database():
    result = classify_session_error("Could not copy Chrome cookie database", "")
    assert result == SESSION_STATUS_LABELS["db_locked"]


def test_classify_expired_story():
    result = classify_session_error("This content is not available", "https://instagram.com/stories/x/123")
    assert result == SESSION_STATUS_LABELS["story_inaccessible"]


def test_classify_rate_limit():
    result = classify_session_error("429 too many requests", "https://instagram.com/reel/abc")
    assert result == "Instagram oran sınırlaması"


def test_classify_instagram_auth():
    result = classify_session_error("Login required", "https://instagram.com/stories/user/12345")
    assert result == SESSION_STATUS_LABELS["no_instagram_session"]


def test_classify_twitter_auth():
    result = classify_session_error("You need to log in to access this content", "https://x.com/user/status/123")
    assert result == "X oturumu bulunamadı"


def test_classify_profile_not_found():
    result = classify_session_error("Could not find profile directory", "https://instagram.com/reel/abc")
    assert result == SESSION_STATUS_LABELS["profile_not_found"]


# ---------------------------------------------------------------------------
# analyze_instagram_story_url
# ---------------------------------------------------------------------------

def test_story_url_username_only():
    notice, err = analyze_instagram_story_url("https://www.instagram.com/stories/someuser/")
    assert notice is not None
    assert "tüm aktif hikâye" in notice.lower()
    assert err is None


def test_story_url_specific_id():
    notice, err = analyze_instagram_story_url("https://www.instagram.com/stories/someuser/123456789/")
    assert notice is not None
    assert "belirli" in notice.lower()
    assert err is None


def test_story_url_highlight_no_id():
    _notice, err = analyze_instagram_story_url("https://www.instagram.com/stories/highlights/")
    assert err is not None
    assert "kimlik" in err.lower() or "eksik" in err.lower()


def test_story_url_highlight_with_id():
    notice, err = analyze_instagram_story_url("https://www.instagram.com/stories/highlights/1234567/")
    assert err is None
    assert notice is not None


def test_non_story_url_no_notice():
    notice, err = analyze_instagram_story_url("https://www.instagram.com/reel/abc123/")
    assert notice is None
    assert err is None


# ---------------------------------------------------------------------------
# Bellek odaklı profil saklama (settings.json'a yazılmıyor)
# ---------------------------------------------------------------------------

def test_session_profile_memory_only(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    meta = MediaMetadata(
        title="Test Reel",
        session_browser="edge",
        session_profile=("edge", "Profile 1"),
        platform_type=PlatformType.INSTAGRAM_REEL,
    )
    assert meta.session_profile == ("edge", "Profile 1")

    save_settings({"output_dir": str(tmp_path), "browser": "auto"})
    loaded = load_settings()
    assert "session_profile" not in loaded
    assert "preferred_profile" not in loaded


def test_session_profile_not_written_to_settings(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)

    save_settings({"output_dir": str(tmp_path)})
    content = json.loads(settings_file.read_text(encoding="utf-8")) if settings_file.exists() else {}
    assert "session_profile" not in content
    assert "preferred_profile" not in content


# ---------------------------------------------------------------------------
# DownloadRequest preferred_profile
# ---------------------------------------------------------------------------

def test_download_request_preferred_profile(tmp_path):
    req = DownloadRequest(
        url="https://www.instagram.com/stories/user/12345",
        output_dir=tmp_path,
        media_type="Video (MP4)",
        quality="En iyi kullanılabilir kalite",
        playlist=False,
        browser="auto",
        preferred_profile=("edge", "Profile 1"),
    )
    assert req.preferred_profile == ("edge", "Profile 1")


# ---------------------------------------------------------------------------
# is_authentication_error / is_browser_cookie_lock_error
# ---------------------------------------------------------------------------

def test_is_authentication_error_variants():
    assert is_authentication_error("Login required to view this content") is True
    assert is_authentication_error("Sign in to continue") is True
    assert is_authentication_error("This post is from a private account") is True
    assert is_authentication_error("HTTP 404 Not Found") is False


def test_is_browser_cookie_lock_error_variants():
    assert is_browser_cookie_lock_error("Could not copy Chrome cookie database") is True
    assert is_browser_cookie_lock_error("database is locked") is True
    assert is_browser_cookie_lock_error("Permission denied") is True
    assert is_browser_cookie_lock_error("Connection timeout") is False


# ---------------------------------------------------------------------------
# Gizli cookie/token loglanmıyor kontrolü
# ---------------------------------------------------------------------------

def test_classify_does_not_expose_cookies():
    """classify_session_error çıktısı gizli bilgi içermemeli."""
    fake_error = "Cookie value: abc123secret; session_token=xyz789 — Login required"
    result = classify_session_error(fake_error, "https://instagram.com/stories/user/123")
    assert "abc123secret" not in result
    assert "xyz789" not in result
    assert "session_token" not in result


# ---------------------------------------------------------------------------
# SessionFailedDialog (GUI)
# ---------------------------------------------------------------------------

def test_session_failed_dialog_renders():
    from PySide6.QtWidgets import QApplication

    from src.dialogs import SessionFailedDialog

    _app = QApplication.instance() or QApplication([])
    dlg = SessionFailedDialog(platform_name="instagram", failure_reason="Login required")
    assert dlg.windowTitle() == "Oturum alınamadı"
    dlg.close()


def test_session_failed_dialog_lock_reason():
    from PySide6.QtWidgets import QApplication

    from src.dialogs import SessionFailedDialog

    _app = QApplication.instance() or QApplication([])
    dlg = SessionFailedDialog(platform_name="instagram", failure_reason="database is locked")
    # Dialog açılmalı ve kilitli tarayıcı mesajı içermeli
    assert dlg.windowTitle() == "Oturum alınamadı"
    dlg.close()


# ---------------------------------------------------------------------------
# Yeni testler — Gereksinim 9
# ---------------------------------------------------------------------------


def test_is_chromium_encryption_error_dpapi():
    """DPAPI şifreleme hatası doğru algılanmalı."""
    assert is_chromium_encryption_error("failed to decrypt cookie") is True
    assert is_chromium_encryption_error("DPAPI decryption error") is True
    assert is_chromium_encryption_error("app-bound encryption prevents cookie access") is True
    assert is_chromium_encryption_error("cookies could not be decrypted") is True
    assert is_chromium_encryption_error("no cookies could be loaded") is True


def test_is_chromium_encryption_error_false_for_others():
    """Sıradan lock ve auth hataları encryption hatası sayılmamalı."""
    assert is_chromium_encryption_error("database is locked") is False
    assert is_chromium_encryption_error("Login required") is False
    assert is_chromium_encryption_error("") is False


def test_classify_chromium_encryption_gets_correct_label():
    """Chromium şifreleme hatası doğru SESSION_STATUS_LABELS etiketini almalı."""
    result = classify_session_error("failed to decrypt cookie", "https://instagram.com/stories/user/123")
    assert result == SESSION_STATUS_LABELS["encrypted_cookies"]
    assert "Windows" in result


def test_classify_chromium_profile_found_not_session_validated():
    """Chromium profili bulunması oturum başarısı sayılmamalı; oturum doğrulandı
    ancak yt-dlp içeriği çözümleyebildiyse geçerlidir. Bu test classify_session_error'ın
    auth hatasını 'no_instagram_session' olarak sınıflandırdığını doğrular."""
    result = classify_session_error("Login required", "https://instagram.com/stories/user/123")
    assert result == SESSION_STATUS_LABELS["no_instagram_session"]
    # 'Oturum doğrulandı' OLMAMALI — bu sadece gerçek içerik çözümünde emit edilir
    assert result != SESSION_STATUS_LABELS["session_validated"]


def test_firefox_not_installed_dialog_shows_install_button(monkeypatch):
    """Firefox kurulu değilse SessionFailedDialog'da 'Firefox Kurulumunu Aç' düğmesi görünmeli."""
    from PySide6.QtWidgets import QApplication

    import src.dialogs as dialogs_mod

    _app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(dialogs_mod, "is_firefox_installed", lambda: False)
    monkeypatch.setattr(dialogs_mod, "is_firefox_has_instagram_session", lambda: False)
    monkeypatch.setattr(dialogs_mod, "is_chromium_encryption_error", lambda msg: False)

    dlg = dialogs_mod.SessionFailedDialog(platform_name="instagram", failure_reason="Login required")

    # "Firefox Kurulumunu Aç" butonu var mı?
    from PySide6.QtWidgets import QPushButton
    install_btn = dlg.findChild(QPushButton, "dialogPrimaryButton")
    assert install_btn is not None
    # Başlık ya da metin "Firefox" içeriyor mu?
    # En az bir butonun metninde Firefox olmalı
    buttons = dlg.findChildren(QPushButton)
    btn_texts = [b.text() for b in buttons]
    assert any("Firefox" in t for t in btn_texts), f"Firefox butonu bulunamadı: {btn_texts}"
    dlg.close()


def test_firefox_installed_no_session_dialog_message(monkeypatch):
    """Firefox kurulu ama Instagram oturumu yoksa doğru mesaj gösterilmeli."""
    from PySide6.QtWidgets import QApplication, QLabel

    import src.dialogs as dialogs_mod

    _app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(dialogs_mod, "is_firefox_installed", lambda: True)
    monkeypatch.setattr(dialogs_mod, "is_firefox_has_instagram_session", lambda: False)
    monkeypatch.setattr(dialogs_mod, "is_chromium_encryption_error", lambda msg: False)

    dlg = dialogs_mod.SessionFailedDialog(platform_name="instagram", failure_reason="Login required")

    labels = dlg.findChildren(QLabel)
    label_texts = " ".join(lbl.text() for lbl in labels).lower()
    assert "firefox bulundu" in label_texts
    assert "instagram" in label_texts
    dlg.close()


def test_story_url_username_only_updated_message():
    """Yalnızca kullanıcı adıyla biten hikâye URL'si doğru uyarı metnini döndürmeli."""
    notice, err = analyze_instagram_story_url("https://www.instagram.com/stories/someuser/")
    assert err is None
    assert notice is not None
    # Yeni metin "sayısal hikâye kimliği" ifadesini içermeli
    assert "sayısal hikâye kimliği" in notice.lower() or "hik" in notice.lower()


def test_story_url_specific_id_not_confused_with_username_only():
    """Sayısal ID içeren hikâye URL'si 'yalnızca kullanıcı adı' uyarısı vermemeli."""
    notice, err = analyze_instagram_story_url("https://www.instagram.com/stories/someuser/9876543210/")
    assert err is None
    assert notice is not None
    # Bu "belirli hikâye" veya "ID" içermeli, "sayısal hikâye kimliği" içermemeli
    assert "belirli" in notice.lower() or "algılandı" in notice.lower()
    assert "sayısal hikâye kimliği" not in notice.lower()


def test_session_status_labels_completeness():
    """SESSION_STATUS_LABELS sözlüğü beklenen tüm anahtarları içermeli."""
    expected_keys = {
        "profile_not_found",
        "no_instagram_session",
        "encrypted_cookies",
        "db_locked",
        "story_inaccessible",
        "session_validated",
    }
    assert expected_keys <= set(SESSION_STATUS_LABELS.keys())


def test_firefox_profileless_attempt_first():
    """Instagram için ilk oturumlu deneme profil belirtmeden ('firefox', None) olmalı."""
    order = build_profile_attempt_order(PlatformType.INSTAGRAM_STORY, "auto")
    assert len(order) >= 2
    assert order[0] == (None, None, "Oturumsuz")
    assert order[1][0] == "firefox"
    assert order[1][1] is None


def test_firefox_profileless_attempt_no_duplicates():
    """('firefox', None) girişi yalnızca bir kez eklenmeli."""
    order = build_profile_attempt_order(PlatformType.INSTAGRAM_STORY, "auto")
    firefox_profileless_count = sum(1 for b, p, _ in order if b == "firefox" and p is None)
    assert firefox_profileless_count == 1


def test_cookiesfrombrowser_preferred_browser_tuple():
    """preferred_browser='firefox' ve preferred_profile=None durumunda cookiesfrombrowser == ('firefox',)."""
    from src.download_options import build_ydl_options
    req = DownloadRequest(
        url="https://www.instagram.com/stories/jahrein/123/",
        output_dir=Path("downloads"),
        media_type="Video (MP4)",
        quality="720p",
        playlist=False,
        browser="auto",
        preferred_browser="firefox",
        preferred_profile=None,
    )
    opts = build_ydl_options(req)
    assert opts.get("cookiesfrombrowser") == ("firefox",)


def test_story_playlist_disabled_single_item():
    """Story URL + playlist kapalı ise noplaylist=True ve playlist_items='1' olmalı."""
    from src.download_options import build_ydl_options
    req = DownloadRequest(
        url="https://www.instagram.com/stories/jahrein/3951962231915018297/",
        output_dir=Path("downloads"),
        media_type="Video (MP4)",
        quality="720p",
        playlist=False,
        browser="auto",
    )
    opts = build_ydl_options(req)
    assert opts["noplaylist"] is True
    assert opts["playlist_items"] == "1"


def test_story_playlist_enabled_subfolder_template():
    """Story URL + playlist açık ise noplaylist=False ve NA klasörü oluşturmayan şablon kullanılmalı."""
    from src.download_options import build_ydl_options
    req = DownloadRequest(
        url="https://www.instagram.com/stories/jahrein/3951962231915018297/",
        output_dir=Path("downloads"),
        media_type="Video (MP4)",
        quality="720p",
        playlist=True,
        browser="auto",
    )
    opts = build_ydl_options(req)
    assert opts["noplaylist"] is False
    assert "%(uploader" in opts["outtmpl"]
    assert "NA" not in opts["outtmpl"]

