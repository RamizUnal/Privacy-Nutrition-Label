from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import tldextract


_TRACKERS_CACHE: Optional[List[Dict[str, Any]]] = None
_VENDORS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
_TRACKERS_CACHE_KEY: Optional[Tuple[str, str]] = None


def _host(url: str) -> Optional[str]:
    try:
        host = (urlparse(url).hostname or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def _etld1(hostname: Optional[str]) -> Optional[str]:
    if not hostname:
        return None
    ext = tldextract.extract(hostname)
    if not ext.domain or not ext.suffix:
        return None
    return f"{ext.domain}.{ext.suffix}".lower()


def _tracker_cache_key() -> Tuple[str, str]:
    return (
        (os.getenv("PNL_EXTRA_TRACKER_DB") or "").strip(),
        (os.getenv("PNL_TEST_MODE") or "").strip().lower(),
    )


def _candidate_tracker_paths() -> List[Path]:
    base_dir = Path(__file__).parent / "databases"
    paths: List[Path] = [base_dir / "trackers.json"]

    extra_db = (os.getenv("PNL_EXTRA_TRACKER_DB") or "").strip()
    if extra_db:
        paths.append(Path(extra_db))

    if (os.getenv("PNL_TEST_MODE") or "").strip().lower() == "true":
        test_db = base_dir / "trackers.test.json"
        if test_db.exists():
            paths.append(test_db)

    unique_paths: List[Path] = []
    seen = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)
    return unique_paths


def _load_tracker_records() -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for tracker_path in _candidate_tracker_paths():
        try:
            payload = json.loads(tracker_path.read_text(encoding="utf-8"))
            trackers = payload.get("trackers", []) if isinstance(payload, dict) else []
            merged.extend(item for item in trackers if isinstance(item, dict))
        except Exception:
            continue

    deduped: List[Dict[str, Any]] = []
    seen_domains = set()
    for tracker in merged:
        domain = str(tracker.get("domain") or "").lower().strip()
        if domain:
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
        deduped.append(tracker)
    return deduped


def _load_databases() -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    global _TRACKERS_CACHE, _VENDORS_CACHE, _TRACKERS_CACHE_KEY

    cache_key = _tracker_cache_key()
    if _TRACKERS_CACHE is None or _TRACKERS_CACHE_KEY != cache_key:
        _TRACKERS_CACHE = _load_tracker_records()
        _TRACKERS_CACHE_KEY = cache_key

    if _VENDORS_CACHE is None:
        third_parties_path = Path(__file__).parent / "databases" / "third_parties.json"
        try:
            payload = json.loads(third_parties_path.read_text(encoding="utf-8"))
            _VENDORS_CACHE = payload if isinstance(payload, dict) else {}
        except Exception:
            _VENDORS_CACHE = {}

    return _TRACKERS_CACHE, _VENDORS_CACHE


def _find_vendor_enrichment(tracker_name: str, tracker_domain: str, vendors: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    name_lower = tracker_name.lower()
    domain_lower = tracker_domain.lower()
    for vendor_key, vendor in vendors.items():
        key = str(vendor_key).lower().strip()
        if not key:
            continue
        if key in name_lower or name_lower in key or key in domain_lower:
            return vendor if isinstance(vendor, dict) else {}
    return {}


def match_known_trackers_from_urls(
    urls: list[str],
    first_party_etld1: str | None = None,
) -> dict:
    trackers, vendors = _load_databases()
    first_party = (first_party_etld1 or "").lower() or None

    matched_by_domain: Dict[str, Dict[str, Any]] = {}

    for request_url in urls or []:
        host = _host(request_url)
        if not host:
            continue

        request_etld1 = _etld1(host)
        if first_party and request_etld1 and request_etld1 == first_party:
            continue

        for tracker in trackers:
            tracker_domain = str(tracker.get("domain") or "").lower().strip()
            if not tracker_domain:
                continue
            if tracker_domain.startswith("www."):
                tracker_domain = tracker_domain[4:]

            if host != tracker_domain and not host.endswith("." + tracker_domain):
                continue

            if tracker_domain in matched_by_domain:
                continue

            tracker_name = str(tracker.get("name") or tracker_domain)
            vendor = _find_vendor_enrichment(tracker_name, tracker_domain, vendors)
            matched_by_domain[tracker_domain] = {
                "name": tracker_name,
                "domain": tracker_domain,
                "category": tracker.get("category"),
                "risk": tracker.get("risk"),
                "fingerprinting": tracker.get("fingerprinting"),
                "session_recording": tracker.get("session_recording"),
                "description": tracker.get("description"),
                "opt_out": tracker.get("opt_out"),
                "url_sample": request_url,
                "vendor_trust_score": vendor.get("trust_score") if isinstance(vendor, dict) else None,
                "vendor_is_data_broker": vendor.get("is_data_broker") if isinstance(vendor, dict) else None,
                "vendor_purposes": vendor.get("purposes") if isinstance(vendor, dict) and isinstance(vendor.get("purposes"), list) else None,
            }

    known_trackers = list(matched_by_domain.values())
    known_tracker_names = sorted({item.get("name") for item in known_trackers if item.get("name")})
    known_tracker_domains = sorted(matched_by_domain.keys())

    return {
        "known_tracker_count": len(known_trackers),
        "known_tracker_names": known_tracker_names,
        "known_tracker_domains": known_tracker_domains,
        "known_trackers": known_trackers,
        "known_tracker_matching_available": True,
    }
