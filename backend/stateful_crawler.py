from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import tldextract
from playwright.async_api import Page, async_playwright

from tracker.known_tracker_matcher import match_known_trackers_from_urls


ACCEPT_PATTERNS = [
    "accept all", "accept", "agree", "i agree", "allow all",
    "kabul", "kabul et", "tümünü kabul", "hepsini kabul", "onayla",
]

REJECT_PATTERNS = [
    "reject all", "reject", "decline", "deny", "refuse",
    "reddet", "tümünü reddet", "hepsini reddet", "kabul etmiyorum",
]

MANAGE_PATTERNS = [
    "manage", "preferences", "settings", "options",
    "tercih", "ayar", "seçenek", "yönet",
]

LOGIN_KEYWORDS = [
    "login", "log in", "sign in", "signin", "authenticate",
    "giriş", "oturum", "uye girisi", "üye girişi",
]

BLOCK_KEYWORDS = [
    "recaptcha", "hcaptcha", "g-recaptcha", "cf-challenge", "cloudflare",
    "verify you are human", "checking your browser", "access denied",
    "bot detection", "security check", "datadome", "arkoselabs",
]

CONSENT_STORAGE_KEYWORDS = [
    "consent", "cookie", "gdpr", "ccpa", "onetrust", "optanon", "cookiebot", "didomi", "trustarc", "euconsent",
]

CONSENT_COOKIE_NAME_HINTS = [
    "consent",
    "essential_cookie",
    "optanonconsent",
    "cookieconsent",
    "cookiebot",
    "didomi",
    "trustarc",
    "euconsent",
    "onetrust",
]

BANNER_VISIBLE_SELECTORS = [
    "#banner",
    "[id*='cookie' i]",
    "[class*='cookie' i]",
    "[id*='consent' i]",
    "[class*='consent' i]",
    "[id*='onetrust' i]",
    "[class*='onetrust' i]",
    "[aria-label*='cookie' i]",
    "[aria-label*='consent' i]",
    "[role='dialog']",
    "[role='alertdialog']",
]

BANNER_KEYWORDS = ["cookie", "consent", "çerez", "onetrust", "optanon", "cookiebot", "trustarc", "gdpr"]


def _host(url: str) -> Optional[str]:
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def _etld1(hostname: Optional[str]) -> Optional[str]:
    if not hostname:
        return None
    ext = tldextract.extract(hostname)
    if not ext.domain or not ext.suffix:
        parts = [part for part in hostname.split(".") if part]
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return hostname
    return f"{ext.domain}.{ext.suffix}"


def _is_consent_key(key: str) -> bool:
    key_lower = key.lower()
    return any(token in key_lower for token in CONSENT_STORAGE_KEYWORDS)


def _is_consent_or_essential_cookie_name(name: str) -> bool:
    name_lower = str(name or "").strip().lower()
    if not name_lower:
        return False
    return any(token in name_lower for token in CONSENT_COOKIE_NAME_HINTS)


async def _read_consent_storage(page: Page) -> Dict[str, Any]:
    try:
        storage = await page.evaluate(
            """
            () => {
                const match = (key) => {
                    const k = String(key || '').toLowerCase();
                    return ['consent','cookie','gdpr','ccpa','onetrust','optanon','cookiebot','didomi','trustarc','euconsent']
                        .some(t => k.includes(t));
                };

                const readStorage = (store) => {
                    const out = {};
                    try {
                        for (let i = 0; i < store.length; i++) {
                            const key = store.key(i);
                            if (match(key)) {
                                out[key] = store.getItem(key);
                            }
                        }
                    } catch (_) {}
                    return out;
                };

                const cookieOut = {};
                try {
                    const raw = document.cookie || '';
                    for (const part of raw.split(';')) {
                        const piece = part.trim();
                        if (!piece) continue;
                        const idx = piece.indexOf('=');
                        const key = idx >= 0 ? piece.slice(0, idx).trim() : piece;
                        const value = idx >= 0 ? piece.slice(idx + 1).trim() : '';
                        if (match(key)) {
                            cookieOut[key] = value;
                        }
                    }
                } catch (_) {}

                return {
                    localStorage: readStorage(window.localStorage),
                    sessionStorage: readStorage(window.sessionStorage),
                    cookies: cookieOut,
                };
            }
            """
        )
        if isinstance(storage, dict):
            return storage
    except Exception:
        pass
    return {"localStorage": {}, "sessionStorage": {}, "cookies": {}}


