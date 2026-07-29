"""Çalışma zamanı bağımlılıklarını denetler."""

import shutil


def dependency_warnings() -> list[str]:
    warnings: list[str] = []
    if not shutil.which("ffmpeg"):
        warnings.append(
            "FFmpeg bulunamadı. MP3 dönüştürme ve ses/video birleştirme çalışmayabilir."
        )
    if not shutil.which("deno") and not shutil.which("node"):
        warnings.append(
            "Deno veya Node.js bulunamadı. Bazı YouTube formatları sınırlı olabilir."
        )
    return warnings
