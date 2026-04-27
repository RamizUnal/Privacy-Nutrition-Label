"""
Third-Party Ecosystem Researcher
For every tracker, named third party, and ad/analytics partner found in an analysis,
this module:
  1. Resolves their privacy policy, security page, DPA, and trust/certifications URLs
  2. Fetches and extracts readable text from those pages
  3. Uses Claude to produce a structured "trust dossier" for each party
  4. Returns a full ecosystem map

This answers "who gets my data and what do they do with it?"
"""
from __future__ import annotations
import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .claude_client import acomplete, FAST_MODEL

# ─────────────────────────────────────────────────────────────────────────────
# Known page registry for major players
# Maps lowercase company name → dict of useful URLs
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_PAGES: Dict[str, Dict[str, str]] = {
    "google": {
        "privacy": "https://policies.google.com/privacy",
        "security": "https://safety.google/",
        "dpa": "https://cloud.google.com/terms/data-processing-addendum",
        "trust": "https://cloud.google.com/security/compliance",
        "sub_processors": "https://cloud.google.com/terms/subprocessors",
    },
    "google llc": {
        "privacy": "https://policies.google.com/privacy",
        "security": "https://safety.google/",
        "dpa": "https://cloud.google.com/terms/data-processing-addendum",
        "trust": "https://cloud.google.com/security/compliance",
    },
    "google analytics": {
        "privacy": "https://policies.google.com/privacy",
        "security": "https://support.google.com/analytics/answer/6004245",
        "dpa": "https://business.safety.google/adsprocessorterms/",
        "opt_out": "https://tools.google.com/dlpage/gaoptout",
    },
    "meta": {
        "privacy": "https://www.facebook.com/privacy/policy/",
        "security": "https://www.facebook.com/security",
        "dpa": "https://www.facebook.com/legal/EU_data_transfer_addendum",
        "trust": "https://www.facebook.com/help/safetycenter/",
        "sub_processors": "https://www.facebook.com/legal/ads-subprocessors",
    },
    "facebook": {
        "privacy": "https://www.facebook.com/privacy/policy/",
        "security": "https://www.facebook.com/security",
        "dpa": "https://www.facebook.com/legal/EU_data_transfer_addendum",
    },
    "stripe": {
        "privacy": "https://stripe.com/privacy",
        "security": "https://stripe.com/docs/security",
        "dpa": "https://stripe.com/legal/dpa",
        "trust": "https://stripe.com/docs/security/stripe",
        "sub_processors": "https://stripe.com/legal/service-providers",
        "certifications": "PCI-DSS Level 1, SOC 1 & 2, ISO 27001",
    },
    "paypal": {
        "privacy": "https://www.paypal.com/us/legalhub/privacy-full",
        "security": "https://www.paypal.com/us/webapps/mpp/security/security-home",
        "dpa": "https://www.paypal.com/us/legalhub/paypal-data-processing-agreement",
    },
    "hotjar": {
        "privacy": "https://www.hotjar.com/legal/policies/privacy/",
        "security": "https://help.hotjar.com/hc/en-us/articles/115011639587",
        "dpa": "https://www.hotjar.com/legal/support-and-security/data-processing-agreement/",
        "trust": "https://www.hotjar.com/legal/compliance/",
        "opt_out": "https://www.hotjar.com/legal/compliance/opt-out",
    },
    "fullstory": {
        "privacy": "https://www.fullstory.com/legal/privacy-policy",
        "security": "https://www.fullstory.com/legal/security",
        "dpa": "https://www.fullstory.com/legal/dpa",
        "trust": "https://www.fullstory.com/security/",
        "opt_out": "https://www.fullstory.com/optout",
    },
    "mixpanel": {
        "privacy": "https://mixpanel.com/legal/privacy-policy/",
        "security": "https://mixpanel.com/legal/security/",
        "dpa": "https://mixpanel.com/legal/data-processing-agreement/",
        "sub_processors": "https://mixpanel.com/legal/mixpanel-subprocessors/",
    },
    "amplitude": {
        "privacy": "https://amplitude.com/privacy",
        "security": "https://amplitude.com/security",
        "dpa": "https://amplitude.com/data-privacy-framework",
        "trust": "https://amplitude.com/trust",
        "sub_processors": "https://amplitude.com/amplitude-subprocessors",
    },
    "segment": {
        "privacy": "https://www.twilio.com/legal/privacy",
        "security": "https://www.twilio.com/en-us/security",
        "dpa": "https://www.twilio.com/legal/data-protection-addendum",
        "trust": "https://www.twilio.com/en-us/trust-center",
        "sub_processors": "https://www.twilio.com/legal/sub-processors",
    },
    "hubspot": {
        "privacy": "https://legal.hubspot.com/privacy-policy",
        "security": "https://legal.hubspot.com/security",
        "dpa": "https://legal.hubspot.com/dpa",
        "trust": "https://trust.hubspot.com/",
        "sub_processors": "https://legal.hubspot.com/sub-processors",
    },
    "mailchimp": {
        "privacy": "https://mailchimp.com/legal/privacy/",
        "security": "https://mailchimp.com/about/security/",
        "dpa": "https://mailchimp.com/legal/data-processing-addendum/",
        "sub_processors": "https://mailchimp.com/legal/subprocessors/",
    },
    "salesforce": {
        "privacy": "https://www.salesforce.com/company/privacy/",
        "security": "https://www.salesforce.com/products/platform/best-practices/security/",
        "dpa": "https://www.salesforce.com/content/dam/web/en_us/www/documents/legal/Agreements/data-processing-addendum.pdf",
        "trust": "https://trust.salesforce.com/",
        "certifications": "ISO 27001, SOC 1 & 2, PCI-DSS, HIPAA",
    },
    "zendesk": {
        "privacy": "https://www.zendesk.com/company/agreements-and-terms/privacy-notice/",
        "security": "https://www.zendesk.com/company/privacy-and-data-protection/",
        "dpa": "https://www.zendesk.com/company/agreements-and-terms/data-processing-agreement/",
        "trust": "https://www.zendesk.com/trust-center/",
        "sub_processors": "https://www.zendesk.com/company/agreements-and-terms/subprocessors/",
    },
    "intercom": {
        "privacy": "https://www.intercom.com/legal/privacy",
        "security": "https://www.intercom.com/legal/security",
        "dpa": "https://www.intercom.com/legal/data-processing-agreement",
        "trust": "https://www.intercom.com/security",
        "sub_processors": "https://www.intercom.com/legal/subprocessors",
    },
    "criteo": {
        "privacy": "https://www.criteo.com/privacy/",
        "security": "https://www.criteo.com/privacy/security/",
        "opt_out": "https://www.criteo.com/privacy/disable-criteo-services-on-internet/",
    },
    "twilio": {
        "privacy": "https://www.twilio.com/legal/privacy",
        "security": "https://www.twilio.com/en-us/security",
        "dpa": "https://www.twilio.com/legal/data-protection-addendum",
        "trust": "https://www.twilio.com/en-us/trust-center",
        "certifications": "SOC 2, ISO 27001, PCI-DSS",
    },
    "microsoft": {
        "privacy": "https://privacy.microsoft.com/en-us/privacystatement",
        "security": "https://www.microsoft.com/en-us/trust-center/security",
        "dpa": "https://www.microsoft.com/en-us/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection-Addendum-DPA",
        "trust": "https://www.microsoft.com/en-us/trust-center",
        "certifications": "ISO 27001, SOC 1 & 2, PCI-DSS, HIPAA, FedRAMP",
    },
    "amazon web services": {
        "privacy": "https://aws.amazon.com/privacy/",
        "security": "https://aws.amazon.com/security/",
        "dpa": "https://d1.awsstatic.com/legal/aws-dpa/aws-dpa.pdf",
        "trust": "https://aws.amazon.com/compliance/",
        "sub_processors": "https://aws.amazon.com/compliance/sub-processors/",
        "certifications": "SOC 1/2/3, ISO 27001, PCI-DSS, HIPAA, FedRAMP",
    },
    "cloudflare": {
        "privacy": "https://www.cloudflare.com/privacypolicy/",
        "security": "https://www.cloudflare.com/security-policy/",
        "dpa": "https://www.cloudflare.com/cloudflare-customer-dpa/",
        "trust": "https://www.cloudflare.com/trust-hub/",
        "certifications": "SOC 2, ISO 27001, PCI-DSS",
    },
    "tiktok": {
        "privacy": "https://www.tiktok.com/legal/page/us/privacy-policy/en",
        "security": "https://www.tiktok.com/safety/en/",
        "trust": "https://www.tiktok.com/transparency",
    },
    "klaviyo": {
        "privacy": "https://www.klaviyo.com/legal/privacy-notice",
        "security": "https://www.klaviyo.com/security",
        "dpa": "https://www.klaviyo.com/legal/data-processing-agreement",
        "sub_processors": "https://www.klaviyo.com/legal/subprocessors",
    },
    "optimizely": {
        "privacy": "https://www.optimizely.com/legal/privacy/",
        "security": "https://www.optimizely.com/security/",
        "dpa": "https://www.optimizely.com/legal/dpa/",
    },
    "adobe": {
        "privacy": "https://www.adobe.com/privacy/policy.html",
        "security": "https://www.adobe.com/trust/compliance/adobe-ccf.html",
        "dpa": "https://www.adobe.com/content/dam/cc/en/legal/terms/enterprise/pdfs/DPCC-EE-en-US-20231108.pdf",
        "trust": "https://www.adobe.com/trust.html",
        "certifications": "SOC 2, ISO 27001, FedRAMP",
    },
    "adroll": {
        "privacy": "https://www.adroll.com/about/privacy",
        "opt_out": "https://app.adroll.com/optout/safari",
    },
    "linkedin": {
        "privacy": "https://www.linkedin.com/legal/privacy-policy",
        "security": "https://security.linkedin.com/",
        "dpa": "https://www.linkedin.com/legal/data-processing-agreement",
    },
    "twitter": {
        "privacy": "https://twitter.com/en/privacy",
        "security": "https://help.twitter.com/en/safety-and-security",
        "opt_out": "https://twitter.com/settings/personalization",
    },
    "sendgrid": {
        "privacy": "https://www.twilio.com/legal/privacy",
        "security": "https://www.twilio.com/en-us/security",
        "dpa": "https://www.twilio.com/legal/data-protection-addendum",
        "certifications": "SOC 2, ISO 27001",
    },
    "logrocket": {
        "privacy": "https://logrocket.com/privacy/",
        "security": "https://logrocket.com/security/",
        "dpa": "https://logrocket.com/dpa/",
    },
    "heap": {
        "privacy": "https://heap.io/privacy",
        "security": "https://heap.io/security",
        "dpa": "https://heap.io/dpa",
    },
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PrivacyResearchBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = httpx.Timeout(15.0, connect=8.0)
MAX_CHARS = 6000  # max chars to send to Claude per page

GENERIC_PARTY_NAMES = {
    "service provider",
    "service providers",
    "business partner",
    "business partners",
    "partner",
    "partners",
    "affiliate",
    "affiliates",
    "vendor",
    "vendors",
    "supplier",
    "suppliers",
    "advertiser",
    "advertisers",
    "advertising partners",
    "analytics providers",
    "payment processors",
    "cloud providers",
    "law enforcement",
    "government authorities",
    "professional advisors",
    "third parties",
    "third party",
    "unnamed recipient category",
}

LEGAL_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|gmbh|plc|sa|sarl)\b\.?",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PageFetch:
    url: str
    label: str          # "privacy" | "security" | "dpa" | "trust" | "sub_processors"
    content: str        # extracted text
    success: bool
    error: Optional[str] = None


