# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

project_dir = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (
        os.path.join(project_dir, "assets", "Loadvia-Brand-Assets"),
        os.path.join("assets", "Loadvia-Brand-Assets"),
    ),
]

# Certifi ve curl_cffi veri dosyaları
try:
    datas += collect_data_files("certifi")
except Exception:
    pass

try:
    datas += collect_data_files("curl_cffi")
except Exception:
    pass

hiddenimports = [
    "certifi",
    "charset_normalizer",
    "urllib3",
    "requests",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

hiddenimports += collect_submodules("yt_dlp")
try:
    hiddenimports += collect_submodules("curl_cffi")
except Exception:
    pass

a = Analysis(
    [os.path.join(project_dir, "app.py")],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Loadvia",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, "assets", "Loadvia-Brand-Assets", "loadvia.ico"),
    version=os.path.join(project_dir, "packaging", "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Loadvia",
)
