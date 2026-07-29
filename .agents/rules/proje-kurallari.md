---
activation: always_on
---

# Kolayİndir Proje Kuralları

- Kullanıcıya yapılan açıklamalar Türkçe olacak.
- Tüm Git commit mesajları Türkçe ve açıklayıcı olacak.
- Her commit tek bir mantıksal değişiklik içerecek.
- Kod Python 3.12 ile uyumlu tutulacak.
- Arayüz PySide6 ile geliştirilecek.
- İndirme motoru yeniden yazılmayacak; yt-dlp bir adaptör üzerinden kullanılacak.
- Ağ ve indirme işlemleri ana arayüz iş parçacığını bloke etmeyecek.
- Çerezler, parolalar, erişim anahtarları ve kişisel indirme geçmişi Git'e eklenmeyecek.
- DRM veya erişim kontrolü aşmaya yönelik özellik eklenmeyecek.
- Hata mesajları anlaşılır Türkçe olacak.
- Kod değişikliğinden sonra `python -m compileall app.py src` ve `pytest` çalıştırılacak.