@dataclass
class ThirdPartyDossier:
    name: str
    category: str
    pages_fetched: List[PageFetch]
    pages_found: Dict[str, str]      # label → url
    ai_summary: str
    data_collected: List[str]
    data_shared_with: List[str]      # their sub-processors
    certifications: List[str]
    gdpr_role: str                   # "Controller" | "Processor" | "Joint Controller" | "Unknown"
    data_location: List[str]
    retention_claimed: str
    opt_out_url: Optional[str]
    risk_flags: List[str]
    positive_signals: List[str]
    trust_score_ai: int              # 0-100 AI-derived trust score
    error: Optional[str] = None


@dataclass
class EcosystemMap:
    domain: str
    total_parties_researched: int
    dossiers: List[ThirdPartyDossier]
    executive_summary: str           # AI overall summary
    highest_risk_party: Optional[str]
    data_flow_description: str       # AI-generated data flow narrative
    recommended_actions: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Fetching helpers
# ─────────────────────────────────────────────────────────────────────────────

def _canonical_party_key(name: str) -> str:
    key = (name or "").lower()
    key = LEGAL_SUFFIX_RE.sub("", key)
    key = re.sub(r"[^a-z0-9.]+", " ", key)
    key = " ".join(key.split())
    aliases = {
        "google llc": "google",
        "google analytics": "google analytics",
        "facebook": "meta",
        "facebook pixel": "meta",
        "meta pixel": "meta",
        "aws": "amazon web services",
        "amazon aws": "amazon web services",
        "twitter": "x",
    }
    return aliases.get(key, key)


