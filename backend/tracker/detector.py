"""
Tracker & Cookie Detection Engine
Performs static analysis of a webpage's HTML to identify:
 - Third-party script sources (matched against tracker database)
 - Tracking pixels (1×1 images, beacons)
 - Cookie headers and their security attributes
 - Inline script fingerprinting patterns
 - Consent Management Platform presence
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# Load tracker database
# ─────────────────────────────────────────────────────────────────────────────

_DB_PATH = os.path.join(os.path.dirname(__file__), "databases", "trackers.json")

def _load_tracker_db() -> tuple[Dict, Dict]:
    try:
        with open(_DB_PATH) as f:
            data = json.load(f)
        trackers = {t["domain"]: t for t in data["trackers"]}
        categories = data.get("categories", {})
        return trackers, categories
    except Exception:
        return {}, {}

TRACKER_DB, TRACKER_CATEGORIES = _load_tracker_db()

# ─────────────────────────────────────────────────────────────────────────────
# Fingerprinting patterns in inline scripts
# ─────────────────────────────────────────────────────────────────────────────

FINGERPRINTING_SIGNALS = [
    # Canvas fingerprinting
    r"canvas\.toDataURL",
    r"getImageData",
    r"HTMLCanvasElement",
    # AudioContext fingerprinting
    r"AudioContext\(\)",
    r"webkitAudioContext",
    r"createOscillator",
    r"createAnalyser",
    # WebGL fingerprinting
    r"WebGLRenderingContext",
    r"getParameter\s*\(\s*(?:RENDERER|VENDOR|VERSION)",
    r"getSupportedExtensions",
    # Font enumeration
    r"document\.fonts\.check",
    r"measureText\b",
    # Navigator probing
    r"navigator\.plugins\b",
    r"navigator\.mimeTypes\b",
    r"navigator\.hardwareConcurrency",
    r"navigator\.deviceMemory",
    # Battery API
    r"navigator\.getBattery",
    # Screen details
    r"screen\.colorDepth",
    r"screen\.pixelDepth",
    # Network info
    r"navigator\.connection\.",
    # FingerprintJS library signals
    r"FingerprintJS",
    r"Fingerprint2",
    r"fingerprintjs",
    r"getFingerprint\b",
    r"visitorId",
]

# ─────────────────────────────────────────────────────────────────────────────
# Session recording patterns
# ─────────────────────────────────────────────────────────────────────────────

SESSION_RECORDING_SIGNALS = [
    r"hj\.q\b",           # Hotjar
    r"_hj\b",             # Hotjar
    r"FS\.identify",      # FullStory
    r"window\['_fs_",     # FullStory
    r"LR\.identify",      # LogRocket
    r"window\.LogRocket", # LogRocket
    r"clarity\(",         # Microsoft Clarity
    r"smartlook\.",       # Smartlook
    r"mouseflow\.",       # Mouseflow
]

# ─────────────────────────────────────────────────────────────────────────────
# Consent Management Platform detection
# ─────────────────────────────────────────────────────────────────────────────

CMP_SIGNALS = {
    "OneTrust": [r"onetrust", r"optanon", r"cookielawscript"],
    "Cookiebot": [r"cookiebot", r"consent\.cookiebot"],
    "TrustArc": [r"trustarc", r"truste\.com"],
    "Osano": [r"osano\.com"],
    "Consentmanager": [r"consentmanager\.net"],
    "Quantcast Choice": [r"quantcast\.com.*consent"],
    "GDPR Cookie Notice": [r"gdpr-cookie-notice"],
    "Cookie Information": [r"cookieinformation\.com"],
    "Usercentrics": [r"usercentrics"],
    "Didomi": [r"sdk\.privacy-center\.org", r"didomi"],
    "Termly": [r"termly\.io"],
    "Iubenda": [r"iubenda\.com"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DetectedTracker:
    domain: str
    name: str
    category: str
    risk: str
    source_type: str        # "script" | "pixel" | "iframe" | "inline"
    url: str
    fingerprinting: bool
    session_recording: bool
    opt_out: Optional[str]
    description: str


@dataclass
class CookieInfo:
    name: str
    value_preview: str      # first 20 chars of value
    httponly: bool
    secure: bool
    samesite: Optional[str]
    path: str
    domain: Optional[str]
    max_age: Optional[int]  # seconds
    category: str           # "necessary" | "analytics" | "advertising" | "functional" | "unknown"
    duration_label: str     # "session" | "persistent" | specific


@dataclass
class TrackerDetectionResult:
    trackers: List[DetectedTracker]
    total_tracker_count: int
    by_category: Dict[str, int]
    high_risk_count: int
    fingerprinting_detected: bool
    fingerprinting_evidence: List[str]
    session_recording_detected: bool
    session_recording_evidence: List[str]
    cookies: List[CookieInfo]
    cookie_security: Dict[str, float]  # percentage with each flag
    cmp_detected: Optional[str]         # name of CMP if found
    inline_tracker_signals: List[str]
    unique_third_party_domains: List[str]
    privacy_sandbox_detected: bool


# ─────────────────────────────────────────────────────────────────────────────
# Core detection logic
# ─────────────────────────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.split(":", 1)[0].lower().strip(".")
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _match_tracker(domain: str) -> Optional[Dict]:
    """Match a domain against tracker DB, checking domain and parent domains."""
    if domain in TRACKER_DB:
        return TRACKER_DB[domain]
    # Try parent domains
    parts = domain.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in TRACKER_DB:
            return TRACKER_DB[parent]
    return None


def _categorize_cookie(name: str, domain: Optional[str]) -> str:
    name_lower = name.lower()
    domain_lower = (domain or "").lower()

    # Necessary/functional cookies
    necessary_names = {"sessionid", "session", "csrftoken", "csrf", "phpsessid", "jsessionid", "asp.net_sessionid", "auth", "token", "__host-", "secure-"}
    if any(name_lower.startswith(n) or name_lower == n for n in necessary_names):
        return "necessary"

    # Analytics cookies
    analytics_names = {"_ga", "_gid", "_gat", "mp_", "__hssc", "__hssrc", "__hstc", "_hjid", "_hjsessionuser", "amplitude", "ajs_"}
    if any(name_lower.startswith(n) for n in analytics_names):
        return "analytics"
    if domain_lower and any(d in domain_lower for d in ["google-analytics", "hotjar", "mixpanel", "amplitude"]):
        return "analytics"

    # Advertising cookies
    ad_names = {"_fbp", "_fbc", "fr", "__gads", "__gac", "nid", "sid", "1p_jar", "ide", "dsid", "dsp_uid", "uid", "criteo", "adrl"}
    if any(name_lower.startswith(n) or name_lower == n for n in ad_names):
        return "advertising"
    if domain_lower and any(d in domain_lower for d in ["doubleclick", "facebook", "criteo", "adroll"]):
        return "advertising"

    return "unknown"


def detect_trackers_from_html(
    html: str,
    page_domain: str,
    cookies_raw: List[str],
) -> TrackerDetectionResult:
    """
    Analyze raw HTML and cookie headers to detect trackers.
    """
    soup = BeautifulSoup(html, "lxml")
    html_lower = html.lower()

    detected: List[DetectedTracker] = []
    third_party_domains: Set[str] = set()
    fp_evidence: List[str] = []
    sr_evidence: List[str] = []

    # ── Script tags ───────────────────────────────────────────────────────────
    for script in soup.find_all("script", src=True):
        src = script.get("src", "")
        if not src:
            continue
        domain = _extract_domain(src)
        if not domain or domain == page_domain or f".{page_domain}" in domain:
            continue

        third_party_domains.add(domain)
        tracker = _match_tracker(domain)
        if tracker:
            detected.append(DetectedTracker(
                domain=domain,
                name=tracker["name"],
                category=tracker["category"],
                risk=tracker["risk"],
                source_type="script",
                url=src[:200],
                fingerprinting=tracker.get("fingerprinting", False),
                session_recording=tracker.get("session_recording", False),
                opt_out=tracker.get("opt_out"),
                description=tracker.get("description", ""),
            ))

    # ── Image pixels (tracking beacons) ───────────────────────────────────────
    for img in soup.find_all("img"):
        src = img.get("src", "")
        width = img.get("width", "")
        height = img.get("height", "")
        is_pixel = (str(width) in {"1", "0"} and str(height) in {"1", "0"}) or \
                   any(s in src.lower() for s in ["pixel", "beacon", "track", "1x1"])
        if not src or not is_pixel:
            continue
        domain = _extract_domain(src)
        if not domain or domain == page_domain:
            continue
        third_party_domains.add(domain)
        tracker = _match_tracker(domain)
        if tracker:
            detected.append(DetectedTracker(
                domain=domain,
                name=tracker["name"],
                category=tracker["category"],
                risk=tracker["risk"],
                source_type="pixel",
                url=src[:200],
                fingerprinting=False,
                session_recording=False,
                opt_out=tracker.get("opt_out"),
                description=tracker.get("description", ""),
            ))
        else:
            detected.append(DetectedTracker(
                domain=domain,
                name=f"Unknown pixel ({domain})",
                category="Advertising / Analytics",
                risk="medium",
                source_type="pixel",
                url=src[:200],
                fingerprinting=False,
                session_recording=False,
                opt_out=None,
                description="Unidentified tracking pixel.",
            ))

    # ── iFrame sources ─────────────────────────────────────────────────────────
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if not src:
            continue
        domain = _extract_domain(src)
        if not domain or domain == page_domain:
            continue
        third_party_domains.add(domain)
        tracker = _match_tracker(domain)
        if tracker:
            detected.append(DetectedTracker(
                domain=domain,
                name=tracker["name"],
                category=tracker["category"],
                risk=tracker["risk"],
                source_type="iframe",
                url=src[:200],
                fingerprinting=tracker.get("fingerprinting", False),
                session_recording=False,
                opt_out=tracker.get("opt_out"),
                description=tracker.get("description", ""),
            ))

    # ── Inline script analysis ─────────────────────────────────────────────────
    inline_signals: List[str] = []
    fp_detected = False
    sr_detected = False

    for script in soup.find_all("script", src=False):
        content = script.get_text() or ""
        for pattern in FINGERPRINTING_SIGNALS:
            if re.search(pattern, content):
                fp_detected = True
                fp_evidence.append(f"Pattern `{pattern}` found in inline script")
                break
        for pattern in SESSION_RECORDING_SIGNALS:
            if re.search(pattern, content):
                sr_detected = True
                sr_evidence.append(f"Session recording pattern found: `{pattern[:40]}`")
                break

        # Additional inline signal checks against tracker patterns
        for domain, tracker in TRACKER_DB.items():
            if domain.replace(".", r"\.") and domain in content:
                inline_signals.append(f"Reference to {tracker['name']} in inline script")

    # ── Fingerprinting from known domains ──────────────────────────────────────
    for d in detected:
        if d.fingerprinting:
            fp_detected = True
            fp_evidence.append(f"Known fingerprinting service: {d.name}")
        if d.session_recording:
            sr_detected = True
            sr_evidence.append(f"Known session recorder: {d.name}")

    # ── CMP detection ──────────────────────────────────────────────────────────
    cmp_name = None
    for cmp, signals in CMP_SIGNALS.items():
        if any(re.search(s, html_lower) for s in signals):
            cmp_name = cmp
            break

    # ── Privacy Sandbox signals ───────────────────────────────────────────────
    privacy_sandbox = bool(re.search(
        r"attribution-reporting|fledge|topics-api|privacy.sandbox|pa\.js",
        html_lower,
    ))

    # ── Cookie analysis ────────────────────────────────────────────────────────
    cookies: List[CookieInfo] = []
    for cookie_str in cookies_raw:
        parts = [p.strip() for p in cookie_str.split(";")]
        if not parts:
            continue
        name_val = parts[0].split("=", 1)
        name = name_val[0].strip() if name_val else "unknown"
        value = name_val[1][:20] + "…" if len(name_val) > 1 and name_val[1] else ""

        attrs = {p.lower().split("=")[0].strip(): (p.split("=", 1)[1].strip() if "=" in p else True)
                 for p in parts[1:]}
        httponly = "httponly" in attrs
        secure = "secure" in attrs
        samesite = attrs.get("samesite")
        if isinstance(samesite, bool):
            samesite = "Lax"

        max_age_raw = attrs.get("max-age")
        max_age = None
        if max_age_raw and str(max_age_raw).lstrip("-").isdigit():
            max_age = int(max_age_raw)

        if max_age is None:
            duration = "session"
        elif max_age <= 0:
            duration = "deleted"
        elif max_age <= 86400:
            duration = "≤1 day"
        elif max_age <= 604800:
            duration = "≤1 week"
        elif max_age <= 2592000:
            duration = "≤30 days"
        elif max_age <= 31536000:
            duration = "≤1 year"
        else:
            duration = f"{max_age // 31536000}+ years"

        cookie_domain = attrs.get("domain") or None
        if isinstance(cookie_domain, bool):
            cookie_domain = None

        cookies.append(CookieInfo(
            name=name,
            value_preview=value,
            httponly=httponly,
            secure=secure,
            samesite=str(samesite) if samesite else None,
            path=str(attrs.get("path", "/")),
            domain=cookie_domain,
            max_age=max_age,
            category=_categorize_cookie(name, cookie_domain),
            duration_label=duration,
        ))

    # ── Cookie security metrics ────────────────────────────────────────────────
    total_cookies = len(cookies)
    if total_cookies > 0:
        cookie_security = {
            "httponly_pct": round(sum(1 for c in cookies if c.httponly) / total_cookies * 100, 1),
            "secure_pct": round(sum(1 for c in cookies if c.secure) / total_cookies * 100, 1),
            "samesite_pct": round(sum(1 for c in cookies if c.samesite) / total_cookies * 100, 1),
        }
    else:
        cookie_security = {"httponly_pct": 0.0, "secure_pct": 0.0, "samesite_pct": 0.0}

    # ── Summary stats ──────────────────────────────────────────────────────────
    by_category: Dict[str, int] = {}
    for t in detected:
        by_category[t.category] = by_category.get(t.category, 0) + 1

    high_risk = sum(1 for t in detected if t.risk in {"high", "critical"})

    # Dedup: keep first occurrence per domain
    seen_domains: Set[str] = set()
    unique_detected: List[DetectedTracker] = []
    for t in detected:
        if t.domain not in seen_domains:
            seen_domains.add(t.domain)
            unique_detected.append(t)

    return TrackerDetectionResult(
        trackers=unique_detected,
        total_tracker_count=len(unique_detected),
        by_category=by_category,
        high_risk_count=high_risk,
        fingerprinting_detected=fp_detected,
        fingerprinting_evidence=list(set(fp_evidence))[:5],
        session_recording_detected=sr_detected,
        session_recording_evidence=list(set(sr_evidence))[:5],
        cookies=cookies[:50],  # cap
        cookie_security=cookie_security,
        cmp_detected=cmp_name,
        inline_tracker_signals=list(set(inline_signals))[:10],
        unique_third_party_domains=sorted(third_party_domains)[:50],
        privacy_sandbox_detected=privacy_sandbox,
    )
