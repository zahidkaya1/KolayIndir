"""Loadvia marka entegrasyonu ve kaynak yönetimi testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from src.config import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_USER_AGENT,
    APP_VERSION,
    GITHUB_OWNER,
    GITHUB_REPO,
    HTTP_USER_AGENT,
)
from src.main_window import MainWindow
from src.queue_dialog import DownloadQueueDialog
from src.settings import get_default_download_dir, load_settings
from src.utils import get_brand_asset_path, get_resource_path


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_branding_constants():
    assert APP_NAME == "Loadvia"
    assert APP_VERSION == "1.0.0"
    assert APP_DESCRIPTION == "Hızlı, Kolay ve Yüksek Kaliteli Medya İndirici"
    assert APP_USER_AGENT == "Loadvia/1.0.0"
    assert HTTP_USER_AGENT == "Loadvia/1.0.0"
    assert GITHUB_OWNER == "zahidkaya1"
    assert GITHUB_REPO == "KolayIndir"


def test_main_window_branding_title_and_icon(qapp, monkeypatch):
    monkeypatch.setattr(MainWindow, "_show_dependency_status", lambda self: None)
    win = MainWindow()
    assert win.windowTitle() == "Loadvia 1.0.0"
    assert not win.windowIcon().isNull()
    win.close()
    win.deleteLater()


def test_queue_dialog_branding_title(qapp):
    dlg = DownloadQueueDialog()
    assert "Loadvia" in dlg.windowTitle()
    assert dlg.windowTitle() == "Loadvia — İndirme Kuyruğu"
    dlg.close()


def test_brand_assets_exist_and_loadable():
    ico_path = get_brand_asset_path("loadvia.ico")
    symbol_path = get_brand_asset_path("loadvia-symbol.png")

    assert ico_path.exists()
    assert symbol_path.exists()

    icon = QIcon(str(ico_path))
    assert not icon.isNull()

    pixmap = QPixmap(str(symbol_path))
    assert not pixmap.isNull()


def test_resource_path_helper_normal_and_meipass(tmp_path, monkeypatch):
    # Normal dev environment test
    res_path = get_resource_path(Path("assets") / "Loadvia-Brand-Assets" / "loadvia.ico")
    assert res_path.exists()

    # sys._MEIPASS test
    meipass_dir = tmp_path / "meipass"
    asset_dir = meipass_dir / "assets" / "Loadvia-Brand-Assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    fake_asset = asset_dir / "test_asset.txt"
    fake_asset.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)
    resolved = get_resource_path(Path("assets") / "Loadvia-Brand-Assets" / "test_asset.txt")
    assert resolved == fake_asset
    assert resolved.read_text(encoding="utf-8") == "ok"


def test_missing_icon_does_not_crash():
    missing_path = get_brand_asset_path("non_existent_file.ico")
    assert not missing_path.exists()

    icon = QIcon(str(missing_path))
    assert icon.isNull()


def test_download_directory_settings_and_compatibility(tmp_path, monkeypatch):
    import json

    # Test new installation default
    default_dir = get_default_download_dir()
    assert default_dir == str(Path.home() / "Downloads" / "Loadvia")

    # Test custom settings preservation
    custom_dir = str(tmp_path / "CustomDownloads")
    Path(custom_dir).mkdir(parents=True, exist_ok=True)
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"output_dir": custom_dir}), encoding="utf-8")

    monkeypatch.setattr("src.settings.SETTINGS_FILE", settings_file)
    loaded = load_settings()
    assert loaded["output_dir"] == custom_dir


def test_readme_main_heading():
    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    assert content.startswith("# Loadvia")
