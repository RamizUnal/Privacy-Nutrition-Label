"""
AI-Powered Privacy Policy Analyzer
Uses Claude to generate plain-language summaries, identify red flags,
analyze compliance gaps, and produce risk narratives.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional

from .claude_client import acomplete, astream, FAST_MODEL

# ─────────────────────────────────────────────────────────────────────────────
# System prompts
# ─────────────────────────────────────────────────────────────────────────────

ANALYST_SYSTEM = """You are an expert data privacy attorney and compliance officer specializing in GDPR, CCPA/CPRA, ePrivacy Directive, EDPB Guidelines, COPPA, and global privacy law.

Your analysis is:
- Precise and legally-informed
- Written for non-lawyers but technically accurate
- Evidence-based (quote or reference specific policy text or detected data)
- Actionable (tell users what they can concretely do)
Always respond with valid JSON when JSON is requested. Never include markdown fences in responses."""

CHAT_SYSTEM = """You are a privacy expert assistant helping users understand the privacy practices of websites they visit. You have access to a detailed privacy analysis including policy text analysis, tracker detection, dark pattern findings, and third-party data.

Your responses are:
- Clear and accessible to non-technical users
- Grounded in the provided analysis (don't speculate beyond it)
- Actionable (suggest specific steps users can take)
- Honest about limitations

When users ask about specific practices, reference the evidence from the analysis.
Keep responses focused (2-4 paragraphs max unless detail is needed).
Format with short paragraphs. Use plain text, no markdown headers."""


# ─────────────────────────────────────────────────────────────────────────────
# Output models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RedFlag:
    issue: str
    evidence: str
    severity: str   # critical | high | medium | low
    action: str


@dataclass
class ComplianceGap:
    regulation: str
    gap: str
    recommendation: str


@dataclass
class PolicyAIAnalysis:
    plain_summary: str
    tldr: str
    privacy_posture: str
    headline_risks: List[str]
    red_flags: List[Dict]
    positive_findings: List[str]
    compliance_gaps: List[Dict]
    user_rights_summary: str
    recommended_actions: List[str]
    quick_wins: List[str]
    important_quotes: List[Dict]
    confidence_notes: List[str]
    risk_narrative: str
    data_story: str
    ai_score_commentary: str
    ai_available: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Main AI analysis function
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_policy_ai(
    domain: str,
    policy_text: str,
    analysis_result: dict,
) -> PolicyAIAnalysis:
    """Use Claude to produce a deep AI-powered analysis of a privacy policy."""

    score = analysis_result.get("overall_score", 0)
    grade = analysis_result.get("grade", "F")
    risk_level = analysis_result.get("risk_level", "unknown")

    data_type_items = analysis_result.get("data_types", []) or []
    data_types = [dt.get("name", "") for dt in data_type_items[:20]]
    dark_patterns = analysis_result.get("dark_patterns", {}).get("detected", [])
    dp_names = [dp.get("name", "") for dp in dark_patterns[:5]]
    tracker_items = analysis_result.get("trackers", {}).get("trackers", []) or []
    trackers = [t.get("name", "") for t in tracker_items[:15]]
    third_party_items = analysis_result.get("third_parties", {}).get("parties", []) or []
    third_parties_count = analysis_result.get("third_parties", {}).get("count", 0)
    named_third_parties = [p.get("name", "") for p in third_party_items[:18] if p.get("name")]
    data_sold = analysis_result.get("third_parties", {}).get("data_sold", False)
    gdpr_score = analysis_result.get("rights", {}).get("gdpr_score", 0)
    ccpa_score = analysis_result.get("rights", {}).get("ccpa_score", 0)
    fingerprinting = analysis_result.get("trackers", {}).get("fingerprinting_detected", False)
    session_recording = analysis_result.get("trackers", {}).get("session_recording_detected", False)
    retention = analysis_result.get("retention", {}).get("overall_rating", "unknown")
    vagueness = analysis_result.get("sentiment", {}).get("vagueness_score", 0)
    transparency = analysis_result.get("sentiment", {}).get("transparency_score", 0)

    # Key penalties/bonuses
    penalties = [p.get("reason", "") for p in analysis_result.get("penalties", [])[:5]]
    bonuses = [b.get("reason", "") for b in analysis_result.get("bonuses", [])[:3]]

    def _evidence_lines(items: list, label_key: str = "name", limit: int = 8) -> str:
        lines = []
        for item in items[:limit]:
            label = item.get(label_key) or item.get("name") or item.get("category_id") or "Finding"
            evidence = item.get("evidence")
            if isinstance(evidence, list):
                quote = next((str(e) for e in evidence if e), "")
            elif isinstance(evidence, str):
                quote = evidence
            else:
                quote = ""
            if quote:
                lines.append(f"- {label}: {quote[:220]}")
        return "\n".join(lines) if lines else "No direct quote evidence in cached analysis."

    retention_items = analysis_result.get("retention", {}).get("items", []) or []
    rights = analysis_result.get("rights", {}) or {}
    gdpr_rights = rights.get("gdpr", {}) or {}
    ccpa_rights = rights.get("ccpa", {}) or {}
    covered_gdpr = [v.get("name", k) for k, v in gdpr_rights.items() if isinstance(v, dict) and v.get("covered")]
    missing_gdpr = [v.get("name", k) for k, v in gdpr_rights.items() if isinstance(v, dict) and not v.get("covered")]
    covered_ccpa = [v.get("name", k) for k, v in ccpa_rights.items() if isinstance(v, dict) and v.get("covered")]
    missing_ccpa = [v.get("name", k) for k, v in ccpa_rights.items() if isinstance(v, dict) and not v.get("covered")]

    context_summary = f"""Domain: {domain}
Privacy Score: {score}/100 (Grade: {grade}, Risk: {risk_level})
Data Collected: {', '.join(data_types) if data_types else 'Unknown'}
Third Parties: {third_parties_count} detected ({', '.join(named_third_parties) if named_third_parties else 'none named'}) | Data Sold: {'YES' if data_sold else 'No/Not stated'}
Active Trackers: {', '.join(trackers) if trackers else 'None'}
Browser Fingerprinting: {'DETECTED' if fingerprinting else 'Not detected'}
Session Recording: {'ACTIVE' if session_recording else 'Not detected'}
Dark Patterns: {', '.join(dp_names) if dp_names else 'None detected'}
GDPR Rights Coverage: {gdpr_score}% | CCPA Coverage: {ccpa_score}%
Retention Policy: {retention} | Vagueness Score: {vagueness}/100 | Transparency: {transparency}/100
Score Penalties: {'; '.join(penalties) if penalties else 'None'}
Score Bonuses: {'; '.join(bonuses) if bonuses else 'None'}"""

    evidence_summary = f"""DATA EVIDENCE:
{_evidence_lines(data_type_items, limit=10)}

THIRD-PARTY EVIDENCE:
{_evidence_lines(third_party_items, limit=10)}

RETENTION EVIDENCE:
{chr(10).join(f"- {item.get('period_text', 'Retention')}: {item.get('context', '')[:220]}" for item in retention_items[:8]) or 'No retention quotes in cached analysis.'}

DARK PATTERN EVIDENCE:
{_evidence_lines(dark_patterns, label_key='name', limit=8)}

RIGHTS COVERAGE:
GDPR covered: {', '.join(covered_gdpr) if covered_gdpr else 'none'}
GDPR missing: {', '.join(missing_gdpr) if missing_gdpr else 'none'}
CCPA covered: {', '.join(covered_ccpa) if covered_ccpa else 'none'}
CCPA missing: {', '.join(missing_ccpa) if missing_ccpa else 'none'}"""

    # Add mismatch context if available
    mismatch_data = analysis_result.get("mismatch_analysis")
    if mismatch_data and mismatch_data.get("total_count", 0) > 0:
        mismatch_items = mismatch_data.get("mismatches", [])
        mismatch_summaries = [f"- {m.get('title', '')} (severity: {m.get('severity', 'unknown')})" for m in mismatch_items[:5]]
        context_summary += f"""
Policy-Behavior Mismatches: {mismatch_data.get('total_count', 0)} detected (Score: {mismatch_data.get('mismatch_score', 'N/A')}/100)
Consent Effective: {'YES' if mismatch_data.get('consent_effective') else 'NO — rejecting cookies does NOT reduce tracking'}
Pre-Consent Tracking: {'YES — {0} trackers active before consent'.format(mismatch_data.get('pre_consent_tracker_count', 0)) if mismatch_data.get('pre_consent_tracking') else 'No'}
Undeclared Trackers: {mismatch_data.get('undeclared_tracker_count', 0)} ({', '.join(mismatch_data.get('undeclared_tracker_names', [])[:5]) or 'None'})
Mismatch Details:
{chr(10).join(mismatch_summaries)}"""

    policy_excerpt = (policy_text[:6500] if policy_text else "No policy text available")

    prompt = f"""Analyze the privacy practices for {domain}.

AUTOMATED ANALYSIS DATA:
{context_summary}

CACHED POLICY EVIDENCE:
{evidence_summary}

PRIVACY POLICY EXCERPT:
{policy_excerpt}

Respond with ONLY valid JSON (no markdown fences) with this exact schema:
{{
  "tldr": "One sentence starting with the domain name that captures the key privacy fact",
  "privacy_posture": "Excellent|Good|Mixed|Concerning|Dangerous",
  "plain_summary": "3-4 sentence plain English summary of what this site does with user data",
  "headline_risks": ["Top 3-5 specific concrete risks for users"],
  "red_flags": [
    {{
      "issue": "Short title of the issue",
      "evidence": "Direct evidence from the policy text or detected data",
      "severity": "critical|high|medium|low",
      "action": "What the user can do about this right now"
    }}
  ],
  "positive_findings": ["2-3 things this privacy policy does well, or [] if none"],
  "compliance_gaps": [
    {{
      "regulation": "GDPR|CCPA|ePrivacy|COPPA",
      "gap": "Specific compliance gap found",
      "recommendation": "What the site should do to comply"
    }}
  ],
  "user_rights_summary": "2-3 sentences about what rights users have under GDPR and CCPA for this site",
  "recommended_actions": ["3-5 specific actionable steps a user can take RIGHT NOW"],
  "quick_wins": ["2-4 short user actions that reduce risk fastest"],
  "important_quotes": [
    {{
      "label": "Short label",
      "quote": "Exact quote from the policy or cached evidence",
      "why_it_matters": "One sentence explaining why this quote matters"
    }}
  ],
  "confidence_notes": ["2-3 limitations or confidence notes based on policy length, missing text, dynamic crawl availability, or AI fallback"],
  "risk_narrative": "One paragraph risk narrative for a non-technical person explaining what this score means for them",
  "data_story": "2-3 sentences narrating what happens to user data: collection → processing → sharing",
  "ai_score_commentary": "1-2 sentences explaining the key factors behind this specific score"
}}

Be specific and factual. Base everything on the provided analysis data. Prefer direct quotes from CACHED POLICY EVIDENCE when possible."""

    result_text = await acomplete(prompt, system=ANALYST_SYSTEM, model=FAST_MODEL, max_tokens=3000)

    if not result_text:
        return _fallback_analysis(domain, score, grade, risk_level)

    try:
        clean = result_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```(?:json)?", "", clean).strip()
            if clean.endswith("```"):
                clean = clean[:-3].strip()
        data = json.loads(clean)

        return PolicyAIAnalysis(
            plain_summary=data.get("plain_summary", ""),
            tldr=data.get("tldr", ""),
            privacy_posture=data.get("privacy_posture", ""),
            headline_risks=data.get("headline_risks", []),
            red_flags=data.get("red_flags", []),
            positive_findings=data.get("positive_findings", []),
            compliance_gaps=data.get("compliance_gaps", []),
            user_rights_summary=data.get("user_rights_summary", ""),
            recommended_actions=data.get("recommended_actions", []),
            quick_wins=data.get("quick_wins", []),
            important_quotes=data.get("important_quotes", []),
            confidence_notes=data.get("confidence_notes", []),
            risk_narrative=data.get("risk_narrative", ""),
            data_story=data.get("data_story", ""),
            ai_score_commentary=data.get("ai_score_commentary", ""),
            ai_available=True,
        )
    except Exception:
        return _fallback_analysis(domain, score, grade, risk_level)


def _fallback_analysis(domain: str, score: int, grade: str, risk_level: str) -> PolicyAIAnalysis:
    return PolicyAIAnalysis(
        plain_summary=f"{domain} has a privacy grade of {grade} ({score}/100). Set ANTHROPIC_API_KEY to enable AI-powered analysis.",
        tldr=f"{domain} scored {score}/100 — AI analysis unavailable.",
        privacy_posture="Unknown",
        headline_risks=["AI analysis unavailable – set ANTHROPIC_API_KEY in backend/.env"],
        red_flags=[],
        positive_findings=[],
        compliance_gaps=[],
        user_rights_summary="AI analysis unavailable. Set ANTHROPIC_API_KEY to enable.",
        recommended_actions=["Add your ANTHROPIC_API_KEY to backend/.env and restart the backend"],
        quick_wins=[],
        important_quotes=[],
        confidence_notes=["AI analysis did not run, so this view only reflects automated scoring."],
        risk_narrative=f"{domain} received a {grade} privacy grade ({score}/100). AI analysis is unavailable.",
        data_story="AI analysis unavailable.",
        ai_score_commentary=f"Score of {score}/100 based on automated analysis only.",
        ai_available=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Streaming chat
# ─────────────────────────────────────────────────────────────────────────────

async def stream_chat_response(
    domain: str,
    analysis_result: dict,
    conversation: list,  # [{"role": "user"|"assistant", "content": "..."}]
    policy_text: str = "",
) -> AsyncIterator[str]:
    """Stream a privacy assistant response using the full analysis as context."""

    score = analysis_result.get("overall_score", 0)
    grade = analysis_result.get("grade", "F")
    risk_level = analysis_result.get("risk_level", "unknown")

    data_type_items = analysis_result.get("data_types", []) or []
    data_types = [dt.get("name", "") for dt in data_type_items[:25]]
    trackers = analysis_result.get("trackers", {}).get("trackers", [])[:10]
    third_parties = analysis_result.get("third_parties", {}).get("parties", [])[:10]
    dark_patterns = analysis_result.get("dark_patterns", {}).get("detected", [])[:5]
    gdpr_rights = analysis_result.get("rights", {}).get("gdpr", {})
    ccpa_rights = analysis_result.get("rights", {}).get("ccpa", {})
    data_sold = analysis_result.get("third_parties", {}).get("data_sold", False)
    fingerprinting = analysis_result.get("trackers", {}).get("fingerprinting_detected", False)
    session_recording = analysis_result.get("trackers", {}).get("session_recording_detected", False)
    cookies = analysis_result.get("trackers", {}).get("cookies", [])[:5]

    covered_gdpr = [k for k, v in gdpr_rights.items() if isinstance(v, dict) and v.get("covered")]
    missing_gdpr = [k for k, v in gdpr_rights.items() if isinstance(v, dict) and not v.get("covered")]

    tracker_list = ", ".join([t.get("name", "") for t in trackers]) if trackers else "None detected"
    party_list = ", ".join([p.get("name", "") for p in third_parties]) if third_parties else "None named"
    dp_list = ", ".join([d.get("name", "") for d in dark_patterns]) if dark_patterns else "None detected"
    cookie_names = ", ".join([c.get("name", "") for c in cookies]) if cookies else "None detected"
    retention = analysis_result.get("retention", {}) or {}
    sentiment = analysis_result.get("sentiment", {}) or {}
    ai_extraction = analysis_result.get("ai_extraction", {}) or {}
    policy_excerpt = (policy_text or "")[:4500]

    def _quotes(items: list, label_key: str = "name", limit: int = 6) -> str:
        rows = []
        for item in items[:limit]:
            label = item.get(label_key) or item.get("name") or "Finding"
            evidence = item.get("evidence")
            if isinstance(evidence, list):
                evidence = next((str(e) for e in evidence if e), "")
            if isinstance(evidence, str) and evidence:
                rows.append(f"- {label}: {evidence[:220]}")
        return "\n".join(rows) if rows else "No direct quotes cached."

    context = f"""PRIVACY ANALYSIS FOR {domain}
Overall Score: {score}/100 (Grade: {grade}, Risk Level: {risk_level})

DATA COLLECTION:
Types Collected: {', '.join(data_types) if data_types else 'Unknown'}
Data Sold to Third Parties: {'YES' if data_sold else 'No/Not stated'}

TRACKING:
Active Trackers: {tracker_list}
Browser Fingerprinting: {'DETECTED' if fingerprinting else 'Not detected'}
Session Recording: {'ACTIVE' if session_recording else 'Not detected'}
Cookies Seen: {cookie_names}

THIRD PARTIES:
Named Partners: {party_list}

PRIVACY CONCERNS:
Dark Patterns: {dp_list}
Retention: {retention.get('overall_rating', 'unknown')} | Vague retention: {retention.get('has_vague_retention', False)}
Transparency Score: {sentiment.get('transparency_score', 0)}/100 | Vagueness: {sentiment.get('vagueness_score', 0)}/100

USER RIGHTS:
GDPR Rights Covered: {', '.join(covered_gdpr) if covered_gdpr else 'None covered'}
GDPR Rights Missing: {', '.join(missing_gdpr) if missing_gdpr else 'All covered'}

AI EXTRACTION SOURCES:
Data categories: {ai_extraction.get('data_categories_source', 'unknown')}
Third parties: {ai_extraction.get('third_parties_source', 'unknown')}
Retention: {ai_extraction.get('retention_source', 'unknown')}
Dark patterns: {ai_extraction.get('dark_patterns_source', 'unknown')}
Rights: {ai_extraction.get('rights_source', 'unknown')}
Transparency: {ai_extraction.get('transparency_source', 'unknown')}

DIRECT POLICY EVIDENCE:
Data collection:
{_quotes(data_type_items, limit=8)}

Third-party sharing:
{_quotes(third_parties, limit=8)}

Dark patterns:
{_quotes(dark_patterns, limit=5)}

POLICY EXCERPT:
{policy_excerpt if policy_excerpt else 'No raw policy text available in this chat context.'}
"""

    system = f"""{CHAT_SYSTEM}

Here is the complete privacy analysis for {domain} — use this as your factual knowledge base:

{context}"""

    async for chunk in astream(
        prompt="",
        system=system,
        model=FAST_MODEL,
        max_tokens=600,
        messages=conversation,
    ):
        yield chunk
