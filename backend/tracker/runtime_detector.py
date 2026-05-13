"""
Single-load runtime tracker and cookie detector.

This is the browser-observed source of truth for tracker/cookie detection:
open a fresh Playwright context, capture network requests and response cookies,
then summarize those events into the legacy TrackerDetectionResult shape.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qsl, urlparse

import tldextract
from playwright.async_api import Request, Response, async_playwright

from tracker.detector import (
    CMP_SIGNALS,
    FINGERPRINTING_SIGNALS,
    SESSION_RECORDING_SIGNALS,
    CookieInfo,
    DetectedTracker,
    TrackerDetectionResult,
    _categorize_cookie,
    _match_tracker,
)

TLD_EXTRACTOR = tldextract.TLDExtract(
    suffix_list_urls=(),
    fallback_to_snapshot=True,
    cache_dir="/private/tmp/tldextract-cache",
)


TRACKING_PATH_HINTS = re.compile(
    r"(pixel|beacon|collect|track|tracking|analytics|telemetry|conversion|remarket|retarget|ads?|"
    r"measure|event|tr|gtag|fbevents|bat\.bing)",
    re.IGNORECASE,
)

TRACKING_QUERY_KEYS = {
    "cid",
    "uid",
    "userid",
    "user_id",
    "visitorid",
    "visitor_id",
    "client_id",
    "fbclid",
    "gclid",
    "msclkid",
    "ttclid",
    "twclid",
    "mc_cid",
    "campaignid",
    "adid",
}

COOKIE_DURATION_BUCKETS = [
    (0, "deleted"),
    (86400, "<=1 day"),
    (604800, "<=1 week"),
    (2592000, "<=30 days"),
    (31536000, "<=1 year"),
]


@dataclass
class TrackerEvent:
    url: str
    domain: str
    etld1: Optional[str]
    vendor: Optional[str]
    category: str
    risk: str
    resource_type: str
    source: str
    evidence: str
    fingerprinting: bool = False
    session_recording: bool = False
    opt_out: Optional[str] = None
    description: str = ""
    known: bool = False


@dataclass
class CookieEvent:
    name: str
    domain: Optional[str]
    etld1: Optional[str]
    first_party: bool
    category: str
    value_preview: str
    secure: bool
    httponly: bool
    samesite: Optional[str]
    expires: Optional[float]
    duration_label: str
    source: str
    matched_vendor: Optional[str] = None
    evidence: str = ""


@dataclass
class VendorSummary:
    domain: str
    name: str
    category: str
    risk: str
    request_count: int
    resource_types: List[str]
    sample_url: str
    fingerprinting: bool = False
    session_recording: bool = False
    known: bool = False


@dataclass
class RuntimeDetectionResult:
    url: str
    final_url: str
    first_party_etld1: Optional[str]
    total_requests: int
    third_party_request_count: int
    tracker_events: List[TrackerEvent]
    cookie_events: List[CookieEvent]
    vendors: List[VendorSummary]
    total_tracker_count: int
    total_cookie_count: int
    third_party_cookie_count: int
    by_category: Dict[str, int]
    cmp_detected: Optional[str]
    fingerprinting_detected: bool
    fingerprinting_evidence: List[str]
    session_recording_detected: bool
    session_recording_evidence: List[str]
    privacy_sandbox_detected: bool
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _host(url: str) -> Optional[str]:
    try:
        host = (urlparse(url).hostname or "").lower().strip(".")
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def _etld1(hostname: Optional[str]) -> Optional[str]:
    if not hostname:
        return None
    ext = TLD_EXTRACTOR(hostname)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    parts = [part for part in hostname.split(".") if part]
    if len(parts) >= 2:
        return ".".join(parts[-2:]).lower()
    return hostname.lower() if hostname else None


def _is_first_party(hostname: Optional[str], first_party_etld1: Optional[str]) -> bool:
    if not hostname or not first_party_etld1:
        return False
    return _etld1(hostname) == first_party_etld1


def _query_has_tracking_ids(url: str) -> bool:
    try:
        query = parse_qsl(urlparse(url).query, keep_blank_values=True)
    except Exception:
        return False
    return any(key.lower() in TRACKING_QUERY_KEYS for key, _ in query)


def _looks_like_tracking_request(url: str, resource_type: str) -> bool:
    parsed = urlparse(url)
    path_and_query = f"{parsed.path}?{parsed.query}"
    if TRACKING_PATH_HINTS.search(path_and_query):
        return True
    if _query_has_tracking_ids(url):
        return True
    if resource_type in {"image", "beacon"} and TRACKING_PATH_HINTS.search(url):
        return True
    return False


def _duration_label(expires: Optional[float]) -> str:
    if not expires or expires < 0:
        return "session"

    # Playwright exposes expires as seconds since epoch. We avoid wall-clock
    # subtraction here because tests and browser clocks can vary; the label is
    # only a coarse persistence signal.
    if expires == 0:
        return "deleted"
    return "persistent"


def _cookie_duration_from_max_age(max_age: Optional[int]) -> str:
    if max_age is None:
        return "session"
    for seconds, label in COOKIE_DURATION_BUCKETS:
        if max_age <= seconds:
            return label
    return f"{max_age // 31536000}+ years"


def _parse_set_cookie_header(raw: str, request_url: str, first_party_etld1: Optional[str]) -> List[CookieEvent]:
    events: List[CookieEvent] = []
    if not raw:
        return events

    # Playwright may return multiple Set-Cookie headers joined by newlines.
    # We intentionally do not split on commas; Expires contains commas.
    for cookie_str in [part.strip() for part in raw.split("\n") if part.strip()]:
        pieces = [piece.strip() for piece in cookie_str.split(";") if piece.strip()]
        if not pieces or "=" not in pieces[0]:
            continue

        name, value = pieces[0].split("=", 1)
        attrs: Dict[str, Any] = {}
        for piece in pieces[1:]:
            if "=" in piece:
                key, attr_value = piece.split("=", 1)
                attrs[key.lower().strip()] = attr_value.strip()
            else:
                attrs[piece.lower().strip()] = True

        response_host = _host(request_url)
        domain = attrs.get("domain")
        if isinstance(domain, str):
            domain = domain.lower().lstrip(".")
        else:
            domain = response_host

        max_age = None
        raw_max_age = attrs.get("max-age")
        if isinstance(raw_max_age, str) and raw_max_age.lstrip("-").isdigit():
            max_age = int(raw_max_age)

        etld1 = _etld1(domain)
        tracker = _match_tracker(domain or "") if domain else None
        events.append(CookieEvent(
            name=name.strip(),
            domain=domain,
            etld1=etld1,
            first_party=bool(etld1 and first_party_etld1 and etld1 == first_party_etld1),
            category=_categorize_cookie(name, domain),
            value_preview=(value[:20] + "…") if len(value) > 20 else value,
            secure="secure" in attrs,
            httponly="httponly" in attrs,
            samesite=str(attrs.get("samesite")) if attrs.get("samesite") else None,
            expires=None,
            duration_label=_cookie_duration_from_max_age(max_age),
            source="set_cookie_header",
            matched_vendor=tracker.get("name") if tracker else None,
            evidence=f"Set-Cookie on response from {response_host or 'unknown host'}",
        ))

    return events


def _cookie_event_from_browser_cookie(cookie: Dict[str, Any], first_party_etld1: Optional[str]) -> CookieEvent:
    domain = str(cookie.get("domain") or "").lower().lstrip(".") or None
    etld1 = _etld1(domain)
    tracker = _match_tracker(domain or "") if domain else None
    value = str(cookie.get("value") or "")
    return CookieEvent(
        name=str(cookie.get("name") or ""),
        domain=domain,
        etld1=etld1,
        first_party=bool(etld1 and first_party_etld1 and etld1 == first_party_etld1),
        category=_categorize_cookie(str(cookie.get("name") or ""), domain),
        value_preview=(value[:20] + "…") if len(value) > 20 else value,
        secure=bool(cookie.get("secure")),
        httponly=bool(cookie.get("httpOnly")),
        samesite=str(cookie.get("sameSite")) if cookie.get("sameSite") else None,
        expires=cookie.get("expires") if isinstance(cookie.get("expires"), (int, float)) else None,
        duration_label=_duration_label(cookie.get("expires") if isinstance(cookie.get("expires"), (int, float)) else None),
        source="browser_cookie_jar",
        matched_vendor=tracker.get("name") if tracker else None,
        evidence="Cookie present in browser jar after page load",
    )


def _detect_inline_signals(html: str) -> tuple[bool, List[str], bool, List[str], Optional[str], bool]:
    html_lower = html.lower()
    fp_evidence: List[str] = []
    sr_evidence: List[str] = []

    for pattern in FINGERPRINTING_SIGNALS:
        if re.search(pattern, html):
            fp_evidence.append(f"Fingerprinting pattern in rendered HTML: {pattern}")
            break

    for pattern in SESSION_RECORDING_SIGNALS:
        if re.search(pattern, html):
            sr_evidence.append(f"Session recording pattern in rendered HTML: {pattern}")
            break

    cmp_name = None
    for cmp, signals in CMP_SIGNALS.items():
        if any(re.search(signal, html_lower) for signal in signals):
            cmp_name = cmp
            break

    privacy_sandbox = bool(re.search(
        r"attribution-reporting|fledge|topics-api|privacy.sandbox|pa\.js",
        html_lower,
    ))

    return bool(fp_evidence), fp_evidence, bool(sr_evidence), sr_evidence, cmp_name, privacy_sandbox


def _build_tracker_events(
    request_rows: List[Dict[str, str]],
    first_party_etld1: Optional[str],
) -> List[TrackerEvent]:
    events: List[TrackerEvent] = []

    for row in request_rows:
        url = row.get("url", "")
        host = _host(url)
        if not host or _is_first_party(host, first_party_etld1):
            continue

        resource_type = row.get("resource_type") or "unknown"
        etld1 = _etld1(host)
        tracker = _match_tracker(host)

        if tracker:
            events.append(TrackerEvent(
                url=url[:500],
                domain=host,
                etld1=etld1,
                vendor=tracker.get("name") or host,
                category=tracker.get("category") or "Unknown",
                risk=tracker.get("risk") or "medium",
                resource_type=resource_type,
                source="network_request",
                evidence=f"{resource_type} request to known tracker domain {host}",
                fingerprinting=bool(tracker.get("fingerprinting")),
                session_recording=bool(tracker.get("session_recording")),
                opt_out=tracker.get("opt_out"),
                description=tracker.get("description") or "",
                known=True,
            ))
        elif _looks_like_tracking_request(url, resource_type):
            events.append(TrackerEvent(
                url=url[:500],
                domain=host,
                etld1=etld1,
                vendor=None,
                category="Unknown third-party tracking",
                risk="medium",
                resource_type=resource_type,
                source="network_request_heuristic",
                evidence=f"{resource_type} request contains tracking-like path or identifiers",
                known=False,
            ))

    return events


def _summarize_vendors(events: List[TrackerEvent]) -> List[VendorSummary]:
    grouped: Dict[str, List[TrackerEvent]] = {}
    for event in events:
        key = event.etld1 or event.domain
        grouped.setdefault(key, []).append(event)

    summaries: List[VendorSummary] = []
    risk_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}
    for domain, items in grouped.items():
        primary = sorted(items, key=lambda item: risk_rank.get(item.risk, 0), reverse=True)[0]
        summaries.append(VendorSummary(
            domain=domain,
            name=primary.vendor or f"Unknown third party ({domain})",
            category=primary.category,
            risk=primary.risk,
            request_count=len(items),
            resource_types=sorted({item.resource_type for item in items}),
            sample_url=primary.url,
            fingerprinting=any(item.fingerprinting for item in items),
            session_recording=any(item.session_recording for item in items),
            known=any(item.known for item in items),
        ))

    return sorted(summaries, key=lambda item: (not item.known, -item.request_count, item.domain))


def _dedupe_cookie_events(events: List[CookieEvent]) -> List[CookieEvent]:
    seen: Set[tuple[str, Optional[str], str]] = set()
    out: List[CookieEvent] = []
    for event in events:
        key = (event.name, event.domain, event.source)
        if key in seen:
            continue
        seen.add(key)
        out.append(event)
    return out


async def detect_runtime_privacy_signals(
    url: str,
    timeout_ms: int = 25000,
    settle_ms: int = 2500,
) -> RuntimeDetectionResult:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    initial_host = _host(url)
    first_party_etld1 = _etld1(initial_host)
    request_rows: List[Dict[str, str]] = []
    cookie_events: List[CookieEvent] = []
    warnings: List[str] = []
    response_tasks: List[asyncio.Task] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        def on_request(request: Request) -> None:
            request_rows.append({
                "url": request.url,
                "resource_type": request.resource_type,
                "method": request.method,
            })

        async def handle_response(response: Response) -> None:
            try:
                set_cookie = await response.header_value("set-cookie")
            except Exception:
                set_cookie = None
            if set_cookie:
                cookie_events.extend(_parse_set_cookie_header(set_cookie, response.url, first_party_etld1))

        def on_response(response: Response) -> None:
            response_tasks.append(asyncio.create_task(handle_response(response)))

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                warnings.append("networkidle_timeout")
            await page.wait_for_timeout(settle_ms)
        except Exception as exc:
            warnings.append(f"navigation_error:{str(exc)[:160]}")

        final_url = page.url
        final_host = _host(final_url)
        final_first_party = _etld1(final_host)
        if final_first_party:
            first_party_etld1 = final_first_party

        try:
            html = await page.content()
        except Exception:
            html = ""

        if response_tasks:
            await asyncio.gather(*response_tasks, return_exceptions=True)

        try:
            for cookie in await context.cookies():
                cookie_events.append(_cookie_event_from_browser_cookie(cookie, first_party_etld1))
        except Exception as exc:
            warnings.append(f"cookie_read_error:{str(exc)[:120]}")

        await context.close()
        await browser.close()

    tracker_events = _build_tracker_events(request_rows, first_party_etld1)
    vendors = _summarize_vendors(tracker_events)
    cookie_events = _dedupe_cookie_events(cookie_events)

    inline_fp, fp_evidence, inline_sr, sr_evidence, cmp_name, privacy_sandbox = _detect_inline_signals(html)

    for vendor in vendors:
        if vendor.fingerprinting:
            fp_evidence.append(f"Known fingerprinting service observed at runtime: {vendor.name}")
        if vendor.session_recording:
            sr_evidence.append(f"Known session recording service observed at runtime: {vendor.name}")

    by_category: Dict[str, int] = {}
    for vendor in vendors:
        by_category[vendor.category] = by_category.get(vendor.category, 0) + 1

    third_party_request_count = 0
    for row in request_rows:
        host = _host(row.get("url", ""))
        if host and not _is_first_party(host, first_party_etld1):
            third_party_request_count += 1

    third_party_cookie_count = sum(1 for event in cookie_events if not event.first_party)

    return RuntimeDetectionResult(
        url=url,
        final_url=final_url,
        first_party_etld1=first_party_etld1,
        total_requests=len(request_rows),
        third_party_request_count=third_party_request_count,
        tracker_events=tracker_events,
        cookie_events=cookie_events,
        vendors=vendors,
        total_tracker_count=len(vendors),
        total_cookie_count=len(cookie_events),
        third_party_cookie_count=third_party_cookie_count,
        by_category=by_category,
        cmp_detected=cmp_name,
        fingerprinting_detected=bool(fp_evidence) or inline_fp,
        fingerprinting_evidence=sorted(set(fp_evidence))[:8],
        session_recording_detected=bool(sr_evidence) or inline_sr,
        session_recording_evidence=sorted(set(sr_evidence))[:8],
        privacy_sandbox_detected=privacy_sandbox,
        warnings=warnings,
    )


def runtime_to_tracker_detection_result(runtime: RuntimeDetectionResult) -> TrackerDetectionResult:
    trackers: List[DetectedTracker] = []
    for vendor in runtime.vendors:
        matching_event = next(
            (event for event in runtime.tracker_events if (event.etld1 or event.domain) == vendor.domain),
            None,
        )
        trackers.append(DetectedTracker(
            domain=vendor.domain,
            name=vendor.name,
            category=vendor.category,
            risk=vendor.risk if vendor.risk in {"low", "medium", "high", "critical"} else "medium",
            source_type=(matching_event.resource_type if matching_event else "network"),
            url=vendor.sample_url[:200],
            fingerprinting=vendor.fingerprinting,
            session_recording=vendor.session_recording,
            opt_out=matching_event.opt_out if matching_event else None,
            description=(matching_event.description if matching_event else "Observed at runtime."),
        ))

    cookies: List[CookieInfo] = []
    for event in runtime.cookie_events[:100]:
        cookies.append(CookieInfo(
            name=event.name,
            value_preview=event.value_preview,
            httponly=event.httponly,
            secure=event.secure,
            samesite=event.samesite,
            path="/",
            domain=event.domain,
            max_age=None,
            category=event.category,
            duration_label=event.duration_label,
        ))

    total_cookies = len(cookies)
    cookie_security = {
        "httponly_pct": round(sum(1 for c in cookies if c.httponly) / total_cookies * 100, 1) if total_cookies else 0.0,
        "secure_pct": round(sum(1 for c in cookies if c.secure) / total_cookies * 100, 1) if total_cookies else 0.0,
        "samesite_pct": round(sum(1 for c in cookies if c.samesite) / total_cookies * 100, 1) if total_cookies else 0.0,
    }

    high_risk_count = sum(1 for tracker in trackers if tracker.risk in {"high", "critical"})

    return TrackerDetectionResult(
        trackers=trackers,
        total_tracker_count=len(trackers),
        by_category=runtime.by_category,
        high_risk_count=high_risk_count,
        fingerprinting_detected=runtime.fingerprinting_detected,
        fingerprinting_evidence=runtime.fingerprinting_evidence,
        session_recording_detected=runtime.session_recording_detected,
        session_recording_evidence=runtime.session_recording_evidence,
        cookies=cookies,
        cookie_security=cookie_security,
        cmp_detected=runtime.cmp_detected,
        inline_tracker_signals=[],
        unique_third_party_domains=sorted({event.etld1 or event.domain for event in runtime.tracker_events})[:50],
        privacy_sandbox_detected=runtime.privacy_sandbox_detected,
    )
