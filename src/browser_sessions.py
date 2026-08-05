"""Tarayıcı profil tespiti, sıralama ve oturum hata yönetimi yardımcı modülü."""

from __future__ import annotations

import configparser
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.models import PlatformType, is_rehydration_error


@dataclass(frozen=True, slots=True)
class BrowserProfileCandidate:
    browser: str
    profile_name: str
    profile_path: Path | None
    display_name: str
    priority: int = 10


def _detect_firefox_profiles() -> list[BrowserProfileCandidate]:
    profiles: list[BrowserProfileCandidate] = []
    appdata = os.environ.get("APPDATA", "")
    home = Path.home()
    base_dirs = []
    if appdata:
        base_dirs.append(Path(appdata) / "Mozilla" / "Firefox")
    base_dirs.append(home / "AppData" / "Roaming" / "Mozilla" / "Firefox")

    for base in base_dirs:
        ini_path = base / "profiles.ini"
        if ini_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(ini_path, encoding="utf-8")

                install_default_path = None
                profile_defaults: list[Path] = []
                other_profiles: list[Path] = []

                for section in config.sections():
                    if section.startswith("Install"):
                        install_default_str = config.get(
                            section, "Default", fallback=""
                        )
                        if install_default_str:
                            install_default_path = base / install_default_str

                    if section.lower().startswith("profile"):
                        rel_path = config.get(section, "Path", fallback="")
                        if not rel_path:
                            continue
                        is_rel = config.get(section, "IsRelative", fallback="1") == "1"
                        full_path = (base / rel_path) if is_rel else Path(rel_path)

                        is_default = config.get(section, "Default", fallback="0") == "1"
                        if is_default:
                            profile_defaults.append(full_path)
                        else:
                            other_profiles.append(full_path)

                candidates_to_check = []
                if install_default_path:
                    candidates_to_check.append(install_default_path)
                candidates_to_check.extend(profile_defaults)
                candidates_to_check.extend(other_profiles)

                seen = set()
                for full_path in candidates_to_check:
                    if full_path in seen:
                        continue
                    seen.add(full_path)

                    cookies_db = full_path / "cookies.sqlite"
                    if cookies_db.exists():
                        profiles.append(
                            BrowserProfileCandidate(
                                browser="firefox",
                                profile_name=full_path.name,
                                profile_path=full_path,
                                display_name=f"Firefox ({full_path.name})",
                                priority=1,
                            )
                        )
            except Exception:  # noqa: BLE001, S110
                pass

        if not profiles:
            profiles_dir = base / "Profiles"
            if profiles_dir.exists():
                try:
                    for child in profiles_dir.iterdir():
                        if child.is_dir():
                            cookies_db = child / "cookies.sqlite"
                            if cookies_db.exists():
                                profiles.append(
                                    BrowserProfileCandidate(
                                        browser="firefox",
                                        profile_name=child.name,
                                        profile_path=child,
                                        display_name=f"Firefox ({child.name})",
                                        priority=1,
                                    )
                                )
                except OSError:
                    pass
        if profiles:
            break

    return profiles


def _detect_chromium_profiles(
    browser: str, relative_user_data_path: str, base_priority: int
) -> list[BrowserProfileCandidate]:
    profiles: list[BrowserProfileCandidate] = []
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    home = Path.home()
    base_dirs = []
    if local_appdata:
        base_dirs.append(Path(local_appdata) / relative_user_data_path)
    base_dirs.append(home / "AppData" / "Local" / relative_user_data_path)

    b_title = "Edge" if browser == "edge" else browser.capitalize()

    for user_data in base_dirs:
        if user_data.exists():
            try:
                # Default profile first
                default_dir = user_data / "Default"
                if default_dir.exists():
                    profiles.append(
                        BrowserProfileCandidate(
                            browser=browser,
                            profile_name="Default",
                            profile_path=default_dir,
                            display_name=f"{b_title} (Default)",
                            priority=base_priority,
                        )
                    )

                # Then Profile 1, Profile 2, etc.
                profile_dirs = sorted(
                    [
                        child
                        for child in user_data.iterdir()
                        if child.is_dir() and child.name.startswith("Profile ")
                    ],
                    key=lambda p: p.name,
                )
                for p_dir in profile_dirs:
                    profiles.append(
                        BrowserProfileCandidate(
                            browser=browser,
                            profile_name=p_dir.name,
                            profile_path=p_dir,
                            display_name=f"{b_title} ({p_dir.name})",
                            priority=base_priority + 1,
                        )
                    )
            except OSError:
                pass
            if profiles:
                break

    return profiles