def _is_researchable_party(name: str) -> bool:
    key = _canonical_party_key(name)
    if not key or len(key) < 2:
        return False
    if key in GENERIC_PARTY_NAMES:
        return False
    if key.endswith(" providers") or key.endswith(" partners"):
        return False
    return True

async def _fetch_page(client: httpx.AsyncClient, url: str) -> Tuple[str, bool, Optional[str]]:
    """Fetch URL and return (text, success, error)."""
    try:
        resp = await client.get(url, headers=BROWSER_HEADERS, follow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "button", "svg"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 5]
            text = "\n".join(lines)[:MAX_CHARS]
            return text, True, None
        return "", False, f"HTTP {resp.status_code}"
    except Exception as e:
        return "", False, str(e)[:80]


async def _discover_pages(client: httpx.AsyncClient, domain: str) -> Dict[str, str]:
    """
    For unknown parties, try to auto-discover their privacy/security/trust pages
    by fetching the root domain and scanning footer/legal links.
    """
    pages: Dict[str, str] = {}
    LINK_KEYWORDS = {
        "privacy": ["privacy", "datenschutz", "confidentialit"],
        "security": ["security", "safety", "sicherheit"],
        "dpa": ["data-processing", "dpa", "data-protection-addendum", "gdpr"],
        "trust": ["trust", "compliance", "certifications"],
        "sub_processors": ["sub-processor", "subprocessor", "third-party-service"],
    }
    try:
        url = f"https://{domain}"
        resp = await client.get(url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=10.0)
        if resp.status_code != 200:
            return pages
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").lower()
            text = a.get_text(separator=" ").lower().strip()
            full = urljoin(url, href)
            if not full.startswith("http"):
                continue
            for label, keywords in LINK_KEYWORDS.items():
                if label not in pages:
                    if any(kw in href or kw in text for kw in keywords):
                        pages[label] = full
                        break
    except Exception:
        pass
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# AI analysis
# ─────────────────────────────────────────────────────────────────────────────

