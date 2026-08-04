"""Meta Threads için özel yt-dlp InfoExtractor ve yardımcıları."""

from __future__ import annotations

import contextlib
import html
import json
import re
import urllib.parse
from typing import Any

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError

_TRUSTED_MEDIA_DOMAINS = (
    "fbcdn.net",
    "cdninstagram.com",
    "threads.com",
    "threads.net",
    "facebook.com",
    "instagram.com",
)

_BLOCKED_HOST_PREFIXES = (
    "127.",
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "169.254.",
    "0.",
)


def _unescape_url(raw_url: str | None) -> str:
    """Escaped JSON/HTML URL karakterlerini (\\/, \\u0026, &amp;, \\u003d) temizler."""
    if not raw_url or not isinstance(raw_url, str):
        return ""
    # 1. Çift veya tekli ters eğik çizgili escape'leri temizle (\\/ ve \/)
    cleaned = raw_url.replace(r"\\/", "/").replace(r"\/", "/")
    # 2. Unicode escape dizileri (\u0026 -> &, \u003d -> =)
    with contextlib.suppress(ValueError, TypeError, KeyError, OverflowError):
        cleaned = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            cleaned,
        )
    # 3. HTML entity unescape (&amp; -> &)
    cleaned = html.unescape(cleaned)
    return cleaned.strip()


def is_valid_media_url(media_url: str | None) -> bool:
    """Medya bağlantısının güvenlik ve Meta CDN host kurallarına uygunluğunu denetler."""
    if not media_url or not isinstance(media_url, str):
        return False

    url_clean = _unescape_url(media_url)
    try:
        parsed = urllib.parse.urlparse(url_clean)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return False

    if parsed.scheme.lower() != "https":
        return False

    if parsed.username or parsed.password:
        return False

    host = (parsed.hostname or "").lower()
    if not host:
        return False

    if host in ("localhost", "127.0.0.1", "::1") or host.startswith(_BLOCKED_HOST_PREFIXES):
        return False

    return any(host == domain or host.endswith(f".{domain}") for domain in _TRUSTED_MEDIA_DOMAINS)


def _clean_text(raw_text: str | None) -> str:
    """HTML etiketlerini temizler ve karakterleri dönüştürür."""
    if not raw_text or not isinstance(raw_text, str):
        return ""
    cleaned = re.sub(r"<[^>]+>", "", raw_text)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class _ThreadsMediaGroup:
    """Tekil bir medya nesnesine ait tüm formatları ve üst verileri bir arada tutar."""

    def __init__(
        self,
        media_id: str,
        caption: str | None = None,
        thumbnail_url: str | None = None,
    ) -> None:
        self.media_id = media_id
        self.caption = caption
        self.thumbnail_url = thumbnail_url
        self.formats: list[dict[str, Any]] = []
        self.seen_urls: set[str] = set()

    def add_format(self, fmt: dict[str, Any]) -> None:
        raw_url = fmt.get("url")
        if not raw_url or not isinstance(raw_url, str):
            return
        unescaped = _unescape_url(raw_url).strip()
        if not is_valid_media_url(unescaped) or unescaped in self.seen_urls:
            return
        self.seen_urls.add(unescaped)
        fmt["url"] = unescaped
        self.formats.append(fmt)


