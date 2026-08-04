"""Loadvia Inno Setup ve Windows installer testleri."""

from __future__ import annotations

from pathlib import Path

from src.config import APP_VERSION


def test_iss_script_exists_and_valid():
    project_root = Path(__file__).resolve().parent.parent
    iss_path = project_root / "installer" / "Loadvia.iss"

    assert iss_path.exists()
    content = iss_path.read_text(encoding="utf-8")

    assert '#define MyAppName "Loadvia"' in content
    assert f'#define MyAppVersion "{APP_VERSION}"' in content
    assert 'AppId={{6411DE40-247B-45E7-9345-73DCCAF9DA69}' in content
    assert "OutputBaseFilename=Loadvia-Setup-1.1.0" in content
    assert r"SetupIconFile=..\assets\Loadvia-Brand-Assets\loadvia.ico" in content
    assert r"UninstallDisplayIcon={app}\{#MyAppExeName}" in content
    assert "ArchitecturesAllowed=x64compatible" in content
    assert r"DefaultDirName={autopf}\Loadvia" in content
    assert "PrivilegesRequired=lowest" in content
    assert "PrivilegesRequiredOverridesAllowed=dialog" in content
    assert r'Source: "..\dist\Loadvia\*"' in content
    assert "recursesubdirs" in content
    assert r'Name: "{group}\{#MyAppName}"' in content
    assert 'Name: "desktopicon"' in content
    assert "Flags: unchecked" in content
    assert "skipifsilent" in content
    assert "[UninstallDelete]" not in content


def test_installer_scripts_exist():
    project_root = Path(__file__).resolve().parent.parent
    build_script = project_root / "scripts" / "build_installer.ps1"
    verify_script = project_root / "scripts" / "verify_installer.ps1"
    readme_file = project_root / "installer" / "README.md"

    assert build_script.exists()
    assert verify_script.exists()
    assert readme_file.exists()

    build_content = build_script.read_text(encoding="utf-8")
    assert "Loadvia.iss" in build_content
    assert "ISCC" in build_content

    verify_content = verify_script.read_text(encoding="utf-8")
    assert "Loadvia-Setup-1.1.0.exe" in verify_content
    assert "6411DE40-247B-45E7-9345-73DCCAF9DA69" in verify_content


def test_gitignore_contains_setup_exe():
    project_root = Path(__file__).resolve().parent.parent
    gitignore_path = project_root / ".gitignore"

    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")

    assert "release/*.exe" in content or "release/" in content
