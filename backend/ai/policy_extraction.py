"""
Claude-assisted extraction for policy data categories and third-party recipients.

The deterministic analyzers remain the fallback. This module keeps the existing
data-category taxonomy, then asks Claude to choose from that taxonomy and provide
direct policy evidence for each decision.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from analyzer.data_categories import DATA_TAXONOMY, DetectedDataType
from analyzer.dark_pattern_detector import (
    DARK_PATTERN_DEFINITIONS,
    DarkPatternAnalysis,
    DetectedDarkPattern,
)
from analyzer.retention_parser import RetentionAnalysis, RetentionItem
from analyzer.rights_checker import (
    CCPA_RIGHTS,
    COOKIE_COMPLIANCE,
    GDPR_RIGHTS,
    OTHER_FRAMEWORKS,
    RightCoverage,
    RightsAnalysis,
)
from analyzer.sentiment_analyzer import ACCOUNTABILITY_PATTERNS, SentimentResult
from analyzer.third_party_analyzer import (
    SHARING_PURPOSES,
    ThirdPartyAnalysis,
    ThirdPartyEntry,
    _load_trust_db,
)
from ai.claude_client import FAST_MODEL, acomplete

AI_POLICY_EXTRACTION_VERSION = 7


@dataclass
class AIExtractionResult:
    data_types: List[DetectedDataType]
    third_parties: ThirdPartyAnalysis
    retention: RetentionAnalysis
    dark_patterns: DarkPatternAnalysis
    rights: RightsAnalysis
    sentiment: SentimentResult
    meta: Dict[str, Any]


def _ai_extraction_enabled() -> bool:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
    if os.getenv("ENABLE_AI_POLICY_EXTRACTION", "true").lower() not in {"1", "true", "yes"}:
        return False
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(acomplete and api_key and "your-api-key" not in api_key)


def ai_policy_extraction_enabled() -> bool:
    return _ai_extraction_enabled()


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _as_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    cleaned: List[str] = []
    for item in value:
        if isinstance(item, str):
            s = " ".join(item.split()).strip()
            if s and s not in cleaned:
                cleaned.append(s)
    return cleaned


def _as_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _as_int(value: Any, default: int = 0, *, min_value: int = 0, max_value: int = 100) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _as_float(value: Any, default: float = 0.0, *, min_value: float = 0.0, max_value: float = 1.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _normalize_purpose(value: str) -> str:
    value = (value or "").lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "ads": "advertising",
        "ad": "advertising",
        "marketing": "advertising",
        "email": "email_marketing",
        "support": "customer_support",
        "customer_service": "customer_support",
        "cloud": "hosting",
        "infrastructure": "hosting",
        "legal": "legal_compliance",
        "compliance": "legal_compliance",
    }
    return aliases.get(value, value)


def _normalize_purposes(values: Any) -> List[str]:
    purposes = []
    allowed = set(SHARING_PURPOSES.keys())
    for value in _as_list(values):
        normalized = _normalize_purpose(value)
        if normalized in allowed and normalized not in purposes:
            purposes.append(normalized)
    return purposes


def _taxonomy_prompt() -> str:
    rows = []
    for cat_id, cat in DATA_TAXONOMY.items():
        keywords = ", ".join(cat.get("keywords", [])[:8])
        rows.append(
            f"- {cat_id}: {cat['name']} | sensitivity={cat['sensitivity']} | examples={keywords}"
        )
    return "\n".join(rows)


def _normalize_for_match(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _quote_appears_in_text(quote: str, source_text: str) -> bool:
    quote_norm = _normalize_for_match(quote.strip(" .…"))
    source_norm = _normalize_for_match(source_text)
    if not quote_norm:
        return False
    if quote_norm in source_norm:
        return True

    words = quote_norm.split()
    if len(words) < 6:
        return False
    window = min(10, len(words))
    for idx in range(0, len(words) - window + 1):
        if " ".join(words[idx:idx + window]) in source_norm:
            return True
    return False


def _quote_list(value: Any, limit: int = 3, source_text: str | None = None) -> List[str]:
    quotes = []
    for quote in _as_list(value):
        if len(quote) > 260:
            quote = quote[:260].rsplit(" ", 1)[0].strip()
        if source_text and not _quote_appears_in_text(quote, source_text):
            continue
        if quote and quote not in quotes:
            quotes.append(quote)
        if len(quotes) >= limit:
            break
    return quotes


def _build_ai_data_types(items: Any, source_text: str) -> List[DetectedDataType]:
    if not isinstance(items, list):
        return []

    detected: List[DetectedDataType] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        cat_id = str(item.get("category_id", "")).strip()
        cat = DATA_TAXONOMY.get(cat_id)
        evidence = _quote_list(item.get("evidence"), source_text=source_text)
        if not cat or cat_id in seen or not evidence:
            continue
        seen.add(cat_id)
        detected.append(DetectedDataType(
            category_id=cat_id,
            name=cat["name"],
            sensitivity=cat["sensitivity"],
            gdpr_special_category=cat["gdpr_special_category"],
            gdpr_article=cat["gdpr_article"],
            ccpa_category=cat["ccpa_category"],
            color=cat["color"],
            icon=cat["icon"],
            evidence=[f"...{quote}..." for quote in evidence],
            shared=_as_bool(item.get("shared")),
            shared_with=_as_list(item.get("shared_with"))[:8],
            purposes=_normalize_purposes(item.get("purposes")),
            risk_description=cat["risk_description"],
        ))

    sensitivity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(detected, key=lambda d: sensitivity_order.get(d.sensitivity, 99))


def _trust_label(score: int) -> str:
    if score >= 70:
        return "trusted"
    if score >= 50:
        return "moderate"
    if score >= 30:
        return "concerning"
    return "unknown"


def _build_ai_third_parties(payload: Dict[str, Any], source_text: str) -> ThirdPartyAnalysis | None:
    if not isinstance(payload, dict):
        return None

    trust_db = _load_trust_db()
    parties: List[ThirdPartyEntry] = []
    seen = set()

    named_items = payload.get("named_parties", [])
    if isinstance(named_items, list):
        for item in named_items:
            if not isinstance(item, dict):
                continue
            name = " ".join(str(item.get("name", "")).split()).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            evidence = _quote_list(item.get("evidence"), limit=2, source_text=source_text)
            if not evidence:
                continue
            seen.add(key)

            db_entry = trust_db.get(key, {})
            trust_score = int(db_entry.get("trust_score", item.get("trust_score", 50) or 50))
            purposes = _normalize_purposes(item.get("purposes")) or db_entry.get("purposes", [])
            parties.append(ThirdPartyEntry(
                name=name,
                category=item.get("category") or db_entry.get("category", "Unknown"),
                trust_score=trust_score,
                trust_label=_trust_label(trust_score),
                data_types_shared=_as_list(item.get("data_types_shared")) or db_entry.get("typical_data", []),
                purposes=purposes,
                opt_out_url=db_entry.get("opt_out_url"),
                privacy_url=db_entry.get("privacy_url"),
                gdpr_compliant=db_entry.get("gdpr_compliant"),
                cross_border_transfer=_as_bool(item.get("cross_border_transfer"), db_entry.get("us_based", False)),
                is_data_broker=_as_bool(item.get("is_data_broker"), db_entry.get("is_data_broker", False)),
                evidence=[f"...{quote}..." for quote in evidence],
            ))

    named_count = len(parties)
    unnamed_items = payload.get("unnamed_recipients", [])
    unnamed_entries: List[ThirdPartyEntry] = []
    if isinstance(unnamed_items, list):
        for item in unnamed_items:
            if not isinstance(item, dict):
                continue
            label = " ".join(str(item.get("label", "")).split()).strip()
            evidence = _quote_list(item.get("evidence"), limit=2, source_text=source_text)
            if not label or not evidence:
                continue
            purposes = _normalize_purposes(item.get("purposes"))
            unnamed_entries.append(ThirdPartyEntry(
                name=label,
                category="Unnamed recipient category",
                trust_score=50,
                trust_label="unknown",
                data_types_shared=_as_list(item.get("data_types_shared")),
                purposes=purposes,
                opt_out_url=None,
                privacy_url=None,
                gdpr_compliant=None,
                cross_border_transfer=False,
                is_data_broker=False,
                evidence=[f"...{quote}..." for quote in evidence],
            ))
    unnamed_count = len(unnamed_entries)
    parties.extend(unnamed_entries)

    purpose_values = set()
    for party in parties:
        purpose_values.update(party.purposes)
    if isinstance(unnamed_items, list):
        for item in unnamed_items:
            if isinstance(item, dict):
                purpose_values.update(_normalize_purposes(item.get("purposes")))

    sharing_purposes = {
        purpose: purpose in purpose_values
        for purpose in SHARING_PURPOSES.keys()
    }

    data_sold = _as_bool(payload.get("data_sold"))
    cross_border = _as_bool(payload.get("cross_border_transfers")) or any(p.cross_border_transfer for p in parties)
    safeguards = _as_list(payload.get("transfer_safeguards"))

    advertising = sum(1 for p in parties if "advertising" in p.category.lower() or "advertising" in p.purposes)
    analytics = sum(1 for p in parties if "analytics" in p.category.lower() or "analytics" in p.purposes)
    total = named_count + unnamed_count

    if data_sold or any(p.is_data_broker for p in parties):
        risk = "critical"
    elif total >= 20 or advertising >= 5:
        risk = "high"
    elif total >= 8 or advertising >= 2:
        risk = "medium"
    else:
        risk = "low"

    sharing_score = min(100, (
        len(parties) * 3
        + unnamed_count
        + advertising * 5
        + (20 if data_sold else 0)
        + (10 if cross_border and not safeguards else 0)
    ))

    return ThirdPartyAnalysis(
        count=total,
        named_count=named_count,
        unnamed_count=unnamed_count,
        parties=sorted(parties, key=lambda p: p.trust_score),
        sharing_purposes=sharing_purposes,
        data_sold=data_sold,
        cross_border_transfers=cross_border,
        transfer_safeguards=safeguards,
        advertising_partners=advertising,
        analytics_partners=analytics,
        risk_level=risk,
        sharing_score=sharing_score,
    )


def _retention_rating(days: int | None, period_type: str, is_vague: bool) -> tuple[str, str]:
    if is_vague or period_type == "vague":
        return "very_poor", "No specific period"
    if period_type == "event_based":
        return "good", "Event-based deletion"
    if days is None:
        return "unknown", "Unknown"
    if days <= 30:
        return "excellent", "<= 30 days"
    if days <= 180:
        return "good", "1-6 months"
    if days <= 365:
        return "fair", "6-12 months"
    if days <= 730:
        return "poor", "1-2 years"
    return "very_poor", f">{days // 365} years"


def _overall_retention_rating(
    items: List[RetentionItem],
    *,
    has_indefinite_retention: bool = False,
) -> str:
    if has_indefinite_retention:
        return "very_poor"
    if not items:
        return "very_poor"
    # Retention is scored by the worst extracted retention posture, not by
    # Claude's self-assigned summary label.
    scores = {"unknown": 0, "very_poor": 1, "poor": 2, "fair": 3, "good": 4, "excellent": 5}
    return min(items, key=lambda item: scores.get(item.rating, 0)).rating


def _build_ai_retention(payload: Any, source_text: str) -> RetentionAnalysis | None:
    if not isinstance(payload, dict):
        return None

    items: List[RetentionItem] = []
    raw_items = payload.get("items", [])
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            quote_value = item.get("evidence") or item.get("context")
            evidence = _quote_list(
                [quote_value] if isinstance(quote_value, str) else quote_value,
                limit=1,
                source_text=source_text,
            )
            if not evidence:
                continue
            period_type = str(item.get("period_type", "")).strip().lower()
            if period_type not in {"specific", "event_based", "vague"}:
                continue
            raw_days = item.get("period_days")
            period_days = raw_days if isinstance(raw_days, int) and raw_days >= 0 else None
            period_text = " ".join(str(item.get("period_text", "")).split()).strip()
            if not period_text:
                period_text = "Vague / Unspecified" if period_type == "vague" else "Retention period"
            is_vague = period_type == "vague"
            rating, label = _retention_rating(period_days, period_type, is_vague)
            items.append(RetentionItem(
                context=f"...{evidence[0]}...",
                period_text=period_text,
                period_days=period_days,
                period_type=period_type,
                rating=rating,
                rating_label=label,
                is_vague=is_vague,
            ))
            if len(items) >= 20:
                break

    has_event = any(item.period_type == "event_based" for item in items)
    has_specific = any(item.period_type == "specific" for item in items)
    deletion_on_request = _as_bool(payload.get("deletion_on_request")) or any(
        "request" in item.period_text.lower() or "request" in item.context.lower()
        for item in items
    )
    has_indefinite = _as_bool(payload.get("has_indefinite_retention")) or any(
        "indefinite" in item.period_text.lower() or "indefinite" in item.context.lower()
        for item in items
    )
    days_values = [item.period_days for item in items if item.period_days is not None]
    overall = _overall_retention_rating(
        items,
        has_indefinite_retention=has_indefinite,
    )

    return RetentionAnalysis(
        items=items,
        overall_rating=overall,
        has_vague_retention=any(item.is_vague for item in items),
        has_indefinite_retention=has_indefinite,
        has_event_based_deletion=has_event,
        has_specific_periods=has_specific,
        has_deletion_policy=deletion_on_request or has_event,
        deletion_on_request=deletion_on_request,
        shortest_days=min(days_values) if days_values else None,
        longest_days=max(days_values) if days_values else None,
        storage_limitation_mentioned=_as_bool(payload.get("storage_limitation_mentioned")),
    )


def _dark_pattern_risk(detected: List[DetectedDarkPattern]) -> str:
    high = sum(1 for item in detected if item.severity == "high")
    medium = sum(1 for item in detected if item.severity == "medium")
    low = sum(1 for item in detected if item.severity == "low")
    if high >= 2:
        return "critical"
    if high >= 1:
        return "high"
    if medium >= 2:
        return "medium"
    if medium + low >= 1:
        return "low"
    return "none"


def _build_ai_dark_patterns(payload: Any, source_text: str) -> DarkPatternAnalysis | None:
    if not isinstance(payload, dict):
        return None
    definitions = {item["type"]: item for item in DARK_PATTERN_DEFINITIONS}
    detected: List[DetectedDarkPattern] = []
    seen = set()

    raw_patterns = payload.get("detected", [])
    if isinstance(raw_patterns, list):
        for item in raw_patterns:
            if not isinstance(item, dict):
                continue
            pattern_type = str(item.get("pattern_type", "")).strip()
            definition = definitions.get(pattern_type)
            if not definition or pattern_type in seen:
                continue
            evidence = _quote_list(item.get("evidence"), limit=2, source_text=source_text)
            if not evidence:
                continue
            seen.add(pattern_type)
            detected.append(DetectedDarkPattern(
                pattern_type=pattern_type,
                name=definition["name"],
                severity=definition["severity"],
                description=definition["description"],
                evidence=[f"...{quote}..." for quote in evidence],
                gdpr_reference=definition["gdpr_reference"],
                confidence=round(_as_float(item.get("confidence"), 0.8), 2),
            ))

    high = sum(1 for item in detected if item.severity == "high")
    medium = sum(1 for item in detected if item.severity == "medium")
    low = sum(1 for item in detected if item.severity == "low")
    consent_quality = str(payload.get("consent_mechanism_quality", "")).strip().lower()
    if consent_quality not in {"good", "adequate", "poor", "unclear"}:
        consent_quality = "poor" if high else "unclear"

    return DarkPatternAnalysis(
        detected=detected,
        count=len(detected),
        high_severity_count=high,
        medium_severity_count=medium,
        low_severity_count=low,
        overall_risk=_dark_pattern_risk(detected),
        consent_mechanism_quality=consent_quality,
    )


def _rights_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 55:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def _build_right_map(payload: Any, definitions: Dict[str, Dict[str, Any]], source_text: str) -> Dict[str, RightCoverage]:
    payload = payload if isinstance(payload, dict) else {}
    coverage: Dict[str, RightCoverage] = {}
    for right_id, right_def in definitions.items():
        item = payload.get(right_id, {})
        item = item if isinstance(item, dict) else {}
        evidence_value = item.get("evidence")
        evidence = _quote_list(
            [evidence_value] if isinstance(evidence_value, str) else evidence_value,
            limit=1,
            source_text=source_text,
        )
        covered = _as_bool(item.get("covered")) and bool(evidence)
        coverage[right_id] = RightCoverage(
            right_id=right_id,
            name=right_def["name"],
            article=right_def["article"],
            description=right_def["description"],
            covered=covered,
            evidence=f"...{evidence[0]}..." if covered else None,
        )
    return coverage


def _build_ai_rights(payload: Any, source_text: str) -> RightsAnalysis | None:
    if not isinstance(payload, dict):
        return None

    gdpr = _build_right_map(payload.get("gdpr"), GDPR_RIGHTS, source_text)
    ccpa = _build_right_map(payload.get("ccpa"), CCPA_RIGHTS, source_text)
    gdpr_score = int(sum(1 for right in gdpr.values() if right.covered) / len(GDPR_RIGHTS) * 100)
    ccpa_score = int(sum(1 for right in ccpa.values() if right.covered) / len(CCPA_RIGHTS) * 100)

    allowed_frameworks = {value["name"] for value in OTHER_FRAMEWORKS.values()}
    frameworks = [item for item in _as_list(payload.get("frameworks_mentioned")) if item in allowed_frameworks]
    raw_cookie = payload.get("cookie_compliance", {})
    raw_cookie = raw_cookie if isinstance(raw_cookie, dict) else {}
    cookie_compliance = {
        key: _as_bool(raw_cookie.get(key))
        for key in COOKIE_COMPLIANCE.keys()
    }

    return RightsAnalysis(
        gdpr=gdpr,
        gdpr_score=gdpr_score,
        gdpr_grade=_rights_grade(gdpr_score),
        ccpa=ccpa,
        ccpa_score=ccpa_score,
        ccpa_grade=_rights_grade(ccpa_score),
        frameworks_mentioned=frameworks,
        cookie_compliance=cookie_compliance,
        dnt_mentioned=_as_bool(payload.get("dnt_mentioned")) or cookie_compliance.get("dnt_honored", False),
        dnt_honored=_as_bool(payload.get("dnt_honored")) or cookie_compliance.get("dnt_honored", False),
        global_privacy_control=_as_bool(payload.get("global_privacy_control")),
        overall_rights_score=int((gdpr_score + ccpa_score) / 2),
    )


def _build_ai_sentiment(payload: Any, source_text: str, fallback: SentimentResult) -> SentimentResult | None:
    if not isinstance(payload, dict):
        return None

    accountability_payload = payload.get("accountability", {})
    accountability_payload = accountability_payload if isinstance(accountability_payload, dict) else {}
    accountability = {
        key: _as_bool(accountability_payload.get(key), fallback.accountability.get(key, False))
        for key in ACCOUNTABILITY_PATTERNS.keys()
    }
    accountability_score = int(sum(1 for value in accountability.values() if value) / len(accountability) * 100)

    overall = str(payload.get("overall_transparency", "")).strip().lower()
    if overall not in {"high", "medium", "low", "very_low"}:
        score = _as_int(payload.get("transparency_score"), fallback.transparency_score)
        if score >= 70:
            overall = "high"
        elif score >= 45:
            overall = "medium"
        elif score >= 20:
            overall = "low"
        else:
            overall = "very_low"

    named_parties = _as_list(payload.get("named_third_parties")) or fallback.named_third_parties
    named_parties = list(dict.fromkeys(named_parties))

    return SentimentResult(
        vagueness_score=_as_int(payload.get("vagueness_score"), fallback.vagueness_score),
        specificity_score=_as_int(payload.get("specificity_score"), fallback.specificity_score),
        passive_voice_ratio=_as_float(payload.get("passive_voice_ratio"), fallback.passive_voice_ratio),
        active_voice_count=_as_int(payload.get("active_voice_count"), fallback.active_voice_count, max_value=10000),
        passive_voice_count=_as_int(payload.get("passive_voice_count"), fallback.passive_voice_count, max_value=10000),
        named_third_parties=named_parties,
        named_third_party_count=len(named_parties),
        vague_term_examples=_quote_list(payload.get("vague_term_examples"), limit=10, source_text=source_text) or fallback.vague_term_examples,
        hedging_examples=_quote_list(payload.get("hedging_examples"), limit=10, source_text=source_text) or fallback.hedging_examples,
        specific_purpose_count=_as_int(payload.get("specific_purpose_count"), fallback.specific_purpose_count, max_value=1000),
        accountability=accountability,
        accountability_score=accountability_score,
        overall_transparency=overall,
        transparency_score=_as_int(payload.get("transparency_score"), fallback.transparency_score),
        avg_sentence_length=fallback.avg_sentence_length,
        readability_rating=fallback.readability_rating,
        flesch_kincaid_words=fallback.flesch_kincaid_words,
    )


def _build_extraction_prompt(
    *,
    domain: str,
    policy_excerpt: str,
    max_data_categories: int,
    max_evidence_quotes: int,
    max_string_items: int,
) -> str:
    return f"""
