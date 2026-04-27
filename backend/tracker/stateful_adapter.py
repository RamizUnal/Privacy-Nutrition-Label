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

    matching_available = bool(state.get("known_tracker_matching_available"))

    total_trackers = _first_value(state, ["known_tracker_count", "total_trackers"], default=0)
    if not isinstance(total_trackers, int):
        try:
            total_trackers = int(total_trackers)
        except Exception:
            total_trackers = 0

    known_tracker_count = _first_value(state, ["known_tracker_count"], default=None)
    if known_tracker_count is not None and not isinstance(known_tracker_count, int):
        try:
            known_tracker_count = int(known_tracker_count)
        except Exception:
            known_tracker_count = None

    third_party_request_count = _first_value(state, ["third_party_request_count"], default=0)
    if not isinstance(third_party_request_count, int):
        try:
            third_party_request_count = int(third_party_request_count)
        except Exception:
            third_party_request_count = 0

    nonessential_cookie_count = _first_value(state, ["nonessential_cookie_count"], default=0)
    if not isinstance(nonessential_cookie_count, int):
        try:
            nonessential_cookie_count = int(nonessential_cookie_count)
        except Exception:
            nonessential_cookie_count = 0

    action_taken = _first_value(state, ["action_taken", "action", "status"], default="unknown")
    known_tracker_names = state.get("known_tracker_names") if isinstance(state.get("known_tracker_names"), list) else []
    known_tracker_domains = state.get("known_tracker_domains") if isinstance(state.get("known_tracker_domains"), list) else []
    known_trackers = state.get("known_trackers") if isinstance(state.get("known_trackers"), list) else []

    if not matching_available:
        total_trackers = 0
        known_tracker_count = None
        known_tracker_names = []
        known_tracker_domains = []
        known_trackers = []

    return {
        "state": state_name,
        "total_requests": _first_value(state, ["request_count_total", "total_requests"], default=0),
        "third_party_domains": third_party_domains,
        "total_cookies": _first_value(state, ["cookies_total", "total_cookies"], default=0),
        "nonessential_cookie_count": nonessential_cookie_count,
        "total_trackers": total_trackers,
        "known_tracker_count": known_tracker_count,
        "known_tracker_domains": known_tracker_domains,
        "third_party_request_count": third_party_request_count,
        "tracker_names": known_tracker_names,
        "cookie_names": [],
        "trackers_detected": known_trackers,
        "known_tracker_matching_available": matching_available,
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

    click_verification = s1.get("click_verification") or {}
    if isinstance(click_verification, dict) and "likely_click_worked" in click_verification:
        if click_verification.get("likely_click_worked") is False:
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

    click_verification = s2.get("click_verification") or {}
    if isinstance(click_verification, dict) and "likely_click_worked" in click_verification:
        if click_verification.get("likely_click_worked") is False:
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

    s1_action = str(_first_value(s1, ["action", "action_taken", "status"], default="") or "").lower()
    s2_action = str(_first_value(s2, ["action", "action_taken", "status"], default="") or "").lower()
    s1_verification = s1.get("click_verification") or {}
    s2_verification = s2.get("click_verification") or {}

    if "reject_clicked" in s1_action and isinstance(s1_verification, dict):
        if s1_verification.get("likely_click_worked") is False:
            reasons.append("S1_reject_click_unverified")

    if "accept_clicked" in s2_action and isinstance(s2_verification, dict):
        if s2_verification.get("likely_click_worked") is False:
            reasons.append("S2_accept_click_unverified")

    tracker_matching_available = any(
        bool(_first_value(state, ["known_tracker_matching_available"], default=False))
        for state in (s0, s1, s2)
    )
    if not tracker_matching_available:
        reasons.append("tracker_matching_unavailable")

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
    usable_for_mismatch = (not requires_human) and _is_reject_state_valid(s1) and tracker_matching_available

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

    s0_trackers = int(_first_value(s0, ["known_tracker_count"], default=0) or 0)
    s1_trackers = int(_first_value(s1, ["known_tracker_count"], default=0) or 0)
    s0_nonessential_cookies = int(_first_value(s0, ["nonessential_cookie_count"], default=0) or 0)
    s1_nonessential_cookies = int(_first_value(s1, ["nonessential_cookie_count"], default=0) or 0)

    # Primary rule: any pre-consent or post-reject tracker presence is a mismatch.
    if s0_trackers > 0 or s1_trackers > 0:
        return True

    # Secondary rule: only non-essential cookies may indicate tracking.
    # Consent/essential cookies are excluded at the crawler layer.
    if s0_nonessential_cookies > 0 or s1_nonessential_cookies > 0:
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
                "total_trackers <- known_tracker_count",
                "trackers_detected <- known_trackers",
                "third_party_request_count preserved separately",
                "tracker_names <- known_tracker_names",
                "cookie_names unavailable in source and left empty",
            ],
        },
    }
