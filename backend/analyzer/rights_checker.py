"""
Privacy Rights Coverage Checker
Verifies which data subject rights are explicitly addressed in a privacy policy.

Frameworks covered:
 - GDPR (EU) Arts. 15-22
 - CCPA/CPRA (California)
 - LGPD (Brazil) Arts. 17-22
 - PIPEDA (Canada)
 - UK GDPR (post-Brexit)
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# GDPR Rights (Chapter III)
# ─────────────────────────────────────────────────────────────────────────────

GDPR_RIGHTS = {
    "access": {
        "name": "Right of Access",
        "article": "Art. 15 GDPR",
        "description": "Right to obtain confirmation of processing and a copy of personal data.",
        "patterns": [
            r"right\s+(?:of|to)\s+(?:access|know|be\s+informed\s+about)",
            r"access\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"request\s+a\s+copy\s+of\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"right\s+to\s+know\s+what\s+(?:personal\s+)?(?:data|information)",
            r"subject\s+access\s+request",
            r"data\s+access\s+request",
        ],
    },
    "rectification": {
        "name": "Right to Rectification",
        "article": "Art. 16 GDPR",
        "description": "Right to have inaccurate personal data corrected without undue delay.",
        "patterns": [
            r"right\s+(?:of|to)\s+rectification",
            r"rectif(?:y|ication)\s+(?:your|inaccurate)\s+(?:personal\s+)?(?:data|information)",
            r"correct\s+(?:inaccurate|incorrect|wrong)\s+(?:personal\s+)?(?:data|information)",
            r"update\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"right\s+to\s+correct",
            r"amend\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
        ],
    },
    "erasure": {
        "name": "Right to Erasure (Right to be Forgotten)",
        "article": "Art. 17 GDPR",
        "description": "Right to have personal data erased under certain circumstances.",
        "patterns": [
            r"right\s+(?:of|to)\s+erasure",
            r"right\s+to\s+(?:be\s+forgotten|deletion|delete)",
            r"request\s+(?:the\s+)?deletion\s+of\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"erase\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"request\s+(?:that\s+)?(?:we|us)\s+delete",
            r"delete\s+(?:your|the)\s+(?:personal\s+)?(?:data|account|information)",
        ],
    },
    "restriction": {
        "name": "Right to Restriction of Processing",
        "article": "Art. 18 GDPR",
        "description": "Right to restrict processing of personal data under specific conditions.",
        "patterns": [
            r"right\s+(?:of|to)\s+restriction",
            r"restrict\s+(?:the\s+)?processing\s+of\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"right\s+to\s+limit\s+(?:the\s+)?(?:use|processing)",
            r"object\s+to\s+(?:the\s+)?processing",
        ],
    },
    "portability": {
        "name": "Right to Data Portability",
        "article": "Art. 20 GDPR",
        "description": "Right to receive personal data in machine-readable format and transmit to another controller.",
        "patterns": [
            r"right\s+(?:of|to)\s+(?:data\s+)?portability",
            r"portable\s+(?:copy|format)\s+of\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"machine.readable\s+format",
            r"receive\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)\s+in\s+a\s+(?:structured|common|machine.readable)",
            r"transfer\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)\s+to\s+another",
            r"export\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
        ],
    },
    "objection": {
        "name": "Right to Object",
        "article": "Art. 21 GDPR",
        "description": "Right to object to processing, particularly for direct marketing and legitimate interests.",
        "patterns": [
            r"right\s+(?:of|to)\s+object",
            r"object\s+to\s+(?:the\s+)?(?:processing|use)\s+of\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
            r"opt.out\s+of\s+(?:direct\s+)?(?:marketing|advertising)",
            r"unsubscribe\s+from\s+(?:marketing|promotional)",
            r"object\s+to\s+direct\s+marketing",
        ],
    },
    "automated_decisions": {
        "name": "Rights re: Automated Decision-Making",
        "article": "Art. 22 GDPR",
        "description": "Right not to be subject to solely automated decisions with significant effects.",
        "patterns": [
            r"automated\s+(?:decision.?making|decisions?)",
            r"right\s+(?:not\s+to\s+be\s+subject|regarding)\s+automated",
            r"profiling\s+(?:that|which)\s+(?:has|produces|results\s+in)\s+(?:a\s+)?(?:legal|significant)",
            r"human\s+(?:review|oversight|involvement)\s+(?:of|in)\s+automated",
            r"contest\s+automated\s+decisions?",
        ],
    },
    "withdraw_consent": {
        "name": "Right to Withdraw Consent",
        "article": "Art. 7(3) GDPR",
        "description": "Right to withdraw consent at any time without affecting prior lawful processing.",
        "patterns": [
            r"withdraw\s+(?:your\s+)?consent",
            r"revoke\s+(?:your\s+)?consent",
            r"opt.out\s+(?:at\s+any\s+time|whenever|from)",
            r"change\s+(?:your\s+)?(?:consent|mind)\s+at\s+any\s+time",
            r"without\s+affecting\s+the\s+lawfulness",
        ],
    },
    "lodge_complaint": {
        "name": "Right to Lodge Complaint",
        "article": "Art. 77 GDPR",
        "description": "Right to lodge a complaint with a supervisory authority.",
        "patterns": [
            r"supervisory\s+authority",
            r"data\s+protection\s+authority",
            r"lodge\s+a\s+complaint",
            r"file\s+a\s+complaint",
            r"information\s+commissioner",
            r"\bICO\b",
            r"\bCNIL\b",
            r"\bGarante\b",
            r"\bBfDI\b",
            r"data\s+protection\s+regulator",
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CCPA/CPRA Rights
# ─────────────────────────────────────────────────────────────────────────────

CCPA_RIGHTS = {
    "right_to_know": {
        "name": "Right to Know",
        "article": "CCPA §1798.100",
        "description": "Right to know what personal information is collected, used, shared, or sold.",
        "patterns": [
            r"right\s+to\s+know",
            r"request\s+information\s+about\s+(?:the\s+)?(?:personal\s+)?(?:data|information)\s+(?:we\s+)?collect",
            r"disclose\s+(?:the\s+)?(?:categories|types)\s+of\s+personal\s+information",
            r"right\s+to\s+request\s+disclosure",
        ],
    },
    "right_to_delete": {
        "name": "Right to Delete",
        "article": "CCPA §1798.105",
        "description": "Right to request deletion of personal information.",
        "patterns": [
            r"right\s+to\s+delete",
            r"right\s+to\s+(?:request\s+)?deletion",
            r"california\s+(?:consumer|resident)[^.]*delete",
            r"delete\s+(?:your\s+)?personal\s+information\s+(?:upon\s+)?request",
        ],
    },
    "right_to_opt_out": {
        "name": "Right to Opt-Out of Sale/Sharing",
        "article": "CCPA §1798.120 / CPRA §1798.135",
        "description": "Right to direct a business not to sell or share personal information.",
        "patterns": [
            r"do\s+not\s+sell\s+(?:my\s+)?personal\s+information",
            r"opt.out\s+of\s+(?:the\s+)?(?:sale|selling)",
            r"right\s+to\s+opt.out\s+of\s+(?:the\s+)?(?:sale|sharing)",
            r"do\s+not\s+(?:sell\s+or\s+)?share\s+(?:my\s+)?personal\s+information",
            r"opt.out\s+of\s+(?:targeted\s+advertising|cross.context)",
            r"\bCCPA\b",
        ],
    },
    "right_to_non_discrimination": {
        "name": "Right to Non-Discrimination",
        "article": "CCPA §1798.125",
        "description": "Right not to be discriminated against for exercising CCPA rights.",
        "patterns": [
            r"(?:not|no)\s+(?:discriminate|discrimination)",
            r"we\s+will\s+not\s+(?:deny|charge|penalize)\s+(?:you\s+)?for\s+exercising",
            r"non.discriminatory",
            r"right\s+not\s+to\s+be\s+discriminated\s+against",
        ],
    },
    "right_to_correct": {
        "name": "Right to Correct (CPRA)",
        "article": "CPRA §1798.106",
        "description": "Right to correct inaccurate personal information (CPRA addition).",
        "patterns": [
            r"right\s+to\s+correct",
            r"correct\s+inaccurate\s+(?:personal\s+)?information",
            r"update\s+(?:or\s+correct|and\s+correct)",
            r"(?:access,\s*)?correct,\s*or\s*modify\s+(?:the\s+)?information\s+(?:you\s+)?provided",
            r"correct\s+or\s+modify\s+(?:your|the)\s+(?:personal\s+)?(?:data|information)",
        ],
    },
    "right_to_limit_sensitive": {
        "name": "Right to Limit Sensitive PI Use (CPRA)",
        "article": "CPRA §1798.121",
        "description": "Right to limit use/disclosure of sensitive personal information.",
        "patterns": [
            r"limit\s+(?:the\s+)?(?:use|disclosure)\s+of\s+(?:your\s+)?sensitive",
            r"right\s+to\s+limit\s+(?:use|sharing)\s+of\s+sensitive",
            r"sensitive\s+personal\s+information[^.]*opt.out",
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Additional frameworks
# ─────────────────────────────────────────────────────────────────────────────

OTHER_FRAMEWORKS = {
    "lgpd": {
        "name": "LGPD (Brazil)",
        "patterns": [r"\bLGPD\b", r"Lei Geral de Prote[cç][aã]o de Dados", r"Brazilian\s+(?:data\s+)?law"],
    },
    "pipeda": {
        "name": "PIPEDA (Canada)",
        "patterns": [r"\bPIPEDA\b", r"Personal\s+Information\s+Protection\s+and\s+Electronic\s+Documents", r"Canadian\s+(?:privacy\s+)?law"],
    },
    "coppa": {
        "name": "COPPA (Children's Privacy)",
        "patterns": [r"\bCOPPA\b", r"Children'?s\s+Online\s+Privacy\s+Protection", r"under\s+(?:the\s+age\s+of\s+)?13"],
    },
    "hipaa": {
        "name": "HIPAA (Health Data US)",
        "patterns": [r"\bHIPAA\b", r"Health\s+Insurance\s+Portability", r"Protected\s+Health\s+Information", r"\bPHI\b"],
    },
    "pecr": {
        "name": "PECR / ePrivacy (UK/EU)",
        "patterns": [r"\bPECR\b", r"ePrivacy\s+(?:Regulation|Directive)", r"Privacy\s+and\s+Electronic\s+Communications"],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Cookie-related rights & compliance
# ─────────────────────────────────────────────────────────────────────────────

COOKIE_COMPLIANCE = {
    "consent_required": [
        r"(?:we\s+)?(?:obtain|ask|request|require)\s+(?:your\s+)?consent\s+(?:before|for|prior\s+to)\s+(?:using|setting|placing)",
        r"cookie\s+consent",
        r"cookie\s+banner",
        r"consent\s+management",
    ],
    "cookie_categories": [
        r"(?:necessary|essential|strictly\s+necessary)\s+(?:and\s+)?(?:functional|analytics|advertising)\s+cookies?",
        r"categories?\s+of\s+cookies?",
        r"analytical\s+cookies?",
        r"advertising\s+cookies?",
        r"performance\s+cookies?",
    ],
    "httponly_secure": [
        r"(?:httponly|http\s+only)\s+(?:flag|attribute|cookie)",
        r"secure\s+(?:flag|attribute|cookie)",
        r"samesite",
        r"(?:cookie\s+)?security\s+(?:flag|attribute|settings?)",
    ],
    "dnt_honored": [
        r"(?:do\s+not\s+track|DNT)",
        r"honor\s+(?:do\s+not\s+track|DNT)",
        r"respond\s+to\s+(?:do\s+not\s+track|DNT)",
        r"Global\s+Privacy\s+Control",
        r"\bGPC\b",
    ],
}


@dataclass
class RightCoverage:
    right_id: str
    name: str
    article: str
    description: str
    covered: bool
    evidence: Optional[str]


@dataclass
class RightsAnalysis:
    gdpr: Dict[str, RightCoverage]
    gdpr_score: int       # 0–100
    gdpr_grade: str
    ccpa: Dict[str, RightCoverage]
    ccpa_score: int
    ccpa_grade: str
    frameworks_mentioned: List[str]
    cookie_compliance: Dict[str, bool]
    dnt_mentioned: bool
    dnt_honored: bool
    global_privacy_control: bool
    overall_rights_score: int


def _grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 55: return "C"
    if score >= 35: return "D"
    return "F"


def check_rights(policy_text: str) -> RightsAnalysis:
    text_lower = policy_text.lower()

    # ── GDPR ──────────────────────────────────────────────────────────────────
    gdpr_coverage: Dict[str, RightCoverage] = {}
    for right_id, right_def in GDPR_RIGHTS.items():
        matched = False
        evidence = None
        for pattern in right_def["patterns"]:
            m = re.search(pattern, text_lower)
            if m:
                matched = True
                start = max(0, m.start() - 50)
                end = min(len(policy_text), m.end() + 80)
                evidence = "…" + " ".join(policy_text[start:end].split()) + "…"
                break
        gdpr_coverage[right_id] = RightCoverage(
            right_id=right_id,
            name=right_def["name"],
            article=right_def["article"],
            description=right_def["description"],
            covered=matched,
            evidence=evidence,
        )

    gdpr_covered = sum(1 for r in gdpr_coverage.values() if r.covered)
    gdpr_score = int(gdpr_covered / len(GDPR_RIGHTS) * 100)

    # ── CCPA ──────────────────────────────────────────────────────────────────
    ccpa_coverage: Dict[str, RightCoverage] = {}
    for right_id, right_def in CCPA_RIGHTS.items():
        matched = False
        evidence = None
        for pattern in right_def["patterns"]:
            m = re.search(pattern, text_lower)
            if m:
                matched = True
                start = max(0, m.start() - 50)
                end = min(len(policy_text), m.end() + 80)
                evidence = "…" + " ".join(policy_text[start:end].split()) + "…"
                break
        ccpa_coverage[right_id] = RightCoverage(
            right_id=right_id,
            name=right_def["name"],
            article=right_def["article"],
            description=right_def["description"],
            covered=matched,
            evidence=evidence,
        )

    ccpa_covered = sum(1 for r in ccpa_coverage.values() if r.covered)
    ccpa_score = int(ccpa_covered / len(CCPA_RIGHTS) * 100)

    # ── Other frameworks ──────────────────────────────────────────────────────
    mentioned_frameworks: List[str] = []
    for fw_id, fw_def in OTHER_FRAMEWORKS.items():
        if any(re.search(p, text_lower) for p in fw_def["patterns"]):
            mentioned_frameworks.append(fw_def["name"])

    # ── Cookie compliance ─────────────────────────────────────────────────────
    cookie_comp: Dict[str, bool] = {}
    for key, patterns in COOKIE_COMPLIANCE.items():
        cookie_comp[key] = any(re.search(p, text_lower) for p in patterns)

    dnt = bool(re.search(r"do\s+not\s+track|\bDNT\b", text_lower))
    dnt_honored = bool(re.search(r"honor\w*\s+(?:do\s+not\s+track|DNT)", text_lower))
    gpc = bool(re.search(r"Global\s+Privacy\s+Control|\bGPC\b", text_lower))

    overall = int((gdpr_score + ccpa_score) / 2)

    return RightsAnalysis(
        gdpr=gdpr_coverage,
        gdpr_score=gdpr_score,
        gdpr_grade=_grade(gdpr_score),
        ccpa=ccpa_coverage,
        ccpa_score=ccpa_score,
        ccpa_grade=_grade(ccpa_score),
        frameworks_mentioned=mentioned_frameworks,
        cookie_compliance=cookie_comp,
        dnt_mentioned=dnt,
        dnt_honored=dnt_honored,
        global_privacy_control=gpc,
        overall_rights_score=overall,
    )