Analyze this privacy policy for {domain}.

Use ONLY the allowed data category IDs below. Do not invent category IDs.
Count a data category only when the policy says the site/service collects, receives,
uses, stores, or processes that user data. Do not count examples from user rights,
security disclaimers, or hypothetical legal text unless they describe actual collection.
Be exhaustive and strict: include every supported data category and every recipient
category with direct evidence, including sensitive data, device/browser identifiers,
tracking data, advertising identifiers, affiliates, service providers, analytics
providers, ad partners, and legal/government disclosures. Do not soften the result
because wording is common or industry-standard.

For third parties, extract recipients of user data. Exclude {domain}, the site itself,
and obvious first-party/parent-company references unless the policy clearly says data
is shared with separate affiliates or external recipients.
Treat "share", "disclose", "transfer", "make available", "sell", "targeted advertising",
and "cross-context behavioral advertising" as third-party sharing signals when the
policy connects them to personal data.

Every item MUST include exact short quotes copied from the policy text.
Keep the output compact:
- Return every supported data category that has direct evidence; there are at most {max_data_categories} allowed categories.
- Return every named third-party recipient mentioned as receiving user data.
- Return every generic recipient category mentioned as receiving user data, such as service providers, affiliates, advertisers, analytics providers, payment processors, law enforcement, or cloud providers.
- Do not stop at the most important examples. Include all unique recipients that have evidence.
- Each evidence array must contain {max_evidence_quotes} short quote(s), each under 180 characters.
- shared_with and data_types_shared may contain at most {max_string_items} short strings.
- purposes must only use these enum values:
  analytics, advertising, payment, customer_support, email_marketing, social_media, hosting, legal_compliance.
