"""
Privacy Score Calculator
Produces a composite 0–100 score and letter grade (A–F) based on
all analysis dimensions. Scoring methodology is transparent and
grounded in GDPR/CCPA compliance factors and privacy best practices.

Weighting rationale:
 - Data collection (20%): The foundation – what's collected drives everything else
 - Third-party sharing (20%): Major privacy risk vector
 - Transparency/Sentiment (15%): How honest/clear is the policy
 - Rights coverage (15%): Legal compliance signal
 - Retention (12%): Storage limitation principle (GDPR Art 5(1)(e))
 - Dark patterns (10%): Consent manipulation
 - Cookie/tracker security (8%): Technical privacy controls
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


SENSITIVITY_PENALTY = {
    "critical": 12,
    "high": 6,
    "medium": 2,
    "low": 0,
}

RETENTION_RATING_SCORE = {
    "excellent": 100,
    "good": 80,
    "fair": 55,
    "poor": 30,
    "very_poor": 5,
    "unknown": 0,
}

DARK_PATTERN_PENALTIES = {
    "high": 15,
    "medium": 8,
    "low": 4,
}

TRANSPARENCY_LEVELS = {
    "high": 90,
    "medium": 60,
    "low": 30,
    "very_low": 10,
}


@dataclass
class ScoreBreakdown:
    overall: int
    grade: str
    risk_level: str
    summary: str

    # Dimension scores (0–100 each, higher = better privacy)
    data_collection_score: int
    sharing_score: int
    transparency_score: int
    rights_score: int
    retention_score: int
    dark_patterns_score: int
    technical_score: int
    mismatch_score: int

    # Weight of each dimension
    weights: Dict[str, float]

    # Penalty details
    penalties: List[Dict]
    bonuses: List[Dict]


def _grade(score: int) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 50: return "C"
    if score >= 30: return "D"
    return "F"


def _risk_level(score: int) -> str:
    if score >= 75: return "low"
    if score >= 50: return "medium"
    if score >= 30: return "high"
    return "critical"


def _calculate_transparency_score(sentiment) -> int:
    """Score transparency from extracted facts; never trust an upstream score field."""
    vagueness_score = getattr(sentiment, "vagueness_score", 0) or 0
    specificity_score = getattr(sentiment, "specificity_score", 0) or 0
    passive_ratio = getattr(sentiment, "passive_voice_ratio", 0.0) or 0.0
    accountability = getattr(sentiment, "accountability", {}) or {}
    named_count = len(getattr(sentiment, "named_third_parties", []) or [])

    if accountability:
        accountability_score = int(sum(1 for value in accountability.values() if value) / len(accountability) * 100)
    else:
        accountability_score = 0

    score = int(
        (specificity_score * 0.3)
        + (accountability_score * 0.3)
        + ((1 - passive_ratio) * 100 * 0.2)
        + (min(named_count, 10) * 3)
        - (vagueness_score * 0.2)
    )
    return max(0, min(100, score))


def calculate_score(
    data_types,          # List[DetectedDataType]
    third_parties,       # ThirdPartyAnalysis
    retention,           # RetentionAnalysis
    rights,              # RightsAnalysis
    sentiment,           # SentimentResult
    dark_patterns,       # DarkPatternAnalysis
    tracker_result,      # TrackerDetectionResult
    policy_found: bool,
    dynamic_crawling: Optional[dict] = None,
    mismatch_analysis: Optional[dict] = None,
) -> ScoreBreakdown:

    penalties: List[Dict] = []
    bonuses: List[Dict] = []

    # ── If no policy found, score is very low ─────────────────────────────────
    if not policy_found:
        return ScoreBreakdown(
            overall=-1,
            grade="N/A",
            risk_level="unknown",
            summary="No privacy policy found. Score cannot be calculated without a policy to analyze.",
            data_collection_score=0,
            sharing_score=0,
            transparency_score=0,
            rights_score=0,
            retention_score=0,
            dark_patterns_score=0,
            technical_score=0,
            mismatch_score=0,
            weights={},
            penalties=[{"reason": "No privacy policy found", "penalty": 0}],
            bonuses=[],
        )

    # ── 1. DATA COLLECTION SCORE (0–100) ─────────────────────────────────────
    # Starts at 100, deduct for sensitive data categories
    data_score = 100
    special_count = 0
    high_count = 0

    for dt in data_types:
        if dt.sensitivity == "critical":
            if dt.gdpr_special_category:
                special_count += 1
                data_score -= 10
                penalties.append({
                    "dimension": "data_collection",
                    "reason": f"GDPR special category data: {dt.name}",
                    "penalty": 10
                })
            else:
                special_count += 1
                data_score -= 8
                penalties.append({
                    "dimension": "data_collection",
                    "reason": f"Highly sensitive data: {dt.name}",
                    "penalty": 8
                })
        elif dt.sensitivity == "high":
            high_count += 1
            data_score -= 4
        elif dt.sensitivity == "medium":
            data_score -= 1

    # Penalize if many types are shared
    shared_count = sum(1 for dt in data_types if dt.shared)
    if shared_count > 5:
        data_score -= (shared_count - 5) * 3
        penalties.append({"dimension": "data_collection", "reason": f"{shared_count} data types shared with third parties", "penalty": (shared_count - 5) * 3})

    if third_parties.data_sold:
        data_score -= 20
        penalties.append({"dimension": "data_collection", "reason": "Personal data is sold to third parties", "penalty": 20})

    data_score = max(0, data_score)

    # ── 2. SHARING SCORE (0–100) ──────────────────────────────────────────────
    sharing_score = 100
    tp_count = third_parties.count

    if tp_count == 0:
        bonuses.append({"dimension": "sharing", "reason": "No third-party sharing detected", "bonus": 5})
    elif tp_count <= 5:
        sharing_score -= tp_count * 3
    elif tp_count <= 15:
        sharing_score -= 15 + (tp_count - 5) * 4
        penalties.append({"dimension": "sharing", "reason": f"{tp_count} third-party data recipients", "penalty": 15 + (tp_count - 5) * 4})
    else:
        sharing_score -= 55 + (tp_count - 15) * 2
        penalties.append({"dimension": "sharing", "reason": f"Excessive third-party sharing ({tp_count} parties)", "penalty": 55 + (tp_count - 15) * 2})

    if third_parties.advertising_partners > 3:
        sharing_score -= third_parties.advertising_partners * 4
        penalties.append({"dimension": "sharing", "reason": f"{third_parties.advertising_partners} advertising partners", "penalty": third_parties.advertising_partners * 4})

    if third_parties.data_sold:
        sharing_score -= 25
        penalties.append({"dimension": "sharing", "reason": "Data sold to third parties (CCPA opt-out required)", "penalty": 25})

    if third_parties.cross_border_transfers and not third_parties.transfer_safeguards:
        sharing_score -= 15
        penalties.append({"dimension": "sharing", "reason": "International data transfers without documented safeguards", "penalty": 15})
    elif third_parties.transfer_safeguards:
        bonuses.append({"dimension": "sharing", "reason": f"Transfer safeguards documented: {', '.join(third_parties.transfer_safeguards[:2])}", "bonus": 5})

    # Unnamed third parties penalty
    if third_parties.unnamed_count > 10:
        sharing_score -= 10
        penalties.append({"dimension": "sharing", "reason": f"≥{third_parties.unnamed_count} unnamed third parties referenced", "penalty": 10})

    sharing_score = max(0, sharing_score)

    # ── 3. TRANSPARENCY SCORE (0–100) ─────────────────────────────────────────
    transparency_score = _calculate_transparency_score(sentiment)

    # DPO presence
    if sentiment.accountability.get("dpo_named"):
        bonuses.append({"dimension": "transparency", "reason": "Data Protection Officer (DPO) named", "bonus": 5})
    else:
        penalties.append({"dimension": "transparency", "reason": "No DPO identified (recommended under GDPR Art. 37)", "penalty": 5})

    if sentiment.accountability.get("legitimate_basis"):
        bonuses.append({"dimension": "transparency", "reason": "Lawful basis for processing explicitly stated", "bonus": 5})
    else:
        penalties.append({"dimension": "transparency", "reason": "Lawful basis for processing not clearly stated (GDPR Art. 6)", "penalty": 8})

    if sentiment.accountability.get("privacy_by_design"):
        bonuses.append({"dimension": "transparency", "reason": "Privacy by Design/Default principles mentioned", "bonus": 5})

    if sentiment.named_third_party_count > 5:
        bonuses.append({"dimension": "transparency", "reason": f"{sentiment.named_third_party_count} third parties specifically named", "bonus": 5})

    transparency_score = max(0, min(100, transparency_score))

    # ── 4. RIGHTS SCORE (0–100) ───────────────────────────────────────────────
    rights_score = int((rights.gdpr_score + rights.ccpa_score) / 2)

    if rights.dnt_honored:
        bonuses.append({"dimension": "rights", "reason": "Do Not Track (DNT) / GPC honored", "bonus": 5})
    elif rights.dnt_mentioned:
        bonuses.append({"dimension": "rights", "reason": "DNT mentioned", "bonus": 2})

    if rights.global_privacy_control:
        bonuses.append({"dimension": "rights", "reason": "Global Privacy Control (GPC) supported", "bonus": 5})

    if rights.frameworks_mentioned:
        bonuses.append({"dimension": "rights", "reason": f"Frameworks referenced: {', '.join(rights.frameworks_mentioned[:3])}", "bonus": 3})

    rights_score = max(0, min(100, rights_score))

    # ── 5. RETENTION SCORE (0–100) ────────────────────────────────────────────
    retention_score = RETENTION_RATING_SCORE.get(retention.overall_rating, 0)

    if retention.has_event_based_deletion:
        bonuses.append({"dimension": "retention", "reason": "Event-based deletion policy (e.g., upon account closure)", "bonus": 10})

    if retention.deletion_on_request:
        bonuses.append({"dimension": "retention", "reason": "Data deletion on user request confirmed", "bonus": 10})

    if retention.has_indefinite_retention:
        retention_score -= 30
        penalties.append({"dimension": "retention", "reason": "Data retained indefinitely", "penalty": 30})

    if not retention.has_specific_periods and not retention.has_event_based_deletion:
        penalties.append({"dimension": "retention", "reason": "No specific retention periods stated (violates GDPR Art. 5(1)(e))", "penalty": 20})

    if retention.storage_limitation_mentioned:
        bonuses.append({"dimension": "retention", "reason": "Storage limitation principle explicitly acknowledged", "bonus": 5})

    retention_score = max(0, min(100, retention_score))

    # ── 6. DARK PATTERNS SCORE (0–100) ───────────────────────────────────────
    dark_patterns_score = 100
    for dp in dark_patterns.detected:
        penalty = DARK_PATTERN_PENALTIES.get(dp.severity, 5)
        dark_patterns_score -= penalty
        penalties.append({
            "dimension": "dark_patterns",
            "reason": f"Dark pattern: {dp.name} ({dp.gdpr_reference})",
            "penalty": penalty
        })

    if dark_patterns.consent_mechanism_quality == "good":
        bonuses.append({"dimension": "dark_patterns", "reason": "Good consent mechanism: explicit, granular, withdrawable", "bonus": 10})
    elif dark_patterns.consent_mechanism_quality == "adequate":
        bonuses.append({"dimension": "dark_patterns", "reason": "Adequate consent mechanism", "bonus": 5})

    dark_patterns_score = max(0, dark_patterns_score)

    # ── 7. TECHNICAL SCORE (0–100) ─────────────────────────────────────────────
    # Covers cookie security, tracker count, fingerprinting
    technical_score = 100

    tracker_count = tracker_result.total_tracker_count if tracker_result else 0
    if tracker_count > 20:
        technical_score -= 30
        penalties.append({"dimension": "technical", "reason": f"{tracker_count} trackers detected on website", "penalty": 30})
    elif tracker_count > 10:
        technical_score -= 18
    elif tracker_count > 5:
        technical_score -= 10

    if tracker_result and tracker_result.fingerprinting_detected:
        technical_score -= 25
        penalties.append({"dimension": "technical", "reason": "Browser fingerprinting detected (high risk, often unconsented)", "penalty": 25})

    if tracker_result and tracker_result.session_recording_detected:
        technical_score -= 15
        penalties.append({"dimension": "technical", "reason": "Session recording active (captures all user interactions)", "penalty": 15})

    if tracker_result and tracker_result.cookies:
        sec = tracker_result.cookie_security
        if sec.get("secure_pct", 0) < 50:
            technical_score -= 10
            penalties.append({"dimension": "technical", "reason": f"Only {sec.get('secure_pct', 0):.0f}% of cookies have Secure flag", "penalty": 10})
        if sec.get("httponly_pct", 0) < 50:
            technical_score -= 8
            penalties.append({"dimension": "technical", "reason": f"Only {sec.get('httponly_pct', 0):.0f}% of cookies have HttpOnly flag", "penalty": 8})
        if sec.get("samesite_pct", 0) < 30:
            technical_score -= 5
            penalties.append({"dimension": "technical", "reason": f"Only {sec.get('samesite_pct', 0):.0f}% of cookies have SameSite attribute", "penalty": 5})

    if tracker_result and tracker_result.cmp_detected:
        bonuses.append({"dimension": "technical", "reason": f"Consent Management Platform detected: {tracker_result.cmp_detected}", "bonus": 8})

    if tracker_result and not tracker_result.trackers:
        bonuses.append({"dimension": "technical", "reason": "No trackers detected on website", "bonus": 15})

    # ── Dynamic Crawling Evaluation (S0, S1, S2) ───────────────────────────────
    if dynamic_crawling:
        state_quality = dynamic_crawling.get("state_quality") or {}
        if isinstance(state_quality, dict):
            usable_for_scoring = bool(state_quality.get("usable_for_scoring", True))
        else:
            usable_for_scoring = bool(getattr(state_quality, "usable_for_scoring", True))

        if usable_for_scoring:
            s0 = dynamic_crawling.get("S0", {})
            s1 = dynamic_crawling.get("S1", {})
            s0_trackers = s0.get("total_trackers", 0)
            s1_trackers = s1.get("total_trackers", 0)
            mismatch = dynamic_crawling.get("mismatch_detected", False)

            if mismatch:
                # S1 (Reject) resulted in same or more trackers than S0 (Baseline)
                technical_score -= 25
                penalties.append({"dimension": "technical", "reason": f"Consent mismatch: Tracking behavior unchanged or worsened after explicitly rejecting consent (S0: {s0_trackers}, S1: {s1_trackers})", "penalty": 25})
            elif s0_trackers > 0 and s1_trackers < s0_trackers:
                bonuses.append({"dimension": "technical", "reason": f"Trackers successfully reduced after rejecting consent (S0: {s0_trackers} -> S1: {s1_trackers})", "bonus": 10})
            
            if s0_trackers > 5:
                technical_score -= 10
                penalties.append({"dimension": "technical", "reason": f"Tracking started before consent (S0/Baseline has {s0_trackers} trackers)", "penalty": 10})
        else:
            penalties.append({
                "dimension": "technical",
                "reason": "Dynamic crawl inconclusive; technical crawl adjustments skipped.",
                "penalty": 0,
            })

    technical_score = max(0, technical_score)

    # ── 8. MISMATCH SCORE (0–100) ──────────────────────────────────────────────
    # Comes from the mismatch analyzer; defaults to neutral if unavailable
    m_score = 50  # neutral default when no mismatch analysis
    if mismatch_analysis:
        m_score = mismatch_analysis.get("mismatch_score", 50)

        # Add mismatch-specific penalties
        for mm in mismatch_analysis.get("mismatches", []):
            if mm.get("severity") == "critical":
                penalties.append({
                    "dimension": "mismatch",
                    "reason": f"Policy-behavior mismatch: {mm.get('title', 'Unknown')}",
                    "penalty": 25,
                })
            elif mm.get("severity") == "high":
                penalties.append({
                    "dimension": "mismatch",
                    "reason": f"Policy-behavior mismatch: {mm.get('title', 'Unknown')}",
                    "penalty": 15,
                })

        if mismatch_analysis.get("consent_effective") is True and mismatch_analysis.get("total_count", 0) == 0:
            bonuses.append({
                "dimension": "mismatch",
                "reason": "No policy-behavior mismatches detected. Observed behavior matches policy claims.",
                "bonus": 10,
            })

    # ── Weighted overall score ─────────────────────────────────────────────────
    weights = {
        "data_collection": 0.18,
        "sharing": 0.18,
        "transparency": 0.13,
        "rights": 0.13,
        "retention": 0.10,
        "dark_patterns": 0.08,
        "technical": 0.08,
        "mismatch": 0.12,
    }

    overall = int(
        data_score * weights["data_collection"]
        + sharing_score * weights["sharing"]
        + transparency_score * weights["transparency"]
        + rights_score * weights["rights"]
        + retention_score * weights["retention"]
        + dark_patterns_score * weights["dark_patterns"]
        + technical_score * weights["technical"]
        + m_score * weights["mismatch"]
    )

    overall = max(0, min(100, overall))
    grade = _grade(overall)
    risk = _risk_level(overall)

    # ── Summary ────────────────────────────────────────────────────────────────
    summaries = {
        "A": "Strong privacy practices. Policy is transparent, rights are covered, and data collection is proportionate.",
        "B": "Good privacy practices with some areas for improvement. Generally compliant with major privacy regulations.",
        "C": "Average privacy posture. Several concerning practices detected. Review the detailed findings.",
        "D": "Poor privacy practices. Significant compliance gaps and risky data handling detected.",
        "F": "Very poor privacy practices. Major violations detected across multiple dimensions.",
    }

    return ScoreBreakdown(
        overall=overall,
        grade=grade,
        risk_level=risk,
        summary=summaries[grade],
        data_collection_score=data_score,
        sharing_score=sharing_score,
        transparency_score=transparency_score,
        rights_score=rights_score,
        retention_score=retention_score,
        dark_patterns_score=dark_patterns_score,
        technical_score=technical_score,
        mismatch_score=m_score,
        weights=weights,
        penalties=penalties[:20],
        bonuses=bonuses[:10],
    )