def _cookie_name_set(cookies: List[Dict[str, Any]]) -> set[str]:
    return {str(cookie.get("name", "")) for cookie in cookies if cookie.get("name")}


def _third_party_domains_from_urls(urls: List[str], first_party_etld1: str) -> List[str]:
    domains: List[str] = []
    if not first_party_etld1:
        return domains

    seen = set()
    for request_url in urls:
        hostname = _host(request_url)
        domain = _etld1(hostname)
        if not domain or domain == first_party_etld1:
            continue
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains


async def _click_first_matching_button(page: Page, keywords: List[str]) -> bool:
    locators = [
        page.locator("button"),
        page.locator("a[role='button']"),
        page.locator("a"),
        page.locator("[role='button']"),
        page.locator("input[type='button']"),
        page.locator("input[type='submit']"),
    ]

    keywords_lower = [keyword.lower() for keyword in keywords]
    for loc in locators:
        try:
            count = await loc.count()
        except Exception:
            continue

        for index in range(min(count, 120)):
            item = loc.nth(index)
            try:
                if not await item.is_visible():
                    continue
                text = ((await item.inner_text()) or "").strip().lower()
                value = ((await item.get_attribute("value")) or "").strip().lower()
                combined = (text + " " + value).strip()
                if not combined:
                    continue
                if any(keyword in combined for keyword in keywords_lower):
                    await item.click(timeout=3000)
                    await page.wait_for_timeout(1200)
                    return True
            except Exception:
                continue
    return False


async def _perform_consent_action(page: Page, consent_action: str, click_fn=None) -> tuple[bool, str]:
    if click_fn is None:
        click_fn = _click_first_matching_button

    if consent_action == "accept":
        clicked = await click_fn(page, ACCEPT_PATTERNS)
        if clicked:
            return True, "accept_clicked"

        managed = await click_fn(page, MANAGE_PATTERNS)
        if managed:
            clicked_accept = await click_fn(page, ACCEPT_PATTERNS)
            return bool(clicked_accept), ("manage_then_accept_clicked" if clicked_accept else "manage_no_accept")

        return False, "accept_not_found"

    if consent_action == "reject":
        clicked = await click_fn(page, REJECT_PATTERNS)
        if clicked:
            return True, "reject_clicked"

        managed = await click_fn(page, MANAGE_PATTERNS)
        if managed:
            clicked_reject = await click_fn(page, REJECT_PATTERNS)
            return bool(clicked_reject), ("manage_then_reject_clicked" if clicked_reject else "manage_no_reject")

        return False, "reject_not_found"

    return False, "none"


async def _detect_banner(page: Page) -> bool:
    candidate_seen = False
    try:
        for selector in BANNER_VISIBLE_SELECTORS:
            try:
                loc = page.locator(selector)
                count = await loc.count()
            except Exception:
                continue

            if count > 0:
                candidate_seen = True

            for index in range(min(count, 20)):
                item = loc.nth(index)
                try:
                    if not await item.is_visible():
                        continue
                    text = ((await item.inner_text()) or "").lower()
                    aria = ((await item.get_attribute("aria-label")) or "").lower()
                    combined = f"{text} {aria}".strip()
                    if combined and any(keyword in combined for keyword in BANNER_KEYWORDS):
                        return True
                except Exception:
                    continue

        if candidate_seen:
            return False

        # Conservative fallback only when there are no obvious banner-like candidates.
        html = (await page.content()).lower()
    except Exception:
        return False
    return any(keyword in html for keyword in BANNER_KEYWORDS)