class ThreadsIE(InfoExtractor):
    """Meta Threads video gönderileri için özel InfoExtractor."""

    IE_NAME = "threads"
    _VALID_URL = (
        r"https?://(?:www\.)?threads\.(?:net|com)/(?:@(?P<user>[\w.]+)/post/|t/)(?P<id>[a-zA-Z0-9_-]+)"
    )

    def _fetch_oembed(self, url: str) -> dict[str, Any] | None:
        """Tokenless Meta Threads oEmbed endpoint'inden temel gönderi bilgilerini sorgular."""
        with contextlib.suppress(ExtractorError, OSError, ValueError, KeyError, TypeError):
            encoded_url = urllib.parse.quote(url, safe="")
            oembed_url = f"https://graph.threads.com/oembed?url={encoded_url}"
            oembed_json = self._download_json(
                oembed_url,
                None,
                note=False,
                fatal=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if isinstance(oembed_json, dict) and (
                oembed_json.get("html") or oembed_json.get("author_name") or oembed_json.get("title")
            ):
                return oembed_json
        return None

    def _extract_meta_tags(self, webpage: str) -> dict[str, str]:
        """HTML içindeki Open Graph ve Twitter Card meta etiketlerini ayıklar."""
        meta_dict: dict[str, str] = {}
        if not webpage:
            return meta_dict

        pattern = re.compile(
            r"""<meta\s+[^>]*(?:property|name)=["'](?P<key>[^"']+)["'][^>]*content=["'](?P<val>[^"']*)["']""",
            re.IGNORECASE,
        )
        for match in pattern.finditer(webpage):
            key = match.group("key").strip().lower()
            val = _unescape_url(match.group("val").strip())
            if key not in meta_dict and val:
                meta_dict[key] = val

        pattern_rev = re.compile(
            r"""<meta\s+[^>]*content=["'](?P<val>[^"']*)["'][^>]*(?:property|name)=["'](?P<key>[^"']+)["']""",
            re.IGNORECASE,
        )
        for match in pattern_rev.finditer(webpage):
            key = match.group("key").strip().lower()
            val = _unescape_url(match.group("val").strip())
            if key not in meta_dict and val:
                meta_dict[key] = val

        return meta_dict

    def _extract_json_ld_candidates(self, webpage: str) -> list[dict[str, Any]]:
        """HTML içindeki application/ld+json bloklarından video adaylarını çıkarır."""
        candidates: list[dict[str, Any]] = []
        if not webpage:
            return candidates

        scripts = re.findall(
            r"""<script\b[^>]*type=["']application/ld\+json["'][^>]*>(?P<content>[\s\S]*?)</script>""",
            webpage,
            re.IGNORECASE,
        )
        for script_content in scripts:
            try:
                data = json.loads(script_content.strip())
            except (json.JSONDecodeError, UnicodeError, ValueError):
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("@type")
                if item_type == "VideoObject" or "contentUrl" in item or "embedUrl" in item:
                    candidates.append(item)

        return candidates

    def _extract_node_formats(
        self,
        node: dict[str, Any],
        shortcode: str,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """Video düğümünden indirilebilir format listesi, küçük resim ve açıklama oluşturur."""
        formats: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        thumb_url: str | None = None
        caption_text: str | None = None

        # Caption
        caption = node.get("caption", {})
        if isinstance(caption, dict) and caption.get("text"):
            caption_text = _clean_text(caption.get("text"))
        elif isinstance(node.get("text"), str):
            caption_text = _clean_text(node.get("text"))

        # Thumbnail adayı
        image_versions = node.get("image_versions2", {}).get("candidates", [])
        if isinstance(image_versions, list) and image_versions:
            first_img = image_versions[0]
            if isinstance(first_img, dict):
                raw_thumb = _unescape_url(first_img.get("url"))
                if is_valid_media_url(raw_thumb):
                    thumb_url = raw_thumb

        # 1. video_versions
        video_versions = node.get("video_versions", [])
        if isinstance(video_versions, list):
            for v in video_versions:
                if not isinstance(v, dict):
                    continue
                v_url = _unescape_url(v.get("url"))
                if not is_valid_media_url(v_url) or v_url in seen_urls:
                    continue
                seen_urls.add(v_url)
                width = v.get("width")
                height = v.get("height")
                bitrate = v.get("bandwidth") or v.get("bitrate")
                formats.append({
                    "format_id": f"http-{height}p" if height else f"http-{len(formats)+1}",
                    "url": v_url,
                    "ext": "mp4",
                    "protocol": "https",
                    "width": width if isinstance(width, int) else None,
                    "height": height if isinstance(height, int) else None,
                    "tbr": (bitrate // 1000) if isinstance(bitrate, int) and bitrate > 1000 else None,
                    "vcodec": "unknown",
                    "acodec": "unknown",
                })

        # 2. playback_url / progressive_url / video_url
        for key in ("playback_url", "progressive_url", "video_url", "content_url"):
            v_url = _unescape_url(node.get(key))
            if isinstance(v_url, str) and is_valid_media_url(v_url) and v_url not in seen_urls:
                seen_urls.add(v_url)
                formats.append({
                    "format_id": f"http-{len(formats)+1}",
                    "url": v_url,
                    "ext": "mp4",
                    "protocol": "https",
                    "vcodec": "unknown",
                    "acodec": "unknown",
                })

        # 3. dash_manifest / manifest_url
        for key in ("dash_manifest", "manifest_url"):
            manifest = _unescape_url(node.get(key))
            if (
                isinstance(manifest, str)
                and manifest.strip()
                and manifest.startswith("http")
                and is_valid_media_url(manifest)
            ):
                with contextlib.suppress(ExtractorError, OSError, ValueError, KeyError):
                    mpd_fmts = self._extract_mpd_formats(manifest, shortcode, fatal=False)
                    for f in mpd_fmts or []:
                        f_url = _unescape_url(f.get("url"))
                        if f_url and is_valid_media_url(f_url) and f_url not in seen_urls:
                            seen_urls.add(f_url)
                            f["url"] = f_url
                            formats.append(f)

        return formats, thumb_url, caption_text

    def _collect_media_groups_from_json(
        self,
        obj: Any,
        shortcode: str,
        groups: dict[str, _ThreadsMediaGroup],
    ) -> None:
        """Gömülü JSON ağacında medya öğelerini tespit edip medya kimliğine göre gruplar."""
        if isinstance(obj, dict):
            # Carousel/çoklu medya kontrolü
            carousel_media = obj.get("carousel_media") or obj.get("carousel_share_child_media")
            if isinstance(carousel_media, list) and carousel_media:
                for idx, child in enumerate(carousel_media):
                    if not isinstance(child, dict):
                        continue
                    child_id = str(child.get("id") or child.get("pk") or f"{shortcode}_{idx+1}")
                    fmts, thumb, cap = self._extract_node_formats(child, shortcode)
                    if fmts:
                        if child_id not in groups:
                            groups[child_id] = _ThreadsMediaGroup(
                                media_id=child_id, caption=cap, thumbnail_url=thumb
                            )
                        for f in fmts:
                            groups[child_id].add_format(f)
                        if not groups[child_id].thumbnail_url and thumb:
                            groups[child_id].thumbnail_url = thumb
                        if not groups[child_id].caption and cap:
                            groups[child_id].caption = cap
                return

            # Tekil medya düğümü kontrolü
            has_video_fields = bool(
                obj.get("video_versions")
                or obj.get("playback_url")
                or obj.get("progressive_url")
                or obj.get("video_url")
                or obj.get("dash_manifest")
                or obj.get("manifest_url")
            )
            if has_video_fields:
                raw_id = obj.get("id") or obj.get("pk") or shortcode
                media_id = str(raw_id)
                # Eğer tekil bir post içindeki farklı alt yapılarsa kök shortcode altında topla
                if not groups or shortcode in groups:
                    media_id = shortcode
                fmts, thumb, cap = self._extract_node_formats(obj, shortcode)
                if fmts:
                    if media_id not in groups:
                        groups[media_id] = _ThreadsMediaGroup(
                            media_id=media_id, caption=cap, thumbnail_url=thumb
                        )
                    for f in fmts:
                        groups[media_id].add_format(f)
                    if not groups[media_id].thumbnail_url and thumb:
                        groups[media_id].thumbnail_url = thumb
                    if not groups[media_id].caption and cap:
                        groups[media_id].caption = cap

            # Alt elemanlara devam et
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    self._collect_media_groups_from_json(val, shortcode, groups)

        elif isinstance(obj, list):
            for elem in obj:
                if isinstance(elem, (dict, list)):
                    self._collect_media_groups_from_json(elem, shortcode, groups)

    def _extract_regex_video_formats(self, webpage: str) -> list[dict[str, Any]]:
        """Sayfa metninde regex ile escaped veya düz video_versions ve video bağlantılarını arar."""
        formats: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        if not webpage:
            return formats

        # 1. video_versions blokları
        for m in re.finditer(r'["\']video_versions["\']\s*:\s*(\[[^\]]+\])', webpage):
            raw_array = m.group(1)
            try:
                parsed_versions = json.loads(raw_array)
                if isinstance(parsed_versions, list):
                    for v in parsed_versions:
                        if isinstance(v, dict):
                            u = _unescape_url(v.get("url"))
                            if is_valid_media_url(u) and u not in seen_urls:
                                seen_urls.add(u)
                                w = v.get("width")
                                h = v.get("height")
                                formats.append({
                                    "format_id": f"http-{h}p" if h else f"http-{len(formats)+1}",
                                    "url": u,
                                    "ext": "mp4",
                                    "protocol": "https",
                                    "width": w if isinstance(w, int) else None,
                                    "height": h if isinstance(h, int) else None,
                                    "vcodec": "unknown",
                                    "acodec": "unknown",
                                })
            except (json.JSONDecodeError, ValueError, TypeError):
                for obj_match in re.finditer(r'\{[^{}]*\}', raw_array):
                    block = obj_match.group(0)
                    url_m = re.search(r'["\']url["\']\s*:\s*["\']([^"\'\s]+)["\']', block)
                    if url_m:
                        u = _unescape_url(url_m.group(1))
                        if is_valid_media_url(u) and u not in seen_urls:
                            seen_urls.add(u)
                            w_m = re.search(r'["\']width["\']\s*:\s*(\d+)', block)
                            h_m = re.search(r'["\']height["\']\s*:\s*(\d+)', block)
                            w_val = int(w_m.group(1)) if w_m else None
                            h_val = int(h_m.group(1)) if h_m else None
                            formats.append({
                                "format_id": f"http-{h_val}p" if h_val else f"http-{len(formats)+1}",
                                "url": u,
                                "ext": "mp4",
                                "protocol": "https",
                                "width": w_val,
                                "height": h_val,
                                "vcodec": "unknown",
                                "acodec": "unknown",
                            })

        # 2. playback_url, progressive_url, video_url
        for m in re.finditer(
            r'["\'](?:playback_url|progressive_url|video_url)["\']\s*:\s*["\']([^"\'\s]+)["\']',
            webpage,
        ):
            raw_url = _unescape_url(m.group(1))
            if is_valid_media_url(raw_url) and raw_url not in seen_urls:
                seen_urls.add(raw_url)
                formats.append({
                    "format_id": f"http-{len(formats)+1}",
                    "url": raw_url,
                    "ext": "mp4",
                    "protocol": "https",
                    "vcodec": "unknown",
                    "acodec": "unknown",
                })

        return formats

    def _real_extract(self, url: str) -> dict[str, Any]:
        match = self._match_valid_url(url)
        if not match:
            raise ExtractorError("Geçersiz Threads bağlantısı.", expected=True)

        shortcode = match.group("id")
        url_username = match.group("user") if "user" in match.groupdict() else None

        # Sayfa içeriğini indir (yt-dlp session / cookie jar ve headers altyapısını kullanır)
        webpage: str | None = None
        download_err: Exception | None = None
        req_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }
        try:
            webpage = self._download_webpage(
                url,
                shortcode,
                headers=req_headers,
                fatal=False,
            )
        except (ExtractorError, OSError, ValueError, KeyError) as exc:
            download_err = exc

        err_str = str(download_err or "").lower()
        if "429" in err_str or "too many requests" in err_str:
            raise ExtractorError(
                "Threads isteği geçici olarak sınırlandırdı. Bir süre sonra yeniden deneyin.",
                expected=True,
            )

        webpage_text = webpage or ""
        webpage_lower = webpage_text.lower()
        title_m = re.search(r"<title>(.*?)</title>", webpage_text, re.IGNORECASE)
        html_title = title_m.group(1).strip() if title_m else ""
        html_title_lower = html_title.lower()

        is_login_page = (
            "threads • log in" in html_title_lower
            or "threads • giriş yap" in html_title_lower
            or ("giriş yap" in webpage_lower and "login_required" in webpage_lower)
            or ('"logged_out"' in webpage_text and "login" in webpage_lower)
            or ('id="login_form"' in webpage_lower)
        )

        is_not_found = (
            "bu sayfa kullanılamıyor" in webpage_lower
            or "sayfa bulunamadı" in webpage_lower
            or "page not found" in webpage_lower
            or "sorry, this page isn't available" in webpage_lower
        )

        is_rate_limited = (
            "too many requests" in webpage_lower
            or "rate limit" in webpage_lower
            or "http error 429" in webpage_lower
        )

        is_js_shell_only = (
            "fail_ssr_disabled" in webpage_text
            or "is_crawler_ssr_html_only_mo" in webpage_text
        )

        meta_tags = self._extract_meta_tags(webpage_text)
        json_ld_items = self._extract_json_ld_candidates(webpage_text)

        # Medya gruplarını topla
        groups: dict[str, _ThreadsMediaGroup] = {}

        # 1. Embedded JSON blokları
        scripts = re.findall(
            r"""<script\b[^>]*>(?P<content>[\s\S]*?)</script>""",
            webpage_text,
            re.IGNORECASE,
        )
        for script_content in scripts:
            raw = script_content.strip()
            if not raw or (
                "video_versions" not in raw
                and "playback_url" not in raw
                and "dash_manifest" not in raw
                and "carousel_media" not in raw
            ):
                continue

            try:
                data = json.loads(raw)
                self._collect_media_groups_from_json(data, shortcode, groups)
                continue
            except (json.JSONDecodeError, ValueError):
                pass

            json_matches = re.finditer(r"(\{[\s\S]*\})", raw)
            for jm in json_matches:
                snippet = jm.group(1)
                try:
                    data = json.loads(snippet)
                    self._collect_media_groups_from_json(data, shortcode, groups)
                except (json.JSONDecodeError, ValueError):
                    continue

        # 2. Regex fallback
        regex_formats = self._extract_regex_video_formats(webpage_text)
        if regex_formats:
            if not groups:
                groups[shortcode] = _ThreadsMediaGroup(media_id=shortcode)
            # Eğer tek video ise regex formatlarını tek videonun formatlarına ekle
            if len(groups) == 1:
                target_group = next(iter(groups.values()))
                for f in regex_formats:
                    target_group.add_format(f)

        # 3. Meta etiketleri ve JSON-LD formatları
        ld_and_meta_formats: list[dict[str, Any]] = []
        seen_extra: set[str] = set()

        for ld in json_ld_items:
            c_url = _unescape_url(ld.get("contentUrl") or ld.get("embedUrl"))
            if is_valid_media_url(c_url) and c_url not in seen_extra:
                seen_extra.add(c_url)
                w = ld.get("width")
                h = ld.get("height")
                ld_and_meta_formats.append({
                    "format_id": f"http-{h}p" if isinstance(h, int) else f"http-{len(ld_and_meta_formats)+1}",
                    "url": c_url,
                    "ext": "mp4",
                    "protocol": "https",
                    "width": w if isinstance(w, int) else None,
                    "height": h if isinstance(h, int) else None,
                    "vcodec": "unknown",
                    "acodec": "unknown",
                })

        for tag_key in (
            "og:video",
            "og:video:url",
            "og:video:secure_url",
            "twitter:player:stream",
        ):
            v_url = _unescape_url(meta_tags.get(tag_key))
            if is_valid_media_url(v_url) and v_url not in seen_extra:
                seen_extra.add(v_url)
                w_str = meta_tags.get("og:video:width")
                h_str = meta_tags.get("og:video:height")
                w_val = int(w_str) if w_str and w_str.isdigit() else None
                h_val = int(h_str) if h_str and h_str.isdigit() else None
                ld_and_meta_formats.append({
                    "format_id": f"http-{h_val}p" if h_val else f"http-{len(ld_and_meta_formats)+1}",
                    "url": v_url,
                    "ext": "mp4",
                    "protocol": "https",
                    "width": w_val,
                    "height": h_val,
                    "vcodec": "unknown",
                    "acodec": "unknown",
                })

        if ld_and_meta_formats:
            if not groups:
                groups[shortcode] = _ThreadsMediaGroup(media_id=shortcode)
            if len(groups) == 1:
                target_group = next(iter(groups.values()))
                for f in ld_and_meta_formats:
                    target_group.add_format(f)

        # Başlık ve açıklama
        og_title = meta_tags.get("og:title") or meta_tags.get("twitter:title")
        og_desc = (
            meta_tags.get("og:description")
            or meta_tags.get("description")
            or meta_tags.get("twitter:description")
        )
        og_thumb = meta_tags.get("og:image") or meta_tags.get("twitter:image")
        if og_thumb and not is_valid_media_url(og_thumb):
            og_thumb = None

        uploader = url_username
        uploader_id = url_username

        post_title = ""
        if og_title:
            cleaned = _clean_text(og_title)
            cleaned = re.sub(r"^[^:]+\s+on\s+Threads:\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"^[^:]+\s+Threads['’]te:\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*[•|]\s*Threads\s*$", "", cleaned, flags=re.IGNORECASE)
            post_title = cleaned.strip()

        if not post_title and og_desc:
            desc_cleaned = _clean_text(og_desc)
            if desc_cleaned:
                post_title = desc_cleaned.splitlines()[0][:100]

        if not post_title:
            post_title = (
                f"Threads Videosu - @{uploader}" if uploader else f"Threads Videosu - {shortcode}"
            )

        # Geçerli video formatı içeren grupları filtrele
        valid_video_groups = [g for g in groups.values() if g.formats]

        # 1. Birden fazla video içeren çoklu medya (gerçek carousel)
        if len(valid_video_groups) > 1:
            entries: list[dict[str, Any]] = []
            for idx, g in enumerate(valid_video_groups):
                entry_title = g.caption if g.caption else f"{post_title} - {idx + 1}"
                entries.append({
                    "id": f"{shortcode}_{idx + 1}",
                    "title": entry_title,
                    "description": g.caption or og_desc or "",
                    "thumbnail": g.thumbnail_url or og_thumb,
                    "uploader": uploader,
                    "uploader_id": uploader_id,
                    "webpage_url": url,
                    "formats": g.formats,
                })
            return self.playlist_result(
                entries,
                playlist_id=shortcode,
                playlist_title=post_title,
                playlist_description=og_desc,
            )

        # 2. Tek video içeren gönderi
        if len(valid_video_groups) == 1:
            single_group = valid_video_groups[0]
            return {
                "id": shortcode,
                "title": post_title,
                "description": single_group.caption or og_desc or "",
                "thumbnail": single_group.thumbnail_url or og_thumb,
                "uploader": uploader,
                "uploader_id": uploader_id,
                "webpage_url": url,
                "formats": single_group.formats,
            }

        # 3. Hiçbir video bulunamadı -> Durum sınıflandırma
        if is_rate_limited:
            raise ExtractorError(
                "Threads isteği geçici olarak sınırlandırdı. Bir süre sonra yeniden deneyin.",
                expected=True,
            )

        oembed_data = self._fetch_oembed(url)

        if oembed_data is None:
            if is_not_found or not webpage_text:
                raise ExtractorError(
                    "Threads gönderisi silinmiş, gizlenmiş veya kullanılamıyor olabilir.",
                    expected=True,
                )
            if is_login_page:
                raise ExtractorError(
                    "Bu Threads gönderisini görüntülemek için tarayıcı oturumu gerekebilir.",
                    expected=True,
                )
            raise ExtractorError(
                "Threads gönderisi silinmiş, gizlenmiş veya kullanılamıyor olabilir.",
                expected=True,
            )

        if is_login_page:
            raise ExtractorError(
                "Bu Threads gönderisini görüntülemek için tarayıcı oturumu gerekebilir.",
                expected=True,
            )

        if is_js_shell_only:
            raise ExtractorError(
                "Threads video bilgileri alınamadı. Threads sayfa yapısını değiştirmiş olabilir.",
                expected=True,
            )

        # oembed döndü ama video bulunamadı → sayfa yapısı değişmiş/kısıtlı
        if oembed_data is not None:
            raise ExtractorError(
                "Threads gönderisi bulundu ancak video kaynağı alınamadı. "
                "Threads sayfa yapısını değiştirmiş olabilir.",
                expected=True,
            )

        # Sayfa açıldı, giriş sorunu yok ama video formatı yok -> Gerçekten video içermiyor
        raise ExtractorError("Bu Threads gönderisi video içermiyor.", expected=True)


def register_custom_extractors(ydl: Any) -> None:
    """YoutubeDL nesnesine ThreadsIE özel extractor'ını kaydeder."""
    if not hasattr(ydl, "_ies") or not hasattr(ydl, "_ies_instances"):
        if hasattr(ydl, "add_info_extractor"):
            with contextlib.suppress(AttributeError, TypeError, ValueError, ExtractorError):
                ydl.add_info_extractor(ThreadsIE(ydl))
        return

    ie = ThreadsIE(ydl)
    ie_key = ie.ie_key()
    ydl._ies_instances[ie_key] = ie
    if ie_key not in ydl._ies:
        new_ies = {ie_key: ie}
        new_ies.update(ydl._ies)
        ydl._ies = new_ies
