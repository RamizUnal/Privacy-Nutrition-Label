import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from tracker.dynamic_crawler import run_3_state_crawl, collect_state, click_banner_button, ACCEPT_BUTTON_REGEX, REJECT_BUTTON_REGEX
from playwright.async_api import async_playwright

async def debug_twitter():
    url = "https://x.com/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("Visiting x.com...")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        print("Page loaded. Looking for buttons...")
        buttons = page.get_by_role("button")
        count = await buttons.count()
        for i in range(count):
            btn = buttons.nth(i)
            text = await btn.text_content()
            if text:
                text = text.strip()
                if text:
                    print(f"Button text: {text}")
                    print(f"Accept Regex match: {bool(ACCEPT_BUTTON_REGEX.search(text))}")
                    print(f"Reject Regex match: {bool(REJECT_BUTTON_REGEX.search(text))}")

        await page.screenshot(path="x_banner.png")
        print("Screenshot saved to x_banner.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_twitter())