async def _detect_challenge_or_login(page: Page) -> Dict[str, bool]:
    html = ""
    try:
        html = (await page.content()).lower()
    except Exception:
        pass

    recaptcha = any(keyword in html for keyword in ["recaptcha", "hcaptcha", "g-recaptcha"]) if html else False
    blocked = any(keyword in html for keyword in BLOCK_KEYWORDS) if html else False
    
    login_wall = False
    try:
        visible_password = await page.locator("input[type='password']:visible").count()
        if visible_password > 0:
            login_wall = True
        
        if not login_wall:
            visible_forms = await page.locator("form:visible, button:visible, input[type='submit']:visible").count()
            if visible_forms > 0:
                try:
                    visible_text = (await page.locator("body").inner_text()).lower()
                    if any(keyword in visible_text for keyword in LOGIN_KEYWORDS):
                        login_wall = True
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "recaptcha": recaptcha,
        "blocked": blocked,
        "login_required": login_wall,
    }


@dataclass
class CrawlStateResult:
    ok: bool
    state: str
    request_urls: List[str]
    cookies: List[Dict[str, Any]]
    banner_detected: bool
    action: str
    challenge: Dict[str, bool]
    note: Optional[str] = None
    click_verification: Optional[Dict[str, Any]] = None


async def crawl_site_states(
    url: str,
    timeout_ms: int = 45000,
    artifacts_dir: Optional[str] = None,
    headless: bool = True,
) -> Dict[str, Any]:
    if not url.startswith("http"):
        url = "https://" + url

    first_party = _etld1(_host(url))
    out: Dict[str, Any] = {
        "site": url,
        "first_party_etld1": first_party,
        "states": {},
        "requires_human": False,
        "human_reasons": [],
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)

        async def run_state(state_name: str, consent_action: str) -> CrawlStateResult:
            request_urls: List[str] = []
            context = await browser.new_context()
            page = await context.new_page()

            def on_req(req):
                request_urls.append(req.url)

            page.on("request", on_req)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=7000)
                except Exception:
                    pass
                await page.wait_for_timeout(1200)
            except Exception as exc:
                await context.close()
                return CrawlStateResult(
                    ok=False,
                    state=state_name,
                    request_urls=request_urls,
                    cookies=[],
                    banner_detected=False,
                    action=consent_action,
                    challenge={"recaptcha": False, "blocked": False, "login_required": False},
                    note=str(exc),
                )

            banner = await _detect_banner(page)
            challenge = await _detect_challenge_or_login(page)
            action_taken = "none"
            click_verification: Optional[Dict[str, Any]] = None
            clicked = False

            request_count_before_click = len(request_urls)
            url_before = page.url
            banner_before = banner
            try:
                cookies_before = await context.cookies()
            except Exception:
                cookies_before = []
            storage_before = await _read_consent_storage(page)

            if consent_action in ("accept", "reject"):
                clicked, action_taken = await _perform_consent_action(page, consent_action)

            await page.wait_for_timeout(1800)

            requests_after_click = request_urls[request_count_before_click:]
            url_after = page.url
            banner_after = await _detect_banner(page)
            try:
                cookies_after = await context.cookies()
            except Exception:
                cookies_after = []
            storage_after = await _read_consent_storage(page)

            third_party_request_urls_after_click: List[str] = []
            third_party_domains_after_click: List[str] = []
            seen_third_party_domains = set()
            for request_url in requests_after_click:
                domain = _etld1(_host(request_url))
                if not domain or domain == first_party:
                    continue
                third_party_request_urls_after_click.append(request_url)
                if domain not in seen_third_party_domains:
                    seen_third_party_domains.add(domain)
                    third_party_domains_after_click.append(domain)

            cookie_names_before = _cookie_name_set(cookies_before)
            cookie_names_after = _cookie_name_set(cookies_after)
            new_cookie_names = sorted(cookie_names_after - cookie_names_before)

            banner_disappeared = bool(banner_before and (not banner_after))
            consent_storage_changed = storage_before != storage_after
            post_click_network_activity = len(requests_after_click) > 0

            likely_click_worked = clicked and (
                banner_disappeared
                or consent_storage_changed
                or len(new_cookie_names) > 0
                or post_click_network_activity
            )

            evidence: List[str] = []
            if clicked:
                evidence.append("click_element_triggered")
            else:
                evidence.append("click_element_not_triggered")
            if banner_disappeared:
                evidence.append("banner_disappeared")
            if consent_storage_changed:
                evidence.append("consent_storage_changed")
            if new_cookie_names:
                evidence.append(f"new_cookie_names:{', '.join(new_cookie_names[:8])}")
            if post_click_network_activity:
                evidence.append("post_click_network_activity_observed_weak_signal")
            if not likely_click_worked:
                evidence.append("click_effect_not_observed")

            if consent_action in ("reject", "accept"):
                click_verification = {
                    "target_action": consent_action,
                    "clicked": bool(clicked),
                    "url_before": url_before,
                    "url_after": url_after,
                    "banner_before": bool(banner_before),
                    "banner_after": bool(banner_after),
                    "banner_disappeared": banner_disappeared,
                    "requests_before_click": request_count_before_click,
                    "requests_after_click": len(requests_after_click),
                    "request_urls_after_click": requests_after_click,
                    "third_party_requests_after_click": len(third_party_request_urls_after_click),
                    "third_party_request_urls_after_click": third_party_request_urls_after_click,
                    "new_third_party_domains_after_click": third_party_domains_after_click,
                    "cookies_before_click": len(cookies_before),
                    "cookies_after_click": len(cookies_after),
                    "new_cookie_names_after_click": new_cookie_names,
                    "consent_storage_before": storage_before,
                    "consent_storage_after": storage_after,
                    "consent_storage_changed": consent_storage_changed,
                    "likely_click_worked": likely_click_worked,
                    "evidence": evidence,
                }

            post_challenge = await _detect_challenge_or_login(page)
            challenge = {
                "recaptcha": challenge["recaptcha"] or post_challenge["recaptcha"],
                "blocked": challenge["blocked"] or post_challenge["blocked"],
                "login_required": challenge["login_required"] or post_challenge["login_required"],
            }

            if artifacts_dir:
                try:
                    os.makedirs(artifacts_dir, exist_ok=True)
                    await page.screenshot(path=os.path.join(artifacts_dir, f"{state_name}.png"), full_page=True)
                except Exception:
                    pass

            try:
                cookies = await context.cookies()
            except Exception:
                cookies = []

            try:
                page.remove_listener("request", on_req)
            except Exception:
                pass

            await context.close()

            return CrawlStateResult(
                ok=True,
                state=state_name,
                request_urls=request_urls,
                cookies=cookies_after,
                banner_detected=banner,
                action=action_taken,
                challenge=challenge,
                click_verification=click_verification,
            )

        s0 = await run_state("S0", "none")
        s1 = await run_state("S1", "reject")
        s2 = await run_state("S2", "accept")
        await browser.close()

    def summarize(state: CrawlStateResult) -> Dict[str, Any]:
        req_hosts = [_host(url_item) for url_item in state.request_urls]
        req_domains = [_etld1(hostname) for hostname in req_hosts if hostname]
        req_domains = [domain for domain in req_domains if domain]

        third_party_domains = [domain for domain in req_domains if first_party and domain != first_party]
        third_party_counts = Counter(third_party_domains)

        cookie_third_party = 0
        cookie_http_only_false = 0
        cookie_secure_false = 0
        cookie_samesite_none = 0
        cookie_total = len(state.cookies) if state.cookies else 0
        cookie_names: List[str] = []
        nonessential_cookie_names: List[str] = []
        nonessential_cookie_count = 0

        for cookie in state.cookies:
            cookie_name = str(cookie.get("name") or "")
            if cookie_name:
                cookie_names.append(cookie_name)
                if not _is_consent_or_essential_cookie_name(cookie_name):
                    nonessential_cookie_names.append(cookie_name)
                    nonessential_cookie_count += 1

            domain_raw = (cookie.get("domain") or "").lstrip(".")
            cookie_domain = _etld1(domain_raw)
            if cookie_domain and first_party and cookie_domain != first_party:
                cookie_third_party += 1
            if cookie.get("httpOnly") is False:
                cookie_http_only_false += 1
            if cookie.get("secure") is False:
                cookie_secure_false += 1
            same_site = cookie.get("sameSite")
            if isinstance(same_site, str) and same_site.lower() == "none":
                cookie_samesite_none += 1

        tracker_matches = match_known_trackers_from_urls(
            state.request_urls,
            first_party_etld1=first_party,
        )

        return {
            "ok": state.ok,
            "note": state.note,
            "banner_detected": state.banner_detected,
            "action": state.action,
            "challenge": state.challenge,
            "click_verification": state.click_verification,
            "request_count_total": len(state.request_urls),
            "unique_etld1_total": len(set(req_domains)),
            "unique_third_party_etld1": len(set(third_party_domains)),
            "third_party_request_count": len(third_party_domains),
            "cookies_total": cookie_total,
            "cookie_names": cookie_names,
            "nonessential_cookie_count": nonessential_cookie_count,
            "nonessential_cookie_names": nonessential_cookie_names,
            "cookies_third_party_est": cookie_third_party,
            "cookie_httpOnly_false_pct": (cookie_http_only_false / cookie_total) if cookie_total else None,
            "cookie_secure_false_pct": (cookie_secure_false / cookie_total) if cookie_total else None,
            "cookie_samesite_none_pct": (cookie_samesite_none / cookie_total) if cookie_total else None,
            "top_third_party_domains_by_req": third_party_counts.most_common(12),
            "known_tracker_count": tracker_matches.get("known_tracker_count", 0),
            "known_tracker_names": tracker_matches.get("known_tracker_names", []),
            "known_tracker_domains": tracker_matches.get("known_tracker_domains", []),
            "known_trackers": tracker_matches.get("known_trackers", []),
            "known_tracker_matching_available": tracker_matches.get("known_tracker_matching_available", False),
        }

    out["states"]["S0"] = summarize(s0)
    out["states"]["S1"] = summarize(s1)
    out["states"]["S2"] = summarize(s2)

    s0_cookies = out["states"]["S0"].get("cookies_third_party_est") or 0
    s1_cookies = out["states"]["S1"].get("cookies_third_party_est") or 0
    s2_cookies = out["states"]["S2"].get("cookies_third_party_est") or 0

    out["derived"] = {
        "preconsent_third_party_cookies": s0_cookies,
        "accept_lift_third_party_cookies": s2_cookies - s0_cookies,
        "reject_effectiveness_cookie": (1 - (s1_cookies / s2_cookies)) if s2_cookies > 0 else None,
    }

    human_reasons: List[str] = []
    for state_name in ("S0", "S1", "S2"):
        challenge = out["states"][state_name].get("challenge") or {}
        if challenge.get("recaptcha"):
            human_reasons.append(f"{state_name}:recaptcha")
        if challenge.get("blocked"):
            human_reasons.append(f"{state_name}:bot_or_access_block")
        if challenge.get("login_required"):
            human_reasons.append(f"{state_name}:login_required")
        if out["states"][state_name].get("ok") is False:
            human_reasons.append(f"{state_name}:navigation_error")

    out["human_reasons"] = sorted(set(human_reasons))
    out["requires_human"] = len(out["human_reasons"]) > 0

    if artifacts_dir:
        out["artifacts_dir"] = artifacts_dir

    return out