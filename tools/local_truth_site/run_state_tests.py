#!/usr/bin/env python3
import asyncio
import os
import sys
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

from tracker.stateful_adapter import run_integrated_state_crawl


BASE = "http://truthsite.test:9999"


TESTS = [
    {
        "name": "effective_consent",
        "url": f"{BASE}/effective",
        "expected_trackers": {"S0": 0, "S1": 0, "S2": 1},
        "expected_mismatch_detected": False,
        "expected_cookie_order": "S2_gt_S1",
        "expect_s1_valid": True,
        "expect_s2_valid": True,
    },
    {
        "name": "bad_reject_loads_tracker",
        "url": f"{BASE}/bad-reject",
        "expected_trackers": {"S0": 0, "S1": 1, "S2": 1},
        "expected_mismatch_detected": True,
        "expect_s1_valid": True,
        "expect_s2_valid": True,
    },
    {
        "name": "preconsent_tracking",
        "url": f"{BASE}/preconsent",
        "expected_trackers": {"S0": 1, "S1": 1, "S2": 1},
        "expected_mismatch_detected": True,
        "expect_s1_valid": True,
        "expect_s2_valid": True,
    },
    {
        "name": "manage_only_flow",
        "url": f"{BASE}/manage-only",
        "expected_trackers": {"S0": 0, "S1": 0, "S2": 1},
        "expected_mismatch_detected": False,
        "expect_s1_valid": True,
        "expect_s2_valid": True,
    },
    {
        "name": "no_banner_inconclusive",
        "url": f"{BASE}/no-banner",
        "expected_trackers": {"S0": 0, "S1": 0, "S2": 0},
        "expected_mismatch_detected": False,
        "expect_s1_valid": False,
        "expect_s2_valid": False,
    },
    {
        "name": "blocked_requires_human",
        "url": f"{BASE}/blocked",
        "expected_trackers": {"S0": 0, "S1": 0, "S2": 0},
        "expected_mismatch_detected": False,
        "expect_requires_human": True,
    },
    {
        "name": "fake_click_no_effect",
        "url": f"{BASE}/fake-click",
        "expected_trackers": {"S0": 0, "S1": 0, "S2": 0},
        "expected_mismatch_detected": False,
        "expect_s1_valid": False,
        "expect_s2_valid": False,
    },
]


def get_raw_state(result: dict[str, Any], name: str) -> dict[str, Any]:
    return ((result.get("_stateful") or {}).get("states") or {}).get(name) or {}


def known_count(result: dict[str, Any], name: str) -> int:
    raw = get_raw_state(result, name)
    if "known_tracker_count" in raw:
        return raw.get("known_tracker_count") or 0
    return (result.get(name) or {}).get("total_trackers") or 0


def action(result: dict[str, Any], name: str) -> str:
    return get_raw_state(result, name).get("action") or (result.get(name) or {}).get("action_taken") or ""


def click_worked(result: dict[str, Any], name: str) -> Any:
    cv = get_raw_state(result, name).get("click_verification") or {}
    return cv.get("likely_click_worked")


def cookies(result: dict[str, Any], name: str) -> int:
    raw = get_raw_state(result, name)
    return raw.get("cookies_total") if "cookies_total" in raw else (result.get(name) or {}).get("total_cookies", 0)


def print_state(result: dict[str, Any], name: str):
    raw = get_raw_state(result, name)
    legacy = result.get(name) or {}
    print(f"  {name}:")
    print(f"    action: {action(result, name)}")
    print(f"    known_tracker_count: {known_count(result, name)}")
    print(f"    known_tracker_names: {raw.get('known_tracker_names') or legacy.get('tracker_names')}")
    print(f"    known_tracker_domains: {raw.get('known_tracker_domains')}")
    print(f"    third_party_request_count: {raw.get('third_party_request_count') or legacy.get('third_party_request_count')}")
    print(f"    third_party_domains: {legacy.get('third_party_domains')}")
    print(f"    cookies_total: {cookies(result, name)}")
    print(f"    click_worked: {click_worked(result, name)}")
    print(f"    click_verification: {raw.get('click_verification')}")


async def run_one(test: dict[str, Any]) -> bool:
    print("\n" + "=" * 80)
    print("TEST:", test["name"])
    print("URL:", test["url"])

    result = await run_integrated_state_crawl("truthsite.test", test["url"])

    for state in ["S0", "S1", "S2"]:
        print_state(result, state)

    print("state_quality:", result.get("state_quality"))
    print("requires_human:", result.get("requires_human"))
    print("human_reasons:", result.get("human_reasons"))
    print("mismatch_detected:", result.get("mismatch_detected"))

    passed = True

    for state, expected in test.get("expected_trackers", {}).items():
        actual = known_count(result, state)
        if actual != expected:
            print(f"FAIL: {state} known_tracker_count expected {expected}, got {actual}")
            passed = False

    if test.get("expected_cookie_order") == "S2_gt_S1":
        if not (cookies(result, "S2") > cookies(result, "S1")):
            print(f"FAIL: expected S2 cookies > S1 cookies, got S1={cookies(result, 'S1')} S2={cookies(result, 'S2')}")
            passed = False

    if "expect_s1_valid" in test:
        worked = click_worked(result, "S1")
        if bool(worked) != test["expect_s1_valid"]:
            print(f"FAIL: S1 click_worked expected {test['expect_s1_valid']}, got {worked}")
            passed = False

    if "expect_s2_valid" in test:
        worked = click_worked(result, "S2")
        if bool(worked) != test["expect_s2_valid"]:
            print(f"FAIL: S2 click_worked expected {test['expect_s2_valid']}, got {worked}")
            passed = False

    if "expect_requires_human" in test:
        actual = bool(result.get("requires_human"))
        if actual != test["expect_requires_human"]:
            print(f"FAIL: requires_human expected {test['expect_requires_human']}, got {actual}")
            passed = False

    if "expected_mismatch_detected" in test:
        actual = bool(result.get("mismatch_detected"))
        if actual != test["expected_mismatch_detected"]:
            print(f"FAIL: mismatch_detected expected {test['expected_mismatch_detected']}, got {actual}")
            passed = False

    print("RESULT:", "PASS" if passed else "FAIL")
    return passed


async def main():
    results = []
    for test in TESTS:
        results.append(await run_one(test))

    print("\n" + "=" * 80)
    print(f"PASSED {sum(results)}/{len(results)}")
    if not all(results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
