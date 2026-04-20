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
    headline_risks: List[str]
    red_flags: List[Dict]
    positive_findings: List[str]
    compliance_gaps: List[Dict]
    user_rights_summary: str
    recommended_actions: List[str]
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

    data_types = [dt.get("name", "") for dt in analysis_result.get("data_types", [])[:12]]
    dark_patterns = analysis_result.get("dark_patterns", {}).get("detected", [])
    dp_names = [dp.get("name", "") for dp in dark_patterns[:5]]
    trackers = [t.get("name", "") for t in analysis_result.get("trackers", {}).get("trackers", [])[:10]]
    third_parties_count = analysis_result.get("third_parties", {}).get("count", 0)
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

    context_summary = f"""Domain: {domain}
Privacy Score: {score}/100 (Grade: {grade}, Risk: {risk_level})
Data Collected: {', '.join(data_types) if data_types else 'Unknown'}
Third Parties: {third_parties_count} detected | Data Sold: {'YES' if data_sold else 'No/Not stated'}
Active Trackers: {', '.join(trackers) if trackers else 'None'}
Browser Fingerprinting: {'DETECTED' if fingerprinting else 'Not detected'}
Session Recording: {'ACTIVE' if session_recording else 'Not detected'}
Dark Patterns: {', '.join(dp_names) if dp_names else 'None detected'}
GDPR Rights Coverage: {gdpr_score}% | CCPA Coverage: {ccpa_score}%
Retention Policy: {retention} | Vagueness Score: {vagueness}/100 | Transparency: {transparency}/100
Score Penalties: {'; '.join(penalties) if penalties else 'None'}
Score Bonuses: {'; '.join(bonuses) if bonuses else 'None'}"""

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

    policy_excerpt = (policy_text[:3500] if policy_text else "No policy text available")

    prompt = f"""Analyze the privacy practices for {domain}.

AUTOMATED ANALYSIS DATA:
{context_summary}

PRIVACY POLICY EXCERPT:
{policy_excerpt}

Respond with ONLY valid JSON (no markdown fences) with this exact schema:
{{
  "tldr": "One sentence starting with the domain name that captures the key privacy fact",
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
  "risk_narrative": "One paragraph risk narrative for a non-technical person explaining what this score means for them",
  "data_story": "2-3 sentences narrating what happens to user data: collection → processing → sharing",
  "ai_score_commentary": "1-2 sentences explaining the key factors behind this specific score"
}}

Be specific and factual. Base everything on the provided analysis data."""

    result_text = await acomplete(prompt, system=ANALYST_SYSTEM, model=FAST_MODEL, max_tokens=2200)

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
            headline_risks=data.get("headline_risks", []),
            red_flags=data.get("red_flags", []),
            positive_findings=data.get("positive_findings", []),
            compliance_gaps=data.get("compliance_gaps", []),
            user_rights_summary=data.get("user_rights_summary", ""),
            recommended_actions=data.get("recommended_actions", []),
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
        headline_risks=["AI analysis unavailable – set ANTHROPIC_API_KEY in backend/.env"],
        red_flags=[],
        positive_findings=[],
        compliance_gaps=[],
        user_rights_summary="AI analysis unavailable. Set ANTHROPIC_API_KEY to enable.",
        recommended_actions=["Add your ANTHROPIC_API_KEY to backend/.env and restart the backend"],
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
) -> AsyncIterator[str]:
    """Stream a privacy assistant response using the full analysis as context."""

    score = analysis_result.get("overall_score", 0)
    grade = analysis_result.get("grade", "F")
    risk_level = analysis_result.get("risk_level", "unknown")

    data_types = [dt.get("name", "") for dt in analysis_result.get("data_types", [])[:15]]
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

USER RIGHTS:
GDPR Rights Covered: {', '.join(covered_gdpr) if covered_gdpr else 'None covered'}
GDPR Rights Missing: {', '.join(missing_gdpr) if missing_gdpr else 'All covered'}
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
