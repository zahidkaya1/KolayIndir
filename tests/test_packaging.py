"""Loadvia PyInstaller ve Windows paketleme testleri."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from src.config import APP_VERSION
from src.utils import get_external_tool_path, setup_environment_paths


def test_spec_and_version_info_exist():
    project_root = Path(__file__).resolve().parent.parent
    spec_path = project_root / "packaging" / "Loadvia.spec"
    version_info_path = project_root / "packaging" / "version_info.txt"

    assert spec_path.exists()
    assert version_info_path.exists()

    spec_content = spec_path.read_text(encoding="utf-8")
    assert "Loadvia" in spec_content
    assert "console=False" in spec_content

    version_content = version_info_path.read_text(encoding="utf-8")
    assert APP_VERSION in version_content
    assert "1.1.1.1" in version_content


def test_build_scripts_exist():
    project_root = Path(__file__).resolve().parent.parent
    build_script = project_root / "scripts" / "build_windows.ps1"
    verify_script = project_root / "scripts" / "verify_windows_build.ps1"

    assert build_script.exists()
    assert verify_script.exists()

    build_content = build_script.read_text(encoding="utf-8")
    assert "ffmpeg" in build_content
    assert "ffprobe" in build_content
    assert "deno" in build_content

    verify_content = verify_script.read_text(encoding="utf-8")
    assert "Loadvia.exe" in verify_content


def test_gitignore_contains_packaging_outputs():
    project_root = Path(__file__).resolve().parent.parent
    gitignore_path = project_root / ".gitignore"

    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")

    assert "build/" in content
    assert "dist/" in content
    assert "release/" in content


def test_external_tool_resolution_from_tools_dir(tmp_path, monkeypatch):
    ext = ".exe" if sys.platform == "win32" else ""
    fake_tools_dir = tmp_path / "tools"
    fake_tools_dir.mkdir()
    fake_binary = fake_tools_dir / f"ffmpeg{ext}"
    fake_binary.write_text("fake binary content", encoding="utf-8")

    def mock_get_resource_path(rel_path):
        return tmp_path / rel_path

    monkeypatch.setattr("src.utils.get_resource_path", mock_get_resource_path)
    monkeypatch.setattr("sys.frozen", False, raising=False)

    resolved = get_external_tool_path("ffmpeg")
    assert resolved == str(fake_binary)
    assert Path(resolved).exists()


def test_external_tool_resolution_from_system_path(tmp_path, monkeypatch):
    def mock_get_resource_path(rel_path):
        return tmp_path / rel_path

    monkeypatch.setattr("src.utils.get_resource_path", mock_get_resource_path)
    monkeypatch.setattr("sys.frozen", False, raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: "/system/bin/ffmpeg.exe")

    resolved = get_external_tool_path("ffmpeg")
    assert resolved == "/system/bin/ffmpeg.exe"


def test_external_tool_resolution_not_found(tmp_path, monkeypatch):
    def mock_get_resource_path(rel_path):
        return tmp_path / rel_path

    monkeypatch.setattr("src.utils.get_resource_path", mock_get_resource_path)
    monkeypatch.setattr("sys.frozen", False, raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    resolved = get_external_tool_path("ffmpeg")
    assert resolved is None


def test_setup_environment_paths_in_memory_only():
    old_path = os.environ.get("PATH", "")
    setup_environment_paths()
    new_path = os.environ.get("PATH", "")

    # PATH should not be empty
    assert len(new_path) >= len(old_path)