DOSSIER_SYSTEM = """You are a data privacy analyst specializing in third-party data processor assessment.
You analyze privacy policies, DPAs, security pages, and trust documentation to produce structured dossiers.
Be precise, cite specific facts from the text, and flag any concerning practices.
Always respond with valid JSON matching the exact schema requested."""

async def _ai_analyze_party(
    name: str,
    category: str,
    pages: List[PageFetch],
) -> dict:
    """Use Claude to analyze fetched pages and produce a structured dossier."""
    context_parts = []
    for p in pages:
        if p.success and p.content:
            context_parts.append(f"=== {p.label.upper()} PAGE ({p.url}) ===\n{p.content[:2000]}")

    if not context_parts:
        return {
            "summary": f"No pages could be fetched for {name}.",
            "data_collected": [],
            "data_shared_with": [],
            "certifications": [],
            "gdpr_role": "Unknown",
            "data_location": [],
            "retention_claimed": "Not stated",
            "risk_flags": ["No documentation accessible"],
            "positive_signals": [],
            "trust_score_ai": 30,
        }

    context = "\n\n".join(context_parts)

    prompt = f"""Analyze the following pages from "{name}" (a {category} company) and respond with a JSON object:

{context}

Return ONLY valid JSON with this exact schema:
{{
  "summary": "2-3 sentence plain-English summary of their data practices",
  "data_collected": ["list", "of", "data", "types", "they", "collect"],
  "data_shared_with": ["list", "of", "sub-processors", "or", "partners", "named"],
  "certifications": ["ISO 27001", "SOC 2", "PCI-DSS", "etc - only if explicitly mentioned"],
  "gdpr_role": "Controller|Processor|Joint Controller|Unknown",
  "data_location": ["US", "EU", "etc - countries or regions mentioned"],
  "retention_claimed": "What retention period they claim, or Not stated",
  "risk_flags": ["Specific concerning findings with direct evidence"],
  "positive_signals": ["Specific positive findings"],
  "trust_score_ai": 0-100
}}
Be specific and factual. Only include items actually present in the text."""

    result = await acomplete(prompt, system=DOSSIER_SYSTEM, model=FAST_MODEL, max_tokens=1200)
    if not result:
        return {"summary": "AI analysis unavailable.", "data_collected": [], "data_shared_with": [],
                "certifications": [], "gdpr_role": "Unknown", "data_location": [],
                "retention_claimed": "Unknown", "risk_flags": [], "positive_signals": [], "trust_score_ai": 40}
    try:
        # Strip any markdown fences
        clean = result.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```(?:json)?", "", clean).strip().rstrip("```").strip()
        return json.loads(clean)
    except Exception:
        return {"summary": result[:300], "data_collected": [], "data_shared_with": [],
                "certifications": [], "gdpr_role": "Unknown", "data_location": [],
                "retention_claimed": "Unknown", "risk_flags": [], "positive_signals": [], "trust_score_ai": 40}


