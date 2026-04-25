
"""
Privacy Policy Crawler — extraction-first version for Privacy Lens

Goal:
- Given only a base domain / URL, locate the privacy policy automatically.
- Extract privacy policy as raw text for downstream LLM / regex analysis.
- Support English + Turkish sites first, with light support for common EU variants.
- Be permissive enough to FIND real privacy pages, while avoiding obvious
  interstitials and non-privacy legal documents.

Design:
1. Fetch homepage statically
2. Discover privacy candidates from homepage links
3. Probe canonical privacy paths
4. Probe sitemap
5. For each candidate:
   - static fetch + extract
   - if empty / JS shell / gibberish, try Playwright render
   - validate with extraction-first scoring
6. Once a root policy is accepted, collect a few strong same-site
   sub-policy pages (cookie, retention, rights, KVKK addendum, etc.)
   BUT exclude alternate-language copies of the same policy.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple
from urllib.parse import parse_qs, parse_qsl, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from ai.claude_client import FAST_MODEL, acomplete
except Exception:
    FAST_MODEL = ""
    acomplete = None


# ─────────────────────────────────────────────────────────────────────────────
# Candidate paths and patterns
# ─────────────────────────────────────────────────────────────────────────────

PRIVACY_PATHS = [
    # English
    "/privacy",
    "/privacy/policy",
    "/privacy/policy/",
    "/privacy-policy",
    "/privacy_policy",
    "/privacypolicy",
    "/privacy/center",
    "/privacy_center",
    "/legal/privacy",
    "/legal/privacy-policy",
    "/policies/privacy",
    "/data-privacy",
    "/data-protection",
    "/privacy-notice",
    "/privacy-statement",
    "/protection-of-personal-data",
    "/personal-data",
    "/personal-data-collected",
    "/cookie-policy",
    "/cookies",
    "/en/privacy",
    "/en/privacy-policy",
    "/en/privacy-notice",
    "/en/data-protection",
    "/en/protection-of-personal-data",

    # Turkish
    "/gizlilik",
    "/gizlilik-politikasi",
    "/gizlilik_politikasi",
    "/gizlilik-bildirimi",
    "/gizlilik-beyani",
    "/kvkk",
    "/kvkk-aydinlatma-metni",
    "/aydinlatma-metni",
    "/ek-aydinlatma-metni",
    "/kisisel-verilerin-korunmasi",
    "/kisisel_verilerin_korunmasi",
    "/kisisel-veri-koruma",
    "/kisisel-veriler",
    "/veri-koruma",
    "/veri-gizliligi",
    "/cerez-politikasi",
    "/cerez",
    "/tr/gizlilik",
    "/tr/kvkk",
    "/tr/privacy",
    "/s/kisisel-verilerin-korunmasi",

    # Common real-world slugs
    "/safetyandprivacy/personal-data-collected",
    "/privacy_agreement",
]

PRIVACY_LINK_PATTERNS = [
    # English
    r"privacy\s*policy",
    r"privacy\s*notice",
    r"privacy\s*statement",
    r"privacy",
    r"data\s*protection",
    r"data\s*privacy",
    r"personal\s*data",
    r"cookie\s*policy",
    r"cookies?",
    # Turkish
    r"gizlilik\s*politikas[iı]",
    r"gizlilik\s*bildirim[i]",
    r"gizlilik\s*beyan[iı]",
    r"gizlilik",
    r"kvkk",
    r"ayd[iı]nlatma\s*metn[i]",
    r"ek\s*ayd[iı]nlatma\s*metn[i]",
    r"ki[sş]isel\s*ver[i]",
    r"veri\s*koruma",
    r"veri\s*gizlili[gğ][i]",
    r"[cç]erez\s*politikas[iı]",
    r"[cç]erez",
    # Other
    r"datenschutz",
    r"confidentialit[eé]",
    r"privacidad",
]

PRIVACY_URL_SIGNALS = [
    "privacy", "privacy-policy", "privacy_policy", "privacypolicy",
    "privacy-notice", "privacy-statement",
    "data-protection", "data-privacy",
    "personal-data", "personal-data-collected",
    "protection-of-personal-data",
    "cookie-policy", "cookies",
    "privacy_agreement", "safetyandprivacy",
    "gizlilik", "kvkk", "aydinlatma", "kisisel-veri", "kisisel_veri",
    "veri-koruma", "veri-gizliligi", "cerez",
    "datenschutz", "confidentialit", "privacidad",
]

KNOWN_POLICY_URLS = {
    "amazon.com": [
        "https://www.amazon.com/-/en/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ",
        "https://www.amazon.com/gp/help/customer/display.html?nodeId=201909010",
        "https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ",
    ],
    "anthropic.com": "https://www.anthropic.com/legal/privacy",
    "apple.com": "https://www.apple.com/legal/privacy/en-ww/",
    "cloudflare.com": "https://www.cloudflare.com/privacypolicy/",
    "discord.com": "https://discord.com/privacy",
    "duckduckgo.com": "https://duckduckgo.com/privacy",
    "ebay.com": "https://www.ebay.com/help/policies/member-behaviour-policies/user-privacy-notice-privacy-policy",
    "epicgames.com": "https://www.epicgames.com/site/en-US/privacypolicy",
    "facebook.com": "https://mbasic.facebook.com/privacy/policy/?locale=en_US",
    "fb.com": "https://mbasic.facebook.com/privacy/policy/?locale=en_US",
    "fortnite.com": "https://www.epicgames.com/site/en-US/privacypolicy",
    "github.com": "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
    "google.com": "https://policies.google.com/privacy?hl=en",
    "instagram.com": "https://mbasic.facebook.com/privacy/policy/?locale=en_US",
    "linkedin.com": "https://www.linkedin.com/legal/privacy-policy",
    "microsoft.com": "https://privacy.microsoft.com/en-us/privacystatement",
    "mozilla.org": "https://www.mozilla.org/en-US/privacy/firefox/",
    "netflix.com": "https://help.netflix.com/legal/privacy",
    "openai.com": "https://openai.com/policies/row-privacy-policy/",
    "paypal.com": "https://www.paypal.com/us/legalhub/privacy-full",
    "pinterest.com": "https://policy.pinterest.com/en/privacy-policy",
    "reddit.com": "https://www.reddit.com/policies/privacy-policy",
    "roblox.com": "https://en.help.roblox.com/hc/en-us/articles/115004630823-Roblox-Privacy-and-Cookie-Policy",
    "rockstargames.com": "https://www.rockstargames.com/privacy",
    "snap.com": "https://snap.com/en-US/privacy/privacy-policy",
    "snapchat.com": "https://snap.com/en-US/privacy/privacy-policy",
    "spotify.com": "https://www.spotify.com/us/legal/privacy-policy/",
    "steam.com": "https://store.steampowered.com/privacy_agreement/",
    "steampowered.com": "https://store.steampowered.com/privacy_agreement/",
    "stripe.com": "https://stripe.com/privacy",
    "tiktok.com": "https://www.tiktok.com/legal/page/row/privacy-policy/en",
    "twitch.tv": "https://www.twitch.tv/p/legal/privacy-notice/",
    "twitter.com": "https://x.com/en/privacy",
    "whatsapp.com": "https://www.whatsapp.com/legal/privacy-policy",
    "x.com": "https://x.com/en/privacy",
    "yahoo.com": "https://legal.yahoo.com/us/en/yahoo/privacy/index.htm",
    "youtube.com": "https://policies.google.com/privacy?hl=en",
    "zoom.us": "https://zoom.us/privacy",
}

DOMAIN_ALIASES = {
    "rockstar.com": "rockstargames.com",
}

NON_PRIVACY_LEGAL_SIGNALS = [
    "end-user-agreement",
    "end user agreement",
    "terms-of-use",
    "terms of use",
    "terms-and-conditions",
    "terms and conditions",
    "user agreement",
    "kullanim-sartlari",
    "kullanım şartları",
    "uyelik-sozlesmesi",
    "üyelik sözleşmesi",
]

INTERSTITIAL_URL_SIGNALS = [
    "select-country",
    "choose-country",
    "country-selector",
    "geo-redirect",
]

SUBPOLICY_HINT_RE = re.compile(
    r"(?i)(privacy|cookie|cookies|retention|rights|gdpr|ccpa|"
    r"gizlilik|kvkk|ayd[ıi]nlatma|[cç]erez|haklar[iı]n[iı]z|"
    r"datenschutz|confidentialit[eé]|privacidad)"
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": os.getenv(
        "CRAWLER_ACCEPT_LANGUAGE",
        "en-US,en;q=0.9,tr-TR;q=0.7,tr;q=0.6",
    ),
    # intentionally omit `br` to avoid environments that cannot decode it cleanly
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "DNT": "1",
}
FALLBACK_HEADERS = {
    "User-Agent": "curl/8.4.0",
    "Accept": "*/*",
}
READER_HEADERS = {
    "Accept": "text/plain, text/markdown, */*",
    "User-Agent": BROWSER_HEADERS["User-Agent"],
}

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
FETCH_TIMEOUT = httpx.Timeout(5.0, connect=2.0)
RENDER_TIMEOUT_SECONDS = 6.0
MAX_CONTENT_LENGTH = 3 * 1024 * 1024
MAX_SUBPOLICY_FETCHES = 8

LANGUAGE_ALIASES = {
    "en": "en", "english": "en",
    "tr": "tr", "turkish": "tr", "turkce": "tr", "türkçe": "tr",
    "de": "de", "german": "de", "deutsch": "de",
    "fr": "fr", "french": "fr", "francais": "fr", "français": "fr",
    "es": "es", "spanish": "es", "espanol": "es", "español": "es",
    "it": "it", "italian": "it",
    "pl": "pl", "polish": "pl",
    "pt": "pt", "portuguese": "pt",
    "nl": "nl", "dutch": "nl",
}


# ─────────────────────────────────────────────────────────────────────────────
# Basic models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PolicyTreeResult:
    stitched_text: str
    sub_pages: List[Tuple[str, str]] = field(default_factory=list)


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
# URL helpers
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
    p = urlparse(url)
    path = p.path or "/"
    return path.rstrip("/") or "/"


def _url_has_privacy_signal(url: str) -> bool:
    lower = url.lower()
    return any(sig in lower for sig in PRIVACY_URL_SIGNALS)


def _url_is_interstitial(url: str) -> bool:
    lower = url.lower()
    return any(sig in lower for sig in INTERSTITIAL_URL_SIGNALS)


def _url_is_non_privacy_legal(url: str) -> bool:
    lower = url.lower()
    return any(sig in lower for sig in NON_PRIVACY_LEGAL_SIGNALS)


def _looks_like_product_or_listing_url(url: str) -> bool:
    """
    Filter obvious commerce/content pages that should never be treated as privacy-policy candidates.
    This matters when the user provides a product URL instead of a homepage.
    """
    path = _normalized_path(url).lower()
    full = url.lower()

    product_or_listing_signals = [
        "/pm-", "-pm-", "hbc", "/urun", "/ürün", "/product", "/products",
        "/kategori", "/category", "/search", "search?", "/ara", "ara?",
        "/list", "/listing", "/collections", "/campaign", "/kampanya",
        "/blog", "/article", "/articles", "/news", "/story"
    ]

    if any(sig in path or sig in full for sig in product_or_listing_signals):
        return True

    # Hepsiburada / marketplace-style long product slugs
    slug = path.strip("/")
    if slug and slug.count("-") >= 6 and any(tok in slug for tok in ["-p-", "pm-", "hbc"]):
        return True

    return False


_MULTI_PART_PUBLIC_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk",
    "com.tr", "org.tr", "gov.tr", "edu.tr", "k12.tr",
    "co.jp", "com.au", "net.au", "org.au",
    "co.nz", "com.br", "com.mx", "com.sg",
}


def _registrable_domain(host: str) -> str:
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


def _lookup_known_policies(domain: str) -> List[str]:
    if _skip_known_policy_urls():
        return []

    host = (domain or "").lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    registrable = _registrable_domain(host)
    aliased = DOMAIN_ALIASES.get(registrable, registrable)
    value = (
        KNOWN_POLICY_URLS.get(host)
        or KNOWN_POLICY_URLS.get(registrable)
        or KNOWN_POLICY_URLS.get(aliased)
    )
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [url for url in value if isinstance(url, str)]


def _lookup_known_policy(domain: str) -> Optional[str]:
    known_urls = _lookup_known_policies(domain)
    return known_urls[0] if known_urls else None


def _skip_known_policy_urls() -> bool:
    load_dotenv(Path(__file__).parent / ".env", override=True)
    return os.getenv("SKIP_KNOWN_POLICY_URLS", "").lower() in {"1", "true", "yes"}


def _canonical_search_domain(domain: str) -> str:
    registrable = _registrable_domain(domain)
    return DOMAIN_ALIASES.get(registrable, registrable)


def _same_registered_domain(a: str, b: str) -> bool:
    return _registrable_domain(urlparse(a).netloc) == _registrable_domain(urlparse(b).netloc)


def _path_segments(url: str) -> List[str]:
    return [seg for seg in urlparse(url).path.lower().strip("/").split("/") if seg]


def _normalize_lang_token(token: str) -> Optional[str]:
    token = (token or "").lower().strip()
    if token in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[token]
    if re.fullmatch(r"[a-z]{2}-[a-z]{2}", token):
        base = token.split("-")[0]
        return LANGUAGE_ALIASES.get(base)
    return None


def _detect_lang_bucket_from_url(url: str) -> Optional[str]:
    for seg in _path_segments(url):
        lang = _normalize_lang_token(seg)
        if lang:
            return lang
    return None


def _detect_lang_bucket_from_label(label: str) -> Optional[str]:
    text = (label or "").lower()
    for raw, norm in LANGUAGE_ALIASES.items():
        if re.search(rf"\b{re.escape(raw)}\b", text):
            return norm
    return None


def _detect_lang_bucket_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    markers = {
        "tr": ["gizlilik", "kişisel veri", "kisisel veri", "veri sorumlusu", "çerez", "cerez", "aydınlatma", "aydinlatma"],
        "en": ["privacy", "personal data", "personal information", "data controller", "cookies", "retention"],
        "de": ["datenschutz", "personenbezogene", "cookie-richtlinie"],
        "fr": ["confidentialité", "données personnelles", "politique de confidentialité"],
        "es": ["privacidad", "datos personales", "política de privacidad", "politica de privacidad"],
        "it": ["informativa sulla privacy", "dati personali"],
        "pl": ["polityka prywatności", "dane osobowe"],
    }
    scores = {lang: sum(1 for m in pats if m in t) for lang, pats in markers.items()}
    best_lang, best_score = max(scores.items(), key=lambda x: x[1])
    return best_lang if best_score >= 2 else None


def _policy_family_key(url: str) -> str:
    segs = _path_segments(url)

    if segs and _normalize_lang_token(segs[0]):
        segs = segs[1:]

    if segs and _normalize_lang_token(segs[-1]):
        segs = segs[:-1]

    return "/" + "/".join(segs)


def _is_alternate_language_copy(
    candidate_url: str,
    label: str,
    candidate_text: str,
    root_url: str,
    root_text: str,
) -> bool:
    """
    Reject same-policy alternate language mirrors while still allowing real
    sub-policies (cookie preferences, KVKK addendum, rights pages, etc.).
    """
    root_lang = (
        _detect_lang_bucket_from_url(root_url)
        or _detect_lang_bucket_from_text(root_text)
    )
    cand_lang = (
        _detect_lang_bucket_from_url(candidate_url)
        or _detect_lang_bucket_from_label(label)
        or _detect_lang_bucket_from_text(candidate_text)
    )

    root_family = _policy_family_key(root_url)
    cand_family = _policy_family_key(candidate_url)

    # Same policy family + explicit language marker => alternate mirror
    if root_family == cand_family and cand_lang is not None:
        if root_lang is None or cand_lang != root_lang:
            return True

    # Different family but explicit conflicting language marker
    if root_lang and cand_lang and cand_lang != root_lang:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Fetchers
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch(
    client: httpx.AsyncClient,
    url: str,
) -> Optional[Tuple[str, str, List[str], str]]:
    """
    Returns (final_url, text, set_cookie_headers, content_type)
    """
    for headers in (BROWSER_HEADERS, FALLBACK_HEADERS):
        try:
            resp = await client.get(
                url,
                follow_redirects=True,
                headers=headers,
                timeout=FETCH_TIMEOUT,
            )
            if resp.status_code == 200:
                ct = (resp.headers.get("content-type") or "").lower()
                # Keep html/xhtml/xml/text-ish pages. Many privacy pages are weirdly typed.
                if not any(x in ct for x in ("html", "xml", "text", "json")):
                    return None
                solved = await _solve_simple_js_challenge(client, resp, headers)
                if solved:
                    return solved
                text = resp.text
                if len(text.encode("utf-8", errors="ignore")) > MAX_CONTENT_LENGTH:
                    text = text[:MAX_CONTENT_LENGTH]
                return str(resp.url), text, resp.headers.get_list("set-cookie"), ct
            if 400 <= resp.status_code < 500:
                continue
            return None
        except Exception:
            continue
    return None


async def _solve_simple_js_challenge(
    client: httpx.AsyncClient,
    resp: httpx.Response,
    headers: dict,
) -> Optional[Tuple[str, str, List[str], str]]:
    """
    Some policy pages, notably Reddit, return a tiny no-cookie JS challenge
    before serving the actual legal text. Solve only the simple hidden-form
    shape we can prove from the response, then continue with normal validation.
    """
    html = resp.text or ""
    if "js_challenge" not in html or 'name="solution"' not in html:
        return None

    seed_match = re.search(r'\(async\s+e\s*=>\s*e\s*\+\s*e\)\("([^"]+)"\)', html)
    if not seed_match:
        return None

    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form")
    if not form:
        return None

    params: List[Tuple[str, str]] = []
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        value = inp.get("value") or ""
        if name == "solution":
            value = seed_match.group(1) * 2
        params.append((name, value))

    for name, value in parse_qsl(urlparse(str(resp.url)).query, keep_blank_values=True):
        params.append((name, value))

    action = urljoin(str(resp.url), form.get("action") or str(resp.url))
    try:
        solved = await client.get(
            action,
            params=params,
            follow_redirects=True,
            headers=headers,
            timeout=FETCH_TIMEOUT,
        )
    except Exception:
        return None

    if solved.status_code != 200:
        return None

    ct = (solved.headers.get("content-type") or "").lower()
    if not any(x in ct for x in ("html", "xml", "text", "json")):
        return None

    text = solved.text
    if "js_challenge" in text and 'name="solution"' in text:
        return None
    if len(text.encode("utf-8", errors="ignore")) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH]
    return str(solved.url), text, solved.headers.get_list("set-cookie"), ct


async def _fetch_reader_text(
    client: httpx.AsyncClient,
    url: str,
) -> Optional[str]:
    if os.getenv("ENABLE_READER_FALLBACK", "true").lower() not in {"1", "true", "yes"}:
        return None

    try:
        resp = await client.get(
            "https://r.jina.ai/" + url,
            follow_redirects=True,
            headers=READER_HEADERS,
            timeout=httpx.Timeout(20.0, connect=5.0),
        )
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    text = _clean_reader_text(resp.text or "")
    lower = text.lower()
    if not text or len(text.split()) < 120:
        return None
    if "securitycompromiseerror" in lower or '"code":451' in lower:
        return None
    if "privacy" not in lower and "personal data" not in lower and "personal information" not in lower:
        return None
    return text


def _clean_reader_text(text: str) -> str:
    cleaned = _clean_lines(text)
    lines = []
    for line in cleaned.splitlines():
        if re.match(r"^(Title|URL Source|Published Time|Markdown Content):", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


async def _render_with_playwright(url: str) -> Optional[Tuple[str, str]]:
    """
    Dynamic fallback for JS-heavy privacy pages.
    Returns (final_url, rendered_html)
    """
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None

    async def _render() -> Optional[Tuple[str, str]]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(locale="en-US")
                await page.goto(url, wait_until="domcontentloaded", timeout=8000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass
                html = await page.content()
                final_url = page.url
                return final_url, html
            finally:
                await browser.close()

    try:
        return await asyncio.wait_for(_render(), timeout=RENDER_TIMEOUT_SECONDS)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction
# ─────────────────────────────────────────────────────────────────────────────

def _clean_lines(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) >= 2:
            lines.append(line)
    return "\n".join(lines)


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # remove noisy elements
    for tag in soup(["script", "style", "svg", "canvas", "iframe"]):
        tag.decompose()

    candidates = [
        soup.find("main"),
        soup.find("article"),
        soup.find(attrs={"role": "main"}),
        soup.find(id=re.compile(r"privacy|policy|gizlilik|kvkk|content|main", re.I)),
        soup.find(class_=re.compile(r"privacy|policy|gizlilik|kvkk|content|main|article", re.I)),
        soup.body,
        soup,
    ]
    texts = [
        _clean_lines(node.get_text(separator="\n", strip=True))
        for node in candidates
        if node is not None
    ]
    if not texts:
        return ""
    return max(texts, key=lambda text: len(text.split()))


def _walk_json_for_text(obj: Any, depth: int = 0) -> str:
    if depth > 10:
        return ""
    if isinstance(obj, str):
        if len(obj) > 30:
            if "<" in obj and ">" in obj:
                try:
                    return _extract_text_from_html(obj)
                except Exception:
                    return obj
            return obj
        return ""
    if isinstance(obj, dict):
        return "\n".join(_walk_json_for_text(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return "\n".join(_walk_json_for_text(v, depth + 1) for v in obj[:100])
    return ""


def _extract_js_embedded_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    parts: List[str] = []

    # Next.js / Nuxt / inline JSON
    for tag in soup.find_all("script"):
        tag_id = (tag.get("id") or "").lower()
        tag_type = (tag.get("type") or "").lower()
        content = tag.string or tag.text or ""
        if not content or len(content) < 40:
            continue

        if tag_id == "__next_data__" or "application/json" in tag_type or "ld+json" in tag_type:
            try:
                blob = json.loads(content)
                parts.append(_walk_json_for_text(blob))
                continue
            except Exception:
                pass

        # generic JS blobs containing privacy / kvkk
        if re.search(r"privacy|gizlilik|kvkk|ayd[ıi]nlatma", content, re.I):
            html_blobs = re.findall(r'["\'](<[^"\']{100,})["\']', content)
            for blob in html_blobs[:5]:
                parts.append(_extract_text_from_html(blob))

    for ns in soup.find_all("noscript"):
        txt = ns.get_text(separator="\n", strip=True)
        if len(txt) > 80:
            parts.append(txt)

    return _clean_lines("\n".join(parts))


def _extract_best_text(html: str) -> str:
    text = _extract_text_from_html(html)
    js_text = _extract_js_embedded_text(html)
    return text if len(text) >= len(js_text) else js_text


# ─────────────────────────────────────────────────────────────────────────────
# Heuristics
# ─────────────────────────────────────────────────────────────────────────────

def _privacy_signal_count(text: str) -> int:
    t = (text or "").lower()
    signals = [
        "privacy", "privacy policy", "privacy notice",
        "personal data", "personal information",
        "data protection", "data controller", "data processor",
        "cookies", "retention", "consent", "third party",
        "gizlilik", "kişisel veri", "kisisel veri",
        "kvkk", "aydınlatma", "aydinlatma",
        "veri sorumlusu", "çerez", "cerez", "veri koruma",
        "datenschutz", "confidentialité", "privacidad",
    ]
    return sum(1 for s in signals if s in t)


def _looks_like_gibberish(text: str) -> bool:
    if not text:
        return True
    sample = text[:2500]
    bad = sample.count("�") + sample.count("\x00")
    if bad >= 5:
        return True
    printable = sum(1 for ch in sample if ch.isprintable() or ch in "\n\r\t")
    ratio = printable / max(len(sample), 1)
    return ratio < 0.85


def _looks_like_resource_dump(text: str) -> bool:
    if not text:
        return True
    words = text.split()
    if len(words) < 50:
        return False
    url_like = sum(
        1
        for word in words
        if word.startswith(("http://", "https://", "/ajax/"))
        or "static." in word
        or ".webp" in word
        or ".js" in word
    )
    policy_signals = _privacy_signal_count(text)
    return url_like / max(len(words), 1) > 0.25 and policy_signals < 4


def _looks_like_stub_privacy_page(text: str, url: str) -> bool:
    words = len((text or "").split())
    path = _normalized_path(url).lower()
    if words <= 120 and (
        "privacy-policy" in path
        or "privacy_policy" in path
        or "privacypolicy" in path
        or "/legal/privacy" in path
        or "/policies/privacy" in path
    ):
        return True
    return False


def _looks_like_homepage_or_shell(url: str, text: str, html: str) -> bool:
    path = _normalized_path(url)
    if path == "/":
        return True

    lower_text = (text or "").lower()
    lower_html = (html or "").lower()

    nav_terms = [
        "giriş yap", "favorilerim", "sepetim", "kategoriler", "kampanyalar",
        "ürün, kategori veya marka ara", "canlı yardım",
        "login", "sign in", "favorites", "cart", "basket", "categories",
    ]
    nav_hits = sum(1 for t in nav_terms if t in lower_text or t in lower_html)
    words = len((text or "").split())
    signals = _privacy_signal_count(text)

    if nav_hits >= 3 and signals < 3 and words < 400:
        return True
    return False


def _is_likely_privacy_policy(text: str) -> bool:
    if len(text) < 200:
        return False
    return _privacy_signal_count(text) >= 3


def _candidate_score(url: str, text: str, html: str, original_url: Optional[str] = None) -> int:
    score = 0
    words = len((text or "").split())
    signals = _privacy_signal_count(text)
    lower_blob = f"{url}\n{original_url or ''}\n{text}".lower()

    if _url_has_privacy_signal(url):
        score += 4
    if original_url and _url_has_privacy_signal(original_url):
        score += 3
    if _is_likely_privacy_policy(text):
        score += 5

    if "privacy policy" in lower_blob or "gizlilik politik" in lower_blob:
        score += 3
    if "kvkk" in lower_blob or "kişisel veri" in lower_blob or "kisisel veri" in lower_blob:
        score += 3
    if "data controller" in lower_blob or "veri sorumlusu" in lower_blob:
        score += 2

    if words >= 250:
        score += 2
    if words >= 800:
        score += 2
    if signals >= 4:
        score += 2

    if _looks_like_stub_privacy_page(text, url):
        score -= 6
    if _url_is_interstitial(url):
        score -= 8
    if _url_is_non_privacy_legal(url):
        score -= 8
    if _looks_like_homepage_or_shell(url, text, html):
        score -= 4
    if _looks_like_gibberish(text):
        score -= 10

    return score


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

async def _smart_validate(url: str, html: str, original_url: Optional[str] = None) -> Tuple[bool, str]:
    """
    Extraction-first validation:
    - accept strong privacy URLs if they extract meaningful text
    - reject interstitials / non-privacy legal docs / gibberish
    - allow JS-heavy pages via Playwright fallback upstream
    """
    best_text = _extract_best_text(html)

    if _url_is_interstitial(url):
        return False, ""
    if _url_is_non_privacy_legal(url):
        return False, best_text
    if _looks_like_gibberish(best_text):
        return False, ""
    if _looks_like_resource_dump(best_text):
        return False, ""
    if _looks_like_stub_privacy_page(best_text, url):
        return False, best_text

    score = _candidate_score(url, best_text, html, original_url=original_url)

    # extraction-first thresholds:
    # - strong URL + enough text
    # - or decent signals + enough text
    words = len(best_text.split())
    signals = _privacy_signal_count(best_text)

    if score >= 6 and words >= 120:
        return True, best_text

    if _url_has_privacy_signal(url) and words >= 120 and signals >= 1:
        return True, best_text

    if original_url and _url_has_privacy_signal(original_url) and words >= 120 and signals >= 1:
        return True, best_text

    return False, best_text


# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────

async def _find_privacy_link_in_html(html: str, base: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    anchors = soup.find_all("a", href=True)

    scored: List[Tuple[int, str]] = []
    seen: Set[str] = set()

    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(base, href)
        if full in seen:
            continue
        seen.add(full)

        if _looks_like_product_or_listing_url(full):
            continue

        text = a.get_text(separator=" ", strip=True).lower()
        blob = f"{text} {href}".lower()

        score = 0
        if any(re.search(p, blob, re.I) for p in PRIVACY_LINK_PATTERNS):
            score += 10
        if _url_has_privacy_signal(full):
            score += 8
        if _url_is_non_privacy_legal(full):
            score -= 10
        if _url_is_interstitial(full):
            score -= 6

        if score > 0:
            scored.append((score, full))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return scored[0][1]


def _unwrap_search_result_url(href: str) -> Optional[str]:
    href = (href or "").strip()
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = urljoin("https://search.brave.com", href)

    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    for key in ("url", "u", "uddg"):
        values = qs.get(key)
        if values and values[0].startswith(("http://", "https://")):
            href = values[0]
            break

    return href if href.startswith(("http://", "https://")) else None


def _search_result_mentions_privacy(url: str, title: str = "", snippet: str = "") -> bool:
    if _url_has_privacy_signal(url):
        return True

    haystack = f"{title}\n{snippet}".lower()
    return any(re.search(pattern, haystack, re.I) for pattern in PRIVACY_LINK_PATTERNS)


def _is_off_target_search_subdomain(url: str, domain: str) -> bool:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    # The consumer Amazon policy lives on www.amazon.com. When maps are skipped,
    # Brave often ranks AWS/Amazon Ads policies above the consumer policy.
    if domain == "amazon.com":
        off_target_hosts = {
            "aws.amazon.com",
            "advertising.amazon.com",
            "sellercentral.amazon.com",
            "developer.amazon.com",
            "affiliate-program.amazon.com",
        }
        return host in off_target_hosts

    return False


def _score_search_result(url: str, title: str, snippet: str, domain: str) -> int:
    if _url_is_non_privacy_legal(url) or _url_is_interstitial(url):
        return -100
    if _looks_like_product_or_listing_url(url):
        return -100
    if not _search_result_mentions_privacy(url, title, snippet):
        return -100

    score = 0
    blob = f"{url}\n{title}\n{snippet}".lower()
    domain = _canonical_search_domain(domain)
    domain_stem = domain.split(".", 1)[0]
    target_url = "https://" + domain
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    same_domain = _same_registered_domain(url, target_url)

    if _is_off_target_search_subdomain(url, domain):
        return -100

    noisy_result_signals = [
        "devforum.", "forum.", "forums.", "community.", "discourse.",
        "/forum", "/forums", "/community", "/questions", "/answers", "/t/",
        "/interactive/", "/opinion/", "/article/", "/articles/", "/news/",
        "/wirecutter/", "/reviews/", "/video/", "/live/",
        "broken", "hyperlink", "not working", "bug report",
        "changes to the privacy notice", "changes to our privacy notice",
        "privacy notice changes", "privacy policy changes",
        "previous privacy", "prior privacy", "archived privacy",
    ]
    if any(sig in host or sig in path or sig in blob for sig in noisy_result_signals):
        return -100
    if re.search(r"/20\d{2}/", path):
        return -100
    if "terms" in path and not _url_has_privacy_signal(path):
        return -100

    if not same_domain:
        return -100
    if same_domain:
        score += 10
    if host == domain or host == f"www.{domain}":
        score += 4
    if _url_has_privacy_signal(url):
        score += 8
    if "privacy policy" in blob or "privacy notice" in blob or "gizlilik politikas" in blob:
        score += 5
    if "privacy policy" in title.lower():
        score += 6
    if "kvkk" in blob or "datenschutz" in blob or "privacidad" in blob:
        score += 3
    if "cookie" in blob or "cookies" in blob or "cerez" in blob or "çerez" in blob:
        score += 1

    return score


def _pick_search_candidates(
    rows: List[Tuple[str, str, str]],
    domain: str,
    limit: int = 5,
) -> List[str]:
    scored: List[Tuple[int, str]] = []
    seen: Set[str] = set()

    for raw_url, title, snippet in rows:
        url = _unwrap_search_result_url(raw_url)
        if not url or url in seen:
            continue
        seen.add(url)

        score = _score_search_result(url, title, snippet, domain)
        if score > 0:
            scored.append((score, url))

    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return [url for _, url in scored[:limit]]


def _extract_json_array(text: str) -> Optional[List[str]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return None
    if not isinstance(parsed, list):
        return None
    return [x for x in parsed if isinstance(x, str)]


async def _ai_pick_search_candidates(
    rows: List[Tuple[str, str, str]],
    domain: str,
    limit: int = 3,
) -> List[str]:
    if not acomplete:
        return []
    if os.getenv("ENABLE_AI_SEARCH_RERANK", "true").lower() not in {"1", "true", "yes"}:
        return []
    if not os.getenv("ANTHROPIC_API_KEY"):
        return []

    normalized_rows = []
    seen: Set[str] = set()
    for raw_url, title, snippet in rows[:10]:
        url = _unwrap_search_result_url(raw_url)
        if not url or url in seen:
            continue
        seen.add(url)
        normalized_rows.append((url, title.strip(), snippet.strip()))

    if not normalized_rows:
        return []

    results_text = "\n".join(
        f"{i}. URL: {url}\n   TITLE: {title}\n   SNIPPET: {snippet}"
        for i, (url, title, snippet) in enumerate(normalized_rows, start=1)
    )
    prompt = f"""
