"""Threads /share/ bağlantılarını canonical post URL'lerine çözümleyen yardımcı modül."""

import re
import urllib.parse

from curl_cffi import requests as cffi_requests

from src.session_manager import SessionManager

_RESOLVED_CACHE: dict[str, str] = {}

def normalize_threads_url(url: str) -> str:
    """Threads URL'sindeki xmt, slof, igshid gibi query parametrelerini temizler ve canonical hale getirir."""
    parsed = urllib.parse.urlparse(url)
    
    # query parametrelerini temizle
    qs = urllib.parse.parse_qs(parsed.query)
    for param in ["xmt", "slof", "igshid", "utm_source", "utm_medium", "utm_campaign"]:
        if param in qs:
            del qs[param]
    
    new_query = urllib.parse.urlencode(qs, doseq=True)
    
    # threads.net -> threads.com
    netloc = parsed.netloc
    if netloc == "threads.net" or netloc == "www.threads.net" or netloc == "threads.com":
        netloc = "www.threads.com"
        
    canonical_url = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    return canonical_url

def _parse_netscape_cookies(cookie_text: str) -> dict[str, str]:
    cookies = {}
    for line in cookie_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") and not line.startswith("#HttpOnly_"):
            # HttpOnly line handling
            if line.startswith("#HttpOnly_"):
                line = line[10:]
            else:
                continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies

def resolve_threads_share_url(url: str, session_mgr: SessionManager | None = None) -> str:
    """
    Share URL'yi açıp canonical /@user/post/SHORTCODE adresini bulmaya çalışır.
    Canonical URL bulunamazsa, orjinal (normalize edilmiş) URL'yi döndürür.
    """
    if "/share/" not in url.lower():
        return normalize_threads_url(url)
        
    # Cache kontrolü
    match = re.search(r'/share/([a-zA-Z0-9_-]+)', url)
    if match:
        shortcode = match.group(1)
        if shortcode in _RESOLVED_CACHE:
            return _RESOLVED_CACHE[shortcode]
            
    normalized_url = normalize_threads_url(url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    def attempt_resolve(cookies_dict=None):
        try:
            r = cffi_requests.get(
                normalized_url, 
                impersonate="chrome120", 
                headers=headers, 
                cookies=cookies_dict,
                timeout=10, 
                allow_redirects=True
            )
            
            # 1. Final URL kontrolü
            final_url = str(r.url)
            if "/post/" in final_url and "/@" in final_url:
                return normalize_threads_url(final_url)
                
            # 2. HTML Meta etiketleri
            html_text = r.text
            canon_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            if canon_match:
                c_url = canon_match.group(1)
                if "/post/" in c_url and "/@" in c_url:
                    return normalize_threads_url(c_url)
                    
            og_match = re.search(r'<meta\s+property=["\']og:url["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            if og_match:
                o_url = og_match.group(1)
                if "/post/" in o_url and "/@" in o_url:
                    return normalize_threads_url(o_url)
                    
            # 3. data-text-post-permalink veya gömülü link araması
            permalink_match = re.search(r'data-text-post-permalink=["\']([^"\']+)["\']', html_text)
            if permalink_match:
                p_url = permalink_match.group(1)
                if p_url.startswith("/"):
                    p_url = "https://www.threads.com" + p_url
                if "/post/" in p_url and "/@" in p_url:
                    return normalize_threads_url(p_url)
                    
        except Exception:  # noqa: BLE001, S110
            pass
        return None

    # Oturumsuz ilk deneme
    resolved = attempt_resolve()
    if resolved:
        if match:
            _RESOLVED_CACHE[match.group(1)] = resolved
        return resolved
        
    # Kayıtlı oturum ile tek bir deneme
    if session_mgr:
        status = session_mgr.get_session_status()
        if status in ("Geçerli", "Bağlı"):
            cookie_text = session_mgr.store.load_session()
            if cookie_text:
                cookies_dict = _parse_netscape_cookies(cookie_text)
                resolved = attempt_resolve(cookies_dict=cookies_dict)
                if resolved:
                    if match:
                        _RESOLVED_CACHE[match.group(1)] = resolved
                    return resolved
                    
    return normalized_url
