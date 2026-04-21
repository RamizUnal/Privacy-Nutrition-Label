"""
Privacy Policy Crawler — AI-First Design
=========================================
Discovery is AI-powered first, with regex/heuristic fallbacks:
 1. Fetch homepage → send ALL links to Claude → get the best privacy URL
 2. Regex link scan (footer, nav, all links) as fast fallback
 3. Canonical path probing (/privacy, /gizlilik, /kvkk, …)
 4. Sitemap discovery (robots.txt → sitemap.xml)

Validation is a smart cascade — never rejects a good URL just because
the page is JS-rendered:
 a. Standard text extraction → heuristic check
 b. JS-embedded text extraction (__NEXT_DATA__, inline JSON, <noscript>)
 c. URL-pattern trust (if URL says /privacy-policy, believe it)
 d. AI validation (send raw HTML snippet to Claude: "is this a privacy page?")

Supported languages: English, Turkish (tr), German (de), French (fr), Spanish (es)
"""
from __future__ import annotations
import json
import re
import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, List, Tuple, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# Known privacy policy URL paths (fallback when AI is unavailable)
# ─────────────────────────────────────────────────────────────────────────────

PRIVACY_PATHS = [
    # ── English ───────────────────────────────────────────────────────────────
    "/privacy",
    "/privacy-policy",
    "/privacy_policy",
    "/privacypolicy",
    "/legal/privacy",
    "/legal/privacy-policy",
    "/legal",
    "/policies/privacy",
    "/policies",
    "/data-privacy",
    "/data-protection",
    "/gdpr",
    "/en/privacy",
    "/en/privacy-policy",
    "/about/privacy",
    "/about/legal",
    "/help/privacy",
    "/support/privacy",
    "/info/privacy",
    "/terms/privacy",

    # ── Turkish (tr) ──────────────────────────────────────────────────────────
    "/gizlilik",
    "/gizlilik-politikasi",
    "/gizlilik_politikasi",
    "/gizlilik-bildirimi",
    "/gizlilik-beyani",
    "/kvkk",
    "/kvkk-aydinlatma-metni",
    "/aydinlatma-metni",
    "/kisisel-verilerin-korunmasi",
    "/kisisel_verilerin_korunmasi",
    "/kisisel-veri-koruma",
    "/kisisel-veriler",
    "/veri-koruma",
    "/veri-gizliligi",
    "/cerez-politikasi",
    "/cerez",
    "/yasal/gizlilik",
    "/hukuki/gizlilik",
    "/yasal",
    "/tr/gizlilik",
    "/tr/kvkk",
    "/tr/privacy",

    # ── Common modern slug patterns ──────────────────────────────────────────
    "/protection-of-personal-data",
    "/en/protection-of-personal-data",
    "/de/protection-of-personal-data",
    "/fr/protection-of-personal-data",
    "/es/protection-of-personal-data",
    "/s/kisisel-verilerin-korunmasi",
    "/kisisel-verilerin-korunmasi",
    "/kisisel_verilerin_korunmasi",
]

# ─────────────────────────────────────────────────────────────────────────────
# Link text patterns (regex) — used for fast link scanning
# ─────────────────────────────────────────────────────────────────────────────

PRIVACY_LINK_PATTERNS = [
    # English
    r"privacy\s*policy",
    r"privacy\s*notice",
    r"privacy\s*statement",
    r"privacy\s*center",
    r"privacy\s*choices",
    r"data\s*protection",
    r"data\s*privacy",
    r"personal\s*data",
    r"cookie\s*policy",
    r"cookie\s*notice",
    r"notice\s*at\s*collection",
    r"california\s*privacy",
    r"consumer\s*privacy",
    r"employee\s*privacy",
    r"applicant\s*privacy",
    r"candidate\s*privacy",
    r"vendor\s*privacy",
    r"supplier\s*privacy",
    r"children'?s\s*privacy",

    # Turkish
    r"gizlilik\s*politikas[iı]",
    r"gizlilik\s*bildirim[i]",
    r"gizlilik\s*beyan[iı]",
    r"gizlilik",
    r"kvkk",
    r"ayd[iı]nlatma\s*metn[i]",
    r"ek\s*ayd[iı]nlatma\s*metn[i]",
    r"ki[sş]isel\s*ver[i]",
    r"kişisel\s*ver[i]",
    r"veri\s*koruma",
    r"veri\s*gizlili[gğ][i]",
    r"[cç]erez\s*politikas[iı]",
    r"[cç]erez\s*(gizlilik|bildirimi)",
    r"veri\s*i[sş]leme",
    r"haklar[iı]n[iı]z",

    # German
    r"datenschutz",
    r"datenschutzerkl[äa]rung",

    # French
    r"politique\s*de\s*confidentialit[eé]",
    r"données\s*personnelles",

    # Spanish
    r"pol[ií]tica\s*de\s*privacidad",
    r"privacidad",
]

