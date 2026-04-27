#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tracker.stateful_adapter import run_integrated_state_crawl


DEFAULT_SITES = [
    "https://commission.europa.eu/",
    "https://www.ikea.com/",
    "https://www.mozilla.org/",
    "https://www.wikipedia.org/",
    "https://www.microsoft.com/",
    "https://www.europarl.europa.eu/",
    "https://www.europarl.europa.eu/privacy-policy/en/cookies-policy",
    "https://edps.europa.eu/",
    "https://www.edps.europa.eu/about-edps/legal-notices_en",
    "https://edpb.europa.eu/",
    "https://commission.europa.eu/",
    "https://european-union.europa.eu/",
    "https://eures.europa.eu/",
    "https://school-education.ec.europa.eu/",
    "https://smart-cities-marketplace.ec.europa.eu/"
]


@dataclass
class SiteAnalysis:
    classification: str
    stable: bool
    inconclusive: bool
    actionable: bool
    reasons: List[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_sites(sites_file: str | None) -> List[str]:
    if not sites_file:
        return list(DEFAULT_SITES)

    path = Path(sites_file)
    sites: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        sites.append(value)
    return sites


def _state_snapshot(result: Dict[str, Any], state_name: str) -> Dict[str, Any]:
    raw_state = ((result.get("_stateful") or {}).get("states") or {}).get(state_name) or {}
    legacy_state = result.get(state_name) or {}
    click_verification = raw_state.get("click_verification") if isinstance(raw_state.get("click_verification"), dict) else {}

    return {
        "action": raw_state.get("action") or legacy_state.get("action_taken"),
        "known_tracker_count": raw_state.get("known_tracker_count", legacy_state.get("known_tracker_count", 0)),
        "known_tracker_names": raw_state.get("known_tracker_names") or legacy_state.get("tracker_names") or [],
        "known_tracker_domains": raw_state.get("known_tracker_domains") or legacy_state.get("known_tracker_domains") or [],
        "third_party_request_count": raw_state.get("third_party_request_count", legacy_state.get("third_party_request_count", 0)),
        "third_party_domains": raw_state.get("top_third_party_domains_by_req") or legacy_state.get("third_party_domains") or [],
        "cookies_total": raw_state.get("cookies_total", legacy_state.get("total_cookies", 0)),
        "nonessential_cookie_count": raw_state.get("nonessential_cookie_count", legacy_state.get("nonessential_cookie_count", 0)),
        "click_verification": {
            "clicked": click_verification.get("clicked"),
            "likely_click_worked": click_verification.get("likely_click_worked"),
            "evidence": click_verification.get("evidence") or [],
        },
        "challenge": raw_state.get("challenge") or {},
    }


def _known_matching_available(result: Dict[str, Any]) -> bool:
    states = ((result.get("_stateful") or {}).get("states") or {})
    return any(bool((states.get(state_name) or {}).get("known_tracker_matching_available")) for state_name in ("S0", "S1", "S2"))


def _stability_tuple(entry: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        entry.get("requires_human"),
        bool((entry.get("state_quality") or {}).get("usable_for_mismatch")),
        entry.get("mismatch_detected"),
        (entry.get("S0") or {}).get("known_tracker_count"),
        (entry.get("S1") or {}).get("known_tracker_count"),
        (entry.get("S2") or {}).get("known_tracker_count"),
        ((entry.get("S1") or {}).get("click_verification") or {}).get("likely_click_worked"),
        ((entry.get("S2") or {}).get("click_verification") or {}).get("likely_click_worked"),
    )


def _domain_from_url(url: str) -> str:
    normalized = url if url.startswith("http") else "https://" + url
    parsed = urlparse(normalized)
    return parsed.hostname or url


def _clicks_verified(entry: Dict[str, Any]) -> bool:
    for state_name in ("S1", "S2"):
        state = entry.get(state_name) or {}
        action = str(state.get("action") or "").lower()
        cv = state.get("click_verification") or {}

        if not cv:
            return False

        if cv.get("likely_click_worked") is not True:
            return False

        if state_name == "S1" and "reject" not in action:
            return False

        if state_name == "S2" and "accept" not in action:
            return False

    return True


def _analyze_site(entries: List[Dict[str, Any]]) -> SiteAnalysis:
    reasons: List[str] = []
    if not entries:
        return SiteAnalysis(
            classification="INCONCLUSIVE",
            stable=False,
            inconclusive=True,
            actionable=False,
            reasons=["no_results"],
        )

    stable = len({_stability_tuple(entry) for entry in entries}) == 1
    if not stable:
        reasons.append("variation_across_repeats")

    any_requires_human = any(bool(entry.get("requires_human")) for entry in entries)
    if any_requires_human:
        reasons.append("requires_human_detected")

    any_unusable_for_mismatch = any((entry.get("state_quality") or {}).get("usable_for_mismatch") is False for entry in entries)
    if any_unusable_for_mismatch:
        reasons.append("usable_for_mismatch_false")

    any_click_unverified = any(not _clicks_verified(entry) for entry in entries)
    if any_click_unverified:
        reasons.append("click_verification_unreliable")

    any_matching_unavailable = any(not bool(entry.get("known_tracker_matching_available")) for entry in entries)
    if any_matching_unavailable:
        reasons.append("known_tracker_matching_unavailable")

    inconclusive = any_requires_human or any_unusable_for_mismatch or any_click_unverified

    actionable = (
        stable
        and not any_requires_human
        and not any_unusable_for_mismatch
        and not any_matching_unavailable
        and not any_click_unverified
    )

    if actionable:
        classification = "ACTIONABLE"
    elif inconclusive:
        classification = "INCONCLUSIVE"
    else:
        classification = "UNSTABLE"

    return SiteAnalysis(
        classification=classification,
        stable=stable,
        inconclusive=inconclusive,
        actionable=actionable,
        reasons=reasons,
    )


def _write_summary(path: Path, grouped_results: Dict[str, List[Dict[str, Any]]]) -> None:
    lines: List[str] = []
    lines.append("# Real-Site State Validation Summary")
    lines.append("")
    lines.append("This report is operational evidence only.")
    lines.append("Runtime evidence suggests behavioral patterns; it is not a legal compliance determination.")
    lines.append("")

    for url, entries in grouped_results.items():
        analysis = _analyze_site(entries)
        representative = entries[0] if entries else {}
        quality = representative.get("state_quality") or {}

        lines.append(f"## {url}")
        lines.append(f"- Classification: **{analysis.classification}**")
        lines.append(f"- Stable across repeats: {analysis.stable}")
        lines.append(f"- Runtime requires human: {any(bool(entry.get('requires_human')) for entry in entries)}")
        lines.append(f"- usable_for_mismatch: {quality.get('usable_for_mismatch')}")
        lines.append(f"- mismatch_detected (per repeats): {[entry.get('mismatch_detected') for entry in entries]}")
        lines.append("")

        if analysis.classification == "ACTIONABLE":
            lines.append("Runtime evidence suggests stable state behavior and reliable click verification.")
        elif analysis.classification == "INCONCLUSIVE":
            lines.append("Dynamic crawl inconclusive because signal quality or state usability was insufficient.")
            lines.append("Manual review recommended because runtime evidence could not reliably establish reject/accept behavior.")
        else:
            lines.append("Runtime evidence suggests unstable behavior across repeats.")
            lines.append("Manual review recommended because repeatability was low.")

        if analysis.reasons:
            lines.append(f"- Reasons: {', '.join(sorted(set(analysis.reasons)))}")

        lines.append("")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


async def _run_once(url: str, repeat: int) -> Dict[str, Any]:
    domain = _domain_from_url(url)
    result = await run_integrated_state_crawl(domain, url)
    output = {
        "url": url,
        "repeat": repeat,
        "timestamp": _now_iso(),
        "requires_human": bool(result.get("requires_human")),
        "human_reasons": result.get("human_reasons") or [],
        "state_quality": result.get("state_quality") or {},
        "mismatch_detected": bool(result.get("mismatch_detected")),
        "known_tracker_matching_available": _known_matching_available(result),
        "S0": _state_snapshot(result, "S0"),
        "S1": _state_snapshot(result, "S1"),
        "S2": _state_snapshot(result, "S2"),
    }
    return output


async def main() -> None:
    parser = argparse.ArgumentParser(description="Repeatable real-site state-validation runner")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeats per site")
    parser.add_argument("--outdir", type=str, default="real_site_validation_out", help="Output directory path")
    parser.add_argument("--sites-file", type=str, default=None, help="Optional file with URLs (one per line)")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    results_path = outdir / "results.jsonl"
    summary_path = outdir / "summary.md"

    sites = _load_sites(args.sites_file)
    grouped_results: Dict[str, List[Dict[str, Any]]] = {url: [] for url in sites}

    with results_path.open("w", encoding="utf-8") as handle:
        for url in sites:
            for repeat in range(1, args.repeats + 1):
                entry = await _run_once(url, repeat)
                grouped_results[url].append(entry)
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                handle.flush()
                print(f"[{url}] repeat {repeat}/{args.repeats} done")

    _write_summary(summary_path, grouped_results)

    print(f"Wrote {results_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