def detect_available_browser_profiles() -> list[BrowserProfileCandidate]:
    all_profiles: list[BrowserProfileCandidate] = []
    all_profiles.extend(_detect_firefox_profiles())
    all_profiles.extend(
        _detect_chromium_profiles("edge", R"Microsoft\Edge\User Data", 2)
    )
    all_profiles.extend(
        _detect_chromium_profiles("chrome", R"Google\Chrome\User Data", 4)
    )
    all_profiles.extend(
        _detect_chromium_profiles("brave", R"BraveSoftware\Brave-Browser\User Data", 6)
    )
    return all_profiles


def is_firefox_installed() -> bool:
    """Firefox yürütülebilir dosyasının PATH'de veya bilinen konumlarda olup olmadığını kontrol eder."""
    if shutil.which("firefox") is not None:
        return True
    candidate_paths = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
        / "Mozilla Firefox"
        / "firefox.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))
        / "Mozilla Firefox"
        / "firefox.exe",
        Path.home() / "AppData" / "Local" / "Mozilla Firefox" / "firefox.exe",
    ]
    return any(p.exists() for p in candidate_paths)


def is_firefox_has_instagram_session() -> bool:
    """Firefox profillerinde Instagram oturumuna işaret eden çerez dosyası olup olmadığını kontrol eder."""
    profiles = _detect_firefox_profiles()
    if not profiles:
        return False
    for profile in profiles:
        if profile.profile_path is None:
            continue
        cookies_db = profile.profile_path / "cookies.sqlite"
        if cookies_db.exists() and cookies_db.stat().st_size > 4096:
            return True
    return False


def validate_cookie_file(file_path: str | Path | None) -> tuple[bool, str]:
    """Netscape HTTP Cookie File formatını doğrular."""
    if not file_path:
        return False, "Çerez dosyası yolu belirtilmedi."
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return False, "Belirtilen çerez dosyası bulunamadı."
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(30):
                line = f.readline()
                if not line:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith(
                    ("# HTTP Cookie File", "# Netscape HTTP Cookie File")
                ):
                    return True, ""
                if "\t" in stripped and len(stripped.split("\t")) >= 7:
                    return True, ""
                if stripped.startswith("#"):
                    continue
                return False, "Seçilen dosya Netscape çerez dosyası biçiminde değil."
    except Exception as exc:  # noqa: BLE001
        return False, f"Çerez dosyası okunamadı: {exc}"
    return False, "Seçilen dosya Netscape çerez dosyası biçiminde değil."


