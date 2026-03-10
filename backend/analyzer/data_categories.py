"""
Data Category Detection Engine
Based on GDPR Article 4 definitions, GDPR Article 9 special categories,
CCPA categories, and ISO 29101 privacy framework taxonomy.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Taxonomy Definition
# Each category includes: GDPR/CCPA reference, sensitivity level, keywords,
# contextual phrases that must appear near keywords, and negation patterns.
# ─────────────────────────────────────────────────────────────────────────────

DATA_TAXONOMY: Dict[str, dict] = {
    # ── GDPR Article 9 Special Categories (highest protection) ───────────────
    "health": {
        "name": "Health & Medical Data",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "🏥",
        "keywords": [
            "health", "medical", "health data", "medical history", "diagnosis",
            "treatment", "prescription", "medication", "clinical", "patient",
            "disease", "condition", "disability", "mental health", "psychiatric",
            "psychological", "therapy", "healthcare", "wellness", "fitness data",
            "body weight", "blood pressure", "heart rate", "sleep data",
        ],
        "collection_phrases": [
            r"collect\w* (?:your |health |medical )?(?:health|medical)",
            r"health(?:care)? (?:information|data)",
            r"medical (?:information|data|records|history)",
        ],
        "risk_description": "Most sensitive data class under GDPR. Requires explicit consent and DPA in most cases.",
    },
    "biometric": {
        "name": "Biometric Data",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(e)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "🔐",
        "keywords": [
            "biometric", "fingerprint", "facial recognition", "face recognition",
            "retina scan", "iris scan", "voice recognition", "voice print",
            "palm print", "gait recognition", "keystroke dynamics",
            "behavioral biometrics", "biometric identifier",
        ],
        "collection_phrases": [
            r"biometric(?:\s+data|\s+information|\s+identifier)?",
            r"facial\s+recognition",
            r"fingerprint(?:\s+data)?",
        ],
        "risk_description": "Uniquely identifies individuals; irreplaceable if compromised. Explicit consent required.",
    },
    "genetic": {
        "name": "Genetic Data",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(e)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "🧬",
        "keywords": [
            "genetic", "dna", "genome", "genomic", "genetic data",
            "genetic testing", "ancestry", "hereditary",
        ],
        "collection_phrases": [r"genetic\s+(?:data|information|testing)"],
        "risk_description": "Immutable and familially shared. Requires explicit consent; extremely high risk.",
    },
    "racial_ethnic": {
        "name": "Racial / Ethnic Origin",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(a)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "🌍",
        "keywords": [
            "race", "racial", "ethnic", "ethnicity", "ethnic origin",
            "national origin", "racial origin",
        ],
        "collection_phrases": [r"racial\s+or\s+ethnic\s+origin"],
        "risk_description": "Special category; collection without explicit consent is prohibited under GDPR.",
    },
    "political_opinions": {
        "name": "Political Opinions",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(a)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "🗳️",
        "keywords": [
            "political opinion", "political belief", "political affiliation",
            "political views", "party membership", "voting",
        ],
        "collection_phrases": [r"political\s+(?:opinion|belief|affiliation)"],
        "risk_description": "Special category under GDPR; heightened risk of discrimination.",
    },
    "religious_beliefs": {
        "name": "Religious / Philosophical Beliefs",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(a)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "🙏",
        "keywords": [
            "religion", "religious belief", "philosophical belief",
            "faith", "religious affiliation", "church", "denomination",
        ],
        "collection_phrases": [r"religious\s+or\s+philosophical\s+beliefs"],
        "risk_description": "Special category under GDPR. Must not be processed without explicit consent.",
    },
    "sexual_orientation": {
        "name": "Sexual Orientation / Sex Life",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(a)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "❤️",
        "keywords": [
            "sexual orientation", "sex life", "sexual life", "sexuality",
            "gender identity", "lgbtq",
        ],
        "collection_phrases": [r"sexual\s+(?:orientation|life)"],
        "risk_description": "Special category. Collection without explicit consent is prohibited.",
    },
    "trade_union": {
        "name": "Trade Union Membership",
        "sensitivity": "critical",
        "gdpr_special_category": True,
        "gdpr_article": "Art. 9(2)(a)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff2d2d",
        "icon": "👷",
        "keywords": [
            "trade union", "labor union", "union membership", "union member",
        ],
        "collection_phrases": [r"trade\s+union\s+membership"],
        "risk_description": "Special category under GDPR. Strict processing restrictions apply.",
    },

    # ── High Sensitivity (not special categories but highly sensitive) ────────
    "government_id": {
        "name": "Government Identifiers",
        "sensitivity": "high",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 87 (national IDs)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff6b00",
        "icon": "🪪",
        "keywords": [
            "social security", "ssn", "passport", "driver's license",
            "national id", "tax id", "ein", "government id",
            "national insurance", "voter id", "state id",
        ],
        "collection_phrases": [
            r"social\s+security\s+number",
            r"passport\s+number",
            r"driver.s\s+licen[sc]e",
        ],
        "risk_description": "Used for identity theft; extremely sensitive in regulatory contexts.",
    },
    "financial": {
        "name": "Financial & Payment Data",
        "sensitivity": "high",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff6b00",
        "icon": "💳",
        "keywords": [
            "credit card", "debit card", "payment", "bank account",
            "billing", "financial", "bank details", "transaction",
            "purchase history", "payment method", "iban", "swift",
            "credit score", "financial information",
        ],
        "collection_phrases": [
            r"payment\s+(?:information|data|details)",
            r"bank\s+account",
            r"credit\s+card",
        ],
        "risk_description": "Subject to PCI-DSS and financial regulation. Breach risk is extremely high.",
    },
    "precise_location": {
        "name": "Precise Location Data",
        "sensitivity": "high",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff6b00",
        "icon": "📍",
        "keywords": [
            "precise location", "gps", "geolocation", "real-time location",
            "coordinates", "latitude", "longitude", "location tracking",
            "location data", "location history", "whereabouts",
        ],
        "collection_phrases": [
            r"precise\s+(?:geo)?location",
            r"gps\s+(?:data|coordinates)",
            r"real.time\s+location",
        ],
        "risk_description": "Enables physical tracking and profiling of daily movements.",
    },
    "communications": {
        "name": "Communications Content",
        "sensitivity": "high",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1) + ePrivacy",
        "ccpa_category": "Personal Information",
        "color": "#ff6b00",
        "icon": "✉️",
        "keywords": [
            "message content", "email content", "chat history", "inbox",
            "private messages", "direct messages", "communications",
            "correspondence", "conversation",
        ],
        "collection_phrases": [
            r"content\s+of\s+(?:your\s+)?(?:messages|emails|communications)",
            r"private\s+messages",
        ],
        "risk_description": "Protected under ePrivacy Directive. Constitutes confidential communication.",
    },
    "children_data": {
        "name": "Children's Data",
        "sensitivity": "high",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 8 GDPR / COPPA (US)",
        "ccpa_category": "Sensitive Personal Information",
        "color": "#ff6b00",
        "icon": "👶",
        "keywords": [
            "children", "child", "minor", "under 13", "under 16",
            "parental consent", "coppa", "kids", "under age",
        ],
        "collection_phrases": [
            r"children\s+under\s+\d+",
            r"minors",
            r"parental\s+consent",
        ],
        "risk_description": "COPPA/GDPR Art.8 requires verifiable parental consent. Strict processing limits.",
    },
    "inferences": {
        "name": "Inferences & Profiling",
        "sensitivity": "high",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 22 GDPR",
        "ccpa_category": "Inferences",
        "color": "#ff6b00",
        "icon": "🤖",
        "keywords": [
            "inferences", "profiling", "profile", "automated decision",
            "automated processing", "scoring", "predictions",
            "behavioral profiling", "interest-based advertising",
        ],
        "collection_phrases": [
            r"inferences?\s+(?:drawn|made|about)",
            r"automated\s+decision.making",
            r"profiling",
        ],
        "risk_description": "GDPR Art.22 grants rights against automated decisions with significant effects.",
    },

    # ── Medium Sensitivity ────────────────────────────────────────────────────
    "identity": {
        "name": "Identity Data",
        "sensitivity": "medium",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Identifiers",
        "color": "#f59e0b",
        "icon": "👤",
        "keywords": [
            "name", "full name", "first name", "last name", "username",
            "user id", "account name", "display name", "real name",
            "identity", "date of birth", "age", "gender",
        ],
        "collection_phrases": [
            r"(?:collect|gather|receive)\s+your\s+(?:name|identity)",
            r"full\s+name",
        ],
        "risk_description": "Core personal identifier. Directly enables subject re-identification.",
    },
    "contact": {
        "name": "Contact Information",
        "sensitivity": "medium",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Identifiers",
        "color": "#f59e0b",
        "icon": "📱",
        "keywords": [
            "email address", "phone number", "address", "postal code",
            "zip code", "telephone", "mobile number", "street address",
            "home address", "mailing address", "contact information",
        ],
        "collection_phrases": [
            r"(?:email|phone|address)\s+(?:address|number)?",
            r"contact\s+information",
        ],
        "risk_description": "Enables unsolicited communications; subject to anti-spam regulation.",
    },
    "behavioral": {
        "name": "Behavioral & Usage Data",
        "sensitivity": "medium",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Internet or other electronic network activity",
        "color": "#f59e0b",
        "icon": "📊",
        "keywords": [
            "browsing history", "search history", "usage data", "activity data",
            "interaction data", "clickstream", "page views", "session data",
            "log data", "access logs", "behavioral data",
        ],
        "collection_phrases": [
            r"browsing\s+(?:history|behavior|activity)",
            r"usage\s+(?:data|information|statistics)",
            r"interaction\s+data",
        ],
        "risk_description": "Enables detailed profiling of habits, interests, and preferences.",
    },
    "social_connections": {
        "name": "Social Connections",
        "sensitivity": "medium",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Personal Information",
        "color": "#f59e0b",
        "icon": "👥",
        "keywords": [
            "contacts", "friends list", "connections", "followers",
            "social graph", "address book", "social network",
            "contact list", "people you follow",
        ],
        "collection_phrases": [
            r"social\s+(?:graph|connections|network)",
            r"contact\s+list",
            r"friends\s+list",
        ],
        "risk_description": "Reveals associations; can be used for social manipulation.",
    },
    "user_content": {
        "name": "User-Generated Content",
        "sensitivity": "medium",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Inferences",
        "color": "#f59e0b",
        "icon": "📝",
        "keywords": [
            "content you post", "user content", "reviews", "comments",
            "uploads", "photos", "videos", "posts", "user-generated",
        ],
        "collection_phrases": [
            r"content\s+(?:you|users?)\s+(?:post|upload|share|submit)",
            r"user.generated\s+content",
        ],
        "risk_description": "May contain incidentally disclosed sensitive data.",
    },
    "approximate_location": {
        "name": "Approximate Location",
        "sensitivity": "medium",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Geolocation Data",
        "color": "#f59e0b",
        "icon": "🗺️",
        "keywords": [
            "ip address location", "general location", "city", "region",
            "country", "approximate location", "geographic region",
        ],
        "collection_phrases": [
            r"(?:city|region|country)\s+(?:level\s+)?location",
            r"approximate\s+location",
        ],
        "risk_description": "Can narrow identity to local area; lower risk than precise location.",
    },

    # ── Low Sensitivity ───────────────────────────────────────────────────────
    "device": {
        "name": "Device & Technical Data",
        "sensitivity": "low",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Identifiers",
        "color": "#22c55e",
        "icon": "💻",
        "keywords": [
            "ip address", "device", "browser type", "operating system",
            "hardware", "device id", "cookie identifier", "device fingerprint",
            "user agent", "screen resolution", "time zone", "language",
        ],
        "collection_phrases": [
            r"device\s+(?:information|identifier|data)",
            r"ip\s+address",
            r"browser\s+type",
        ],
        "risk_description": "Used for fingerprinting; can uniquely identify users across sessions.",
    },
    "professional": {
        "name": "Professional Information",
        "sensitivity": "low",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Professional or employment-related information",
        "color": "#22c55e",
        "icon": "💼",
        "keywords": [
            "employer", "job title", "company", "workplace", "occupation",
            "professional information", "work experience", "skills",
            "education", "degree", "university",
        ],
        "collection_phrases": [
            r"professional\s+(?:information|background)",
            r"employment\s+(?:information|history)",
        ],
        "risk_description": "Lower individual risk; may reveal salary/career details when combined.",
    },
    "preferences": {
        "name": "Preferences & Interests",
        "sensitivity": "low",
        "gdpr_special_category": False,
        "gdpr_article": "Art. 4(1)",
        "ccpa_category": "Inferences",
        "color": "#22c55e",
        "icon": "⭐",
        "keywords": [
            "preferences", "interests", "settings", "favorites",
            "wishlist", "recommendations", "personalization",
        ],
        "collection_phrases": [
            r"your\s+preferences",
            r"interests\s+(?:and|or)\s+(?:preferences|activities)",
        ],
        "risk_description": "Low individual risk; enables targeted marketing and personalization.",
    },
}


@dataclass
class DetectedDataType:
    category_id: str
    name: str
    sensitivity: str
    gdpr_special_category: bool
    gdpr_article: str
    ccpa_category: str
    color: str
    icon: str
    evidence: List[str]
    shared: bool = False
    shared_with: List[str] = field(default_factory=list)
    purposes: List[str] = field(default_factory=list)
    risk_description: str = ""


def detect_data_categories(policy_text: str) -> List[DetectedDataType]:
    """
    Scan policy text for mentions of each data category using keyword matching
    and contextual phrase patterns. Returns all detected categories with evidence.
    """
    text_lower = policy_text.lower()
    detected: List[DetectedDataType] = []

    for cat_id, cat in DATA_TAXONOMY.items():
        evidence_snippets: List[str] = []

        # Check plain keywords first
        for kw in cat["keywords"]:
            kw_lower = kw.lower()
            if kw_lower in text_lower:
                # Extract surrounding context (100 chars on each side)
                idx = text_lower.find(kw_lower)
                snippet = policy_text[max(0, idx - 80): idx + len(kw) + 80].strip()
                snippet = " ".join(snippet.split())  # normalize whitespace
                evidence_snippets.append(f'…{snippet}…')
                if len(evidence_snippets) >= 2:
                    break

        # Check contextual phrases for higher confidence
        for pattern in cat.get("collection_phrases", []):
            if re.search(pattern, text_lower):
                idx = [m.start() for m in re.finditer(pattern, text_lower)]
                for i in idx[:1]:
                    snippet = policy_text[max(0, i - 60): i + 120].strip()
                    snippet = " ".join(snippet.split())
                    if snippet not in evidence_snippets:
                        evidence_snippets.append(f'…{snippet}…')

        if evidence_snippets:
            detected.append(DetectedDataType(
                category_id=cat_id,
                name=cat["name"],
                sensitivity=cat["sensitivity"],
                gdpr_special_category=cat["gdpr_special_category"],
                gdpr_article=cat["gdpr_article"],
                ccpa_category=cat["ccpa_category"],
                color=cat["color"],
                icon=cat["icon"],
                evidence=evidence_snippets[:3],
                risk_description=cat["risk_description"],
            ))

    return detected


def extract_sharing_relationships(
    policy_text: str, detected: List[DetectedDataType]
) -> List[DetectedDataType]:
    """
    For each detected data type, look for nearby sharing language to flag
    which categories are shared with third parties.
    """
    sharing_patterns = [
        r"share\w* (?:your |this |such |that )?(?:personal |this )?(?:data|information|details)",
        r"disclose\w* (?:to )?(?:third.?part(?:y|ies)|partner|vendor|affiliate)",
        r"transfer\w* (?:your )?(?:personal |this )?(?:data|information) to",
        r"provid\w* (?:your )?(?:data|information) (?:to|with)",
        r"sell\w* (?:your )?(?:personal )?(?:data|information)",
    ]
    text_lower = policy_text.lower()
    sharing_context_radius = 300  # characters

    for item in detected:
        for evidence in item.evidence:
            ev_clean = evidence.strip("…").lower()
            pos = text_lower.find(ev_clean[:40])
            if pos == -1:
                continue
            window = text_lower[max(0, pos - sharing_context_radius): pos + sharing_context_radius]
            for pattern in sharing_patterns:
                if re.search(pattern, window):
                    item.shared = True
                    break

    return detected


SENSITIVITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def sort_by_sensitivity(detected: List[DetectedDataType]) -> List[DetectedDataType]:
    return sorted(detected, key=lambda d: SENSITIVITY_ORDER.get(d.sensitivity, 99))
