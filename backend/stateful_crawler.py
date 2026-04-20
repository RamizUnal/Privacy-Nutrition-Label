from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import tldextract
from playwright.async_api import Page, async_playwright


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
        return None
    return f"{ext.domain}.{ext.suffix}"


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


async def _detect_banner(page: Page) -> bool:
    try:
        html = (await page.content()).lower()
    except Exception:
        return False
    return (
        "cookie" in html
        or "çerez" in html
        or "consent" in html
        or "onetrust" in html
        or "trustarc" in html
    )


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

            if consent_action == "accept":
                clicked = await _click_first_matching_button(page, ACCEPT_PATTERNS)
                action_taken = "accept_clicked" if clicked else "accept_not_found"
            elif consent_action == "reject":
                clicked = await _click_first_matching_button(page, REJECT_PATTERNS)
                if clicked:
                    action_taken = "reject_clicked"
                else:
                    managed = await _click_first_matching_button(page, MANAGE_PATTERNS)
                    if managed:
                        clicked_reject = await _click_first_matching_button(page, REJECT_PATTERNS)
                        action_taken = "manage_then_reject_clicked" if clicked_reject else "manage_no_reject"
                    else:
                        action_taken = "reject_not_found"

            await page.wait_for_timeout(1800)

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
                cookies=cookies,
                banner_detected=banner,
                action=action_taken,
                challenge=challenge,
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

        for cookie in state.cookies:
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

        return {
            "ok": state.ok,
            "note": state.note,
            "banner_detected": state.banner_detected,
            "action": state.action,
            "challenge": state.challenge,
            "request_count_total": len(state.request_urls),
            "unique_etld1_total": len(set(req_domains)),
            "unique_third_party_etld1": len(set(third_party_domains)),
            "third_party_request_count": len(third_party_domains),
            "cookies_total": cookie_total,
            "cookies_third_party_est": cookie_third_party,
            "cookie_httpOnly_false_pct": (cookie_http_only_false / cookie_total) if cookie_total else None,
            "cookie_secure_false_pct": (cookie_secure_false / cookie_total) if cookie_total else None,
            "cookie_samesite_none_pct": (cookie_samesite_none / cookie_total) if cookie_total else None,
            "top_third_party_domains_by_req": third_party_counts.most_common(12),
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