def build_profile_attempt_order(
    platform_type: PlatformType, requested_mode: str | Any | None
) -> list[tuple[str | None, str | None, str]]:
    """
    Geri dönen liste öğeleri: (browser_name, profile_name, display_name)
    (None, None, 'Oturumsuz') unauthenticated denemedir.
    (browser_name, None, display_name) profil belirtmeksizin tarayıcı çerezlerini kullanır;
    yt-dlp'nin CLI --cookies-from-browser BROWSER davranışına eşdeğerdir.
    """
    mode_str = str(
        requested_mode.value
        if hasattr(requested_mode, "value")
        else requested_mode or ""
    ).lower()

    if mode_str in ("cookie_file", "cookiefile"):
        return []

    if mode_str in ("none", "disabled", "off"):
        return [(None, None, "Oturumsuz")]

    all_profiles = detect_available_browser_profiles()
    seen_profiles: set[tuple[str | None, str | None]] = set()

    if mode_str and mode_str != "auto":
        attempts: list[tuple[str | None, str | None, str]] = []
        b_label = "Edge" if mode_str == "edge" else mode_str.capitalize()
        # Profilesiz varsayılan deneme (CLI --cookies-from-browser BROWSER ile aynı)
        key_profileless = (mode_str, None)
        if key_profileless not in seen_profiles:
            seen_profiles.add(key_profileless)
            attempts.append((mode_str, None, f"{b_label} (varsayılan profil)"))
        # Tespit edilen özel profiller fallback olarak eklenir
        for p in [p for p in all_profiles if p.browser == mode_str]:
            key = (p.browser, p.profile_name)
            if key not in seen_profiles:
                seen_profiles.add(key)
                attempts.append((p.browser, p.profile_name, p.display_name))
        return attempts

    # Auto modu:
    # 1. Oturumsuz deneme ilk sırada
    order: list[tuple[str | None, str | None, str]] = [(None, None, "Oturumsuz")]
    seen_profiles.add((None, None))

    if (
        platform_type
        in (
            PlatformType.INSTAGRAM_REEL,
            PlatformType.INSTAGRAM_POST,
            PlatformType.INSTAGRAM_STORY,
            PlatformType.INSTAGRAM_HIGHLIGHT,
            PlatformType.TIKTOK_VIDEO,
            PlatformType.TIKTOK_SHORT_LINK,
            PlatformType.TIKTOK_PROFILE,
            PlatformType.TIKTOK_LIVE,
            PlatformType.TIKTOK_SLIDESHOW,
            PlatformType.FACEBOOK_VIDEO,
            PlatformType.FACEBOOK_REEL,
            PlatformType.THREADS,
        )
        or platform_type == PlatformType.TWITTER_POST
    ):
        browser_priority = ["firefox", "edge", "chrome", "brave"]
    elif platform_type in (PlatformType.YOUTUBE_VIDEO, PlatformType.YOUTUBE_PLAYLIST):
        browser_priority = ["edge", "firefox", "chrome", "brave"]
    else:
        browser_priority = ["firefox", "edge", "chrome", "brave"]

    for b in browser_priority:
        b_profiles = [p for p in all_profiles if p.browser == b]
        b_label = "Edge" if b == "edge" else b.capitalize()

        # Firefox için profil-belirsiz varsayılan girişi kaldır. Doğrudan listelenen gerçek profiller kullanılır.
        # Sadece liste tamamen boşsa profil-belirsiz eklenebilir.
        if b == "firefox" and not b_profiles:
            key_profileless = ("firefox", None)
            if key_profileless not in seen_profiles:
                seen_profiles.add(key_profileless)
                order.append(("firefox", None, "Firefox (varsayılan profil)"))

        # Tespit edilen profiller eklenir
        for p in b_profiles:
            key = (p.browser, p.profile_name)
            if key not in seen_profiles:
                seen_profiles.add(key)
                order.append((p.browser, p.profile_name, p.display_name))

    return order


def is_chromium_encryption_error(message: str) -> bool:
    """Windows DPAPI / app-bound encryption kaynaklı çerez okuma hatası mı?"""
    if not message:
        return False
    msg_lower = str(message).lower()
    encryption_terms = (
        "failed to decrypt cookie",
        "dpapi",
        "app-bound encryption",
        "cookies could not be decrypted",
        "no cookies could be loaded",
        "could not decrypt",
        "decryption failed",
    )
    return any(term in msg_lower for term in encryption_terms)


def is_browser_cookie_lock_error(message: str) -> bool:
    if not message:
        return False
    msg_lower = str(message).lower()
    lock_terms = (
        "could not copy chrome cookie database",
        "could not copy edge cookie database",
        "could not copy brave cookie database",
        "could not copy",
        "database is locked",
        "permission denied",
        "cookie database",
        "sqlite3.operationalerror",
        "winerror 32",
        "being used by another process",
        "başka bir işlem tarafından",
    )
    return any(term in msg_lower for term in lock_terms)


def is_authentication_error(message: str) -> bool:
    if not message:
        return False
    msg_lower = str(message).lower()
    if is_rehydration_error(message):
        return False
    auth_terms = (
        "login required",
        "log in",
        "sign in",
        "authentication required",
        "age restricted",
        "protected account",
        "private content",
        "cookies required",
        "confirm you're not a bot",
        "story requires authentication",
        "require login",
        "korumalı bir hesaba ait",
        "oturum gerekiyor",
        "oturum isteyebilir",
        "oturum gerekebilir",
        "tarayıcı oturumu",
        "private account",
        "private post",
        "this post only contains photos",
        "you need to log in to access this content",
    )
    return any(term in msg_lower for term in auth_terms)


SESSION_STATUS_LABELS = {
    "profile_not_found": "Profil bulunamadı",
    "no_instagram_session": "Instagram oturumu yok",
    "encrypted_cookies": "Çerezler Windows tarafından şifrelenmiş",
    "db_locked": "Veritabanı kilitli",
    "story_inaccessible": "Hikâye erişilemiyor",
    "session_validated": "Oturum doğrulandı",
}


