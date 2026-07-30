"""Pytest fixtures for Kolayİndir unit tests."""

import pytest
from PySide6.QtWidgets import QApplication

from src.main_window import MainWindow


@pytest.fixture
def main_window(qapp, monkeypatch):
    """Safely creates and tears down a MainWindow instance without leaving dangling threads."""
    monkeypatch.setattr(MainWindow, "_start_history_validation", lambda self: None)
    window = MainWindow()
    yield window

    window._stop_all_threads()
    window.close()
    QApplication.processEvents()
