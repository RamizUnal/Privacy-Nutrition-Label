"""
Dark Pattern Detector for Privacy Policies & Cookie Consent
Based on:
 - Nouwens et al. (2020) "Dark Patterns after GDPR" (CCS)
 - Soe et al. (2020) "Circumvention by Design"
 - EDPB Guidelines 03/2022 on Dark Patterns
 - EFF and Digital Content Next frameworks

Detects patterns in policy TEXT and structural HTML markers.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Pattern definitions: each has regex patterns, severity, description
# ─────────────────────────────────────────────────────────────────────────────

DARK_PATTERN_DEFINITIONS = [

    # ── Confirmshaming ────────────────────────────────────────────────────────
    {
        "type": "confirm_shaming",
        "name": "Confirmshaming",
        "severity": "high",
        "description": (
            "Decline/opt-out option is phrased to induce guilt or shame, "
            "coercing consent. Prohibited under EDPB Guidelines 03/2022 §3.3."
        ),
        "patterns": [
            r"no\s*[,;]?\s*(?:thanks?|thank\s+you)[,;]?\s+i\s+(?:don'?t|do\s+not)\s+(?:want|care|need)",
            r"no\s*[,;]?\s*(?:i\s+)?(?:don'?t|do\s+not)\s+(?:care\s+about|value|want)\s+(?:my\s+)?(?:privacy|data)",
            r"i\s+(?:don'?t|do\s+not)\s+(?:care\s+about|want)\s+(?:my|better|improved)\s+(?:privacy|experience|security)",
            r"i\s+prefer\s+not\s+to\s+(?:know|protect|care)",
            r"no\s*[,;]?\s*(?:i\s+)?prefer\s+(?:less\s+)?(?:privacy|security)",
        ],
        "gdpr_reference": "EDPB Guidelines 03/2022 §3.3",
    },

    # ── Interface Interference (hidden reject / buried opt-out) ───────────────
    {
        "type": "hidden_opt_out",
        "name": "Hidden / Difficult Opt-Out",
        "severity": "high",
        "description": (
            "Opt-out or consent withdrawal is significantly harder to exercise "
            "than opting in. Violates GDPR Art. 7(3) – withdrawal must be as easy as consent."
        ),
        "patterns": [
            r"(?:to\s+opt.out|unsubscribe|withdraw\s+consent)[^.]*(?:contact\s+us|email\s+us|mail\s+us|call\s+us|write\s+to)",
            r"(?:to\s+opt.out)[^.]*(?:send\s+(?:a\s+)?(?:written\s+)?request)",
            r"(?:to\s+opt.out)[^.]*(?:post|mail)[^.]*(?:address|headquarters)",
            r"manage\s+(?:your\s+)?(?:preferences|settings)\s+(?:by\s+)?(?:contacting|emailing|writing)",
        ],
        "gdpr_reference": "GDPR Art. 7(3), EDPB Guidelines 03/2022 §3.1",
    },

    # ── Pre-ticked Boxes ──────────────────────────────────────────────────────
    {
        "type": "pre_ticked_boxes",
        "name": "Pre-Ticked Consent Boxes",
        "severity": "high",
        "description": (
            "Consent checkboxes are described as pre-selected by default. "
            "Invalid consent under GDPR Art. 4(11) – must be affirmative act."
        ),
        "patterns": [
            r"(?:pre.?selected|pre.?ticked|checked\s+by\s+default|ticked\s+by\s+default)",
            r"(?:boxes?\s+(?:are\s+)?(?:pre.?)?(?:checked|ticked|selected))",
            r"(?:default(?:ly|ed)?\s+(?:opted\s+in|selected|enabled|checked))",
            r"(?:automatically\s+(?:opted\s+in|selected|enrolled))",
            r"(?:unless\s+you\s+(?:opt.out|uncheck|deselect|untick))",
        ],
        "gdpr_reference": "GDPR Art. 4(11), Recital 32, Planet49 (C-673/17)",
    },

    # ── Bundled Consent ───────────────────────────────────────────────────────
    {
        "type": "bundled_consent",
        "name": "Bundled / Tied Consent",
        "severity": "high",
        "description": (
            "Consent for optional data processing is bundled with service terms, "
            "making it impossible to consent to service without all data processing."
        ),
        "patterns": [
            r"by\s+(?:using|accessing|registering|signing\s+up|creating\s+an\s+account)[^.]*you\s+(?:agree|consent|authorize)",
            r"your\s+(?:continued\s+use|use\s+of\s+(?:our\s+)?(?:service|site|app))[^.]*constitutes?\s+(?:your\s+)?(?:agreement|consent|acceptance)",
            r"by\s+clicking\s+['\"]?(?:i\s+agree|accept|ok|continue|sign\s+up)['\"]?[^.]*you\s+(?:agree|consent)",
        ],
        "gdpr_reference": "GDPR Art. 4(11), WP259 rev.01 §3.1",
    },

    # ── Misdirection / Misleading Language ───────────────────────────────────
    {
        "type": "misdirection",
        "name": "Misdirection / Misleading Framing",
        "severity": "medium",
        "description": (
            "Policy language frames data sharing/selling as a benefit to the user, "
            "obscuring the actual commercial nature."
        ),
        "patterns": [
            r"(?:share|sell|transfer)\s+your\s+(?:data|information)\s+(?:to|with)\s+(?:our\s+)?(?:trusted\s+)?partners?\s+(?:to|in\s+order\s+to)\s+(?:improve|enhance|personalize|provide)",
            r"we\s+(?:share|use)\s+your\s+(?:data|information)\s+to\s+(?:serve|show)\s+you\s+(?:relevant|personalized|better|more\s+useful)\s+(?:ads?|advertisements?)",
            r"(?:relevant|personalized|tailored)\s+(?:advertising|ads?|marketing)",
        ],
        "gdpr_reference": "EDPB Guidelines 03/2022 §3.2",
    },

    # ── Nagging / Repeated Prompts ─────────────────────────────────────────────
    {
        "type": "nagging",
        "name": "Repeated Consent Requests (Nagging)",
        "severity": "medium",
        "description": (
            "Policy describes repeatedly prompting users who already refused consent, "
            "in violation of the spirit of Art. 7 and EDPB Guidelines."
        ),
        "patterns": [
            r"(?:may|will|could)\s+(?:continue\s+to\s+)?(?:ask|prompt|remind)\s+you\s+(?:again|periodically)",
            r"(?:re.?request|re.?ask)\s+(?:your\s+)?consent",
        ],
        "gdpr_reference": "EDPB Guidelines 03/2022 §3.4",
    },

    # ── Obstruction / Difficult Account Deletion ──────────────────────────────
    {
        "type": "obstruction",
        "name": "Obstruction of Rights Exercise",
        "severity": "medium",
        "description": (
            "Exercising data subject rights is described as requiring multiple steps, "
            "identity verification beyond what is necessary, or long delays."
        ),
        "patterns": [
            r"(?:delete|close|remove|deactivate)\s+(?:your\s+)?account[^.]*(?:contact\s+(?:us|support)|email|call|write)",
            r"(?:deletion|removal|erasure)\s+(?:request)?[^.]*(?:up\s+to|may\s+take|within)\s+\d+\s+(?:business\s+)?(?:day|week|month)s?[^.]*(?:to\s+process|to\s+complete|to\s+fulfill)",
            r"(?:notarized|sworn\s+affidavit|government.issued\s+id)[^.]*(?:required|must\s+provide|submit)",
        ],
        "gdpr_reference": "GDPR Art. 12(3), Art. 17",
    },

    # ── Obfuscation of Purposes ───────────────────────────────────────────────
    {
        "type": "obfuscation",
        "name": "Obfuscated Purposes",
        "severity": "medium",
        "description": (
            "Processing purposes are stated so broadly or vaguely that they are "
            "effectively meaningless, preventing informed consent."
        ),
        "patterns": [
            r"(?:for\s+any\s+(?:other\s+)?(?:purpose|reason))\s+(?:we\s+(?:deem|consider|determine|think))",
            r"for\s+purposes?\s+(?:described|set\s+(?:out|forth|forth)\s+in)\s+(?:this|our)\s+(?:policy|agreement|terms)",
            r"(?:any\s+other\s+)?purpose\s+for\s+which\s+you\s+(?:provide|give|submit)\s+(?:your\s+)?(?:data|information|consent)",
            r"(?:as\s+(?:otherwise\s+)?(?:permitted|allowed|authorized)\s+by\s+(?:law|applicable\s+law))",
        ],
        "gdpr_reference": "GDPR Art. 5(1)(b) – Purpose Limitation",
    },

    # ── Retroactive Consent ───────────────────────────────────────────────────
    {
        "type": "retroactive_consent",
        "name": "Retroactive / Implicit Consent",
        "severity": "high",
        "description": (
            "Policy implies consent is given retroactively through continued use, "
            "or that failure to opt out constitutes consent."
        ),
        "patterns": [
            r"if\s+you\s+(?:continue|do\s+not\s+(?:opt.out|object|contact\s+us))[^.]*(?:will\s+be\s+deemed|(?:will\s+)?constitute|(?:will\s+)?mean)\s+(?:you\s+)?(?:have\s+)?(?:agree|consent|accept)",
            r"your\s+failure\s+to\s+(?:opt.out|object|contact)[^.]*(?:constitutes?|means?|implies?)\s+(?:your\s+)?(?:agreement|consent|acceptance)",
            r"unless\s+you\s+(?:notify|contact|email|tell)\s+us[^.]*(?:will\s+be\s+deemed|(?:will\s+)?constitute)\s+(?:your\s+)?consent",
        ],
        "gdpr_reference": "GDPR Art. 4(11), Recital 32 – freely given, specific, informed",
    },

    # ── False Urgency ─────────────────────────────────────────────────────────
    {
        "type": "false_urgency",
        "name": "False Urgency / Forced Action",
        "severity": "low",
        "description": (
            "Consent banners or policy updates are framed as requiring immediate action, "
            "pressuring users to consent without adequate reflection time."
        ),
        "patterns": [
            r"(?:must|required to)\s+(?:accept|agree|consent)\s+(?:to\s+)?(?:continue|proceed|access)",
            r"(?:click|press)\s+['\"]?(?:agree|accept|ok)['\"]?\s+to\s+continue",
            r"by\s+(?:continuing|proceeding)[^.]*you\s+(?:agree|accept|consent)",
        ],
        "gdpr_reference": "EDPB Guidelines 03/2022 §3.3 – Free choice requirement",
    },
]


@dataclass
class DetectedDarkPattern:
    pattern_type: str
    name: str
    severity: str           # "high" | "medium" | "low"
    description: str
    evidence: List[str]
    gdpr_reference: str
    confidence: float       # 0.0–1.0


@dataclass
class DarkPatternAnalysis:
    detected: List[DetectedDarkPattern]
    count: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    overall_risk: str       # "critical" | "high" | "medium" | "low" | "none"
    consent_mechanism_quality: str


def detect_dark_patterns(policy_text: str) -> DarkPatternAnalysis:
    """
    Run all dark pattern checks against the policy text.
    Returns structured analysis with evidence snippets.
    """
    text_lower = policy_text.lower()
    detected: List[DetectedDarkPattern] = []

    for defn in DARK_PATTERN_DEFINITIONS:
        evidence_snippets: List[str] = []
        total_matches = 0

        for pattern in defn["patterns"]:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                total_matches += 1
                start = max(0, match.start() - 60)
                end = min(len(policy_text), match.end() + 60)
                snippet = " ".join(policy_text[start:end].split())
                evidence_snippets.append(f"…{snippet}…")
                if len(evidence_snippets) >= 2:
                    break
            if len(evidence_snippets) >= 2:
                break

        if evidence_snippets:
            confidence = min(1.0, 0.6 + total_matches * 0.1)
            detected.append(DetectedDarkPattern(
                pattern_type=defn["type"],
                name=defn["name"],
                severity=defn["severity"],
                description=defn["description"],
                evidence=evidence_snippets,
                gdpr_reference=defn["gdpr_reference"],
                confidence=round(confidence, 2),
            ))

    high = sum(1 for d in detected if d.severity == "high")
    medium = sum(1 for d in detected if d.severity == "medium")
    low = sum(1 for d in detected if d.severity == "low")

    if high >= 2:
        risk = "critical"
    elif high >= 1:
        risk = "high"
    elif medium >= 2:
        risk = "medium"
    elif medium + low >= 1:
        risk = "low"
    else:
        risk = "none"

    # Consent mechanism quality
    has_explicit_consent = bool(re.search(
        r"(?:explicit|freely\s+given|informed)\s+consent|opt.in|affirmative\s+(?:action|consent)",
        text_lower,
    ))
    has_granular = bool(re.search(
        r"(?:granular|individual|separate)\s+(?:choice|consent|opt.in)",
        text_lower,
    ))
    has_withdrawal = bool(re.search(
        r"withdraw\s+(?:your\s+)?consent|revoke\s+consent|opt.out\s+at\s+any\s+time",
        text_lower,
    ))

    if has_explicit_consent and has_granular and has_withdrawal and not detected:
        consent_quality = "good"
    elif has_explicit_consent and has_withdrawal:
        consent_quality = "adequate"
    elif any(d.severity == "high" for d in detected):
        consent_quality = "poor"
    else:
        consent_quality = "unclear"

    return DarkPatternAnalysis(
        detected=detected,
        count=len(detected),
        high_severity_count=high,
        medium_severity_count=medium,
        low_severity_count=low,
        overall_risk=risk,
        consent_mechanism_quality=consent_quality,
    )
