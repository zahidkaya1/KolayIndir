"""Loadvia PyInstaller ve Windows paketleme testleri."""

from __future__ import annotations

import os
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
    assert "1.0.0.0" in version_content


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


def test_external_tool_resolution():
    tool_path = get_external_tool_path("ffmpeg")
    assert tool_path is not None
    assert Path(tool_path).exists()


def test_setup_environment_paths_in_memory_only():
    old_path = os.environ.get("PATH", "")
    setup_environment_paths()
    new_path = os.environ.get("PATH", "")

    # PATH should not be empty
    assert len(new_path) >= len(old_path)
