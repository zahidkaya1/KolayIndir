"""Kolayİndir metin ve log yardımcı fonksiyonları."""

from __future__ import annotations

import re

_ANSI_REGEX = re.compile(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    """Metindeki ANSI escape / terminal renk kodlarını temizler."""
    if not text:
        return ""
    return _ANSI_REGEX.sub("", text)


def clean_log_message(text: str) -> str:
    """Metindeki ANSI kodlarını temizler, iç içe geçmiş 'Hata: ERROR:' ön eklerini sadeleştirir ve boşlukları düzenler."""
    cleaned = strip_ansi(text).strip()
    if not cleaned:
        return ""

    pattern = r"^(?:Hata:\s*|ERROR:\s*|Uyarı:\s*|WARNING:\s*)+"
    match = re.match(pattern, cleaned, flags=re.IGNORECASE)
    if match:
        matched_str = match.group(0)
        rest = cleaned[match.end():].strip()
        is_error = "hata" in matched_str.lower() or "error" in matched_str.lower()
        is_warning = "uyarı" in matched_str.lower() or "warning" in matched_str.lower()
        if is_error:
            cleaned = f"Hata: {rest}" if rest else "Hata:"
        elif is_warning:
            cleaned = f"Uyarı: {rest}" if rest else "Uyarı:"

    return cleaned


def is_chrome_cookie_error(text: str) -> bool:
    """Log veya hata mesajında Chrome çerez erişim hatası olup olmadığını denetler."""
    if not text:
        return False
    cleaned = strip_ansi(text).lower()
    return "could not copy chrome cookie database" in cleaned
