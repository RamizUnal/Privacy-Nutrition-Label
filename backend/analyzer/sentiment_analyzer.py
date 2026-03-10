"""
Privacy Policy Sentiment & Vagueness Analyzer
Measures how transparent, specific, and accountable a privacy policy is,
using techniques drawn from research on "privacy policy readability"
(Zimmeck & Bellovin 2014, Fabian et al. 2017, PrivaSeer corpus work).

Key dimensions:
 1. Vagueness score  – how often the policy uses hedging/vague quantifiers
 2. Specificity score – named third parties, concrete timeframes, explicit purposes
 3. Passive-voice ratio – "data may be shared" vs "we share data with Google"
 4. Accountability markers – named DPO, contact info, supervisory authority
 5. Overall transparency grade
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ── Vague language indicators ─────────────────────────────────────────────────
VAGUE_QUANTIFIERS = [
    "various", "certain", "some", "multiple", "other", "many",
    "numerous", "several", "a number of", "a variety of", "a range of",
    "similar", "relevant", "appropriate", "applicable", "related",
    "including but not limited to", "among other things", "inter alia",
    "such as", "for example", "as appropriate",
]

HEDGING_TERMS = [
    "may", "might", "could", "sometimes", "in some cases", "in certain cases",
    "where applicable", "as necessary", "if required", "when necessary",
    "at our discretion", "at our sole discretion", "at any time",
    "from time to time", "as we deem", "as we see fit", "as determined by us",
    "in our sole judgment", "in our reasonable opinion",
]

VAGUE_PURPOSE_PHRASES = [
    "business purposes", "operational purposes", "internal purposes",
    "legitimate interests", "legitimate business interests",
    "service improvement", "product development", "analytical purposes",
    "marketing purposes", "commercial purposes", "administrative purposes",
    "legal purposes", "research purposes", "statistical purposes",
]

# ── Specific / transparent language indicators ────────────────────────────────
SPECIFIC_PURPOSE_PHRASES = [
    r"in order to (?:provide|deliver|process|send|fulfill)",
    r"for the (?:purpose|purposes) of (?:providing|delivering|processing)",
    r"to (?:send you|deliver|process|complete|fulfill) (?:your )?(?:order|purchase|request)",
    r"to (?:verify|authenticate|confirm) (?:your )?(?:identity|account)",
    r"to (?:comply with|meet) (?:our )?(?:legal|regulatory) (?:obligations?|requirements?)",
    r"for (?:fraud\s+)?(?:detection|prevention) (?:and\s+)?(?:security)?",
]

# Named third-party pattern – looks for company-like proper nouns
NAMED_THIRD_PARTY_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+"
    r"(?:Inc\.?|LLC\.?|Ltd\.?|Corp\.?|GmbH|S\.A\.|B\.V\.|AG|PLC|SE)\b"
)

# Known analytics/advertising companies (case-insensitive)
KNOWN_THIRD_PARTY_NAMES = [
    "google analytics", "google ads", "google tag manager", "google llc",
    "meta", "facebook", "instagram", "twitter", "linkedin",
    "salesforce", "hubspot", "mailchimp", "klaviyo",
    "stripe", "paypal", "braintree", "square",
    "amazon web services", "aws", "cloudflare",
    "zendesk", "intercom", "drift",
    "mixpanel", "amplitude", "segment", "heap",
    "hotjar", "fullstory", "logrocket",
    "criteo", "doubleclick", "adroll",
    "microsoft", "apple", "adobe",
    "twilio", "sendgrid",
    "optimizely", "vwo",
]

# Passive voice indicators in privacy context
PASSIVE_PRIVACY_PATTERNS = [
    r"\bdata (?:may|might|could|will|is|are|was|were) (?:be )?(?:shared|disclosed|transferred|sold|processed|collected|used)",
    r"\binformation (?:may|might|could|will|is|are|was|were) (?:be )?(?:shared|disclosed|transferred|sold|processed|collected|used)",
    r"\byour (?:data|information|details) (?:may|might|could|will) (?:be )?",
    r"\b(?:may|might|could) (?:be )?shared",
    r"\b(?:may|might|could) (?:be )?disclosed",
    r"\b(?:may|might|could) (?:be )?transferred",
]

# Active voice indicators
ACTIVE_PRIVACY_PATTERNS = [
    r"\bwe (?:share|disclose|transfer|sell|process|collect|use)\b",
    r"\bwe (?:do not|don'?t) (?:share|sell|disclose)\b",
    r"\b(?:we|our company|[A-Z][a-z]+ (?:Inc|LLC|Ltd)\.?) (?:share|disclose|transfer)\b",
]

# Accountability markers
ACCOUNTABILITY_PATTERNS = {
    "dpo_named": [
        r"data protection officer",
        r"\bDPO\b",
        r"privacy officer",
        r"chief privacy officer",
    ],
    "dpo_contact": [
        r"(?:contact|reach|email)\s+(?:our|the)\s+(?:data protection|privacy)\s+officer",
        r"dpo@",
        r"privacy@",
    ],
    "supervisory_authority": [
        r"supervisory authority",
        r"data protection authority",
        r"information commissioner",
        r"\bICO\b",
        r"\bCNIL\b",
        r"\bGDPR\b.*complaint",
    ],
    "legitimate_basis": [
        r"legal basis",
        r"lawful basis",
        r"legitimate interest",
        r"consent (?:as the|is the) (?:legal|lawful) basis",
        r"contractual (?:necessity|obligation)",
    ],
    "privacy_by_design": [
        r"privacy by design",
        r"privacy by default",
        r"data minimization",
        r"data minimisation",
        r"purpose limitation",
        r"storage limitation",
    ],
    "security_measures": [
        r"encryption",
        r"ssl",
        r"tls",
        r"access controls?",
        r"pseudonym(?:iz|is)ation",
        r"anonymiz(?:ation|ation)",
        r"ISO 27001",
        r"SOC 2",
    ],
}

# Complexity/readability signal (Flesch-Kincaid proxy)
LONG_SENTENCE_THRESHOLD = 60  # words


@dataclass
class SentimentResult:
    vagueness_score: int          # 0–100: higher = more vague
    specificity_score: int        # 0–100: higher = more specific
    passive_voice_ratio: float    # 0.0–1.0
    active_voice_count: int
    passive_voice_count: int
    named_third_parties: List[str]
    named_third_party_count: int
    vague_term_examples: List[str]
    hedging_examples: List[str]
    specific_purpose_count: int
    accountability: Dict[str, bool]
    accountability_score: int     # 0–100
    overall_transparency: str     # "high" | "medium" | "low" | "very_low"
    transparency_score: int       # 0–100
    avg_sentence_length: float
    readability_rating: str       # "accessible" | "complex" | "very_complex"
    flesch_kincaid_words: int


def analyze_sentiment(policy_text: str) -> SentimentResult:
    text_lower = policy_text.lower()
    words = policy_text.split()

    # ── Vague quantifiers ─────────────────────────────────────────────────────
    vague_hits: List[str] = []
    for term in VAGUE_QUANTIFIERS:
        count = text_lower.count(term)
        if count:
            vague_hits.append(f'"{term}" (×{count})')

    hedging_hits: List[str] = []
    for term in HEDGING_TERMS:
        count = text_lower.count(term)
        if count:
            hedging_hits.append(f'"{term}" (×{count})')

    vague_purpose_hits = sum(1 for p in VAGUE_PURPOSE_PHRASES if p in text_lower)

    total_vague_signals = len(vague_hits) + len(hedging_hits) + vague_purpose_hits
    # Normalize: 0 = transparent, 100 = maximally vague
    vagueness_score = min(100, int(total_vague_signals * 4))

    # ── Specific purposes ─────────────────────────────────────────────────────
    specific_count = sum(
        1 for p in SPECIFIC_PURPOSE_PHRASES if re.search(p, text_lower)
    )
    specificity_score = min(100, specific_count * 12)

    # ── Named third parties ───────────────────────────────────────────────────
    named: List[str] = []
    # From known list
    for name in KNOWN_THIRD_PARTY_NAMES:
        if name in text_lower:
            named.append(name.title())
    # From legal entity pattern
    for m in NAMED_THIRD_PARTY_PATTERN.finditer(policy_text):
        entity = m.group(0)
        if entity not in named:
            named.append(entity)
    named = list(dict.fromkeys(named))[:30]  # dedup, cap

    # ── Passive vs active voice ───────────────────────────────────────────────
    passive_count = sum(
        len(re.findall(p, text_lower)) for p in PASSIVE_PRIVACY_PATTERNS
    )
    active_count = sum(
        len(re.findall(p, text_lower)) for p in ACTIVE_PRIVACY_PATTERNS
    )
    total_voice = passive_count + active_count
    passive_ratio = passive_count / total_voice if total_voice else 0.0

    # ── Accountability markers ────────────────────────────────────────────────
    accountability: Dict[str, bool] = {}
    for key, patterns in ACCOUNTABILITY_PATTERNS.items():
        accountability[key] = any(re.search(p, text_lower) for p in patterns)
    accountability_score = int(
        sum(1 for v in accountability.values() if v) / len(accountability) * 100
    )

    # ── Readability ───────────────────────────────────────────────────────────
    sentences = re.split(r'[.!?]+', policy_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_len = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    if avg_len < 25:
        readability = "accessible"
    elif avg_len < 45:
        readability = "complex"
    else:
        readability = "very_complex"

    # ── Transparency score ────────────────────────────────────────────────────
    # Formula: weighted combination of signals
    transparency = (
        (specificity_score * 0.3)
        + (accountability_score * 0.3)
        + ((1 - passive_ratio) * 100 * 0.2)
        + (min(len(named), 10) * 3)  # up to 30 pts for naming parties
        - (vagueness_score * 0.2)
    )
    transparency_score = max(0, min(100, int(transparency)))

    if transparency_score >= 70:
        overall = "high"
    elif transparency_score >= 45:
        overall = "medium"
    elif transparency_score >= 20:
        overall = "low"
    else:
        overall = "very_low"

    return SentimentResult(
        vagueness_score=vagueness_score,
        specificity_score=specificity_score,
        passive_voice_ratio=round(passive_ratio, 3),
        active_voice_count=active_count,
        passive_voice_count=passive_count,
        named_third_parties=named,
        named_third_party_count=len(named),
        vague_term_examples=vague_hits[:10],
        hedging_examples=hedging_hits[:10],
        specific_purpose_count=specific_count,
        accountability=accountability,
        accountability_score=accountability_score,
        overall_transparency=overall,
        transparency_score=transparency_score,
        avg_sentence_length=round(avg_len, 1),
        readability_rating=readability,
        flesch_kincaid_words=len(words),
    )
