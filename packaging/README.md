# Loadvia Packaging & Release Infrastructure

Bu klasör, Loadvia 1.0.0 Windows x64 PyInstaller paketleme ve Windows executable yapılandırma dosyalarını içerir.

## Yapı

- `Loadvia.spec`: PyInstaller 6.x uyumlu, `onedir`, `windowed` Windows x64 build yapılandırması.
- `version_info.txt`: Windows PE metadata (CompanyName, FileDescription, FileVersion 1.0.0.0, ProductName, ProductVersion).
- `README.md`: Paketleme dokümantasyonu.

## Çıktı Mimarisi

- Mode: `onedir` (Klasör halinde taşınabilir paket)
- Windowed: `console=False`
- Hedef Dizin: `dist/Loadvia/`
- Executable: `dist/Loadvia/Loadvia.exe`
- Assetler: `dist/Loadvia/assets/Loadvia-Brand-Assets/`
- Harici Araçlar: `dist/Loadvia/tools/` (`ffmpeg.exe`, `ffprobe.exe`, `deno.exe`)

## DerlemeKomutları

```powershell
.\scripts\build_windows.ps1 -Clean
```