import json


# ─────────────────────────────────────────────────────────────────────────────
# Main research function
# ─────────────────────────────────────────────────────────────────────────────

async def research_single_party(
    name: str,
    category: str,
    opt_out_url: Optional[str] = None,
    max_pages: int = 3,
) -> ThirdPartyDossier:
    """Research a single third party – fetch their pages and analyze."""
    name_lower = name.lower()
    known = KNOWN_PAGES.get(name_lower, {})

    async with httpx.AsyncClient(timeout=TIMEOUT, verify=True) as client:
        # Discover pages if not in known DB
        if not known:
            # Try to extract domain from name
            domain_guess = name_lower.replace(" ", "").replace(",", "").replace(".", "") + ".com"
            # Better: check if name looks like a domain
            if "." in name_lower:
                domain_guess = name_lower.strip()
            discovered = await _discover_pages(client, domain_guess)
            known.update(discovered)

        # Collect opt-out URL
        final_opt_out = known.get("opt_out") or opt_out_url

        # Fetch pages (limit to max_pages)
        page_labels = ["privacy", "security", "dpa", "trust", "sub_processors"][:max_pages]
        fetch_tasks = []
        pages_found: Dict[str, str] = {}

        for label in page_labels:
            url = known.get(label)
            if url:
                pages_found[label] = url
                fetch_tasks.append((label, url))

        fetched_pages: List[PageFetch] = []
        if fetch_tasks:
            results = await asyncio.gather(
                *[_fetch_page(client, url) for _, url in fetch_tasks],
                return_exceptions=True,
            )
            for (label, url), result in zip(fetch_tasks, results):
                if isinstance(result, Exception):
                    fetched_pages.append(PageFetch(url=url, label=label, content="", success=False, error=str(result)[:80]))
                else:
                    text, success, error = result
                    fetched_pages.append(PageFetch(url=url, label=label, content=text, success=success, error=error))

        # AI analysis
        ai_data = await _ai_analyze_party(name, category, fetched_pages)

        return ThirdPartyDossier(
            name=name,
            category=category,
            pages_fetched=fetched_pages,
            pages_found=pages_found,
            ai_summary=ai_data.get("summary", ""),
            data_collected=ai_data.get("data_collected", []),
            data_shared_with=ai_data.get("data_shared_with", []),
            certifications=ai_data.get("certifications", []) + ([known.get("certifications", "")] if known.get("certifications") else []),
            gdpr_role=ai_data.get("gdpr_role", "Unknown"),
            data_location=ai_data.get("data_location", []),
            retention_claimed=ai_data.get("retention_claimed", "Not stated"),
            opt_out_url=final_opt_out,
            risk_flags=ai_data.get("risk_flags", []),
            positive_signals=ai_data.get("positive_signals", []),
            trust_score_ai=ai_data.get("trust_score_ai", 40),
        )


