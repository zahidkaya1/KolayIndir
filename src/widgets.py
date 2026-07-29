"""Özel arayüz widget bileşenleri."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class OptionCard(QFrame):
    """Tıklanabilir ve görsel durumu değişen modern ayar kartı."""

    def __init__(
        self,
        checkbox: QCheckBox,
        description: str = "",
        object_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.checkbox = checkbox
        if object_name:
            self.setObjectName(object_name)
        self.setProperty("optionCard", "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.addWidget(self.checkbox)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("cardDescriptionLabel")
            desc_label.setStyleSheet("color: #64748b; font-size: 12px;")
            text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self.checkbox.installEventFilter(self)
        self.checkbox.toggled.connect(self._update_checked_state)
        self._update_checked_state(self.checkbox.isChecked())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.checkbox.toggle()
        super().mousePressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched == self.checkbox
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.checkbox.toggle()
            return True
        return super().eventFilter(watched, event)


    def _update_checked_state(self, checked: bool) -> None:
        self.setProperty("checked", "true" if checked else "false")
        self.style().unpolish(self)
        self.style().polish(self)
