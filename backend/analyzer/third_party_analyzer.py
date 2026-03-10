"""
Third-Party Sharing Analyzer
Extracts which third parties receive data, classifies them, and cross-references
against our trust database.
"""
from __future__ import annotations
import re
import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Load the embedded trust database (fallback inline if file unavailable)
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tracker", "databases", "third_parties.json")

def _load_trust_db() -> Dict:
    try:
        with open(_DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# Sharing signal patterns
# ─────────────────────────────────────────────────────────────────────────────

SHARING_VERBS = [
    "share", "disclose", "transfer", "sell", "provide", "transmit",
    "send", "give", "pass", "distribute", "make available", "expose",
    "deliver", "furnish", "grant access",
]

THIRD_PARTY_REFERENCES = [
    r"third.?part(?:y|ies)",
    r"service\s+provider",
    r"business\s+partner",
    r"affiliate",
    r"vendor",
    r"contractor",
    r"sub.?processor",
    r"data\s+processor",
    r"advertising\s+partner",
    r"analytics\s+partner",
    r"marketing\s+partner",
    r"cloud\s+(?:service\s+)?provider",
    r"payment\s+processor",
    r"shipping\s+(?:partner|provider)",
    r"customer\s+support\s+(?:partner|provider|tool)",
    r"research\s+partner",
    r"joint\s+controller",
]

NAMED_THIRD_PARTY_PATTERN = re.compile(
    r"(?:"
    # Legal entities
    r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc\.?|LLC\.?|Ltd\.?|Corp\.?|GmbH|S\.A\.|B\.V\.|AG|PLC|SE)\b"
    r"|"
    # Known brand names
    r"\b(?:Google|Facebook|Meta|Twitter|X|LinkedIn|Microsoft|Apple|Amazon|Stripe|PayPal|"
    r"Shopify|Salesforce|HubSpot|Mailchimp|Klaviyo|Twilio|SendGrid|Zendesk|Intercom|"
    r"Drift|Crisp|Hotjar|FullStory|LogRocket|Mixpanel|Amplitude|Segment|Heap|"
    r"Optimizely|Braintree|Adyen|Square|Cloudflare|Fastly|Akamai|"
    r"TikTok|Snapchat|Pinterest|Reddit|YouTube|Instagram|WhatsApp|"
    r"Marketo|Pardot|Eloqua|Constant\s+Contact|Campaign\s+Monitor|"
    r"Criteo|DoubleClick|AdRoll|AppNexus|Xandr|TradeDesk|"
    r"Taboola|Outbrain|ShareThrough|OpenX|Rubicon|PubMatic|"
    r"Nielsen|Comscore|comScore|QuantCast|"
    r"NewRelic|Datadog|Sentry|Dynatrace|Splunk|"
    r"DocuSign|HelloSign|Adobe|Acrobat|"
    r"Zuora|Chargebee|Recurly|"
    r"FedEx|UPS|DHL|USPS|"
    r"Trustpilot|Bazaarvoice|Yotpo)\b"
    r")",
    re.MULTILINE,
)

# Data-for-service exchange patterns (cross-border transfers)
DATA_TRANSFER_PATTERNS = [
    r"transfer\w*\s+(?:personal\s+)?(?:data|information)\s+(?:to|outside of|outside)\s+(?:the\s+)?(?:European|EU|EEA|United\s+Kingdom|UK)",
    r"cross.border\s+(?:data\s+)?transfer",
    r"international\s+(?:data\s+)?transfer",
    r"standard\s+contractual\s+clauses?",
    r"\bSCC\b",
    r"adequacy\s+decision",
    r"binding\s+corporate\s+rules?",
    r"\bBCR\b",
    r"Privacy\s+Shield",  # Historical, now invalid
    r"EU.U\.S\.\s+Data\s+Privacy\s+Framework",
    r"data\s+transfer\s+(?:agreement|mechanism)",
]

# Purpose categories for third-party sharing
SHARING_PURPOSES = {
    "analytics": [
        r"analytics?", r"measurement", r"audience\s+measurement",
        r"traffic\s+analysis", r"performance\s+tracking", r"user\s+behavior",
    ],
    "advertising": [
        r"advertis(?:ing|ement)", r"targeted\s+ads?", r"ad\s+(?:serving|delivery|network)",
        r"behavioral\s+advertising", r"interest.based\s+advertising",
        r"retargeting", r"remarketing",
    ],
    "payment": [
        r"payment\s+processing", r"transaction\s+processing", r"billing",
        r"fraud\s+(?:detection|prevention)", r"credit\s+card\s+processing",
    ],
    "customer_support": [
        r"customer\s+support", r"help\s+desk", r"live\s+chat", r"support\s+ticketing",
    ],
    "email_marketing": [
        r"email\s+marketing", r"newsletters?", r"email\s+campaigns?",
        r"marketing\s+emails?", r"promotional\s+emails?",
    ],
    "social_media": [
        r"social\s+(?:media\s+)?(?:sharing|plugin|widget|button)",
        r"social\s+login", r"social\s+network",
    ],
    "hosting": [
        r"cloud\s+(?:hosting|storage|infrastructure)", r"server", r"hosting\s+provider",
        r"content\s+delivery\s+network", r"\bCDN\b",
    ],
    "legal_compliance": [
        r"law\s+enforcement", r"legal\s+(?:obligation|requirement|process)",
        r"court\s+order", r"government\s+(?:request|authority)",
        r"regulatory\s+(?:requirement|authority)",
    ],
}