async def research_ecosystem(
    domain: str,
    third_parties: list,   # List of ThirdPartyEntry from the main analysis
    trackers: list,        # List of DetectedTracker
    max_parties: int = 12,
) -> EcosystemMap:
    """
    Research all third parties and trackers in parallel,
    then generate an executive summary with Claude.
    """
    # Build unified party list (deduplicated by name)
    seen: set = set()
    party_queue: List[Tuple[str, str, Optional[str]]] = []  # (name, category, opt_out)

    for tp in (third_parties or []):
        nm = tp.name if hasattr(tp, 'name') else tp.get('name', '')
        key = _canonical_party_key(nm)
        if nm and _is_researchable_party(nm) and key not in seen:
            seen.add(key)
            cat = tp.category if hasattr(tp, 'category') else tp.get('category', 'Unknown')
            opt = tp.opt_out_url if hasattr(tp, 'opt_out_url') else tp.get('opt_out_url')
            party_queue.append((nm, cat, opt))

    for t in (trackers or []):
        nm = t.name if hasattr(t, 'name') else t.get('name', '')
        key = _canonical_party_key(nm)
        if nm and _is_researchable_party(nm) and key not in seen:
            seen.add(key)
            cat = t.category if hasattr(t, 'category') else t.get('category', 'Tracker')
            opt = t.opt_out if hasattr(t, 'opt_out') else t.get('opt_out')
            party_queue.append((nm, cat, opt))

    # Cap at max_parties
    party_queue = party_queue[:max_parties]

    # Research all in parallel (with semaphore to avoid overloading)
    sem = asyncio.Semaphore(4)

    async def bounded_research(name: str, cat: str, opt: Optional[str]) -> ThirdPartyDossier:
        async with sem:
            try:
                return await research_single_party(name, cat, opt)
            except Exception as e:
                return ThirdPartyDossier(
                    name=name, category=cat, pages_fetched=[], pages_found={},
                    ai_summary=f"Research failed: {e}", data_collected=[], data_shared_with=[],
                    certifications=[], gdpr_role="Unknown", data_location=[],
                    retention_claimed="Unknown", opt_out_url=opt,
                    risk_flags=["Research unavailable"], positive_signals=[],
                    trust_score_ai=30, error=str(e),
                )

    dossiers = await asyncio.gather(
        *[bounded_research(nm, cat, opt) for nm, cat, opt in party_queue]
    )
    dossiers = list(dossiers)

    # AI executive summary
    exec_summary = await _generate_executive_summary(domain, dossiers)
    highest_risk = min(dossiers, key=lambda d: d.trust_score_ai).name if dossiers else None
    data_flow = await _generate_data_flow(domain, dossiers)
    actions = _derive_actions(dossiers)

    return EcosystemMap(
        domain=domain,
        total_parties_researched=len(dossiers),
        dossiers=dossiers,
        executive_summary=exec_summary,
        highest_risk_party=highest_risk,
        data_flow_description=data_flow,
        recommended_actions=actions,
    )


async def _generate_executive_summary(domain: str, dossiers: List[ThirdPartyDossier]) -> str:
    if not dossiers:
        return f"No third parties were researched for {domain}."

    summary_lines = []
    for d in dossiers[:8]:
        summary_lines.append(f"- {d.name} ({d.category}): trust={d.trust_score_ai}/100, role={d.gdpr_role}. {d.ai_summary[:150]}")

    prompt = f"""You are a privacy analyst. A user visited {domain}. Their data flows to these third parties:

{chr(10).join(summary_lines)}

Write a 3-4 sentence executive summary for a non-technical user explaining:
1. Who gets their data
2. The biggest risks
3. What they should know

Be direct, specific, and avoid jargon."""

    result = await acomplete(prompt, model=FAST_MODEL, max_tokens=300)
    return result or f"Data from {domain} is shared with {len(dossiers)} third parties including advertising, analytics, and support platforms."


async def _generate_data_flow(domain: str, dossiers: List[ThirdPartyDossier]) -> str:
    if not dossiers:
        return ""
    names = [d.name for d in dossiers[:6]]
    prompt = f"""Describe in 2-3 sentences how user data flows from {domain} to: {', '.join(names)}.
Be specific about what types of data move where and for what purpose. Write for a privacy-conscious user."""
    result = await acomplete(prompt, model=FAST_MODEL, max_tokens=200)
    return result or ""


def _derive_actions(dossiers: List[ThirdPartyDossier]) -> List[str]:
    actions = []
    for d in dossiers:
        if d.opt_out_url:
            actions.append(f"Opt out of {d.name} tracking: {d.opt_out_url}")
    if any(d.gdpr_role == "Controller" for d in dossiers):
        actions.append("Submit Subject Access Requests (SARs) to data controllers to see what they hold about you.")
    if any("fingerprint" in " ".join(d.risk_flags).lower() for d in dossiers):
        actions.append("Use Firefox with uBlock Origin to block fingerprinting scripts.")
    if len(dossiers) > 5:
        actions.append("Consider using a privacy-focused browser extension (uBlock Origin, Privacy Badger) to limit tracking.")
    actions.append("Review and adjust your consent preferences in the site's cookie settings.")
    return list(dict.fromkeys(actions))[:8]  # dedup, cap