Target website/domain: {domain}

Brave Search results:
{results_text}

Return a JSON array of up to {limit} URLs that are the official privacy policy,
privacy notice, cookie policy, KVKK/GDPR privacy notice, or official parent-company
privacy policy for the target website.

Rules:
- Prefer official pages operated by the target site, its parent company, or its help/legal center.
- Reject articles, news, opinion pieces, forum posts, bug reports, terms-only pages,
  card/payment terms, docs about someone else's privacy policy, and random third-party mirrors.
- If none are official privacy/cookie policy pages for the target, return [].
- Output only JSON, no prose.
""".strip()

    try:
        raw = await asyncio.wait_for(
            acomplete(
                prompt,
                system="You select official privacy policy URLs from search results. Return only JSON.",
                model=FAST_MODEL,
                max_tokens=180,
            ),
            timeout=8.0,
        )
    except Exception:
        return []

    picked = _extract_json_array(raw or "")
    if not picked:
        return []

    allowed = {url for url, _, _ in normalized_rows}
    candidates: List[str] = []
    for url in picked:
        unwrapped = _unwrap_search_result_url(url)
        if unwrapped in allowed and unwrapped not in candidates:
            candidates.append(unwrapped)
    return candidates[:limit]


async def _brave_search_query(
    client: httpx.AsyncClient,
    query: str,
    domain: str,
) -> List[str]:
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return []

    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": query,
                "count": 10,
                "country": os.getenv("SEARCH_COUNTRY", "US"),
                "search_lang": os.getenv("SEARCH_LANG", "en"),
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    rows = [
        (
            item.get("url", ""),
            item.get("title", ""),
            item.get("description", ""),
        )
        for item in data.get("web", {}).get("results", [])[:10]
    ]
    ai_candidates = await _ai_pick_search_candidates(rows, domain)
    if ai_candidates:
        return ai_candidates
    return _pick_search_candidates(rows, domain)


async def debug_brave_search_candidates(client: httpx.AsyncClient, domain: str) -> dict:
    domain = _canonical_search_domain(domain)
    query = f"{domain} privacy policy"
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return {"query": query, "ai_candidates": [], "heuristic_candidates": [], "raw_results": []}

    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": query,
                "count": 10,
                "country": os.getenv("SEARCH_COUNTRY", "US"),
                "search_lang": os.getenv("SEARCH_LANG", "en"),
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        data = resp.json() if resp.status_code == 200 else {}
    except Exception:
        data = {}

    rows = [
        (
            item.get("url", ""),
            item.get("title", ""),
            item.get("description", ""),
        )
        for item in data.get("web", {}).get("results", [])[:10]
    ]
    return {
        "query": query,
        "ai_candidates": await _ai_pick_search_candidates(rows, domain),
        "heuristic_candidates": _pick_search_candidates(rows, domain),
        "raw_results": [
            {"url": url, "title": title, "description": snippet}
            for url, title, snippet in rows
        ],
    }


async def _find_via_brave_search(client: httpx.AsyncClient, domain: str) -> List[str]:
    """
    Use Brave Search as an optional production search layer.

    We return candidates, not answers: each URL still goes through the normal
    fetch, extraction, Playwright fallback, and privacy-policy validation.
    """
    if not os.getenv("BRAVE_SEARCH_API_KEY"):
        return []

    domain = _canonical_search_domain(domain)
    queries = [
        f"{domain} privacy policy",
        f"site:{domain} privacy policy OR privacy notice OR gizlilik OR KVKK OR datenschutz",
    ]

    candidates: List[str] = []
    seen: Set[str] = set()
    for query in queries:
        for url in await _brave_search_query(client, query, domain):
            if url not in seen:
                seen.add(url)
                candidates.append(url)
        if candidates:
            break

    return candidates[:5]


async def _scan_sitemap_for_privacy(client: httpx.AsyncClient, sitemap_url: str, depth: int = 0) -> Optional[str]:
    if depth > 2:
        return None
    try:
        resp = await client.get(sitemap_url, follow_redirects=True, headers=BROWSER_HEADERS, timeout=10.0)
        if resp.status_code != 200:
            return None
        content = resp.text
        urls = re.findall(r'<loc>\s*(.*?)\s*</loc>', content, re.I)
        for u in urls:
            if _url_has_privacy_signal(u) and not _url_is_non_privacy_legal(u):
                return u.strip()
        if depth == 0:
            nested = re.findall(r'<sitemap>.*?<loc>\s*(.*?)\s*</loc>.*?</sitemap>', content, re.S | re.I)
            for nu in nested[:5]:
                found = await _scan_sitemap_for_privacy(client, nu.strip(), depth + 1)
                if found:
                    return found
    except Exception:
        pass
    return None


async def _find_via_sitemap(client: httpx.AsyncClient, base: str) -> Optional[str]:
    sitemap_urls: List[str] = []
    robots = await _fetch(client, base + "/robots.txt")
    if robots:
        _, txt, _, _ = robots
        sitemap_urls.extend(re.findall(r'(?i)^Sitemap:\s*(\S+)', txt, re.MULTILINE)[:5])

    sitemap_urls += [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/sitemap-index.xml"]
    for su in sitemap_urls:
        found = await _scan_sitemap_for_privacy(client, su)
        if found:
            return found
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Policy tree expansion
# ─────────────────────────────────────────────────────────────────────────────

def _discover_subpolicy_links(html: str, current_url: str, root_url: str, visited: Set[str]) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("main") or soup.find("article") or soup.body or soup
    found: List[Tuple[str, str, int]] = []

    for a in body.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(current_url, href).split("#", 1)[0]
        if not _same_registered_domain(full, root_url):
            continue
        if full in visited:
            continue
        if _looks_like_product_or_listing_url(full):
            continue
        if _url_is_non_privacy_legal(full) or _url_is_interstitial(full):
            continue

        label = re.sub(r"\s+", " ", a.get_text(separator=" ", strip=True))[:160]
        blob = f"{label} {href} {full}"
        if not SUBPOLICY_HINT_RE.search(blob):
            continue

        score = 0
        if _url_has_privacy_signal(full):
            score += 4
        if SUBPOLICY_HINT_RE.search(label):
            score += 3
        if "cookie" in blob.lower() or "çerez" in blob.lower() or "cerez" in blob.lower():
            score += 2

        found.append((full, label or "sub-policy", score))

    found.sort(key=lambda x: (-x[2], len(x[0])))
    return [(u, lbl) for u, lbl, _ in found[:MAX_SUBPOLICY_FETCHES]]


async def _accept_candidate_with_fallback(
    client: httpx.AsyncClient,
    requested_url: str,
    *,
    render_on_fetch_fail: bool = False,
    allow_reader_fallback: bool = False,
) -> Optional[Tuple[str, str, str]]:
    """
    Returns (accepted_url, final_html, extracted_text) if a candidate is accepted.
    """
    static = await _fetch(client, requested_url)
    if not static:
        if render_on_fetch_fail and _url_has_privacy_signal(requested_url):
            rendered = await _render_with_playwright(requested_url)
            if rendered:
                dyn_final_url, dyn_html = rendered
                dyn_valid, dyn_text = await _smart_validate(
                    dyn_final_url,
                    dyn_html,
                    original_url=requested_url,
                )
                if dyn_valid:
                    accepted = (
                        requested_url
                        if dyn_final_url != requested_url and _url_has_privacy_signal(requested_url)
                        else dyn_final_url
                    )
                    return accepted, dyn_html, dyn_text
        if allow_reader_fallback or _url_has_privacy_signal(requested_url):
            reader_text = await _fetch_reader_text(client, requested_url)
            if reader_text:
                reader_valid, reader_extracted = await _smart_validate(
                    requested_url,
                    reader_text,
                    original_url=requested_url,
                )
                if reader_valid:
                    return requested_url, "", reader_extracted
        return None

    final_url, html, _, _ = static
    valid, text = await _smart_validate(final_url, html, original_url=requested_url)

    if valid:
        accepted = requested_url if (final_url != requested_url and _url_has_privacy_signal(requested_url)) else final_url
        return accepted, html, text

    # Dynamic fallback for:
    # - strong privacy URL but empty / JS-heavy text
    # - likely privacy path with shell/static failure
    if _url_has_privacy_signal(final_url) or _url_has_privacy_signal(requested_url):
        rendered = await _render_with_playwright(final_url)
        if rendered:
            dyn_final_url, dyn_html = rendered
            dyn_valid, dyn_text = await _smart_validate(dyn_final_url, dyn_html, original_url=requested_url)

            if dyn_valid:
                accepted = requested_url if (dyn_final_url != requested_url and _url_has_privacy_signal(requested_url)) else dyn_final_url
                return accepted, dyn_html, dyn_text

    reader_target = final_url if _url_has_privacy_signal(final_url) else requested_url
    if allow_reader_fallback or _url_has_privacy_signal(reader_target):
        reader_text = await _fetch_reader_text(client, reader_target)
        if reader_text:
            reader_valid, reader_extracted = await _smart_validate(
                reader_target,
                reader_text,
                original_url=requested_url,
            )
            if reader_valid:
                accepted = (
                    requested_url
                    if reader_target != requested_url and _url_has_privacy_signal(requested_url)
                    else reader_target
                )
                return accepted, "", reader_extracted

    return None


async def fetch_policy_tree(
    client: httpx.AsyncClient,
    root_policy_url: str,
    *,
    root_html: Optional[str] = None,
    root_text: Optional[str] = None,
) -> PolicyTreeResult:
    root_html = root_html or ""
    root_text = root_text or _extract_best_text(root_html)

    parts = [f"=== MAIN PRIVACY POLICY ({root_policy_url}) ===\n{root_text}"]
    sub_pages: List[Tuple[str, str]] = []

    visited: Set[str] = {root_policy_url}
    seen_policy_families: Set[str] = {_policy_family_key(root_policy_url)}

    if not root_html:
        fetched = await _fetch(client, root_policy_url)
        if not fetched:
            return PolicyTreeResult(stitched_text="\n".join(parts), sub_pages=[])
        _, root_html, _, _ = fetched
        root_text = root_text or _extract_best_text(root_html)

    sub_links = _discover_subpolicy_links(root_html, root_policy_url, root_policy_url, visited)

    for sub_url, label in sub_links:
        visited.add(sub_url)
        accepted = await _accept_candidate_with_fallback(client, sub_url)
        if not accepted:
            continue

        accepted_url, _sub_html, extracted_text = accepted
        if not extracted_text.strip():
            continue

        family_key = _policy_family_key(accepted_url)
        if family_key in seen_policy_families:
            continue

        if _is_alternate_language_copy(
            candidate_url=accepted_url,
            label=label,
            candidate_text=extracted_text,
            root_url=root_policy_url,
            root_text=root_text or "",
        ):
            continue

        seen_policy_families.add(family_key)
        sub_pages.append((accepted_url, label))
        parts.append(f"\n\n=== SUB-POLICY: {label} ({accepted_url}) ===\n{extracted_text}")

    return PolicyTreeResult(stitched_text="".join(parts), sub_pages=sub_pages)


# ─────────────────────────────────────────────────────────────────────────────
# Main crawl entry point
# ─────────────────────────────────────────────────────────────────────────────

async def crawl_website(url: str) -> CrawlResult:
    result = CrawlResult()
    url = normalize_url(url)
    base = base_url(url)
    domain = extract_domain(base)

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        verify=True,
        limits=httpx.Limits(max_keepalive_connections=5),
        follow_redirects=True,
    ) as client:

        privacy_url: Optional[str] = None
        accepted_html: Optional[str] = None
        extracted_text: Optional[str] = None
        brave_attempted = False
        known_urls = _lookup_known_policies(domain)
        known_attempted = False

        # 1) Known policy URL shortcuts for large sites with non-obvious paths.
        # This avoids Brave returning random third-party docs for famous sites.
        if known_urls:
            known_attempted = True
            for known_url in known_urls:
                result.fetch_attempts.append(known_url)
                accepted = await _accept_candidate_with_fallback(
                    client,
                    known_url,
                )
                if accepted:
                    privacy_url, accepted_html, extracted_text = accepted
                    result.discovery_method = "known_url"
                    break

        # 2) Brave Search for everything else: search "site + privacy policy",
        # then use the top same-domain privacy-looking result.
        if not privacy_url and not known_attempted:
            for candidate in await _find_via_brave_search(client, domain):
                result.fetch_attempts.append(candidate)
                accepted = await _accept_candidate_with_fallback(
                    client,
                    candidate,
                    allow_reader_fallback=True,
                )
                if accepted:
                    privacy_url, accepted_html, extracted_text = accepted
                    result.discovery_method = "brave_search"
                    brave_attempted = True
                    break

        # Fetch the homepage only when policy discovery still needs local
        # links. This avoids slow/blocking homepages delaying known URL hits.
        if not privacy_url and not known_attempted and not brave_attempted:
            homepage = await _fetch(client, base)
            if homepage:
                _, result.homepage_html, result.homepage_cookies, _ = homepage
            else:
                parsed = urlparse(base)
                if parsed.netloc and not parsed.netloc.startswith("www."):
                    www_base = f"{parsed.scheme}://www.{parsed.netloc}"
                    homepage = await _fetch(client, www_base)
                    if homepage:
                        base = www_base
                        domain = extract_domain(base)
                        _, result.homepage_html, result.homepage_cookies, _ = homepage

                # fallback: if the root cannot be fetched, use the original URL
                if not homepage:
                    homepage = await _fetch(client, url)
                    if homepage:
                        _, result.homepage_html, result.homepage_cookies, _ = homepage

        # 3) Homepage link discovery
        if not privacy_url and result.homepage_html:
            link = await _find_privacy_link_in_html(result.homepage_html, base)
            if link:
                accepted = await _accept_candidate_with_fallback(
                    client,
                    link,
                    render_on_fetch_fail=True,
                )
                if accepted:
                    privacy_url, accepted_html, extracted_text = accepted
                    result.discovery_method = "link_scan"

        # 4) Canonical path probing
        if not privacy_url and not known_attempted and not brave_attempted:
            for path in PRIVACY_PATHS:
                candidate = base + path
                result.fetch_attempts.append(candidate)
                accepted = await _accept_candidate_with_fallback(client, candidate)
                if accepted:
                    privacy_url, accepted_html, extracted_text = accepted
                    result.discovery_method = "canonical_path"
                    break
                await asyncio.sleep(0.1)

        # 5) Sitemap discovery
        if not privacy_url and not known_attempted and not brave_attempted:
            link = await _find_via_sitemap(client, base)
            if link:
                accepted = await _accept_candidate_with_fallback(
                    client,
                    link,
                    render_on_fetch_fail=True,
                )
                if accepted:
                    privacy_url, accepted_html, extracted_text = accepted
                    result.discovery_method = "sitemap"

        # Curated known URLs are reliable enough to return as "found" even
        # when a site blocks static fetching and Playwright is unavailable.
        # The API will surface this as a found-but-unreadable policy instead
        # of hanging or incorrectly saying no policy exists.
        if not privacy_url and (known_attempted and known_urls):
            privacy_url = known_urls[0]
            accepted_html = ""
            extracted_text = ""
            result.discovery_method = "known_url"

        if privacy_url:
            result.policy_url = privacy_url
            result.policy_html = accepted_html or ""
            result.policy_found = True

            if accepted_html or extracted_text:
                tree = await fetch_policy_tree(
                    client,
                    privacy_url,
                    root_html=accepted_html,
                    root_text=extracted_text or "",
                )
                result.policy_text = tree.stitched_text if tree.stitched_text.strip() else (extracted_text or "")
            else:
                result.policy_text = ""
            result.word_count = len(result.policy_text.split()) if result.policy_text else 0
        else:
            result.error = "Privacy policy not found via known URLs, link scan, Brave Search, canonical paths, or sitemap."

    return result
