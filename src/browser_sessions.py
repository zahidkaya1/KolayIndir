"""Tarayıcı profil tespiti, sıralama ve oturum hata yönetimi yardımcı modülü."""

from __future__ import annotations

import configparser
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.models import PlatformType


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
                for section in config.sections():
                    if section.lower().startswith("profile"):
                        name = config.get(section, "Name", fallback="")
                        rel_path = config.get(section, "Path", fallback="")
                        is_rel = config.get(section, "IsRelative", fallback="1") == "1"
                        if rel_path:
                            full_path = (base / rel_path) if is_rel else Path(rel_path)
                            p_name = name or full_path.name
                            if full_path.exists():
                                profiles.append(
                                    BrowserProfileCandidate(
                                        browser="firefox",
                                        profile_name=full_path.name,
                                        profile_path=full_path,
                                        display_name=f"Firefox ({p_name})",
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
    all_profiles.extend(_detect_chromium_profiles("edge", R"Microsoft\Edge\User Data", 2))
    all_profiles.extend(_detect_chromium_profiles("chrome", R"Google\Chrome\User Data", 4))
    all_profiles.extend(_detect_chromium_profiles("brave", R"BraveSoftware\Brave-Browser\User Data", 6))
    return all_profiles


def is_firefox_installed() -> bool:
    """Firefox yürütülebilir dosyasının PATH'de veya bilinen konumlarda olup olmadığını kontrol eder."""
    if shutil.which("firefox") is not None:
        return True
    candidate_paths = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Mozilla Firefox" / "firefox.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Mozilla Firefox" / "firefox.exe",
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


def build_profile_attempt_order(
    platform_type: PlatformType, requested_mode: str | None
) -> list[tuple[str | None, str | None, str]]:
    """
    Geri dönen liste öğeleri: (browser_name, profile_name, display_name)
    (None, None, 'Oturumsuz') unauthenticated denemedir.
    (browser_name, None, display_name) profil belirtmeksizin tarayıcı çerezlerini kullanır;
    yt-dlp'nin CLI --cookies-from-browser BROWSER davranışına eşdeğerdir.
    """
    if requested_mode and requested_mode in ("none", "disabled", "off"):
        return [(None, None, "Oturumsuz")]

    all_profiles = detect_available_browser_profiles()
    seen_profiles: set[tuple[str | None, str | None]] = set()

    if requested_mode and requested_mode != "auto":
        attempts: list[tuple[str | None, str | None, str]] = []
        b_label = "Edge" if requested_mode == "edge" else requested_mode.capitalize()
        # Profilesiz varsayılan deneme (CLI --cookies-from-browser BROWSER ile aynı)
        key_profileless = (requested_mode, None)
        if key_profileless not in seen_profiles:
            seen_profiles.add(key_profileless)
            attempts.append((requested_mode, None, f"{b_label} (varsayılan profil)"))
        # Tespit edilen özel profiller fallback olarak eklenir
        for p in [p for p in all_profiles if p.browser == requested_mode]:
            key = (p.browser, p.profile_name)
            if key not in seen_profiles:
                seen_profiles.add(key)
                attempts.append((p.browser, p.profile_name, p.display_name))
        return attempts

    # Auto modu:
    # 1. Oturumsuz deneme ilk sırada
    order: list[tuple[str | None, str | None, str]] = [(None, None, "Oturumsuz")]
    seen_profiles.add((None, None))

    if platform_type in (
        PlatformType.INSTAGRAM_REEL,
        PlatformType.INSTAGRAM_POST,
        PlatformType.INSTAGRAM_STORY,
        PlatformType.INSTAGRAM_HIGHLIGHT,
    ) or platform_type == PlatformType.TWITTER_POST:
        browser_priority = ["firefox", "edge", "chrome", "brave"]
    elif platform_type in (PlatformType.YOUTUBE_VIDEO, PlatformType.YOUTUBE_PLAYLIST):
        browser_priority = ["edge", "firefox", "chrome", "brave"]
    else:
        browser_priority = ["firefox", "edge", "chrome", "brave"]

    for b in browser_priority:
        b_profiles = [p for p in all_profiles if p.browser == b]
        b_label = "Edge" if b == "edge" else b.capitalize()

        # Firefox için profil-belirsiz varsayılan giriş ilk sırada (CLI --cookies-from-browser firefox)
        if b == "firefox":
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
        "database is locked",
        "permission denied",
        "cookie database",
        "sqlite3.operationalerror",
    )
    return any(term in msg_lower for term in lock_terms)


def is_authentication_error(message: str) -> bool:
    if not message:
        return False
    msg_lower = str(message).lower()
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
        "private account",
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

    if is_chromium_encryption_error(message):
        return SESSION_STATUS_LABELS["encrypted_cookies"]

    if is_browser_cookie_lock_error(message):
        return SESSION_STATUS_LABELS["db_locked"]

    if any(t in msg_lower for t in ("expired", "not available", "404", "does not exist", "unavailable")):
        return SESSION_STATUS_LABELS["story_inaccessible"]

    if any(t in msg_lower for t in ("rate limit", "429", "too many requests")):
        return "Instagram oran sınırlaması"

    if any(t in msg_lower for t in ("file not found", "no such file", "could not find", "cannot read")):
        return SESSION_STATUS_LABELS["profile_not_found"]

    if is_authentication_error(message):
        if "instagram" in url.lower():
            return SESSION_STATUS_LABELS["no_instagram_session"]
        if "twitter" in url.lower() or "x.com" in url.lower():
            return "X oturumu bulunamadı"
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
