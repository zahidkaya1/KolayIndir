# Loadvia Windows Installer (Inno Setup)

Bu klasör, Loadvia 1.1.1 Windows x64 Inno Setup kurulum altyapısını içerir.

## Dosya Mimarisi

- `Loadvia.iss`: Inno Setup 6.x / 7.x uyumlu kurulum betiği.
- `README.md`: Kurulum dokümantasyonu.

## Konfigürasyon ve Sabitler

- **AppId:** `{6411DE40-247B-45E7-9345-73DCCAF9DA69}` (Gelecek tüm 1.x / 2.x güncellemelerinde sabit kalmalıdır).
- **Kurulum Kapsamı:** `PrivilegesRequired=lowest`, `PrivilegesRequiredOverridesAllowed=dialog` (Varsayılan: Mevcut kullanıcı; İsteğe bağlı: Tüm kullanıcılar / UAC).
- **Varsayılan Kurulum Dizin:** `{autopf}\Loadvia` (C:\Program Files\Loadvia veya %LocalAppData%\Programs\Loadvia).
- **Kaynak Dizin:** `dist/Loadvia/` (Önce `scripts/build_windows.ps1` veya portable build hazırlanmış olmalıdır).
- **Çıktı:** `release/Loadvia-Setup-1.1.1.exe`

## Derleme Komutu

```powershell
.\scripts\build_installer.ps1 -Clean
```

## Kod İmzalama Notu

Installer şu anda **imzasızdır (unsigned)**. Windows Defender / SmartScreen uyarısı imzasız exe sebebiyle görünebilir.

## Kaldırma ve Veri Güvenliği

Kurulum kaldırıldığında (`uninstall`), kullanıcının indirdiği medyalar, geçmiş kaydı (`history.json`) ve uygulama ayarları (`settings.json`) **kesinlikle silinmez, korunur**.
