# Loadvia

Loadvia; desteklenen web sayfalarındaki video ve ses içeriklerini, bağlantıyı
uygulamaya yapıştırarak indirmeyi amaçlayan hızlı, kolay ve yüksek kaliteli bir Windows masaüstü uygulamasıdır.

## İlk sürümde bulunanlar

- Tek bağlantıdan video indirme
- YouTube oynatma listesi seçeneği
- MP4 video veya MP3 ses seçimi
- En iyi kalite, 1080p, 720p ve 480p seçenekleri
- Chrome, Edge veya Firefox oturum çerezlerini isteğe bağlı kullanma
- İndirme ilerlemesi, hız, kalan süre ve işlem günlüğü
- Ayarlanabilir indirme hızı sınırı
- İndirme klasörünü hatırlama
- İndirmeyi iptal etme
- GitHub Releases üzerinden güncelleme kontrolü için temel altyapı
- Antigravity çalışma alanı kuralları
- GitHub Actions ile temel kod testi

## Kapsam sınırı

Uygulama internetteki her içeriği garanti ederek indiremez. Destek; sitenin yapısına,
erişim izinlerine ve yt-dlp çıkarıcılarına bağlıdır. Özel hesap içerikleri, silinmiş
paylaşımlar, coğrafi kısıtlamalar ve DRM ile korunan yayınlar indirilemeyebilir.

Uygulamayı yalnızca sahibi olduğunuz, açıkça indirme izniniz bulunan veya hukuken
indirme hakkınız olan içerikler için kullanın. Bu proje erişim kontrolünü veya DRM
korumasını aşmaya yönelik özellik içermez.

## Gereksinimler

- Windows 10 veya Windows 11
- Python 3.12
- FFmpeg
- Güncel Deno önerilir; güncel Node.js de kullanılabilir
- Git

## Kurulum

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Alternatif olarak `scripts\kurulum.bat`, ardından `scripts\calistir.bat`
dosyalarını çalıştırın.

## Ortam kontrolü

```powershell
python scripts\ortam_kontrol.py
```

## EXE oluşturma

```powershell
pip install -r requirements-dev.txt
scripts\build_exe.bat
```

İlk çıktı `dist\KolayIndir\KolayIndir.exe` altında oluşur. İlk aşamada klasörlü
`--onedir` derlemesi kullanılır; tek dosyalı sürüm daha sonra eklenebilir.

## GitHub'a ilk gönderim

Önce GitHub üzerinde `kolay-indir` adında boş ve README'siz bir depo oluşturun.

```powershell
git init
git add .
git commit -m "Masaüstü indirme uygulaması iskeleti oluşturuldu"
git branch -M main
git remote add origin https://github.com/zahidkaya1/kolay-indir.git
git push -u origin main
```

## Güncelleme altyapısı

`src/config.py` içinde GitHub kullanıcı ve depo adları tanımlıdır. Uygulamadaki
“Güncellemeyi kontrol et” düğmesi, son GitHub Release etiketini `APP_VERSION` ile
karşılaştırır. Ayrıntılı geliştirme sırası `docs/YOL_HARITASI.md` dosyasındadır.