def classify_session_error(message: str, url: str) -> str:
    msg_lower = str(message).lower()

    if is_rehydration_error(message):
        return "TikTok video verisi çıkarılamadı (rehydration)"

    if is_chromium_encryption_error(message):
        return SESSION_STATUS_LABELS["encrypted_cookies"]

    if is_browser_cookie_lock_error(message):
        return SESSION_STATUS_LABELS["db_locked"]

    if any(
        t in msg_lower
        for t in ("expired", "not available", "404", "does not exist", "unavailable")
    ):
        return SESSION_STATUS_LABELS["story_inaccessible"]

    if any(t in msg_lower for t in ("rate limit", "429", "too many requests")):
        if "tiktok" in url.lower():
            return "TikTok oran sınırlaması"
        return "Instagram oran sınırlaması"

    if any(
        t in msg_lower
        for t in ("file not found", "no such file", "could not find", "cannot read")
    ):
        return SESSION_STATUS_LABELS["profile_not_found"]

    if is_authentication_error(message):
        if "facebook" in url.lower() or "fb.watch" in url.lower():
            return "Facebook oturumu bulunamadı"
        if "instagram" in url.lower():
            return SESSION_STATUS_LABELS["no_instagram_session"]
        if "twitter" in url.lower() or "x.com" in url.lower():
            return "X oturumu bulunamadı"
        if "tiktok" in url.lower():
            return "TikTok oturumu bulunamadı"
        return "Tarayıcı oturumu bulunamadı"

    return "Bilinmeyen çıkarıcı hatası"


def analyze_instagram_story_url(url: str) -> tuple[str | None, str | None]:
    """
    Instagram hikaye URL'lerini analiz eder.
    Returns: (notice_text, error_text)
    """
    raw = url.strip().lower()
    if "instagram.com/stories/highlights" in raw:
        after = raw.split("instagram.com/stories/highlights")[1].strip("/")
        if not after:
            return (
                None,
                "Instagram Öne Çıkarılanlar bağlantısında içerik kimliği eksik. Lütfen geçerli bir öne çıkan hikâye bağlantısı girin.",
            )
        return "Öne çıkarılan hikâye bağlantısı algılandı.", None

    if "instagram.com/stories/" in raw:
        after = raw.split("instagram.com/stories/")[1].strip("/")
        parts = [p for p in after.split("/") if p]
        if len(parts) == 1:
            return (
                (
                    "Bu bağlantı hesabın tüm aktif hikâyelerini hedefliyor. "
                    "Tek bir hikâye için sayısal hikâye kimliği içeren paylaşım bağlantısını kullanın."
                ),
                None,
            )
        if len(parts) >= 2:
            return "Belirli bir hikâye bağlantısı algılandı.", None

    return None, None


def analyze_tiktok_url(url: str) -> tuple[str | None, str | None]:
    """
    TikTok URL'lerini analiz eder.
    Returns: (notice_text, error_text)
    """
    raw = url.strip().lower()
    if "tiktok.com" not in raw:
        return None, None

    if "vm.tiktok.com" in raw or "vt.tiktok.com" in raw:
        return "TikTok kısa bağlantısı çözümleniyor…", None

    if "/live" in raw or "live.tiktok.com" in raw:
        return None, "TikTok canlı yayın indirme desteği henüz eklenmedi."

    if re.search(r"tiktok\.com/@[^/]+/?(?:\?.*)?$", raw):
        return (
            None,
            "TikTok profil bağlantısı algılandı. Toplu profil indirme desteği henüz etkin değil. Tek bir videonun paylaşım bağlantısını kullanın.",
        )

    return None, None


def analyze_kick_url(url: str) -> tuple[str | None, str | None]:
    """
    Kick URL'lerini analiz eder.
    Returns: (notice_text, error_text)
    """
    raw = url.strip().lower()
    if "kick.com" not in raw:
        return None, None

    if "/clips/" in raw or "clip=" in raw:
        return (
            None,
            "Kick klipleri henüz desteklenmiyor. Yalnızca tamamlanmış Kick VOD videoları destekleniyor.",
        )

    if re.search(r"kick\.com/[^/]+/videos/?(?:\?.*)?$", raw):
        return (
            None,
            "Kick kanal videoları listesi desteklenmiyor. Lütfen indirmek istediğiniz tekil VOD videosunun bağlantısını yapıştırın.",
        )

    if "/videos/" not in raw or "/live" in raw:
        return None, "Kick canlı yayınları henüz desteklenmiyor."

    match = re.search(r"kick\.com/([^/]+)/videos/([a-f0-9\-]{8,})", raw)
    if not match:
        return None, "Geçersiz Kick video bağlantısı veya UUID."

    return "Kick VOD videosu algılandı.", None
