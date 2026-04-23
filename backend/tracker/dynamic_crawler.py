import asyncio
import re
from typing import Dict, List, Set, Any
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, BrowserContext

from tracker.detector import _extract_domain, _match_tracker, _categorize_cookie, CookieInfo

# ─────────────────────────────────────────────────────────────────────────────
# Heuristics for Banners
# ─────────────────────────────────────────────────────────────────────────────

ACCEPT_BUTTON_REGEX = re.compile(
    r"(accept all|allow all|accept cookies|allow cookies|tümünü kabul et|kabul et|her şeyi kabul et)",
    re.IGNORECASE,
)

REJECT_BUTTON_REGEX = re.compile(
    r"(reject all|decline|decline all|continue without accepting|reject cookies|tümünü reddet|reddet|refuse|only essential)",
    re.IGNORECASE,
)

CLASS_ID_ACCEPT = [
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    ".js-accept-all-cookies",
    "#accept-cookies"
]

CLASS_ID_REJECT = [
    "#onetrust-reject-all-handler",
    "#CybotCookiebotDialogBodyButtonDecline",
    ".js-reject-all-cookies",
    "#reject-cookies"
]

class DynamicStateResult:
    def __init__(self):
        self.intercepted_urls: List[str] = []
        self.third_party_domains: Set[str] = set()
        self.trackers_detected: List[Dict] = []
        self.cookies: List[CookieInfo] = []
        
    def to_dict(self):
        return {
            "total_requests": len(self.intercepted_urls),
            "third_party_domains": list(self.third_party_domains),
            "trackers_detected": self.trackers_detected,
            "total_trackers": len(self.trackers_detected),
            "cookies": [vars(c) for c in self.cookies],
            "total_cookies": len(self.cookies)
        }

# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Crawler
# ─────────────────────────────────────────────────────────────────────────────

async def click_banner_button(page: Page, regex: re.Pattern, selectors: List[str]) -> bool:
    """Try to find and click a consent button."""
    try:
        # Try direct selectors first (OneTrust, Cookiebot, etc)
        for sel in selectors:
            loc = page.locator(sel)
            if await loc.count() > 0 and await loc.first.is_visible(timeout=500):
                await loc.first.click(timeout=1000)
                return True
                
        # Try finding button/link/div elements with matching text
        elements = page.locator("button, a, [role='button']")
        count = await elements.count()
        for i in range(count):
            el = elements.nth(i)
            # Only consider visible elements
            if await el.is_visible(timeout=500):
                text = await el.text_content()
                if text and regex.search(text.strip()):
                    await el.click(timeout=1000)
                    return True
                
    except Exception:
        pass
        
    return False

async def extract_network_and_cookies(page: Page, context: BrowserContext, domain: str, requests_log: List[str]) -> DynamicStateResult:
    result = DynamicStateResult()
    
    seen_domains = set()
    
    # Process intercepted network requests
    for url in requests_log:
        result.intercepted_urls.append(url[:300]) # Cap URL length
        req_domain = _extract_domain(url)
        
        if not req_domain or req_domain == domain or f".{domain}" in req_domain:
            continue
            
        result.third_party_domains.add(req_domain)
        
        if req_domain not in seen_domains:
            seen_domains.add(req_domain)
            tracker_info = _match_tracker(req_domain)
            if tracker_info:
                result.trackers_detected.append({
                    "domain": req_domain,
                    "name": tracker_info["name"],
                    "category": tracker_info["category"],
                    "risk": tracker_info.get("risk", "unknown"),
                    "url_preview": url[:100]
                })
                
    # Process cookies
    cookies_raw = await context.cookies()
    for c in cookies_raw:
        cookie_domain = c.get("domain", "")
        duration = "session"
        if c.get("expires", -1) != -1:
            duration = "persistent" # Simplified for this script
            
        result.cookies.append(CookieInfo(
            name=c.get("name", ""),
            value_preview=c.get("value", "")[:20],
            httponly=c.get("httpOnly", False),
            secure=c.get("secure", False),
            samesite=c.get("sameSite", "unknown"),
            path=c.get("path", "/"),
            domain=cookie_domain,
            max_age=None,
            category=_categorize_cookie(c.get("name", ""), cookie_domain),
            duration_label=duration,
        ))
        
    return result

async def collect_state(browser, url: str, domain: str, state_type: str) -> DynamicStateResult:
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    requests_log: List[str] = []
    
    def on_request(request):
        requests_log.append(request.url)
        
    page.on("request", on_request)
    
    try:
        # Load page
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(2) # Allow banner to appear
        
        if state_type == "S1_REJECT":
            clicked = await click_banner_button(page, REJECT_BUTTON_REGEX, CLASS_ID_REJECT)
            if clicked:
                await asyncio.sleep(3) # Wait for network to settle after rejection
        elif state_type == "S2_ACCEPT":
            clicked = await click_banner_button(page, ACCEPT_BUTTON_REGEX, CLASS_ID_ACCEPT)
            if clicked:
                await asyncio.sleep(3) # Wait for network to settle after acceptance
                
        # Wait a bit longer for trackers to finish loading
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass # Timeout or other error, handle gracefully
        
    result = await extract_network_and_cookies(page, context, domain, requests_log)
    
    await page.close()
    await context.close()
    
    return result

async def run_3_state_crawl(domain: str, url: str) -> Dict[str, Any]:
    """Execute the full 3-state crawl returning comprehensive data."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Run sequentially to ensure isolated states
        print(f"Running S0 (Baseline) for {domain}...")
        s0_result = await collect_state(browser, url, domain, "S0_BASELINE")
        
        print(f"Running S1 (Reject) for {domain}...")
        s1_result = await collect_state(browser, url, domain, "S1_REJECT")
        
        print(f"Running S2 (Accept) for {domain}...")
        s2_result = await collect_state(browser, url, domain, "S2_ACCEPT")
        
        await browser.close()
        
    return {
        "S0": s0_result.to_dict(),
        "S1": s1_result.to_dict(),
        "S2": s2_result.to_dict(),
        "mismatch_detected": s1_result.to_dict()["total_trackers"] >= s0_result.to_dict()["total_trackers"] and s0_result.to_dict()["total_trackers"] > 0
    }
