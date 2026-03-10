"""
Retention Period Parser
Extracts and rates data retention periods from privacy policy text.
Based on storage limitation principle (GDPR Art. 5(1)(e)) and best practices.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Time-period normalization
# ─────────────────────────────────────────────────────────────────────────────

TIME_UNITS_TO_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7,
    "month": 30, "months": 30,
    "year": 365, "years": 365,
    "yr": 365, "yrs": 365,
}

WRITTEN_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "twelve": 12, "twenty": 20, "twenty-four": 24, "thirty": 30,
    "ninety": 90,
}

VAGUE_RETENTION_PATTERNS = [
    r"as long as (?:reasonably )?necessary",
    r"as needed",
    r"for (?:a )?reasonable (?:period|time|amount of time)",
    r"in accordance with (?:applicable )?law",
    r"until (?:no longer |it is )?necessary",
    r"for (?:the )?purposes? (?:described|outlined|set out)",
    r"for (?:an )?extended period",
    r"on (?:an )?ongoing basis",
    r"indefinitely",
    r"at our (?:sole )?discretion",
    r"until we (?:no longer )?need",
    r"for (?:business|legal|operational) purposes",
]

SPECIFIC_PERIOD_PATTERN = re.compile(
    r"(?:retain|keep|store|maintain|hold|preserve)\w*\s+(?:for\s+)?(?:up\s+to\s+|at\s+least\s+|approximately\s+)?"
    r"("
    r"(?:\d+(?:\.\d+)?)\s*(?:day|days|week|weeks|month|months|year|years|yr|yrs)"
    r"|(?:one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty|thirty|ninety)\s+"
    r"(?:day|days|week|weeks|month|months|year|years)"
    r")",
    re.IGNORECASE,
)

CONTEXT_PERIOD_PATTERN = re.compile(
    r"(?:for\s+(?:up\s+to\s+)?)"
    r"("
    r"(?:\d+(?:\.\d+)?)\s*(?:day|days|week|weeks|month|months|year|years|yr|yrs)"
    r"|(?:one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty|thirty|ninety)\s+"
    r"(?:day|days|week|weeks|month|months|year|years)"
    r")",
    re.IGNORECASE,
)

EVENT_BASED_PATTERNS = [
    (r"(?:until|upon|after|following)\s+account\s+(?:deletion|closure|termination|cancellation)", "Until account deletion"),
    (r"(?:when|once)\s+(?:you\s+)?(?:delete|close|terminate|cancel)\s+(?:your\s+)?account", "Until account deletion"),
    (r"(?:until|upon)\s+(?:your\s+)?request", "Until user requests deletion"),
    (r"upon\s+(?:written\s+)?request", "Upon request"),
    (r"within\s+\d+\s+(?:days?|months?)\s+of\s+(?:your\s+)?request", "Within defined period of request"),
    (r"(?:after|following)\s+(?:the\s+end\s+of\s+)?(?:our\s+)?(?:business\s+)?relationship", "After relationship ends"),
    (r"(?:upon|after)\s+(?:the\s+)?(?:expiry|expiration)\s+of\s+(?:the\s+)?(?:contract|agreement)", "After contract expiry"),
    (r"(?:as\s+long\s+as\s+)?(?:your\s+)?account\s+(?:is\s+)?(?:active|open|exists)", "While account is active"),
    (r"last\s+active", "Based on last activity"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Rating logic
# GDPR Art. 5(1)(e): "no longer than is necessary"
# Best-practice benchmarks (ICO guidance, EDPB guidelines)
# ─────────────────────────────────────────────────────────────────────────────

def _days_to_rating(days: Optional[int]) -> Tuple[str, str]:
    """
    Returns (rating, label) for a specific number of days.
    Benchmarks based on EDPB and ICO data retention guidance.
    """
    if days is None:
        return "unknown", "Unknown"
    if days <= 30:
        return "excellent", "≤ 30 days"
    if days <= 180:
        return "good", "1–6 months"
    if days <= 365:
        return "fair", "6–12 months"
    if days <= 730:
        return "poor", "1–2 years"
    return "very_poor", f">{days // 365} years"


def _parse_period_string(period_str: str) -> Optional[int]:
    """Convert a matched period string like '6 months' or 'three years' to days."""
    period_str = period_str.lower().strip()

    # Try numeric first
    num_match = re.match(r"(\d+(?:\.\d+)?)\s*(\w+)", period_str)
    if num_match:
        num = float(num_match.group(1))
        unit = num_match.group(2).rstrip("s")  # normalize plural
        multiplier = TIME_UNITS_TO_DAYS.get(unit) or TIME_UNITS_TO_DAYS.get(unit + "s")
        if multiplier:
            return int(num * multiplier)

    # Try written number
    for written, val in WRITTEN_NUMBERS.items():
        for unit, mult in TIME_UNITS_TO_DAYS.items():
            if period_str.startswith(written) and unit in period_str:
                return val * mult

    return None


@dataclass
class RetentionItem:
    context: str           # surrounding text snippet
    period_text: str       # raw matched text (e.g. "3 years" or "until account deletion")
    period_days: Optional[int]
    period_type: str       # "specific" | "event_based" | "vague"
    rating: str            # "excellent" | "good" | "fair" | "poor" | "very_poor" | "unknown"
    rating_label: str
    is_vague: bool


@dataclass
class RetentionAnalysis:
    items: List[RetentionItem]
    overall_rating: str
    has_vague_retention: bool
    has_indefinite_retention: bool
    has_event_based_deletion: bool
    has_specific_periods: bool
    has_deletion_policy: bool
    deletion_on_request: bool
    shortest_days: Optional[int]
    longest_days: Optional[int]
    storage_limitation_mentioned: bool


def analyze_retention(policy_text: str) -> RetentionAnalysis:
    """Full retention period analysis of policy text."""
    text_lower = policy_text.lower()
    items: List[RetentionItem] = []

    # 1. Find specific periods
    for match in SPECIFIC_PERIOD_PATTERN.finditer(text_lower):
        period_str = match.group(1)
        days = _parse_period_string(period_str)
        rating, label = _days_to_rating(days)
        start = max(0, match.start() - 80)
        end = min(len(policy_text), match.end() + 80)
        context = " ".join(policy_text[start:end].split())
        items.append(RetentionItem(
            context=f"…{context}…",
            period_text=period_str,
            period_days=days,
            period_type="specific",
            rating=rating,
            rating_label=label,
            is_vague=False,
        ))

    # 2. Additional "for X months/years" patterns in context
    for match in CONTEXT_PERIOD_PATTERN.finditer(text_lower):
        period_str = match.group(1)
        days = _parse_period_string(period_str)
        # Avoid duplicates
        already = any(i.period_text.lower() == period_str.lower() for i in items)
        if not already and days:
            rating, label = _days_to_rating(days)
            start = max(0, match.start() - 80)
            end = min(len(policy_text), match.end() + 80)
            context = " ".join(policy_text[start:end].split())
            items.append(RetentionItem(
                context=f"…{context}…",
                period_text=period_str,
                period_days=days,
                period_type="specific",
                rating=rating,
                rating_label=label,
                is_vague=False,
            ))

    # 3. Event-based retention
    for pattern, label in EVENT_BASED_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            start = max(0, match.start() - 80)
            end = min(len(policy_text), match.end() + 80)
            context = " ".join(policy_text[start:end].split())
            items.append(RetentionItem(
                context=f"…{context}…",
                period_text=label,
                period_days=None,
                period_type="event_based",
                rating="good",
                rating_label="Event-based deletion",
                is_vague=False,
            ))
            break  # one per pattern

    # 4. Vague retention
    for pattern in VAGUE_RETENTION_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            start = max(0, match.start() - 80)
            end = min(len(policy_text), match.end() + 80)
            context = " ".join(policy_text[start:end].split())
            already = any(i.period_text == "Vague / Unspecified" for i in items)
            if not already:
                items.append(RetentionItem(
                    context=f"…{context}…",
                    period_text="Vague / Unspecified",
                    period_days=None,
                    period_type="vague",
                    rating="very_poor",
                    rating_label="No specific period",
                    is_vague=True,
                ))
            break

    # ── Aggregate signals ─────────────────────────────────────────────────────
    specific = [i for i in items if i.period_type == "specific"]
    vague = [i for i in items if i.period_type == "vague"]
    event = [i for i in items if i.period_type == "event_based"]

    all_days = [i.period_days for i in specific if i.period_days]
    shortest = min(all_days) if all_days else None
    longest = max(all_days) if all_days else None

    deletion_on_request = bool(re.search(
        r"(?:delete|remove|erase)\w*\s+(?:your\s+)?(?:data|information|account)"
        r"(?:\s+upon|\s+on|\s+at|\s+following)\s+(?:your\s+)?request",
        text_lower,
    ))
    has_deletion = deletion_on_request or bool(event)

    storage_limitation = bool(re.search(
        r"(?:storage\s+limitation|data\s+minimiz|purpose\s+limitation|no\s+longer\s+necessary)",
        text_lower,
    ))

    # Overall rating
    rating_scores = {"excellent": 5, "good": 4, "fair": 3, "poor": 2, "very_poor": 1, "unknown": 0}
    if not items:
        overall = "very_poor"
    elif vague and not specific:
        overall = "very_poor"
    else:
        scores = [rating_scores.get(i.rating, 0) for i in items]
        avg = sum(scores) / len(scores) if scores else 0
        if avg >= 4.5:
            overall = "excellent"
        elif avg >= 3.5:
            overall = "good"
        elif avg >= 2.5:
            overall = "fair"
        elif avg >= 1.5:
            overall = "poor"
        else:
            overall = "very_poor"

    indefinite = bool(re.search(r"\bindefinitely\b", text_lower))

    return RetentionAnalysis(
        items=items[:20],  # cap at 20
        overall_rating=overall,
        has_vague_retention=bool(vague),
        has_indefinite_retention=indefinite,
        has_event_based_deletion=bool(event),
        has_specific_periods=bool(specific),
        has_deletion_policy=has_deletion,
        deletion_on_request=deletion_on_request,
        shortest_days=shortest,
        longest_days=longest,
        storage_limitation_mentioned=storage_limitation,
    )
