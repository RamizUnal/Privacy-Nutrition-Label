"""
Curated list of test sites for evaluation of the Privacy Nutrition Label pipeline.
Covers Turkish and international sites across multiple categories.

When `policy_url` is provided on a TestSite, the evaluator fetches that URL
directly and skips the auto-discovery crawl entirely.  This is useful for:
  - Sites whose policies live on a CDN or separate domain (e.g. Twitter/X PDF)
  - Stable reference policies used for repeatable evaluation (Google, etc.)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TestSite:
    url: str
    name: str
    category: str           # e-commerce, social, news, banking, government, streaming
    region: str             # TR, US, EU, UK, Global
    expected_policy: bool   # do we expect a privacy policy to exist?
    notes: Optional[str] = None
    policy_url: Optional[str] = None   # pre-known policy URL — bypasses discovery
    policy_file: Optional[str] = None  # local .txt file with policy text — bypasses fetch


# ─────────────────────────────────────────────────────────────────────────────
# Policy-analysis reference sites (known policy URLs for clean evaluation)
# ─────────────────────────────────────────────────────────────────────────────

POLICY_ANALYSIS_SITES: List[TestSite] = [
    TestSite(
        url="https://www.google.com",
        name="Google",
        category="tech",
        region="US",
        expected_policy=True,
        notes="Gold-standard GDPR/CCPA policy",
        policy_url="https://policies.google.com/privacy",
    ),
    TestSite(
        url="https://www.twitter.com",
        name="Twitter/X",
        category="social",
        region="US",
        expected_policy=True,
        notes="2025 X Privacy Policy (local text copy)",
        policy_file="evaluation/data/x.txt",
    ),
]

# ─────────────────────────────────────────────────────────────────────────────
# Turkish sites (KVKK compliance expected)
# ─────────────────────────────────────────────────────────────────────────────

TURKISH_SITES: List[TestSite] = [
    TestSite("https://www.hepsiburada.com", "Hepsiburada", "e-commerce", "TR", True,
             "Major Turkish e-commerce, KVKK compliant"),
    TestSite("https://www.trendyol.com", "Trendyol", "e-commerce", "TR", True,
             "Largest Turkish e-commerce platform"),
    TestSite("https://www.n11.com", "N11", "e-commerce", "TR", True,
             "Turkish marketplace"),
    TestSite("https://www.sahibinden.com", "Sahibinden", "e-commerce", "TR", True,
             "Turkish classifieds/marketplace"),
    TestSite("https://www.hurriyet.com.tr", "Hurriyet", "news", "TR", True,
             "Major Turkish news portal"),
    TestSite("https://www.milliyet.com.tr", "Milliyet", "news", "TR", True,
             "Turkish news site"),
]

# ─────────────────────────────────────────────────────────────────────────────
# International sites (GDPR/CCPA compliance expected)
# ─────────────────────────────────────────────────────────────────────────────

INTERNATIONAL_SITES: List[TestSite] = [
    TestSite("https://www.amazon.com", "Amazon", "e-commerce", "US", True,
             "Global e-commerce leader"),
    TestSite("https://www.reddit.com", "Reddit", "social", "US", True,
             "Forum/social platform"),
    TestSite("https://www.spotify.com", "Spotify", "streaming", "EU", True,
             "Music streaming, EU-based (GDPR)"),
    TestSite("https://www.bbc.co.uk", "BBC", "news", "UK", True,
             "UK public broadcaster"),
    TestSite("https://www.nytimes.com", "NY Times", "news", "US", True,
             "Major US newspaper"),
    TestSite("https://www.booking.com", "Booking.com", "travel", "EU", True,
             "Travel platform, NL-based (GDPR)"),
    TestSite("https://www.wikipedia.org", "Wikipedia", "reference", "Global", True,
             "Non-profit, minimal tracking expected"),
    TestSite("https://www.github.com", "GitHub", "tech", "US", True,
             "Developer platform"),
]

# ─────────────────────────────────────────────────────────────────────────────
# All sites combined
# ─────────────────────────────────────────────────────────────────────────────

ALL_SITES: List[TestSite] = POLICY_ANALYSIS_SITES + TURKISH_SITES + INTERNATIONAL_SITES


def get_sites_by_category(category: str) -> List[TestSite]:
    return [s for s in ALL_SITES if s.category == category]


def get_sites_by_region(region: str) -> List[TestSite]:
    return [s for s in ALL_SITES if s.region == region]
