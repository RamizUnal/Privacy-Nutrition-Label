"""
Compatibility bridge between the stateful crawler output and the
legacy S0/S1/S2 dynamic crawl shape used by /analyze consumers.

This adapter preserves legacy keys while
surfacing confidence metadata for callers that can handle more semantics.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from stateful_crawler import crawl_site_states


def _first_value(source: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in source and source.get(key) is not None:
            return source.get(key)
    return default


def _normalize_third_party_domains(state: Dict[str, Any]) -> List[str]:
    value = _first_value(
        state,
        [
            "third_party_domains",
            "top_third_party_domains_by_req",
            "third_party_etld1",
        ],
        default=[],
    )

    domains: List[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                domains.append(item)
            elif isinstance(item, (list, tuple)) and item:
                domain = item[0]
                if isinstance(domain, str):
                    domains.append(domain)
            elif isinstance(item, dict):
                domain = _first_value(item, ["domain", "name", "etld1"], default=None)
                if isinstance(domain, str):
                    domains.append(domain)

    # preserve order, dedupe
    seen = set()
    out: List[str] = []
    for domain in domains:
        if domain not in seen:
            seen.add(domain)
            out.append(domain)
    return out


def _state_error(state_name: str, state: Dict[str, Any]) -> Optional[str]:
    if not state:
        return f"{state_name}:missing_state"

    note = state.get("note")
    if isinstance(note, str) and note.strip():
        return note

    challenge = state.get("challenge") or {}
    reasons: List[str] = []
    if challenge.get("login_required"):
        reasons.append("login_required")
    if challenge.get("recaptcha"):
        reasons.append("recaptcha")
    if challenge.get("blocked"):
        reasons.append("blocked")
    if reasons:
        return f"{state_name}:" + ",".join(reasons)

    if state.get("ok") is False:
        return f"{state_name}:state_failed"

    return None


def _legacy_state(state_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    third_party_domains = _normalize_third_party_domains(state)

    total_trackers = _first_value(
        state,
        ["total_trackers", "known_tracker_count", "third_party_request_count"],
        default=0,
    )
    if not isinstance(total_trackers, int):
        try:
            total_trackers = int(total_trackers)
        except Exception:
            total_trackers = 0

    action_taken = _first_value(state, ["action_taken", "action", "status"], default="unknown")

    return {
        "state": state_name,
        "total_requests": _first_value(state, ["request_count_total", "total_requests"], default=0),
        "third_party_domains": third_party_domains,
        "total_cookies": _first_value(state, ["cookies_total", "total_cookies"], default=0),
        "total_trackers": total_trackers,
        "tracker_names": [],
        "cookie_names": [],
        "trackers_detected": [],
        "action_taken": action_taken,
        "error": _state_error(state_name, state),
    }


def _is_reject_state_valid(s1: Dict[str, Any]) -> bool:
    if not s1:
        return False
    if s1.get("ok") is not True:
        return False
    action = str(_first_value(s1, ["action", "action_taken", "status"], default="") or "").lower()
    # conservative: reject must have been explicitly clicked
    if "reject_clicked" not in action:
        return False
    challenge = s1.get("challenge") or {}
    if any(bool(challenge.get(flag)) for flag in ("login_required", "recaptcha", "blocked")):
        return False
    return True


def _is_accept_state_valid(s2: Dict[str, Any]) -> bool:
    if not s2:
        return False
    if s2.get("ok") is not True:
        return False
    action = str(_first_value(s2, ["action", "action_taken", "status"], default="") or "").lower()
    if "accept_clicked" not in action:
        return False
    challenge = s2.get("challenge") or {}
    if any(bool(challenge.get(flag)) for flag in ("login_required", "recaptcha", "blocked")):
        return False
    return True


def _build_quality(stateful: Dict[str, Any]) -> Dict[str, Any]:
    states = stateful.get("states") or {}
    s0 = states.get("S0") or {}
    s1 = states.get("S1") or {}
    s2 = states.get("S2") or {}

    reasons: List[str] = []
    requires_human = bool(stateful.get("requires_human"))
    if requires_human:
        reasons.append("requires_human")

    if not _is_reject_state_valid(s1):
        reasons.append("S1_reject_not_valid")
    if not _is_accept_state_valid(s2):
        reasons.append("S2_accept_not_valid")

    for state_name, state in (("S0", s0), ("S1", s1), ("S2", s2)):
        challenge = state.get("challenge") or {}
        if challenge.get("login_required"):
            reasons.append(f"{state_name}:login_required")
        if challenge.get("recaptcha"):
            reasons.append(f"{state_name}:recaptcha")
        if challenge.get("blocked"):
            reasons.append(f"{state_name}:blocked")
        if state and state.get("ok") is False:
            reasons.append(f"{state_name}:navigation_failed")

    # scoring can still consume counts, mismatch requires stronger confidence
    usable_for_scoring = not requires_human
    usable_for_mismatch = (not requires_human) and _is_reject_state_valid(s1)

    return {
        "usable_for_scoring": usable_for_scoring,
        "usable_for_mismatch": usable_for_mismatch,
        "reasons": sorted(set(reasons)),
    }


def _compute_mismatch_detected(stateful: Dict[str, Any], quality: Dict[str, Any]) -> bool:
    states = stateful.get("states") or {}
    s0 = states.get("S0") or {}
    s1 = states.get("S1") or {}

    if not quality.get("usable_for_mismatch"):
        return False

    s0_trackers = int(_first_value(s0, ["known_tracker_count", "third_party_request_count"], default=0) or 0)
    s1_trackers = int(_first_value(s1, ["known_tracker_count", "third_party_request_count"], default=0) or 0)
    s0_cookies = int(_first_value(s0, ["cookies_total", "total_cookies"], default=0) or 0)
    s1_cookies = int(_first_value(s1, ["cookies_total", "total_cookies"], default=0) or 0)

    # conservative mismatch: reject does not reduce trackers/cookies from baseline.
    if (s0_trackers > 0 and s1_trackers >= s0_trackers) or (s0_cookies > 0 and s1_cookies >= s0_cookies):
        return True
    return False


async def run_integrated_state_crawl(domain: str, url: str) -> Dict[str, Any]:
    """
    Run rich stateful crawl and adapt it to the legacy dynamic-crawling schema.
    """
    stateful = await crawl_site_states(url)
    states = stateful.get("states") or {}

    legacy_s0 = _legacy_state("S0", states.get("S0") or {})
    legacy_s1 = _legacy_state("S1", states.get("S1") or {})
    legacy_s2 = _legacy_state("S2", states.get("S2") or {})

    quality = _build_quality(stateful)
    mismatch_detected = _compute_mismatch_detected(stateful, quality)

    return {
        "S0": legacy_s0,
        "S1": legacy_s1,
        "S2": legacy_s2,
        "mismatch_detected": mismatch_detected,
        "requires_human": bool(stateful.get("requires_human")),
        "human_reasons": list(stateful.get("human_reasons") or []),
        "state_quality": quality,
        "schema_version": "legacy_plus_stateful_v1",
        "_stateful": stateful,
        "_adapter": {
            "source": "stateful_crawler.crawl_site_states",
            "domain_hint": domain,
            "mapping_notes": [
                "total_requests <- request_count_total",
                "third_party_domains <- top_third_party_domains_by_req",
                "total_trackers <- known_tracker_count|third_party_request_count",
                "tracker_names/cookie_names unavailable in source and left empty",
            ],
        },
    }
