"""Kolayİndir metin ve log yardımcı fonksiyonları."""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QComboBox

_ANSI_REGEX = re.compile(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]")


from PySide6.QtWidgets import QSizePolicy

_ANSI_REGEX = re.compile(r"(?:\x1b|\033)\[[0-?]*[ -/]*[@-~]")


def configure_combo_box(combo: QComboBox) -> None:
    """QComboBox ve açılır menüsünün QPalette renklerini ve yükseklik ayarlarını açık temaya sabitler."""
    combo.setEditable(False)
    combo.setMinimumHeight(40)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    palette = combo.palette()

    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.WindowText, QColor("#172033"))
        palette.setColor(group, QPalette.ColorRole.Text, QColor("#172033"))
        palette.setColor(group, QPalette.ColorRole.ButtonText, QColor("#172033"))
        palette.setColor(group, QPalette.ColorRole.Base, QColor("#FFFFFF"))
        palette.setColor(group, QPalette.ColorRole.Window, QColor("#FFFFFF"))
        palette.setColor(group, QPalette.ColorRole.Button, QColor("#FFFFFF"))
        palette.setColor(
            group, QPalette.ColorRole.AlternateBase, QColor("#FFFFFF")
        )
        palette.setColor(group, QPalette.ColorRole.Highlight, QColor("#E8F0FE"))
        palette.setColor(
            group, QPalette.ColorRole.HighlightedText, QColor("#174EA6")
        )

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor("#667085"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#667085")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#667085"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor("#F2F4F7")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, QColor("#F2F4F7")
    )

    combo.setPalette(palette)
    view = combo.view()
    if view:
        view.setPalette(palette)
        view.setMinimumWidth(max(combo.width(), 180))


def set_combo_value(combo: QComboBox, value: str) -> None:
    """QComboBox içinde verilen metni arar; bulunursa seçer, bulunamazsa index 0 seçer."""
    index = combo.findText(value)
    combo.setCurrentIndex(max(index, 0))



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
