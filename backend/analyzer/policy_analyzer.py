"""
Main Policy Analyzer Orchestrator
Coordinates all analysis modules and produces the complete PrivacyLabel result.
"""
from __future__ import annotations
import dataclasses
import datetime
from typing import Any, Dict, List, Optional

from .data_categories import detect_data_categories, extract_sharing_relationships, sort_by_sensitivity
from .retention_parser import analyze_retention
from .sentiment_analyzer import analyze_sentiment
from .dark_pattern_detector import detect_dark_patterns
from .rights_checker import check_rights
from .third_party_analyzer import analyze_third_parties


def _dc(obj) -> Any:
    """Recursively convert dataclasses to dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dc(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dc(v) for k, v in obj.items()}
    return obj


def analyze_policy(
    policy_text: str,
    policy_url: Optional[str] = None,
    domain: str = "",
) -> Dict[str, Any]:
    """
    Run full analysis pipeline on policy text.
    Returns a serializable dict with all analysis results.
    """
    # Run all analyzers
    data_types_raw = detect_data_categories(policy_text)
    data_types = sort_by_sensitivity(extract_sharing_relationships(policy_text, data_types_raw))
    retention = analyze_retention(policy_text)
    sentiment = analyze_sentiment(policy_text)
    dark_patterns = detect_dark_patterns(policy_text)
    rights = check_rights(policy_text)
    third_parties = analyze_third_parties(policy_text)

    return {
        "data_types": _dc(data_types),
        "retention": _dc(retention),
        "sentiment": _dc(sentiment),
        "dark_patterns": _dc(dark_patterns),
        "rights": _dc(rights),
        "third_parties": _dc(third_parties),
        "analyzed_at": datetime.datetime.utcnow().isoformat(),
        "policy_url": policy_url,
        "domain": domain,
    }, data_types, retention, sentiment, dark_patterns, rights, third_parties