- If the same recipient is mentioned repeatedly, include it once with the best evidence quote.
- Do not include markdown, comments, explanations, or trailing commas.

ALLOWED DATA CATEGORIES:
{_taxonomy_prompt()}

Return ONLY valid JSON with this schema:
{{
  "data_categories": [
    {{
      "category_id": "contact",
      "evidence": ["exact short quote from policy"],
      "shared": true,
      "shared_with": ["service providers", "advertising partners"],
      "purposes": ["analytics", "advertising", "payment", "customer_support", "email_marketing", "social_media", "hosting", "legal_compliance"]
    }}
  ],
  "third_parties": {{
    "named_parties": [
      {{
        "name": "Stripe",
        "category": "Payment Processing",
        "evidence": ["exact short quote from policy"],
        "data_types_shared": ["payment information"],
        "purposes": ["payment"],
        "cross_border_transfer": false,
        "is_data_broker": false
      }}
    ],
    "unnamed_recipients": [
      {{
        "label": "service providers",
        "evidence": ["exact short quote from policy"],
        "purposes": ["hosting"]
      }}
    ],
    "data_sold": false,
    "cross_border_transfers": false,
    "transfer_safeguards": []
  }}
}}

POLICY TEXT:
{policy_excerpt}
""".strip()


def _quality_prompt(domain: str, policy_excerpt: str, *, compact: bool = False) -> str:
    dark_rows = "\n".join(
        f"- {item['type']}: {item['name']} | severity={item['severity']} | ref={item['gdpr_reference']}"
        for item in DARK_PATTERN_DEFINITIONS
    )
    gdpr_rows = "\n".join(
        f"- {key}: {value['name']} ({value['article']})"
        for key, value in GDPR_RIGHTS.items()
    )
    ccpa_rows = "\n".join(
        f"- {key}: {value['name']} ({value['article']})"
        for key, value in CCPA_RIGHTS.items()
    )
    framework_rows = ", ".join(value["name"] for value in OTHER_FRAMEWORKS.values())
    accountability_keys = ", ".join(ACCOUNTABILITY_PATTERNS.keys())
    cookie_keys = ", ".join(COOKIE_COMPLIANCE.keys())
    max_retention = 8 if compact else 16
    max_dark = 6 if compact else len(DARK_PATTERN_DEFINITIONS)

    return f"""
