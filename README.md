# Loadvia

Loadvia; desteklenen web sayfalarındaki video ve ses içeriklerini, bağlantıyı uygulamaya yapıştırarak indirmeyi amaçlayan hızlı, kolay ve yüksek kaliteli bir Windows masaüstü uygulamasıdır.

## Özellikler

- YouTube video ve oynatma listesi indirme
- Instagram gönderi ve hikâye desteği
- X / Twitter video desteği
- TikTok video desteği
- Facebook video ve Reels desteği
- Threads video desteği (Threads gönderileri platform kısıtlamaları nedeniyle tarayıcı oturumu gerektirebilir. Bazı Threads gönderilerinde indirme kuyruğu kullanılamayabilir. Böyle durumlarda bağlantıyı doğrudan inceleyip indirin.)
- MP4 video ve MP3 ses indirme
- İndirme kuyruğu
- İndirme hızı sınırı
- İndirme geçmişi
- Pano bağlantısı algılama
- Açık/koyu tema
- Portable kullanım
- Windows installer
- Otomatik güncelleme kontrolü

## Tarayıcı Oturumu Seçenekleri

Bazı içeriklerin indirilebilmesi için ilgili platformda oturum açılmış bir tarayıcı bilgisine ihtiyaç duyulabilir.

Loadvia hesap parolanızı istemez. Tarayıcı oturum bilgileri yalnız içerik inceleme ve indirme işlemlerinde kullanılır. Çerez dosyaları hesap oturum bilgileri içerebilir; bu dosyaları kimseyle paylaşmayın.

Desteklenen oturum yöntemleri:
- Otomatik (Önerilen)
- Oturumsuz
- Firefox
- Microsoft Edge
- Chrome
- Brave
- Netscape çerez dosyası

**Windows Chromium Uyarısı:**
Windows güvenlik kısıtlamaları nedeniyle Chrome, Edge veya Brave oturum bilgileri bazı sistemlerde okunamayabilir. Böyle durumlarda Firefox veya kullanıcının kendi Netscape çerez dosyası kullanılabilir.

## Kapsam Sınırı

Uygulama internetteki her içeriği garanti ederek indiremez. Destek; sitenin yapısına, erişim izinlerine ve yt-dlp çıkarıcılarına bağlıdır. Özel hesap içerikleri, silinmiş paylaşımlar, coğrafi kısıtlamalar ve DRM ile korunan yayınlar indirilemeyebilir.

Uygulamayı yalnızca sahibi olduğunuz, açıkça indirme izniniz bulunan veya hukuken indirme hakkınız olan içerikler için kullanın. Bu proje erişim kontrolünü veya DRM korumasını aşmaya yönelik özellik içermez.

## Paketler

Uygulamayı iki şekilde kullanabilirsiniz:
- Kurulumlu (Installer): `Loadvia-Setup-1.1.0.exe`
- Taşınabilir (Portable): `Loadvia-1.1.0-windows-x64-portable.zip`

## Gelecek Geliştirmeler

- Kick video desteği
- Threads kuyruk format seçimi iyileştirmesi

## Gereksinimler

- Windows 10 veya Windows 11

## Kurulum (Geliştirici)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```