# ─────────────────────────────────────────────────────────────────────────────
# URL fragments that strongly indicate a privacy page
# ─────────────────────────────────────────────────────────────────────────────

PRIVACY_URL_SIGNALS = [
    # English
    "/privacy", "privacy-policy", "privacy_policy", "privacypolicy",
    "privacy-center", "privacy_centre", "privacy-center", "privacy-choices",
    "data-protection", "data_protection", "/gdpr",
    "legal/privacy", "policies/privacy",
    "cookie-policy", "cookie_policy", "cookie-notice", "cookie_notice",
    "notice-at-collection", "consumer-privacy", "california-privacy",
    "employee-privacy", "applicant-privacy", "candidate-privacy",
    "vendor-privacy", "supplier-privacy",
    # Turkish
    "gizlilik", "kvkk", "aydinlatma", "kisisel-veri", "kisisel_veri",
    "verilerin-korunma", "verilerin_korunma",
    "veri-koruma", "veri_koruma", "cerez-politikasi", "cerez_politikasi",
    "veri-gizliligi",
    # German
    "datenschutz",
    # French
    "confidentialit",
    # Spanish
    "privacidad",
]

# Headers
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr,tr-TR;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.5,fr;q=0.4",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "DNT": "1",
}

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_CONTENT_LENGTH = 3 * 1024 * 1024

# Recursive policy-tree expansion: privacy hubs often branch into
# regional / role-based / cookie / retention / rights notices.
_BRANCH_POLICY_HINT_RE = re.compile(
    r"(?i)(?:"
    r"privacy|cookie|cookies|data\s*protection|data\s*privacy|personal\s*data|gdpr|ccpa|"
    r"retention|rights|children|child|california|consumer|notice\s*at\s*collection|"
    r"employee|employees|applicant|applicants|candidate|candidates|vendor|vendors|supplier|suppliers|"
    r"gizlilik|kvkk|ayd[ıi]nlatma|ek\s*ayd[ıi]nlatma|ki[sş]isel\s*veri|veri\s*koruma|"
    r"veri\s*gizlili[gğ][i]|[cç]erez|haklar[iı]n[iı]z|saklama|kamera|"
    r"datenschutz|datenschutzerkl[äa]rung|confidentialit[eé]|privacidad"
    r")"
)

_POLICY_TREE_MAX_FETCHES = 24
_POLICY_TREE_MAX_DEPTH = 2
_POLICY_TREE_PER_PAGE_CANDIDATE_LIMIT = 15


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    return url.rstrip("/")


