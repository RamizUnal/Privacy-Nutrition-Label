from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from crawler import crawl_website
from stateful_crawler import crawl_site_states


CATEGORICAL_FIELDS = [
    "S0.action_semantic",
    "S1.action_semantic",
    "S2.action_semantic",
    "S0.banner_detected",
    "S1.banner_detected",
    "S2.banner_detected",
    "S0.challenge.recaptcha",
    "S1.challenge.recaptcha",
    "S2.challenge.recaptcha",
    "S0.challenge.blocked",
    "S1.challenge.blocked",
    "S2.challenge.blocked",
    "S0.challenge.login_required",
    "S1.challenge.login_required",
    "S2.challenge.login_required",
    "requires_human",
    "human_reasons",
    "policy.found",
    "policy.discovery_method",
]

NUMERIC_FIELDS = [
    "S0.cookies_third_party_est",
    "S1.cookies_third_party_est",
    "S2.cookies_third_party_est",
    "S0.unique_third_party_etld1",
    "S1.unique_third_party_etld1",
    "S2.unique_third_party_etld1",
    "derived.accept_lift_third_party_cookies",
    "derived.reject_effectiveness_cookie",
]


def _read_sites(path: str) -> List[str]:
    output: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                output.append(value)
    return output


def _safe_name(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", url.replace("https://", "").replace("http://", "")).strip("_")


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_s1_action(raw: Any) -> str:
    if not isinstance(raw, str):
        return "unknown"
    mapping = {
        "reject_clicked": "reject_success",
        "manage_then_reject_clicked": "reject_success",
        "reject_not_found": "reject_fail",
        "manage_no_reject": "reject_fail",
    }
    return mapping.get(raw, raw)


def _normalize_s2_action(raw: Any) -> str:
    if not isinstance(raw, str):
        return "unknown"
    mapping = {
        "accept_clicked": "accept_success",
        "accept_not_found": "accept_fail",
    }
    return mapping.get(raw, raw)


def _normalize_state_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    states = row.get("states") or {}
    for state_name in ("S0", "S1", "S2"):
        state = states.get(state_name)
        if not isinstance(state, dict):
            continue
        raw_action = state.get("action")
        if state_name == "S1":
            semantic_action = _normalize_s1_action(raw_action)
        elif state_name == "S2":
            semantic_action = _normalize_s2_action(raw_action)
        else:
            semantic_action = raw_action if isinstance(raw_action, str) else "unknown"

        state["action_raw"] = raw_action
        state["action_semantic"] = semantic_action
    return row


def _get_nested(data: Dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if part in {"S0", "S1", "S2"}:
            current = (current.get("states") or {}).get(part)
        else:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        if current is None:
            return None
    return current


def _normalize_categorical(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(sorted(str(item) for item in value))
    return value


def _numeric_stability(field: str, numeric_values: List[float]) -> bool:
    if len(numeric_values) < 2:
        return True
    min_value = min(numeric_values)
    max_value = max(numeric_values)
    value_range = max_value - min_value
    if field.endswith("reject_effectiveness_cookie"):
        return value_range <= 0.15
    return value_range <= 2.0


def _stability_report(site_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    categorical_report: Dict[str, Dict[str, Any]] = {}
    numeric_report: Dict[str, Dict[str, Any]] = {}

    for field in CATEGORICAL_FIELDS:
        values = [_normalize_categorical(_get_nested(run, field)) for run in site_runs]
        present = [value for value in values if value is not None]
        distinct = sorted({repr(value) for value in present})
        categorical_report[field] = {
            "distinct_count": len(distinct),
            "values": distinct,
            "stable": len(distinct) <= 1,
        }

    for field in NUMERIC_FIELDS:
        values = [_get_nested(run, field) for run in site_runs]
        numeric_values = [float(value) for value in values if isinstance(value, (int, float))]
        if not numeric_values:
            numeric_report[field] = {
                "count": 0,
                "mean": None,
                "min": None,
                "max": None,
                "range": None,
                "stable": True,
                "insufficient_data": True,
            }
            continue

        min_value = min(numeric_values)
        max_value = max(numeric_values)
        value_range = max_value - min_value

        numeric_report[field] = {
            "count": len(numeric_values),
            "mean": round(mean(numeric_values), 4),
            "min": min_value,
            "max": max_value,
            "range": round(value_range, 4),
            "stable": _numeric_stability(field, numeric_values),
            "insufficient_data": False,
        }

    unstable_categorical = [field for field, meta in categorical_report.items() if not meta["stable"]]
    unstable_numeric = [field for field, meta in numeric_report.items() if not meta["stable"]]

    return {
        "categorical": categorical_report,
        "numeric": numeric_report,
        "unstable_fields": {
            "categorical": unstable_categorical,
            "numeric": unstable_numeric,
        },
        "stable_enough": len(unstable_categorical) == 0 and len(unstable_numeric) <= 2,
    }


def _build_flag_meta(site: str, site_runs: List[Dict[str, Any]], report: Dict[str, Any]) -> Dict[str, Any]:
    requires_human = any(bool(run.get("requires_human")) for run in site_runs)
    unstable_categorical = report["unstable_fields"]["categorical"]
    unstable_numeric = report["unstable_fields"]["numeric"]
    unstable = len(unstable_categorical) > 0 or len(unstable_numeric) > 2

    return {
        "site": site,
        "requires_human": requires_human,
        "unstable": unstable,
        "unstable_categorical_fields": unstable_categorical,
        "unstable_numeric_fields": unstable_numeric,
    }


async def _run_single_site(
    site: str,
    artifacts_dir: str,
    include_policy: bool,
    headless: bool,
) -> Dict[str, Any]:
    stateful = await crawl_site_states(site, artifacts_dir=artifacts_dir, headless=headless)
    stateful = _normalize_state_fields(stateful)

    policy_info = None
    if include_policy:
        try:
            policy = await crawl_website(site)
            policy_info = {
                "found": policy.policy_found,
                "url": policy.policy_url,
                "word_count": policy.word_count,
                "discovery_method": policy.discovery_method,
                "error": policy.error,
            }
        except Exception as exc:
            policy_info = {
                "found": False,
                "url": None,
                "word_count": 0,
                "discovery_method": None,
                "error": f"policy_crawl_error: {exc}",
            }

    return {
        **stateful,
        "policy": policy_info,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 validation harness for stateful S0/S1/S2 crawler")
    parser.add_argument("--sites", required=True, help="Validation corpus file")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeated headless runs")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between sites")
    parser.add_argument("--with-policy", action="store_true", help="Also run policy discovery")
    parser.add_argument(
        "--headful-rerun-flagged",
        action="store_true",
        help="After headless repeats, rerun flagged sites once in headful mode",
    )
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    artifacts_root = os.path.join(args.outdir, "artifacts")
    os.makedirs(artifacts_root, exist_ok=True)

    sites = _read_sites(args.sites)
    if not sites:
        raise ValueError("No sites found in corpus file")

    run_ts = datetime.now(timezone.utc).isoformat()
    by_site_runs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    print(f"Phase 0 validation start: sites={len(sites)} repeats={args.repeats}")

    for repeat_idx in range(1, args.repeats + 1):
        run_file = os.path.join(args.outdir, f"results_repeat_{repeat_idx}.jsonl")
        print(f"Running repeat {repeat_idx}/{args.repeats}")

        for site_idx, site in enumerate(sites, 1):
            print(f"  [{site_idx}/{len(sites)}] {site}")
            site_id = _safe_name(site)
            artifacts_dir = os.path.join(artifacts_root, f"repeat_{repeat_idx}", site_id)

            try:
                row = await _run_single_site(
                    site=site,
                    artifacts_dir=artifacts_dir,
                    include_policy=args.with_policy,
                    headless=True,
                )
                row["repeat"] = repeat_idx
                row["run_ts"] = run_ts
            except Exception as exc:
                row = {
                    "site": site,
                    "repeat": repeat_idx,
                    "run_ts": run_ts,
                    "error": str(exc),
                    "requires_human": True,
                    "human_reasons": ["run_error"],
                }

            by_site_runs[site].append(row)
            _append_jsonl(run_file, row)
            await asyncio.sleep(max(args.delay, 0.0))

    stability_by_site: Dict[str, Any] = {}
    flag_meta_by_site: Dict[str, Any] = {}
    requires_human_sites: List[str] = []
    unstable_sites: List[str] = []

    for site in sites:
        site_runs = by_site_runs.get(site, [])
        report = _stability_report(site_runs)
        meta = _build_flag_meta(site, site_runs, report)

        stability_by_site[site] = report
        flag_meta_by_site[site] = meta

        if meta["requires_human"]:
            requires_human_sites.append(site)
        if meta["unstable"]:
            unstable_sites.append(site)

    flagged_sites = sorted(set(requires_human_sites).union(unstable_sites))
    headful_review_rows: List[Dict[str, Any]] = []
    headful_review_by_site: Dict[str, bool] = {site: False for site in flagged_sites}

    if args.headful_rerun_flagged and flagged_sites:
        print(f"Headful rerun for flagged sites: {len(flagged_sites)}")
        headful_file = os.path.join(args.outdir, "headful_flagged.jsonl")
        for site in flagged_sites:
            site_id = _safe_name(site)
            artifacts_dir = os.path.join(artifacts_root, "headful_review", site_id)
            try:
                row = await _run_single_site(
                    site=site,
                    artifacts_dir=artifacts_dir,
                    include_policy=args.with_policy,
                    headless=False,
                )
                row["run_ts"] = run_ts
                row["headful_review"] = True
            except Exception as exc:
                row = {
                    "site": site,
                    "run_ts": run_ts,
                    "headful_review": True,
                    "error": str(exc),
                }
            headful_review_rows.append(row)
            headful_review_by_site[site] = True
            _append_jsonl(headful_file, row)

    summary = {
        "run_ts": run_ts,
        "sites_total": len(sites),
        "repeats": args.repeats,
        "include_policy": args.with_policy,
        "requires_human_sites": sorted(requires_human_sites),
        "unstable_sites": sorted(unstable_sites),
        "flagged_sites": flagged_sites,
        "stable_sites": [site for site in sites if site not in flagged_sites],
        "flag_meta_by_site": flag_meta_by_site,
        "headful_review_by_site": headful_review_by_site,
        "stability_by_site": stability_by_site,
    }

    summary_json_path = os.path.join(args.outdir, "phase0_summary.json")
    with open(summary_json_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    summary_md_path = os.path.join(args.outdir, "phase0_summary.md")
    with open(summary_md_path, "w", encoding="utf-8") as handle:
        handle.write("# Phase 0 Validation Summary\n\n")
        handle.write(f"- Run timestamp: {run_ts}\n")
        handle.write(f"- Sites: {len(sites)}\n")
        handle.write(f"- Repeats: {args.repeats}\n")
        handle.write(f"- Requires-human sites: {len(requires_human_sites)}\n")
        handle.write(f"- Unstable sites: {len(unstable_sites)}\n")
        handle.write(f"- Flagged sites (union): {len(flagged_sites)}\n\n")

        if flagged_sites:
            handle.write("## Triage (flagged sites)\n\n")
            for site in flagged_sites:
                meta = flag_meta_by_site[site]
                unstable_cat = meta["unstable_categorical_fields"]
                unstable_num = meta["unstable_numeric_fields"]
                headful_done = headful_review_by_site.get(site, False)
                site_artifacts = f"artifacts/repeat_*/{_safe_name(site)}/"
                headful_artifacts = f"artifacts/headful_review/{_safe_name(site)}/"

                handle.write(f"### {site}\n")
                handle.write(f"- why flagged: requires_human={meta['requires_human']}, unstable={meta['unstable']}\n")
                handle.write(f"- unstable categorical fields: {', '.join(unstable_cat) if unstable_cat else 'none'}\n")
                handle.write(f"- unstable numeric fields: {', '.join(unstable_num) if unstable_num else 'none'}\n")
                handle.write(f"- headful rerun happened: {headful_done}\n")
                handle.write(f"- screenshots (headless): {site_artifacts}\n")
                if headful_done:
                    handle.write(f"- screenshots (headful): {headful_artifacts}\n")
                handle.write("\n")

        handle.write("## Site-by-site stability\n\n")
        for site in sites:
            report = stability_by_site[site]
            handle.write(f"### {site}\n")
            handle.write(f"- stable enough: {report['stable_enough']}\n")
            handle.write(f"- unstable categorical count: {len(report['unstable_fields']['categorical'])}\n")
            handle.write(f"- unstable numeric count: {len(report['unstable_fields']['numeric'])}\n\n")

    print(f"Wrote {summary_json_path}")
    print(f"Wrote {summary_md_path}")
    print(f"Flagged sites: {len(flagged_sites)}")


if __name__ == "__main__":
    asyncio.run(main())