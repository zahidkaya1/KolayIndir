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
- Küçük ve orta ölçekli hata düzeltmeleri, arayüz düzenlemeleri, test eklemeleri ve yerel kod iyileştirmelerinde `implementation_plan.md` hazırlama ve kullanıcı onayı bekleme. Doğrudan incele, uygula, kontrolleri çalıştır ve sonuç raporla.
- Yalnızca büyük mimari değişiklikler, yeni teknoloji/bağımlılık ekleme, dosya/veri silme, güvenlik/kimlik doğrulama değişiklikleri, veritabanı şema değişiklikleri, Git geçmişini değiştiren işlemler, release/dağıtım işlemleri veya kullanıcının açıkça "önce plan hazırla" dediği durumlarda uygulamadan önce plan ve onay iste.
- Kullanıcı açıkça istemedikçe git commit veya git push yapma.
- Görev açık ve uygulanabilir durumdaysa ek onay sorusu sorma.
- Değişiklik sırasında beklenmeyen kritik bir risk ortaya çıkarsa durup kullanıcıya bildir.
- Kod değişikliğinden sonra `python -m compileall app.py src`, `pytest` ve `ruff check` çalıştırılacak.

