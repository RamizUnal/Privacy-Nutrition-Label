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
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

from analyzer.data_categories import DATA_TAXONOMY, DetectedDataType
from analyzer.third_party_analyzer import (
    SHARING_PURPOSES,
    ThirdPartyAnalysis,
    ThirdPartyEntry,
    _load_trust_db,
)
from ai.claude_client import FAST_MODEL, acomplete

AI_POLICY_EXTRACTION_VERSION = 4


@dataclass
class AIExtractionResult:
    data_types: List[DetectedDataType]
    third_parties: ThirdPartyAnalysis
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

For third parties, extract recipients of user data. Exclude {domain}, the site itself,
and obvious first-party/parent-company references unless the policy clearly says data
is shared with separate affiliates or external recipients.

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


async def extract_policy_entities_ai(
    *,
    domain: str,
    policy_text: str,
    fallback_data_types: List[DetectedDataType],
    fallback_third_parties: ThirdPartyAnalysis,
) -> AIExtractionResult:
    if not _ai_extraction_enabled():
        return AIExtractionResult(
            data_types=fallback_data_types,
            third_parties=fallback_third_parties,
            meta={
                "enabled": False,
                "used": False,
                "version": AI_POLICY_EXTRACTION_VERSION,
                "reason": "disabled_or_unconfigured",
            },
        )

    max_chars = int(os.getenv("AI_POLICY_EXTRACTION_MAX_CHARS", "50000"))
    policy_excerpt = policy_text[:max_chars]

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
    except Exception as exc:
        return AIExtractionResult(
            data_types=fallback_data_types,
            third_parties=fallback_third_parties,
            meta={
                "enabled": True,
                "used": False,
                "version": AI_POLICY_EXTRACTION_VERSION,
                "reason": f"ai_error:{type(exc).__name__}",
            },
        )

    if not data:
        return AIExtractionResult(
            data_types=fallback_data_types,
            third_parties=fallback_third_parties,
            meta={
                "enabled": True,
                "used": False,
                "version": AI_POLICY_EXTRACTION_VERSION,
                "reason": "invalid_json",
                "attempt": attempt_name,
                "raw_response_chars": len(raw or ""),
            },
        )

    ai_data_types = _build_ai_data_types(data.get("data_categories"), policy_excerpt)
    ai_third_parties = _build_ai_third_parties(data.get("third_parties", {}), policy_excerpt)

    used_data = bool(ai_data_types)
    used_parties = ai_third_parties is not None

    return AIExtractionResult(
        data_types=ai_data_types if used_data else fallback_data_types,
        third_parties=ai_third_parties if used_parties else fallback_third_parties,
        meta={
            "enabled": True,
            "used": used_data or used_parties,
            "version": AI_POLICY_EXTRACTION_VERSION,
            "data_categories_source": "ai" if used_data else "fallback_regex",
            "third_parties_source": "ai" if used_parties else "fallback_regex",
            "policy_chars_sent": len(policy_excerpt),
            "attempt": attempt_name,
        },
    )