Analyze this privacy policy for {domain} for retention, dark patterns, user rights, and transparency.

Use only facts directly stated in the policy. Every positive finding that needs evidence
must include exact short quote(s) copied from the policy text. Do not invent quotes.
This output feeds the privacy score directly. You are the scoring analyzer for these sections,
so be realistic, strict, and evidence-led:
- Do not award credit for generic legal boilerplate, vague "may have rights" text, or broad promises without a usable mechanism.
- Retention must reflect the worst meaningful retention posture. If the policy has both specific periods and vague/indefinite clauses, report the vague/indefinite risk too.
- Transparency should be penalized for broad terms like "business purposes", "as necessary", "affiliates", "partners", "may disclose", "from time to time", and "including but not limited to".
- Dark patterns should include consent-by-use, hidden opt-out, bundled consent, obstruction, broad opt-out friction, or manipulative consent language when directly supported by text.
- Rights are covered only when the policy explicitly names or clearly describes the right AND gives enough detail for a user to exercise or understand it. A quote that only says users "may have certain rights" is never enough.

Allowed dark pattern types:
{dark_rows}

GDPR right IDs:
{gdpr_rows}

CCPA/CPRA right IDs:
{ccpa_rows}

Allowed frameworks: {framework_rows}
Allowed cookie compliance keys: {cookie_keys}
Allowed accountability keys: {accountability_keys}

