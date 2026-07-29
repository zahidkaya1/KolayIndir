"""Geliştirme ortamındaki temel bağımlılıkları kontrol eder."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys


def command_version(command: str, argument: str = "--version") -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, argument], capture_output=True, text=True, check=False, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return "bulundu, sürüm okunamadı"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else "bulundu"


def main() -> int:
    print("Kolayİndir ortam kontrolü")
    print("=" * 32)
    print(f"İşletim sistemi : {platform.platform()}")
    print(f"Python          : {sys.version.split()[0]}")
    checks = {
        "Git": command_version("git"),
        "FFmpeg": command_version("ffmpeg"),
        "Deno": command_version("deno"),
        "Node.js": command_version("node"),
    }
    for name, value in checks.items():
        print(f"{name:<15} : {value or 'BULUNAMADI'}")
    print()
    if checks["Git"] is None or checks["FFmpeg"] is None:
        print("Eksik temel araçlar var. Git ve FFmpeg kurulmalıdır.")
    if checks["Deno"] is None and checks["Node.js"] is None:
        print("Deno veya Node.js bulunamadı. YouTube desteği sınırlı kalabilir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
