import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from tracker.dynamic_crawler import run_3_state_crawl

async def main():
    domain = "example.com"
    url = "http://example.com"
    print(f"Testing dynamic crawl for {url}")
    result = await run_3_state_crawl(domain, url)
    print("S0 trackers:", result["S0"]["total_trackers"])
    print("S1 trackers:", result["S1"]["total_trackers"])
    print("S2 trackers:", result["S2"]["total_trackers"])
    print("Mismatch Detected:", result["mismatch_detected"])

if __name__ == "__main__":
    asyncio.run(main())
