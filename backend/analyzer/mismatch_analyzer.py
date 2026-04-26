"""
Policy-Behaviour Mismatch Analyzer
Cross-references privacy policy text claims against observed network behavior
from the 3-state dynamic crawl (S0=Baseline, S1=Reject, S2=Accept).

Detects discrepancies such as:
  - Trackers active despite rejection (consent violation)
  - Trackers present before any consent action (pre-consent tracking)
  - Third parties detected but not declared in the policy
  - Policy claims "no tracking" but trackers are detected
  - Cookie count/category discrepancies
  - Missing consent mechanism despite policy claiming consent-based processing

References:
  - GDPR Art. 5(1)(a): Lawfulness, fairness, transparency
  - GDPR Art. 6(1)(a): Consent as legal basis
  - GDPR Art. 7: Conditions for consent
  - EDPB Guidelines 05/2020: Consent under the GDPR
  - ePrivacy Directive Art. 5(3): Cookie consent requirement
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ─────────────────────────────────────────────────────────────────────────────
# Policy claim patterns
# ─────────────────────────────────────────────────────────────────────────────

# Patterns indicating the policy claims no third-party tracking
NO_TRACKER_CLAIMS = [
    r"we\s+do\s+not\s+(?:use|employ|utilize)\s+(?:any\s+)?third.party\s+track",
    r"we\s+don'?t\s+(?:use|employ|utilize)\s+(?:any\s+)?third.party\s+track",
    r"no\s+third.party\s+track(?:ers?|ing)",
    r"we\s+do\s+not\s+(?:share|sell|disclose)\s+(?:your\s+)?(?:personal\s+)?(?:data|information)\s+(?:with|to)\s+(?:any\s+)?third.part",
    r"we\s+don'?t\s+(?:share|sell)\s+(?:your\s+)?(?:data|information)",
    r"(?:no|without)\s+(?:cookies?|trackers?)\s+(?:from|by)\s+third.part",
]

# Patterns indicating consent-first processing
CONSENT_FIRST_CLAIMS = [
    r"(?:we\s+)?(?:obtain|ask\s+for|request|require)\s+(?:your\s+)?consent\s+(?:before|prior\s+to|first)",
    r"consent\s+(?:is\s+)?(?:obtained|required|necessary)\s+(?:before|prior)",
    r"(?:no|without)\s+(?:cookies?|tracking)\s+(?:before|prior\s+to|until)\s+(?:your\s+)?consent",
    r"we\s+(?:only|exclusively)\s+(?:use|set|place)\s+cookies?\s+(?:after|once|when)\s+(?:you\s+)?(?:have\s+)?(?:given|provided|granted)\s+consent",
    r"cookies?\s+(?:are\s+)?(?:only\s+)?(?:set|placed|used)\s+(?:with|upon|after)\s+(?:your\s+)?consent",
]

# Patterns indicating consent rejection is honored
CONSENT_RESPECT_CLAIMS = [
    r"(?:if|when|should)\s+you\s+(?:reject|decline|refuse|deny)\s+(?:cookies?|consent)",
    r"rejecting\s+(?:cookies?|consent)\s+(?:will|means?|ensures?)\s+(?:that\s+)?(?:we\s+)?(?:will\s+)?(?:not|stop|cease|no\s+longer)\s+(?:use|set|place|track)",
    r"opt.?out\s+(?:of\s+)?(?:all\s+)?(?:non.?essential\s+)?(?:cookies?|tracking)",
    r"you\s+(?:can|may)\s+(?:choose\s+to\s+)?reject\s+(?:all\s+)?(?:non.?essential\s+)?cookies?",
    r"(?:only\s+)?(?:essential|necessary|required)\s+cookies?\s+(?:will\s+)?(?:remain|be\s+used|be\s+kept)",
]

# Patterns indicating specific data collection denial
NO_DATA_SALE_CLAIMS = [
    r"we\s+(?:do\s+not|don'?t|never)\s+sell\s+(?:your\s+)?(?:personal\s+)?(?:data|information)",
    r"(?:we\s+)?(?:do\s+not|don'?t)\s+sell\s+(?:or\s+rent\s+)?(?:your\s+)?(?:personal\s+)?(?:data|information)",
]


# ─────────────────────────────────────────────────────────────────────────────
# Tracker-to-data-type mapping (what data known trackers typically collect)
# Used to detect undeclared data collection
# ─────────────────────────────────────────────────────────────────────────────

TRACKER_DATA_COLLECTION = {
    "Google Analytics": ["behavioral", "device", "approximate_location"],
    "Google Ads": ["behavioral", "inferences", "device", "approximate_location"],
    "Google Tag Manager": ["behavioral", "device"],
    "Facebook Pixel": ["behavioral", "inferences", "social_connections", "device"],
    "Meta Pixel": ["behavioral", "inferences", "social_connections", "device"],
    "TikTok Pixel": ["behavioral", "inferences", "device"],
    "Hotjar": ["behavioral", "device", "user_content"],
    "FullStory": ["behavioral", "device", "user_content", "communications"],
    "LogRocket": ["behavioral", "device", "user_content"],
    "Mixpanel": ["behavioral", "device", "identity"],
    "Amplitude": ["behavioral", "device"],
    "Segment": ["behavioral", "device", "identity"],
    "Criteo": ["behavioral", "inferences", "device"],
    "DoubleClick": ["behavioral", "inferences", "device"],
    "AdRoll": ["behavioral", "inferences"],
    "LinkedIn Insight": ["behavioral", "professional", "device"],
    "Twitter Pixel": ["behavioral", "device"],
    "Pinterest Tag": ["behavioral", "device"],
    "Snapchat Pixel": ["behavioral", "device"],
    "Microsoft Clarity": ["behavioral", "device", "user_content"],
    "Yandex.Metrica": ["behavioral", "device", "approximate_location"],
}

# Known advertising/data-broker related tracker categories
ADVERTISING_CATEGORIES = {"advertising", "ad_network", "ad_exchange", "retargeting", "social_advertising"}
DATA_BROKER_TRACKERS = {"criteo", "adroll", "taboola", "outbrain", "doubleclick"}


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Mismatch:
    mismatch_type: str          # e.g., "undeclared_trackers", "consent_ineffective"
    severity: str               # "critical" | "high" | "medium" | "low"
    title: str                  # short description
    policy_claim: str           # what the policy says
    observed_behavior: str      # what we actually saw
    evidence_policy: str        # text snippet from policy
    evidence_observed: Dict[str, Any]  # data from dynamic crawl
    gdpr_reference: str         # relevant regulation
    recommendation: str         # what the site should fix


@dataclass
class MismatchAnalysis:
    mismatches: List[Mismatch]
    total_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    mismatch_score: int              # 0–100 (100 = no mismatches = good)
    consent_effective: bool          # does rejecting actually reduce tracking?
    consent_effectiveness_pct: float # % reduction in trackers S0->S1
    pre_consent_tracking: bool       # tracking before any consent action?
    pre_consent_tracker_count: int
    undeclared_tracker_count: int
    undeclared_tracker_names: List[str]
    summary: str


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def _find_policy_evidence(policy_text: str, patterns: List[str]) -> Optional[str]:
    """Search for a pattern match in policy text and return surrounding context."""
    text_lower = policy_text.lower()
    for pattern in patterns:
        m = re.search(pattern, text_lower)
        if m:
            start = max(0, m.start() - 60)
            end = min(len(policy_text), m.end() + 80)
            snippet = " ".join(policy_text[start:end].split())
            return f"…{snippet}…"
    return None


def _policy_claims(policy_text: str, patterns: List[str]) -> bool:
    """Check if the policy text makes a specific claim."""
    text_lower = policy_text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _extract_named_parties_from_policy(policy_analysis: dict) -> Set[str]:
    """Extract all named third parties from the policy analysis result."""
    names: Set[str] = set()

    # From third_parties.parties
    for party in policy_analysis.get("third_parties", {}).get("parties", []):
        name = party.get("name", "").lower().strip()
        if name:
            names.add(name)

    # From sentiment.named_third_parties
    for name in policy_analysis.get("sentiment", {}).get("named_third_parties", []):
        names.add(name.lower().strip())

    return names


def _extract_detected_tracker_names(dynamic_result: dict) -> Dict[str, Set[str]]:
    """Extract tracker names per state from dynamic crawl results."""
    result = {}
    for state_key in ("S0", "S1", "S2"):
        state = dynamic_result.get(state_key, {})
        trackers = state.get("trackers_detected", [])
        names = set()
        for t in trackers:
            name = t.get("name", "").lower().strip()
            if name:
                names.add(name)
        result[state_key] = names
    return result


def _extract_all_third_party_domains(dynamic_result: dict) -> Dict[str, Set[str]]:
    """Extract all third-party domains per state."""
    result = {}
    for state_key in ("S0", "S1", "S2"):
        state = dynamic_result.get(state_key, {})
        domains = set(d.lower() for d in state.get("third_party_domains", []))
        result[state_key] = domains
    return result


def _get_data_types_from_policy(policy_analysis: dict) -> Set[str]:
    """Get set of detected data category IDs from policy analysis."""
    return {
        dt.get("category_id", "").lower()
        for dt in policy_analysis.get("data_types", [])
        if dt.get("category_id")
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main analysis function
# ─────────────────────────────────────────────────────────────────────────────

def analyze_mismatches(
    policy_text: str,
    policy_analysis: dict,
    dynamic_result: Optional[dict],
    tracker_result: Optional[dict] = None,
) -> MismatchAnalysis:
    """
    Cross-reference policy text claims against observed dynamic crawl behavior.

    Args:
        policy_text: Raw privacy policy text
        policy_analysis: Dict output from policy_analyzer.analyze_policy()
        dynamic_result: Dict output from dynamic_crawler.run_3_state_crawl()
        tracker_result: Dict output from detector.detect_trackers_from_html()

    Returns:
        MismatchAnalysis with all detected discrepancies
    """
    mismatches: List[Mismatch] = []

    # If no dynamic crawl data, we can only do limited analysis
    if not dynamic_result:
        return MismatchAnalysis(
            mismatches=[],
            total_count=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            mismatch_score=100,
            consent_effective=True,
            consent_effectiveness_pct=100.0,
            pre_consent_tracking=False,
            pre_consent_tracker_count=0,
            undeclared_tracker_count=0,
            undeclared_tracker_names=[],
            summary="Dynamic crawl data unavailable — mismatch analysis skipped.",
        )

    state_quality = dynamic_result.get("state_quality") or {}
    if isinstance(state_quality, dict):
        usable_for_mismatch = bool(state_quality.get("usable_for_mismatch", True))
        quality_reasons = state_quality.get("reasons") or []
    else:
        usable_for_mismatch = bool(getattr(state_quality, "usable_for_mismatch", True))
        quality_reasons = getattr(state_quality, "reasons", []) or []

    if not usable_for_mismatch:
        reason_text = ", ".join(str(reason) for reason in quality_reasons) if quality_reasons else "insufficient confidence in S1/S2 state transitions"
        return MismatchAnalysis(
            mismatches=[],
            total_count=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            mismatch_score=50,
            consent_effective=False,
            consent_effectiveness_pct=0.0,
            pre_consent_tracking=False,
            pre_consent_tracker_count=0,
            undeclared_tracker_count=0,
            undeclared_tracker_names=[],
            summary=f"Dynamic crawl inconclusive for mismatch analysis: {reason_text}.",
        )

    text_lower = policy_text.lower()
    s0 = dynamic_result.get("S0", {})
    s1 = dynamic_result.get("S1", {})
    s2 = dynamic_result.get("S2", {})

    s0_trackers = s0.get("total_trackers", 0)
    s1_trackers = s1.get("total_trackers", 0)
    s2_trackers = s2.get("total_trackers", 0)
    s0_cookies = s0.get("total_cookies", 0)
    s1_cookies = s1.get("total_cookies", 0)
    s2_cookies = s2.get("total_cookies", 0)

    tracker_names_by_state = _extract_detected_tracker_names(dynamic_result)
    third_party_domains = _extract_all_third_party_domains(dynamic_result)
    policy_named_parties = _extract_named_parties_from_policy(policy_analysis)
    policy_data_types = _get_data_types_from_policy(policy_analysis)

    # All trackers detected across any state
    all_detected_trackers = tracker_names_by_state.get("S0", set()) | \
                            tracker_names_by_state.get("S1", set()) | \
                            tracker_names_by_state.get("S2", set())

    all_third_party_domains_observed = third_party_domains.get("S0", set()) | \
                                       third_party_domains.get("S1", set()) | \
                                       third_party_domains.get("S2", set())

    # ── 1. No-Tracker Claim Violation ─────────────────────────────────────────
    if _policy_claims(text_lower, NO_TRACKER_CLAIMS) and all_detected_trackers:
        evidence = _find_policy_evidence(policy_text, NO_TRACKER_CLAIMS)
        mismatches.append(Mismatch(
            mismatch_type="no_tracker_claim_violation",
            severity="critical",
            title="Policy claims no third-party tracking, but trackers were detected",
            policy_claim="The privacy policy explicitly states that no third-party trackers are used.",
            observed_behavior=f"{len(all_detected_trackers)} third-party tracker(s) detected: {', '.join(sorted(all_detected_trackers)[:5])}",
            evidence_policy=evidence or "No-tracker claim found in policy text",
            evidence_observed={
                "detected_trackers": sorted(all_detected_trackers)[:10],
                "s0_count": s0_trackers,
                "s2_count": s2_trackers,
            },
            gdpr_reference="GDPR Art. 5(1)(a) — Transparency principle violated",
            recommendation="Either remove all third-party trackers or update the privacy policy to accurately disclose their use.",
        ))

    # ── 2. Consent Ineffective (S1 ≥ S0) ─────────────────────────────────────
    consent_effective = True
    consent_effectiveness_pct = 100.0

    if s0_trackers > 0:
        if s1_trackers >= s0_trackers:
            consent_effective = False
            consent_effectiveness_pct = 0.0

            severity = "critical"
            evidence = _find_policy_evidence(policy_text, CONSENT_RESPECT_CLAIMS)

            mismatches.append(Mismatch(
                mismatch_type="consent_ineffective",
                severity=severity,
                title="Rejecting cookies did not reduce tracking",
                policy_claim="Consent mechanisms imply that rejecting stops non-essential tracking.",
                observed_behavior=(
                    f"Trackers BEFORE consent: {s0_trackers}, "
                    f"Trackers AFTER rejection: {s1_trackers}. "
                    f"Rejection had no effect on tracking behavior."
                ),
                evidence_policy=evidence or "Consent mechanism present but rejection is ineffective",
                evidence_observed={
                    "s0_trackers": s0_trackers,
                    "s1_trackers": s1_trackers,
                    "s0_tracker_names": sorted(tracker_names_by_state.get("S0", set()))[:10],
                    "s1_tracker_names": sorted(tracker_names_by_state.get("S1", set()))[:10],
                },
                gdpr_reference="GDPR Art. 7(3) — Withdrawal of consent must be effective; ePrivacy Art. 5(3)",
                recommendation=(
                    "Ensure that rejecting cookies actually disables all non-essential "
                    "trackers and third-party scripts. This is a GDPR compliance requirement."
                ),
            ))
        else:
            reduction = ((s0_trackers - s1_trackers) / s0_trackers) * 100
            consent_effectiveness_pct = round(reduction, 1)

            # Partial effectiveness — still some trackers after rejection
            if s1_trackers > 0:
                remaining_after_reject = tracker_names_by_state.get("S1", set())
                mismatches.append(Mismatch(
                    mismatch_type="consent_partial",
                    severity="medium",
                    title="Some trackers persist after rejecting cookies",
                    policy_claim="Rejecting cookies should disable non-essential tracking.",
                    observed_behavior=(
                        f"Trackers reduced from {s0_trackers} to {s1_trackers} after rejection "
                        f"({consent_effectiveness_pct:.0f}% reduction), but {s1_trackers} tracker(s) remain: "
                        f"{', '.join(sorted(remaining_after_reject)[:5])}"
                    ),
                    evidence_policy=_find_policy_evidence(policy_text, CONSENT_RESPECT_CLAIMS) or "",
                    evidence_observed={
                        "s0_trackers": s0_trackers,
                        "s1_trackers": s1_trackers,
                        "remaining_trackers": sorted(remaining_after_reject)[:10],
                        "reduction_pct": consent_effectiveness_pct,
                    },
                    gdpr_reference="ePrivacy Art. 5(3) — Only strictly necessary cookies exempt from consent",
                    recommendation="Review which trackers remain after rejection and ensure they are strictly necessary.",
                ))
    elif s0_trackers == 0 and s1_trackers == 0:
        consent_effective = True
        consent_effectiveness_pct = 100.0

    # ── 3. Pre-Consent Tracking ───────────────────────────────────────────────
    pre_consent_tracking = s0_trackers > 0

    if pre_consent_tracking:
        severity = "high" if s0_trackers >= 3 else "medium"
        claims_consent_first = _policy_claims(text_lower, CONSENT_FIRST_CLAIMS)

        if claims_consent_first:
            severity = "critical"  # claims consent-first but tracks before consent

        evidence = _find_policy_evidence(policy_text, CONSENT_FIRST_CLAIMS) if claims_consent_first else None

        mismatches.append(Mismatch(
            mismatch_type="pre_consent_tracking",
            severity=severity,
            title="Tracking active before user consent",
            policy_claim=(
                "Policy claims consent is obtained before tracking."
                if claims_consent_first else
                "Tracking should not begin before user consent under ePrivacy Directive."
            ),
            observed_behavior=(
                f"{s0_trackers} tracker(s) detected in baseline state (before any user interaction): "
                f"{', '.join(sorted(tracker_names_by_state.get('S0', set()))[:5])}"
            ),
            evidence_policy=evidence or "No explicit consent-first claim, but ePrivacy still requires it",
            evidence_observed={
                "s0_trackers": s0_trackers,
                "s0_tracker_names": sorted(tracker_names_by_state.get("S0", set()))[:10],
                "s0_cookies": s0_cookies,
            },
            gdpr_reference="ePrivacy Art. 5(3) — Prior consent required for non-essential cookies/trackers",
            recommendation=(
                "Defer all non-essential tracker scripts until the user has given explicit consent. "
                "Only strictly necessary cookies should be set before consent."
            ),
        ))

    # ── 4. Undeclared Trackers ────────────────────────────────────────────────
    undeclared_trackers: Set[str] = set()

    for tracker_name in all_detected_trackers:
        # Check if this tracker (or its parent company) is named in the policy
        declared = False
        for policy_name in policy_named_parties:
            # Fuzzy match: handle "Google Analytics" vs "Google", "Meta Pixel" vs "Facebook"
            if (tracker_name in policy_name or policy_name in tracker_name or
                _company_match(tracker_name, policy_name)):
                declared = True
                break
        if not declared:
            undeclared_trackers.add(tracker_name)

    if undeclared_trackers:
        mismatches.append(Mismatch(
            mismatch_type="undeclared_trackers",
            severity="high" if len(undeclared_trackers) >= 3 else "medium",
            title=f"{len(undeclared_trackers)} tracker(s) not declared in privacy policy",
            policy_claim=f"Policy names {len(policy_named_parties)} third parties.",
            observed_behavior=(
                f"{len(undeclared_trackers)} tracker(s) found that are not mentioned in the policy: "
                f"{', '.join(sorted(undeclared_trackers)[:5])}"
            ),
            evidence_policy=f"Named parties in policy: {', '.join(sorted(policy_named_parties)[:8]) or 'None'}",
            evidence_observed={
                "undeclared": sorted(undeclared_trackers)[:15],
                "policy_declared": sorted(policy_named_parties)[:15],
            },
            gdpr_reference="GDPR Art. 13(1)(e) — Recipients of personal data must be disclosed",
            recommendation="Update the privacy policy to disclose all third-party services that receive user data.",
        ))

    # ── 5. Third-Party Count Gap ──────────────────────────────────────────────
    policy_tp_count = policy_analysis.get("third_parties", {}).get("named_count", 0)
    observed_tp_count = len(all_third_party_domains_observed)

    if observed_tp_count > 0 and policy_tp_count > 0:
        ratio = observed_tp_count / max(policy_tp_count, 1)
        if ratio >= 3.0:
            mismatches.append(Mismatch(
                mismatch_type="third_party_count_gap",
                severity="medium",
                title="Significantly more third parties observed than declared",
                policy_claim=f"Policy names {policy_tp_count} third-party recipients.",
                observed_behavior=f"{observed_tp_count} unique third-party domains contacted during browsing.",
                evidence_policy=f"{policy_tp_count} named third parties in policy",
                evidence_observed={
                    "policy_count": policy_tp_count,
                    "observed_count": observed_tp_count,
                    "ratio": round(ratio, 1),
                    "sample_domains": sorted(all_third_party_domains_observed)[:15],
                },
                gdpr_reference="GDPR Art. 5(1)(a) — Transparency principle",
                recommendation="Review all third-party integrations and update the privacy policy accordingly.",
            ))
    elif policy_tp_count == 0 and observed_tp_count > 5:
        mismatches.append(Mismatch(
            mismatch_type="third_party_count_gap",
            severity="high",
            title="Third-party domains contacted but none declared",
            policy_claim="No third parties named in the privacy policy.",
            observed_behavior=f"{observed_tp_count} third-party domains detected during browsing.",
            evidence_policy="No named third parties found",
            evidence_observed={
                "observed_count": observed_tp_count,
                "sample_domains": sorted(all_third_party_domains_observed)[:15],
            },
            gdpr_reference="GDPR Art. 13(1)(e) — Obligation to disclose data recipients",
            recommendation="List all third-party services in the privacy policy.",
        ))

    # ── 6. Undeclared Data Collection via Trackers ────────────────────────────
    undeclared_data_types: Set[str] = set()
    for tracker_name in all_detected_trackers:
        # Normalize name for lookup
        for known_tracker, data_types in TRACKER_DATA_COLLECTION.items():
            if known_tracker.lower() in tracker_name or tracker_name in known_tracker.lower():
                for dt in data_types:
                    if dt not in policy_data_types:
                        undeclared_data_types.add(dt)

    if undeclared_data_types:
        mismatches.append(Mismatch(
            mismatch_type="undeclared_data_collection",
            severity="high" if len(undeclared_data_types) >= 3 else "medium",
            title="Trackers collect data types not disclosed in privacy policy",
            policy_claim=f"Policy discloses {len(policy_data_types)} data categories.",
            observed_behavior=(
                f"Detected trackers are known to collect these undisclosed categories: "
                f"{', '.join(sorted(undeclared_data_types)[:5])}"
            ),
            evidence_policy=f"Disclosed data types: {', '.join(sorted(policy_data_types)[:8]) or 'None'}",
            evidence_observed={
                "undeclared_types": sorted(undeclared_data_types)[:10],
                "source_trackers": sorted(all_detected_trackers)[:10],
            },
            gdpr_reference="GDPR Art. 13(1)(c) — Purposes of processing must be disclosed",
            recommendation="Disclose all data categories that third-party trackers collect in the privacy policy.",
        ))

    # ── 7. Cookie Count Discrepancy ───────────────────────────────────────────
    # Check if cookie count is dramatically different from what policy implies
    if s2_cookies > 20 and s1_cookies > 10:
        # Even after rejection, many cookies remain
        mismatches.append(Mismatch(
            mismatch_type="cookie_discrepancy",
            severity="medium",
            title="High cookie count even after rejecting consent",
            policy_claim="Rejecting non-essential cookies should minimize cookie usage.",
            observed_behavior=(
                f"After accepting: {s2_cookies} cookies. "
                f"After rejecting: {s1_cookies} cookies. "
                f"A large number of cookies persist regardless of consent choice."
            ),
            evidence_policy="",
            evidence_observed={
                "s0_cookies": s0_cookies,
                "s1_cookies": s1_cookies,
                "s2_cookies": s2_cookies,
            },
            gdpr_reference="ePrivacy Art. 5(3) — Only strictly necessary cookies exempt from consent",
            recommendation="Audit all cookies and ensure non-essential ones are blocked when consent is rejected.",
        ))

    # ── 8. CMP Absence Despite Consent Claims ────────────────────────────────
    if tracker_result:
        tr = tracker_result if isinstance(tracker_result, dict) else (
            {k: getattr(tracker_result, k, None) for k in vars(tracker_result)}
            if hasattr(tracker_result, '__dict__') else {}
        )
        cmp_detected = tr.get("cmp_detected")

        policy_mentions_consent = bool(re.search(
            r"cookie\s+consent|consent\s+(?:banner|management|platform|tool)|"
            r"cookie\s+(?:banner|popup|notice|dialog)",
            text_lower,
        ))

        if policy_mentions_consent and not cmp_detected and (s0_trackers > 0 or s2_trackers > 0):
            mismatches.append(Mismatch(
                mismatch_type="cmp_absent",
                severity="high",
                title="No consent mechanism detected despite policy claims",
                policy_claim="Policy references a cookie consent mechanism.",
                observed_behavior="No Consent Management Platform (CMP) was detected on the website.",
                evidence_policy=_find_policy_evidence(policy_text, [
                    r"cookie\s+consent", r"consent\s+banner", r"consent\s+management",
                ]) or "",
                evidence_observed={
                    "cmp_detected": False,
                    "trackers_present": s0_trackers + s2_trackers > 0,
                },
                gdpr_reference="GDPR Art. 7 — Conditions for valid consent",
                recommendation="Implement a functional Consent Management Platform (CMP) to obtain valid consent.",
            ))

    # ── Calculate mismatch score ──────────────────────────────────────────────
    severity_scores = {"critical": 25, "high": 15, "medium": 8, "low": 3}
    total_penalty = sum(severity_scores.get(m.severity, 5) for m in mismatches)
    mismatch_score = max(0, 100 - total_penalty)

    critical = sum(1 for m in mismatches if m.severity == "critical")
    high = sum(1 for m in mismatches if m.severity == "high")
    medium = sum(1 for m in mismatches if m.severity == "medium")
    low = sum(1 for m in mismatches if m.severity == "low")

    # ── Summary ───────────────────────────────────────────────────────────────
    if not mismatches:
        summary = "No policy-behavior mismatches detected. The observed tracking behavior is consistent with the privacy policy."
    elif critical > 0:
        summary = (
            f"Critical privacy violations found: {critical} critical, {high} high severity mismatch(es). "
            f"The website's actual tracking behavior significantly contradicts its privacy policy."
        )
    elif high > 0:
        summary = (
            f"{high} high severity mismatch(es) detected. "
            f"The privacy policy does not fully reflect the website's actual data practices."
        )
    else:
        summary = (
            f"{medium + low} minor mismatch(es) detected. "
            f"Some discrepancies exist between stated and observed practices."
        )

    return MismatchAnalysis(
        mismatches=mismatches[:20],
        total_count=len(mismatches),
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        mismatch_score=mismatch_score,
        consent_effective=consent_effective,
        consent_effectiveness_pct=consent_effectiveness_pct,
        pre_consent_tracking=pre_consent_tracking,
        pre_consent_tracker_count=s0_trackers,
        undeclared_tracker_count=len(undeclared_trackers),
        undeclared_tracker_names=sorted(undeclared_trackers)[:15],
        summary=summary,
    )


def _company_match(tracker_name: str, policy_name: str) -> bool:
    """
    Fuzzy matching for company names to handle cases like:
    "Google Analytics" <-> "Google LLC"
    "Meta Pixel" <-> "Facebook"
    "Microsoft Clarity" <-> "Microsoft Corp"
    """
    ALIASES = {
        "google": {"google analytics", "google ads", "google tag manager", "doubleclick", "google llc", "youtube"},
        "meta": {"facebook", "instagram", "meta pixel", "facebook pixel", "meta platforms"},
        "microsoft": {"microsoft clarity", "bing", "linkedin", "microsoft corp"},
        "amazon": {"amazon", "aws", "amazon web services"},
        "twitter": {"twitter", "x", "twitter pixel"},
        "adobe": {"adobe", "adobe analytics", "omniture"},
        "oracle": {"oracle", "bluekai", "oracle data cloud"},
        "salesforce": {"salesforce", "heroku", "tableau"},
    }

    for canonical, aliases in ALIASES.items():
        tracker_match = tracker_name in aliases or canonical in tracker_name
        policy_match = policy_name in aliases or canonical in policy_name
        if tracker_match and policy_match:
            return True

    # Simple substring match on first word
    t_first = tracker_name.split()[0] if tracker_name else ""
    p_first = policy_name.split()[0] if policy_name else ""
    if t_first and p_first and len(t_first) > 3 and (t_first == p_first):
        return True

    return False