def extract_domain(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return parsed.netloc.lstrip("www.")


def base_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


def _normalized_path(url: str) -> str:
    p = urlparse(normalize_url(url))
    path = p.path or "/"
    return path if path.startswith("/") else f"/{path}"


def _privacy_signal_count(text: str) -> int:
    text_lower = (text or "").lower()
    signals = [
        # English
        "privacy", "personal data", "personal information", "data protection",
        "data controller", "data processor", "cookies", "retention", "consent",
        # Turkish
        "gizlilik", "kişisel veri", "kisisel veri", "kvkk", "aydınlatma", "aydinlatma",
        "veri sorumlusu", "çerez", "cerez", "saklama",
        # Other
        "datenschutz", "confidentialité", "privacidad",
    ]
    return sum(1 for s in signals if s in text_lower)


def _looks_like_homepage_or_shell(url: str, text: str, html: str) -> bool:
    """Detect storefront/homepage shells that contain nav/footer words but no real policy body."""
    path = _normalized_path(url)
    text_lower = (text or "").lower()
    html_lower = (html or "").lower()

    if path in ("", "/"):
        return True

    nav_terms = [
        "giriş yap", "favorilerim", "sepetim", "kategoriler", "kampanyalar",
        "search icon", "ürün, kategori veya marka ara", "canlı yardım",
        "login", "sign in", "favorites", "cart", "basket", "categories",
        "shop from essentials to extras",
    ]
    nav_hits = sum(1 for t in nav_terms if t in text_lower or t in html_lower)

    # Lots of navigation/shell signals and very little policy language => likely homepage/shell.
    if nav_hits >= 3 and _privacy_signal_count(text) < 6:
        return True

    # Very short content dominated by site chrome.
    words = len((text or "").split())
    if words < 450 and nav_hits >= 2 and _privacy_signal_count(text) < 8:
        return True

    return False


def _has_substantive_privacy_body(text: str) -> bool:
    words = len((text or "").split())
    return words >= 600 and _privacy_signal_count(text) >= 8

async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[Tuple[str, str, List[str]]]:
    """Fetch URL → (final_url, html, set_cookie_headers) or None."""
    try:
        resp = await client.get(url, follow_redirects=True, headers=BROWSER_HEADERS)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "html" in ct or "text" in ct:
                text = resp.text
                if len(text.encode()) > MAX_CONTENT_LENGTH:
                    text = text[:MAX_CONTENT_LENGTH]
                return str(resp.url), text, resp.headers.get_list("set-cookie")
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction  (standard + JS-embedded)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text_from_html(html: str) -> str:
    """Standard: strip scripts/styles, find main content, return text."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "noscript", "svg", "button"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find(id=re.compile(
            r"content|main|privacy|policy|gizlilik|kvkk|aydinlatma|datenschutz", re.I
        ))
        or soup.find(class_=re.compile(
            r"content|main|privacy|policy|article|gizlilik|kvkk|aydinlatma|datenschutz", re.I
        ))
        or soup.find("article")
        or soup.body
    )

    raw = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in raw.splitlines() if l.strip() and len(l.strip()) > 2]
    return "\n".join(lines)


def _visit_key(url: str) -> str:
    """Normalize URL for deduplication (scheme + host + path, no fragment)."""
    p = urlparse(url.strip())
    path = p.path or ""
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return f"{(p.scheme or 'https').lower()}://{p.netloc.lower()}{path}".lower()


_MULTI_PART_PUBLIC_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk",
    "com.tr", "org.tr", "gov.tr", "edu.tr", "k12.tr",
    "co.jp", "com.au", "net.au", "org.au",
    "co.nz", "com.br", "com.mx", "com.sg",
}

def _registrable_domain(host: str) -> str:
    """Best-effort eTLD+1 extraction without extra dependencies."""
    host = (host or "").lower().split(":", 1)[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    suffix2 = ".".join(parts[-2:])
    if suffix2 in _MULTI_PART_PUBLIC_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])

def _same_registered_domain(url: str, root_url: str) -> bool:
    return _registrable_domain(urlparse(url).netloc) == _registrable_domain(urlparse(root_url).netloc)


def _main_content_scope_for_links(html: str) -> Any:
    """
    Restrict link discovery to ``<main>``, ``<article>``, or a cleaned ``<body>``
    (nav / footer / sidebar roles removed). Returns a BeautifulSoup node to search under.
    """
    soup = BeautifulSoup(html, "lxml")
    node = (
        soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("article")
    )
    if node is not None:
        return node
    body = soup.find("body")
    if body is None:
        return soup
    for bad in list(body.find_all(["nav", "footer", "aside", "header"])):
        bad.decompose()
    for role in ("navigation", "complementary", "contentinfo"):
        for el in list(body.find_all(attrs={"role": role})):
            el.decompose()
    return body


def _anchor_label(a) -> str:
    label = (a.get_text(separator=" ", strip=True) or a.get("aria-label") or "sub-policy").strip()
    return re.sub(r"\s+", " ", label)[:200]

def _policy_branch_score(href: str, text: str, candidate_url: str, current_page_url: str, root_policy_url: str) -> int:
    """Score whether a link is likely to be a privacy-policy branch worth following."""
    blob = f"{href} {text} {candidate_url}".lower()
    score = 0

    if any(re.search(p, text, re.IGNORECASE) for p in PRIVACY_LINK_PATTERNS):
        score += 6
    if any(re.search(p, href, re.IGNORECASE) for p in PRIVACY_LINK_PATTERNS):
        score += 4
    if _url_strongly_indicates_privacy(candidate_url):
        score += 5
    if _BRANCH_POLICY_HINT_RE.search(blob):
        score += 2

    current_path = urlparse(current_page_url).path.lower().rstrip("/")
    root_path = urlparse(root_policy_url).path.lower().rstrip("/")
    candidate_path = urlparse(candidate_url).path.lower().rstrip("/")

    if current_path and candidate_path.startswith(current_path) and candidate_path != current_path:
        score += 2
    if root_path and candidate_path.startswith(root_path) and candidate_path != root_path:
        score += 2
    if any(token in candidate_path for token in ("/legal", "/policy", "/policies", "/notice", "/notices")):
        score += 1

    return score

def _discover_policy_branch_links(
    html: str,
    current_page_url: str,
    root_policy_url: str,
    *,
    visited_keys: Set[str],
    queued_keys: Optional[Set[str]] = None,
    limit: int = _POLICY_TREE_PER_PAGE_CANDIDATE_LIMIT,
) -> List[Tuple[str, str, int]]:
    """Find same-site privacy-related child links from a privacy hub/page."""
    queued_keys = queued_keys or set()
    soup = BeautifulSoup(html, "lxml")
    scopes: List[Any] = []

    main_scope = (
        soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("article")
    )
    if main_scope is not None:
        scopes.append(main_scope)
    body = soup.find("body") or soup
    scopes.append(body)

    found: List[Tuple[str, str, int]] = []
    local_seen: Set[str] = set()

    for scope in scopes:
        for a in scope.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full = urljoin(current_page_url, href)
            p = urlparse(full)
            if p.scheme not in ("http", "https"):
                continue
            normalized = full.split("#", 1)[0]
            if not _same_registered_domain(normalized, root_policy_url):
                continue

            key = _visit_key(normalized)
            if key in visited_keys or key in queued_keys or key in local_seen:
                continue

            label = _anchor_label(a)
            score = _policy_branch_score(href, label, normalized, current_page_url, root_policy_url)
            if score <= 0:
                continue

            local_seen.add(key)
            found.append((normalized, label, score))

    found.sort(key=lambda row: (-row[2], len(urlparse(row[0]).path), row[0]))
    return found[:limit]


@dataclass
class PolicyTreeResult:
    """Root policy + depth-1 sub-pages, stitched for downstream LLM parsing."""

    stitched_text: str
    root_final_url: str
    root_requested_url: str
    sub_pages: List[Tuple[str, str]] = field(default_factory=list)
    skipped_reasons: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


async def fetch_policy_tree(
    client: httpx.AsyncClient,
    root_policy_url: str,
    *,
    root_html: Optional[str] = None,
    root_final_url: Optional[str] = None,
) -> PolicyTreeResult:
    """
    Recursively expand privacy-policy branches (bounded BFS).
    This catches privacy hubs that split content into cookie / retention /
    role-based / region-based notices living on separate child URLs.
    """
    errors: List[str] = []
    skipped: List[str] = []

    if root_html is not None and root_final_url is not None:
        final_root = str(root_final_url)
        html_root = root_html
    else:
        fetched = await _fetch(client, root_policy_url)
        if not fetched:
            errors.append(f"root_fetch_failed:{root_policy_url}")
            return PolicyTreeResult(
                stitched_text="",
                root_final_url=root_policy_url,
                root_requested_url=root_policy_url,
                errors=errors,
            )
        final_root, html_root, _ = fetched

    visited: Set[str] = {_visit_key(final_root), _visit_key(root_policy_url)}
    queued: Set[str] = set()

    root_text = _extract_text_from_html(html_root) or _extract_js_embedded_text(html_root)
    parts: List[str] = [f"=== MAIN PRIVACY POLICY ({final_root}) ===\n{root_text}"]

    sub_pages: List[Tuple[str, str]] = []
    queue: List[Tuple[str, str, int, str]] = [(final_root, html_root, 0, "MAIN PRIVACY POLICY")]
    total_pages_collected = 1

    while queue and total_pages_collected < _POLICY_TREE_MAX_FETCHES:
        current_url, current_html, depth, _current_label = queue.pop(0)
        if depth >= _POLICY_TREE_MAX_DEPTH:
            continue

        remaining_slots = _POLICY_TREE_MAX_FETCHES - total_pages_collected
        candidates = _discover_policy_branch_links(
            current_html,
            current_url,
            final_root,
            visited_keys=visited,
            queued_keys=queued,
            limit=min(_POLICY_TREE_PER_PAGE_CANDIDATE_LIMIT, remaining_slots),
        )

        if not candidates:
            continue

        async def _fetch_candidate(requested_url: str, label: str, score: int):
            fr = await _fetch(client, requested_url)
            if not fr:
                return requested_url, requested_url, label, score, "", False
            fu, h, _ = fr
            return requested_url, str(fu), label, score, h, True

        rows = await asyncio.gather(*[
            _fetch_candidate(requested_url, label, score)
            for requested_url, label, score in candidates[:remaining_slots]
        ])

        for requested_url, final_url, label, score, html, ok in rows:
            queued.discard(_visit_key(requested_url))
            if not ok:
                errors.append(f"sub_fetch_failed:{requested_url}")
                continue

            final_key = _visit_key(final_url)
            if final_key in visited:
                continue
            if not _same_registered_domain(final_url, final_root):
                skipped.append(f"off_domain:{final_url}")
                continue

            valid, body_txt = await _smart_validate(final_url, html, original_url=requested_url)
            if not valid:
                # Soft-accept strong branch pages when the URL/text clearly suggests
                # a privacy-related child notice, even if the heuristic text check is thin.
                fallback_txt = _extract_text_from_html(html) or _extract_js_embedded_text(html)
                if score >= 6 and fallback_txt and len(fallback_txt) >= 120 and (
                    _BRANCH_POLICY_HINT_RE.search(label)
                    or _url_strongly_indicates_privacy(requested_url)
                    or _url_strongly_indicates_privacy(final_url)
                ):
                    valid, body_txt = True, fallback_txt

            if not valid:
                skipped.append(f"not_privacy_branch:{requested_url}")
                continue

            visited.add(final_key)
            total_pages_collected += 1
            accepted_url = (
                requested_url
                if final_url != requested_url and _url_strongly_indicates_privacy(requested_url)
                else final_url
            )

            body_txt = (body_txt or "").strip()
            if not body_txt:
                errors.append(f"sub_empty_text:{accepted_url}")
                continue

            sub_pages.append((accepted_url, label))
            parts.append(
                f"\n\n=== SUB-POLICY DEPTH {depth + 1}: {label} ({accepted_url}) ===\n{body_txt}"
            )

            if depth + 1 < _POLICY_TREE_MAX_DEPTH and total_pages_collected < _POLICY_TREE_MAX_FETCHES:
                queue.append((accepted_url, html, depth + 1, label))
                queued.add(_visit_key(accepted_url))

    return PolicyTreeResult(
        stitched_text="".join(parts),
        root_final_url=final_root,
        root_requested_url=root_policy_url,
        sub_pages=sub_pages,
        skipped_reasons=skipped,
        errors=errors,
    )


def _extract_js_embedded_text(html: str) -> str:
    """
    Many SPAs embed page data inside <script> tags (Next.js __NEXT_DATA__,
    Nuxt.js __NUXT__, generic JSON-LD, etc.).  Try to extract readable text
    from those blobs.
    """
    soup = BeautifulSoup(html, "lxml")
    extracted_parts: list[str] = []

    # 1. __NEXT_DATA__  (Next.js)
    next_tag = soup.find("script", id="__NEXT_DATA__")
    if next_tag and next_tag.string:
        try:
            blob = json.loads(next_tag.string)
            extracted_parts.append(_walk_json_for_text(blob))
        except (json.JSONDecodeError, TypeError):
            pass

    # 2. Generic <script type="application/json"> or <script type="application/ld+json">
    for tag in soup.find_all("script", attrs={"type": re.compile(r"application/(ld\+)?json")}):
        if tag.string and len(tag.string) > 100:
            try:
                blob = json.loads(tag.string)
                extracted_parts.append(_walk_json_for_text(blob))
            except (json.JSONDecodeError, TypeError):
                pass

    # 3. <noscript> fallback content
    for ns in soup.find_all("noscript"):
        inner = ns.get_text(separator="\n", strip=True)
        if len(inner) > 100:
            extracted_parts.append(inner)

    # 4. Inline JS variables:  var content = "..."  or  innerHTML = "..."
    for script in soup.find_all("script"):
        if script.string and ("privacy" in (script.string or "").lower() or
                              "gizlilik" in (script.string or "").lower() or
                              "kvkk" in (script.string or "").lower()):
            # Try to extract HTML-like content from JS strings
            html_blobs = re.findall(r'["\'](<[^"\']{200,})["\']', script.string or "")
            for blob in html_blobs[:3]:
                blob_soup = BeautifulSoup(blob, "lxml")
                text = blob_soup.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    extracted_parts.append(text)

    combined = "\n".join(extracted_parts)
    lines = [l.strip() for l in combined.splitlines() if l.strip() and len(l.strip()) > 2]
    return "\n".join(lines)


def _walk_json_for_text(obj, depth: int = 0) -> str:
    """Recursively extract string values from a JSON blob."""
    if depth > 10:
        return ""
    if isinstance(obj, str):
        # Only keep strings that look like content (not URLs, IDs, etc.)
        if len(obj) > 30:
            # If it looks like HTML, parse it
            if "<" in obj and ">" in obj:
                soup = BeautifulSoup(obj, "lxml")
                return soup.get_text(separator="\n", strip=True)
            return obj
        return ""
    if isinstance(obj, dict):
        return "\n".join(_walk_json_for_text(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return "\n".join(_walk_json_for_text(v, depth + 1) for v in obj[:50])
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Smart validation cascade
# ─────────────────────────────────────────────────────────────────────────────

def _url_strongly_indicates_privacy(url: str) -> bool:
    """Does the URL itself prove this is a privacy page?"""
    url_lower = url.lower()
    return any(sig in url_lower for sig in PRIVACY_URL_SIGNALS)


def _is_likely_privacy_policy(text: str) -> bool:
    """Keyword heuristic: ≥3 signal hits in 200+ chars of text."""
    if len(text) < 200:
        return False
    text_lower = text.lower()
    signals = [
        # English
        "personal information", "personal data", "privacy", "we collect",
        "data protection", "cookies", "third part", "retention", "consent",
        "data controller", "data processor",
        # Turkish
        "gizlilik", "kişisel veri", "kisisel veri", "kvkk", "aydınlatma",
        "aydinlatma", "veri sorumlusu", "açık rıza", "acik riza",
        "veri işleme", "veri isleme", "çerez", "cerez", "veri koruma",
        # German
        "datenschutz", "personenbezogene",
        # French
        "données personnelles", "confidentialité",
        # Spanish
        "datos personales", "privacidad",
    ]
    return sum(1 for s in signals if s in text_lower) >= 3


async def _ai_validate_page(url: str, html: str) -> bool:
    """Ask Claude: 'is this HTML a privacy policy page?'"""
    try:
        from ai.claude_client import acomplete, FAST_MODEL, is_available
    except ImportError:
        return False
    if not is_available():
        return False

    # Send a compact slice of the raw HTML — enough for Claude to judge
    snippet = html[:4000]

    prompt = f"""Look at this HTML from {url}. Is this a privacy policy, data protection
notice, KVKK aydınlatma metni, Datenschutz page, or similar legal privacy document?

HTML snippet:
{snippet}

Reply with ONLY "yes" or "no"."""

    try:
        result = await acomplete(prompt, model=FAST_MODEL, max_tokens=10)
        return result and result.strip().lower().startswith("yes")
    except Exception:
        return False


async def _smart_validate(url: str, html: str, original_url: Optional[str] = None) -> Tuple[bool, str]:
    """
    Multi-method validation. Returns (is_valid, extracted_text).
    Never rejects a clearly-privacy URL just because the page is JS-rendered,
    but also avoids accepting a storefront homepage merely because the requested
    URL looked privacy-like before redirect.

    ``original_url`` — the URL we *requested* before following redirects.
    SPAs redirect /privacy-policy → / and render client-side, so the
    final URL loses the privacy signal. We keep the original to check.
    """
    # Method 1: Standard text extraction → heuristic
    text = _extract_text_from_html(html)

    # Method 2: JS-embedded text extraction (SPAs: Next.js, Nuxt, etc.)
    js_text = _extract_js_embedded_text(html)

    # Combine whatever text we have
    best_text = text if len(text) >= len(js_text) else js_text
    looks_like_shell = _looks_like_homepage_or_shell(url, best_text, html)

    # Strong body evidence wins immediately.
    if _is_likely_privacy_policy(text) or _is_likely_privacy_policy(js_text):
        if not looks_like_shell or _has_substantive_privacy_body(best_text):
            return True, best_text

    # Method 3: URL pattern trust — only when the resolved page is not obviously
    # a storefront shell, or when the extracted body itself is substantial.
    if _url_strongly_indicates_privacy(url):
        if not looks_like_shell or _has_substantive_privacy_body(best_text):
            return True, best_text

    if original_url and _url_strongly_indicates_privacy(original_url):
        if (
            _normalized_path(url) not in ("", "/")
            and not looks_like_shell
            and len(best_text.split()) >= 500
            and _privacy_signal_count(best_text) >= 8
        ):
            return True, best_text

    # Method 4: AI validation — ask Claude to judge the raw HTML.
    # Still avoid blindly accepting obvious homepages.
    if html and len(html) > 200:
        if await _ai_validate_page(url, html):
            if not looks_like_shell or _has_substantive_privacy_body(best_text):
                return True, best_text

    return False, best_text


# ─────────────────────────────────────────────────────────────────────────────
# Discovery: AI-powered link picker (PRIMARY method)
# ─────────────────────────────────────────────────────────────────────────────

async def _ai_find_privacy_url(html: str, base: str) -> Optional[str]:
    """
    PRIMARY discovery: send all homepage links to Claude and let it pick
    the privacy policy URL.  Falls back gracefully when AI is unavailable.
    """
    try:
        from ai.claude_client import acomplete, FAST_MODEL, is_available
    except ImportError:
        return None
    if not is_available():
        return None

    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        text = a.get_text(separator=" ").strip()[:80]
        links.append(f'"{text}" → {full_url}')

    if not links:
        return None

    links_text = "\n".join(links[:250])

    prompt = f"""I need to find the privacy policy URL for: {base}

Here are all hyperlinks from the homepage:
{links_text}

Find the privacy policy / data protection / KVKK page.

Anchor text clues by language:
- English:  "Privacy Policy", "Privacy Notice", "Data Protection", "Cookie Policy"
- Turkish:  "Gizlilik Politikası", "KVKK", "Aydınlatma Metni",
            "Kişisel Verilerin Korunması", "Çerez Politikası", "Veri Koruma"
- German:   "Datenschutz", "Datenschutzerklärung"
- French:   "Confidentialité", "Politique de confidentialité"
- Spanish:  "Privacidad", "Política de privacidad"

URL path clues: /privacy, /gizlilik, /kvkk, /aydinlatma-metni, /kisisel-veriler,
/kisisel_verilerin_korunmasi, /veri-koruma, /cerez-politikasi, /datenschutz, etc.

Reply with ONLY the full URL on a single line.
If nothing matches, reply: none"""

    try:
        result = await acomplete(prompt, model=FAST_MODEL, max_tokens=300)
        if result:
            candidate = result.strip().split("\n")[0].strip().rstrip(".")
            if candidate.lower() != "none" and candidate.startswith("http"):
                return candidate
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Discovery: regex link scan (fast fallback)
# ─────────────────────────────────────────────────────────────────────────────

async def _find_privacy_link_in_html(html: str, base: str) -> Optional[str]:
    """Scan footer/nav/all links for privacy-related text or URL patterns.
    Returns the best-scoring candidate instead of the first weak match."""
    soup = BeautifulSoup(html, "lxml")

    candidates: list = []
    for selector in [
        "footer", '[role="contentinfo"]',
        '.footer', '#footer', '.legal', '.legal-links',
        'nav', '[role="navigation"]', '.nav', '#nav', '.navbar',
        '.bottom-links', '.site-footer',
    ]:
        container = soup.select_one(selector)
        if container:
            candidates.extend(container.find_all("a", href=True))

    seen: set = set()
    unique = []
    for a in candidates:
        href = a.get("href", "")
        key = (href, a.get_text(separator=" ").strip())
        if key not in seen:
            seen.add(key)
            unique.append(a)

    if not unique:
        unique = soup.find_all("a", href=True)

    scored: list[tuple[int, str]] = []
    for a in unique:
        href = a.get("href", "")
        text = a.get_text(separator=" ").lower().strip()
        full_url = urljoin(base, href)

        if not href.strip() or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        score = 0
        if any(re.search(p, text, re.IGNORECASE) for p in PRIVACY_LINK_PATTERNS):
            score += 10
        if any(sig in href.lower() for sig in PRIVACY_URL_SIGNALS):
            score += 8
        if "privacy policy" in text or "gizlilik politik" in text or "kisisel verilerin korunmas" in text or "kişisel verilerin korunmas" in text:
            score += 8
        if any(x in full_url.lower() for x in ["/s/", "protection-of-personal-data", "kisisel-verilerin-korunmasi", "kisisel_verilerin_korunmasi"]):
            score += 6
        if score > 0:
            scored.append((score, full_url))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return scored[0][1]


# ─────────────────────────────────────────────────────────────────────────────
# Discovery: sitemap
# ─────────────────────────────────────────────────────────────────────────────

async def _scan_sitemap_for_privacy(client: httpx.AsyncClient, sitemap_url: str, depth: int = 0) -> Optional[str]:
    if depth > 2:
        return None
    try:
        resp = await client.get(sitemap_url, follow_redirects=True, headers=BROWSER_HEADERS, timeout=10.0)
        if resp.status_code != 200:
            return None
        content = resp.text
        urls = re.findall(r'<loc>\s*(.*?)\s*</loc>', content, re.IGNORECASE)
        for url in urls:
            if any(sig in url.lower() for sig in PRIVACY_URL_SIGNALS):
                return url.strip()
        if depth == 0:
            nested = re.findall(r'<sitemap>.*?<loc>\s*(.*?)\s*</loc>.*?</sitemap>', content, re.DOTALL | re.IGNORECASE)
            for nu in nested[:5]:
                found = await _scan_sitemap_for_privacy(client, nu.strip(), depth + 1)
                if found:
                    return found
    except Exception:
        pass
    return None


async def _find_via_sitemap(client: httpx.AsyncClient, base: str) -> Optional[str]:
    sitemap_urls: list[str] = []
    try:
        robots = await _fetch(client, base + "/robots.txt")
        if robots:
            _, rtxt, _ = robots
            sitemap_urls.extend(re.findall(r'(?i)^Sitemap:\s*(\S+)', rtxt, re.MULTILINE)[:5])
    except Exception:
        pass
    sitemap_urls += [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/sitemap-index.xml"]
    for su in sitemap_urls:
        found = await _scan_sitemap_for_privacy(client, su)
        if found:
            return found
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CrawlResult
# ─────────────────────────────────────────────────────────────────────────────

class CrawlResult:
    def __init__(self):
        self.policy_url: Optional[str] = None
        self.policy_text: str = ""
        self.policy_html: str = ""
        self.homepage_html: str = ""
        self.homepage_cookies: List[str] = []
        self.policy_found: bool = False
        self.error: Optional[str] = None
        self.word_count: int = 0
        self.fetch_attempts: List[str] = []
        self.discovery_method: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point  —  AI-first discovery cascade
# ─────────────────────────────────────────────────────────────────────────────

async def crawl_website(url: str) -> CrawlResult:
    """
    AI-first crawl:
      1. Fetch homepage
      2. AI picks the best privacy URL from all links  (primary)
      3. Regex link scan                               (fast fallback)
      4. Canonical path probing                        (brute-force fallback)
      5. Sitemap discovery                             (last resort)

    Each candidate URL goes through smart validation that handles
    JS-rendered pages, trusts strong URL patterns, and uses AI to
    validate ambiguous pages.
    """
    result = CrawlResult()
    url = normalize_url(url)
    base = base_url(url)

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        verify=True,
        limits=httpx.Limits(max_keepalive_connections=5),
        follow_redirects=True,
    ) as client:

        # ── Step 1: Fetch homepage ─────────────────────────────────────────
        homepage_result = await _fetch(client, url)
        if homepage_result:
            _, result.homepage_html, result.homepage_cookies = homepage_result

        privacy_url = None

        # ── Step 2: AI discovery (PRIMARY) ─────────────────────────────────
        if not privacy_url and result.homepage_html:
            link = await _ai_find_privacy_url(result.homepage_html, base)
            if link:
                privacy_url = await _try_candidate(
                    client, result, link, "ai_discovery"
                )

        # ── Step 3: Regex link scan ────────────────────────────────────────
        if not privacy_url and result.homepage_html:
            link = await _find_privacy_link_in_html(result.homepage_html, base)
            if link:
                privacy_url = await _try_candidate(
                    client, result, link, "link_scan"
                )

        # ── Step 4: Canonical path probing ─────────────────────────────────
        if not privacy_url:
            for path in PRIVACY_PATHS:
                candidate = base + path
                result.fetch_attempts.append(candidate)
                privacy_url = await _try_candidate(
                    client, result, candidate, "canonical_path"
                )
                if privacy_url:
                    break
                await asyncio.sleep(0.15)

        # ── Step 5: Sitemap discovery ──────────────────────────────────────
        if not privacy_url:
            link = await _find_via_sitemap(client, base)
            if link:
                privacy_url = await _try_candidate(
                    client, result, link, "sitemap"
                )

        # ── Finalize ───────────────────────────────────────────────────────
        if privacy_url:
            result.policy_url = privacy_url
            result.policy_found = True
            result.word_count = len(result.policy_text.split()) if result.policy_text else 0
        else:
            result.error = (
                "Privacy policy not found via AI discovery, link scan, "
                "canonical paths, or sitemap."
            )

    return result


async def _try_candidate(
    client: httpx.AsyncClient,
    result: CrawlResult,
    link: str,
    method: str,
) -> Optional[str]:
    """
    Fetch a candidate URL and run smart validation.
    Passes the *original* requested URL so SPA redirects don't lose context.
    If valid, populate result fields and return the accepted URL.
    """
    fetch_result = await _fetch(client, link)
    if not fetch_result:
        return None
    final_url, html, _ = fetch_result
    valid, text = await _smart_validate(final_url, html, original_url=link)

    print("TRY CANDIDATE")
    print("  method    :", method)
    print("  requested :", link)
    print("  final_url :", final_url)
    print("  valid     :", valid)
    print("  words     :", len((text or "").split()))
    print("  signals   :", _privacy_signal_count(text or ""))
    print("  path      :", _normalized_path(final_url))


    if valid and len((text or "").split()) < 500 and _privacy_signal_count(text or "") < 8:
        return None
    
    # Guardrail: do not accept a root/homepage redirect as the final policy URL
    # unless the extracted body is actually substantive. This is the main failure
    # mode behind short 200–400 word false positives.
    if valid and _normalized_path(final_url) in ("", "/") and not _has_substantive_privacy_body(text):
        return None

    if valid:
        result.policy_html = html
        result.discovery_method = method
        accepted = (
            link
            if (final_url != link and _url_strongly_indicates_privacy(link))
            else str(final_url)
        )
        tree = await fetch_policy_tree(
            client, accepted, root_html=html, root_final_url=str(final_url)
        )
        result.policy_text = (
            tree.stitched_text if tree.stitched_text.strip() else text
        )
        return accepted
    return None