@dataclass
class ThirdPartyEntry:
    name: str
    category: str
    trust_score: int           # 0–100
    trust_label: str           # "trusted" | "moderate" | "concerning" | "unknown"
    data_types_shared: List[str]
    purposes: List[str]
    opt_out_url: Optional[str]
    privacy_url: Optional[str]
    gdpr_compliant: Optional[bool]
    cross_border_transfer: bool
    is_data_broker: bool
    evidence: List[str]


@dataclass
class ThirdPartyAnalysis:
    count: int
    named_count: int
    unnamed_count: int
    parties: List[ThirdPartyEntry]
    sharing_purposes: Dict[str, bool]
    data_sold: bool
    cross_border_transfers: bool
    transfer_safeguards: List[str]
    advertising_partners: int
    analytics_partners: int
    risk_level: str            # "low" | "medium" | "high" | "critical"
    sharing_score: int         # 0–100 (higher = more sharing = worse score)


def analyze_third_parties(policy_text: str) -> ThirdPartyAnalysis:
    trust_db = _load_trust_db()
    text_lower = policy_text.lower()

    # ── Named parties ─────────────────────────────────────────────────────────
    named_in_text = set()
    for m in NAMED_THIRD_PARTY_PATTERN.finditer(policy_text):
        named_in_text.add(m.group(0).strip())

    parties: List[ThirdPartyEntry] = []
    for name in named_in_text:
        name_lower = name.lower()
        db_entry = trust_db.get(name_lower, {})

        # Find evidence in text
        evidence: List[str] = []
        for m in re.finditer(re.escape(name), policy_text, re.IGNORECASE):
            start = max(0, m.start() - 60)
            end = min(len(policy_text), m.end() + 80)
            snippet = " ".join(policy_text[start:end].split())
            evidence.append(f"…{snippet}…")
            if len(evidence) >= 2:
                break

        # Determine purposes from context around the name
        purposes: List[str] = []
        context_window = text_lower[max(0, text_lower.find(name_lower) - 200):
                                    text_lower.find(name_lower) + 200]
        for purpose, pats in SHARING_PURPOSES.items():
            if any(re.search(p, context_window) for p in pats):
                purposes.append(purpose)

        trust_score = db_entry.get("trust_score", 50)
        if trust_score >= 70:
            trust_label = "trusted"
        elif trust_score >= 50:
            trust_label = "moderate"
        elif trust_score >= 30:
            trust_label = "concerning"
        else:
            trust_label = "unknown"

        parties.append(ThirdPartyEntry(
            name=name,
            category=db_entry.get("category", "Unknown"),
            trust_score=trust_score,
            trust_label=trust_label,
            data_types_shared=db_entry.get("typical_data", []),
            purposes=purposes or db_entry.get("purposes", []),
            opt_out_url=db_entry.get("opt_out_url"),
            privacy_url=db_entry.get("privacy_url"),
            gdpr_compliant=db_entry.get("gdpr_compliant"),
            cross_border_transfer=db_entry.get("us_based", False),
            is_data_broker=db_entry.get("is_data_broker", False),
            evidence=evidence,
        ))

    # ── Count unnamed references ───────────────────────────────────────────────
    unnamed_refs = sum(
        len(re.findall(p, text_lower)) for p in THIRD_PARTY_REFERENCES
    )
    unnamed_count = max(0, unnamed_refs - len(named_in_text))

    # ── Sharing purposes ──────────────────────────────────────────────────────
    sharing_purposes: Dict[str, bool] = {
        k: any(re.search(p, text_lower) for p in v)
        for k, v in SHARING_PURPOSES.items()
    }

    # ── Data sale detection ───────────────────────────────────────────────────
    data_sold = bool(re.search(
        r"\b(?:sell|sale|sold)\b.{0,50}(?:personal\s+)?(?:information|data)",
        text_lower,
    ))

    # ── Cross-border transfers ────────────────────────────────────────────────
    cross_border = any(re.search(p, text_lower) for p in DATA_TRANSFER_PATTERNS[:5])
    safeguards: List[str] = []
    safeguard_patterns = {
        "Standard Contractual Clauses (SCCs)": DATA_TRANSFER_PATTERNS[5],
        "Adequacy Decision": DATA_TRANSFER_PATTERNS[6],
        "Binding Corporate Rules (BCRs)": DATA_TRANSFER_PATTERNS[7],
        "EU-U.S. Data Privacy Framework": DATA_TRANSFER_PATTERNS[9],
    }
    for name, pattern in safeguard_patterns.items():
        if re.search(pattern, text_lower):
            safeguards.append(name)

    advertising = sum(1 for p in parties if "advertising" in p.category.lower() or "advertising" in p.purposes)
    analytics = sum(1 for p in parties if "analytics" in p.category.lower() or "analytics" in p.purposes)

    # ── Risk level ────────────────────────────────────────────────────────────
    total = len(parties) + unnamed_count // 2
    if data_sold or any(p.is_data_broker for p in parties):
        risk = "critical"
    elif total >= 20 or advertising >= 5:
        risk = "high"
    elif total >= 8 or advertising >= 2:
        risk = "medium"
    else:
        risk = "low"

    # Sharing score (higher = worse)
    sharing_score = min(100, (
        len(parties) * 3
        + unnamed_count * 1
        + advertising * 5
        + (20 if data_sold else 0)
        + (10 if cross_border and not safeguards else 0)
    ))

    return ThirdPartyAnalysis(
        count=len(parties) + unnamed_count,
        named_count=len(parties),
        unnamed_count=unnamed_count,
        parties=sorted(parties, key=lambda p: p.trust_score)[:30],
        sharing_purposes=sharing_purposes,
        data_sold=data_sold,
        cross_border_transfers=cross_border,
        transfer_safeguards=safeguards,
        advertising_partners=advertising,
        analytics_partners=analytics,
        risk_level=risk,
        sharing_score=sharing_score,
    )
