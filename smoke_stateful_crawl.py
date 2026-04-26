import asyncio
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from tracker.stateful_adapter import run_integrated_state_crawl


def _print_state_metrics(state_name: str, state: dict) -> None:
    third_party_domains = state.get("third_party_domains") or []
    known_tracker_names = state.get("tracker_names") or []
    known_tracker_domains = state.get("known_tracker_domains") or []
    print(f"{state_name} requests:", state.get("total_requests", 0))
    print(f"{state_name} known_tracker_count:", state.get("known_tracker_count"))
    print(f"{state_name} known_tracker_names:", known_tracker_names[:12])
    print(f"{state_name} known_tracker_domains:", known_tracker_domains[:12])
    print(f"{state_name} third-party requests:", state.get("third_party_request_count", 0))
    print(f"{state_name} third-party domains:", len(third_party_domains))
    print(f"{state_name} third-party domains sample:", third_party_domains[:8])
    print(f"{state_name} cookies:", state.get("total_cookies", 0))


def _print_deltas(label: str, prev_state: dict, next_state: dict) -> None:
    prev_domains = set(prev_state.get("third_party_domains") or [])
    next_domains = set(next_state.get("third_party_domains") or [])
    new_domains = sorted(next_domains - prev_domains)
    removed_domains = sorted(prev_domains - next_domains)

    print(f"{label} request delta:", next_state.get("total_requests", 0) - prev_state.get("total_requests", 0))
    print(
        f"{label} third-party request delta:",
        next_state.get("third_party_request_count", 0) - prev_state.get("third_party_request_count", 0),
    )
    print(f"{label} cookie delta:", next_state.get("total_cookies", 0) - prev_state.get("total_cookies", 0))
    print(f"{label} new third-party domains:", new_domains)
    print(f"{label} removed third-party domains:", removed_domains)


async def main():
    domain = "ikea.com"
    url = "http://ikea.com"
    print(f"Testing integrated state crawl for {url}")
    result = await run_integrated_state_crawl(domain, url)

    print("S0 trackers:", result["S0"]["total_trackers"])
    _print_state_metrics("S0", result["S0"])

    print("S1 trackers:", result["S1"]["total_trackers"])
    _print_state_metrics("S1", result["S1"])

    print("S2 trackers:", result["S2"]["total_trackers"])
    _print_state_metrics("S2", result["S2"])

    print("S1-S0 deltas:")
    _print_deltas("S1-S0", result["S0"], result["S1"])

    print("S2-S1 deltas:")
    _print_deltas("S2-S1", result["S1"], result["S2"])

    raw_states = (result.get("_stateful") or {}).get("states") or {}
    print("Raw state debug:")
    for state_name in ("S0", "S1", "S2"):
        state = raw_states.get(state_name) or {}
        print(f"{state_name} action:", state.get("action"))
        print(f"{state_name} banner_detected:", state.get("banner_detected"))
        print(f"{state_name} request_count_total:", state.get("request_count_total"))
        print(f"{state_name} known_tracker_count:", state.get("known_tracker_count"))
        print(f"{state_name} known_tracker_names:", state.get("known_tracker_names"))
        print(f"{state_name} known_tracker_domains:", state.get("known_tracker_domains"))
        print(f"{state_name} third_party_request_count:", state.get("third_party_request_count"))
        print(f"{state_name} third_party_domains sample:", (state.get("top_third_party_domains_by_req") or [])[:8])
        print(f"{state_name} cookies_total:", state.get("cookies_total"))
        print(f"{state_name} known_tracker_matching_available:", state.get("known_tracker_matching_available"))
        print(f"{state_name} click_verification:", state.get("click_verification"))

    print("State quality:", result.get("state_quality"))
    print("Mismatch Detected:", result["mismatch_detected"])


if __name__ == "__main__":
    asyncio.run(main())