Return ONLY valid JSON with this schema:
{{
  "retention": {{
    "items": [
      {{
        "period_text": "90 days",
        "period_days": 90,
        "period_type": "specific",
        "evidence": "exact short quote from policy"
      }}
    ],
    "has_indefinite_retention": false,
    "deletion_on_request": false,
    "storage_limitation_mentioned": false
  }},
  "dark_patterns": {{
    "detected": [
      {{
        "pattern_type": "hidden_opt_out",
        "evidence": ["exact short quote from policy"],
        "confidence": 0.8
      }}
    ],
    "consent_mechanism_quality": "good|adequate|poor|unclear"
  }},
  "rights": {{
    "gdpr": {{
      "access": {{"covered": true, "evidence": "exact short quote from policy"}}
    }},
    "ccpa": {{
      "right_to_know": {{"covered": true, "evidence": "exact short quote from policy"}}
    }},
    "frameworks_mentioned": ["LGPD (Brazil)"],
    "cookie_compliance": {{
      "consent_required": true,
      "cookie_categories": true,
      "httponly_secure": false,
      "dnt_honored": true
    }},
    "dnt_mentioned": true,
    "dnt_honored": true,
    "global_privacy_control": true
  }},
  "transparency": {{
    "vagueness_score": 40,
    "specificity_score": 70,
    "passive_voice_ratio": 0.25,
    "active_voice_count": 8,
    "passive_voice_count": 3,
    "named_third_parties": ["Stripe"],
    "vague_term_examples": ["exact vague phrase from policy"],
    "hedging_examples": ["exact hedging phrase from policy"],
    "specific_purpose_count": 6,
    "accountability": {{
      "dpo_named": false,
      "dpo_contact": false,
      "supervisory_authority": false,
      "legitimate_basis": true,
      "privacy_by_design": false,
      "security_measures": true
    }},
    "overall_transparency": "high|medium|low|very_low",
    "transparency_score": 68
  }}
}}

Rules:
- Return at most {max_retention} retention items.
- Do not return a retention overall_rating; the backend computes it from the extracted retention items and flags.
- Return at most {max_dark} dark pattern findings.
- Dark patterns must use only allowed pattern_type values.
- Rights must use only listed GDPR/CCPA IDs.
- For rights, set covered true only with direct evidence that is specific and actionable. The evidence must identify the specific right and the usable request, opt-out, appeal, complaint, contact, portal, or equivalent mechanism/scope. Vague statements such as "you may have certain rights" should be covered=false.
- For transparency_score, 100 means unusually specific and low-vague. Policies with many broad sharing or retention clauses should usually be below 60.
- Do not include markdown, comments, explanations, or trailing commas.

POLICY TEXT:
{policy_excerpt}
""".strip()


async def extract_policy_entities_ai(
    *,
    domain: str,
    policy_text: str,
    fallback_data_types: List[DetectedDataType],
    fallback_third_parties: ThirdPartyAnalysis,
    fallback_retention: RetentionAnalysis,
    fallback_dark_patterns: DarkPatternAnalysis,
    fallback_rights: RightsAnalysis,
    fallback_sentiment: SentimentResult,
) -> AIExtractionResult:
    if not _ai_extraction_enabled():
        return AIExtractionResult(
            data_types=fallback_data_types,
            third_parties=fallback_third_parties,
            retention=fallback_retention,
            dark_patterns=fallback_dark_patterns,
            rights=fallback_rights,
            sentiment=fallback_sentiment,
            meta={
                "enabled": False,
                "used": False,
                "complete": False,
                "version": AI_POLICY_EXTRACTION_VERSION,
                "reason": "disabled_or_unconfigured",
            },
        )

    max_chars = int(os.getenv("AI_POLICY_EXTRACTION_MAX_CHARS", "50000"))
    policy_excerpt = policy_text[:max_chars]

    data_types = fallback_data_types
    third_parties = fallback_third_parties
    retention = fallback_retention
    dark_patterns = fallback_dark_patterns
    rights = fallback_rights
    sentiment = fallback_sentiment
    errors: List[str] = []
    attempts_meta: Dict[str, Any] = {}
    meta: Dict[str, Any] = {
        "enabled": True,
        "used": False,
        "complete": False,
        "version": AI_POLICY_EXTRACTION_VERSION,
        "policy_chars_sent": len(policy_excerpt),
        "analysis_mode": "strict_ai_primary",
    }

    try:
        all_data_categories = len(DATA_TAXONOMY)
        attempts = [
            {
                "name": "standard",
                "max_data_categories": all_data_categories,
                "max_evidence_quotes": 1,
                "max_string_items": 4,
                "max_tokens": 8000,
            },
            {
                "name": "compact_retry",
                "max_data_categories": all_data_categories,
                "max_evidence_quotes": 1,
                "max_string_items": 2,
                "max_tokens": 6000,
            },
        ]
        raw = ""
        data = None
        attempt_name = attempts[-1]["name"]
        for attempt in attempts:
            attempt_name = attempt["name"]
            raw = await acomplete(
                _build_extraction_prompt(
                    domain=domain,
                    policy_excerpt=policy_excerpt,
                    max_data_categories=attempt["max_data_categories"],
                    max_evidence_quotes=attempt["max_evidence_quotes"],
                    max_string_items=attempt["max_string_items"],
                ),
                system=(
                    "You extract structured privacy-policy facts. Return only JSON. "
                    "Use exact quotes from the policy as evidence."
                ),
                model=FAST_MODEL,
                max_tokens=attempt["max_tokens"],
            )
            data = _extract_json_object(raw or "")
            if data:
                break
        attempts_meta["entities"] = {
            "attempt": attempt_name,
            "raw_response_chars": len(raw or ""),
        }
    except Exception as exc:
        data = None
        errors.append(f"entities:{type(exc).__name__}")

    if data:
        data_category_items = data.get("data_categories")
        ai_data_types = _build_ai_data_types(data_category_items, policy_excerpt)
        ai_third_parties = _build_ai_third_parties(data.get("third_parties", {}), policy_excerpt)

        if isinstance(data_category_items, list) and (not data_category_items or ai_data_types):
            data_types = ai_data_types
            meta["data_categories_source"] = "ai"
        else:
            meta["data_categories_source"] = "fallback_regex"
            errors.append("data_categories:invalid_or_empty")

        if ai_third_parties is not None:
            third_parties = ai_third_parties
            meta["third_parties_source"] = "ai"
        else:
            meta["third_parties_source"] = "fallback_regex"
            errors.append("third_parties:invalid_or_empty")
    else:
        meta["data_categories_source"] = "fallback_regex"
        meta["third_parties_source"] = "fallback_regex"
        errors.append("entities:invalid_json")

    try:
        quality_attempts = [
            {
                "name": "standard",
                "prompt": _quality_prompt(domain, policy_excerpt, compact=False),
                "max_tokens": 8000,
            },
            {
                "name": "compact_retry",
                "prompt": _quality_prompt(domain, policy_excerpt, compact=True),
                "max_tokens": 6000,
            },
        ]
        raw = ""
        quality = None
        quality_attempt_name = quality_attempts[-1]["name"]
        for attempt in quality_attempts:
            quality_attempt_name = attempt["name"]
            raw = await acomplete(
                attempt["prompt"],
                system=(
                    "You extract structured privacy-policy facts. Return only JSON. "
                    "Use exact quotes from the policy as evidence."
                ),
                model=FAST_MODEL,
                max_tokens=attempt["max_tokens"],
            )
            quality = _extract_json_object(raw or "")
            if quality:
                break
        attempts_meta["quality"] = {
            "attempt": quality_attempt_name,
            "raw_response_chars": len(raw or ""),
        }
    except Exception as exc:
        quality = None
        errors.append(f"quality:{type(exc).__name__}")

    if quality:
        ai_retention = _build_ai_retention(quality.get("retention", {}), policy_excerpt)
        ai_dark_patterns = _build_ai_dark_patterns(quality.get("dark_patterns", {}), policy_excerpt)
        ai_rights = _build_ai_rights(quality.get("rights", {}), policy_excerpt)
        ai_sentiment = _build_ai_sentiment(quality.get("transparency", {}), policy_excerpt, fallback_sentiment)

        if ai_retention is not None:
            retention = ai_retention
            meta["retention_source"] = "ai"
        else:
            meta["retention_source"] = "fallback_regex"
            errors.append("retention:invalid_json")

        if ai_dark_patterns is not None:
            dark_patterns = ai_dark_patterns
            meta["dark_patterns_source"] = "ai"
        else:
            meta["dark_patterns_source"] = "fallback_regex"
            errors.append("dark_patterns:invalid_json")

        if ai_rights is not None:
            rights = ai_rights
            meta["rights_source"] = "ai"
        else:
            meta["rights_source"] = "fallback_regex"
            errors.append("rights:invalid_json")

        if ai_sentiment is not None:
            sentiment = ai_sentiment
            meta["transparency_source"] = "ai"
        else:
            meta["transparency_source"] = "fallback_regex"
            errors.append("transparency:invalid_json")
    else:
        meta["retention_source"] = "fallback_regex"
        meta["dark_patterns_source"] = "fallback_regex"
        meta["rights_source"] = "fallback_regex"
        meta["transparency_source"] = "fallback_regex"
        errors.append("quality:invalid_json")

    source_keys = [
        "data_categories_source",
        "third_parties_source",
        "retention_source",
        "dark_patterns_source",
        "rights_source",
        "transparency_source",
    ]
    meta["used"] = any(meta.get(key) == "ai" for key in source_keys)
    meta["complete"] = all(meta.get(key) == "ai" for key in source_keys)
    meta["attempts"] = attempts_meta
    if errors:
        meta["errors"] = errors[:10]
        if not meta["used"]:
            meta["reason"] = ";".join(errors[:4])

    return AIExtractionResult(
        data_types=data_types,
        third_parties=third_parties,
        retention=retention,
        dark_patterns=dark_patterns,
        rights=rights,
        sentiment=sentiment,
        meta=meta,
    )
