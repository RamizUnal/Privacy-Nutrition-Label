"""
Privacy Nutrition Label Pipeline Evaluator
Runs the full analysis pipeline against test sites and computes metrics.

Metrics computed:
  1. Policy Discovery Rate — % of sites where privacy policy was found
  2. Banner Detection Rate — % of sites where consent banner was found
  3. Consent Effectiveness Rate — % of sites where reject reduces tracking
  4. Mismatch Frequency — % of sites with ≥1 policy-behavior mismatch  
  5. LLM Accuracy — precision/recall/F1 vs OPP-115 ground truth
"""
from __future__ import annotations

import asyncio
import json
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from evaluation.test_sites import TestSite, ALL_SITES


@dataclass
class SiteEvaluation:
    """Evaluation result for a single site."""
    url: str
    name: str
    category: str
    region: str
    
    # Pipeline metrics
    policy_found: bool = False
    policy_url: Optional[str] = None
    policy_word_count: int = 0
    policy_discovery_method: Optional[str] = None
    
    # Score
    overall_score: int = 0
    grade: str = "F"
    risk_level: str = "critical"
    
    # Dynamic crawl metrics
    banner_detected: bool = False
    accept_button_found: bool = False
    reject_button_found: bool = False
    s0_trackers: int = 0
    s1_trackers: int = 0
    s2_trackers: int = 0
    s0_cookies: int = 0
    s1_cookies: int = 0
    s2_cookies: int = 0
    consent_effective: bool = False
    consent_effectiveness_pct: float = 0.0
    
    # Mismatch metrics
    mismatch_count: int = 0
    mismatch_critical: int = 0
    mismatch_high: int = 0
    mismatch_score: int = 100
    pre_consent_tracking: bool = False
    undeclared_trackers: int = 0
    
    # Timing
    analysis_time_seconds: float = 0.0
    
    # Errors
    error: Optional[str] = None
    success: bool = False


@dataclass
class PipelineEvaluation:
    """Aggregate evaluation results."""
    timestamp: str
    total_sites: int
    successful_sites: int
    failed_sites: int
    
    # Discovery metrics
    policy_discovery_rate: float = 0.0
    policy_discovery_by_method: Dict[str, int] = field(default_factory=dict)
    
    # Banner detection metrics
    banner_detection_rate: float = 0.0
    accept_button_rate: float = 0.0
    reject_button_rate: float = 0.0
    
    # Consent metrics
    consent_effective_rate: float = 0.0
    pre_consent_tracking_rate: float = 0.0
    avg_s0_trackers: float = 0.0
    avg_s1_trackers: float = 0.0
    avg_s2_trackers: float = 0.0
    
    # Mismatch metrics
    mismatch_frequency: float = 0.0
    avg_mismatches: float = 0.0
    
    # Score distribution
    avg_score: float = 0.0
    grade_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Timing
    total_time_seconds: float = 0.0
    avg_time_per_site: float = 0.0
    
    # Per-site details
    site_results: List[SiteEvaluation] = field(default_factory=list)


def _fetch_policy_url_html(policy_url: str) -> tuple[bool, str]:
    """Fetch policy text from a known HTML URL. Returns (success, text)."""
    import httpx
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        resp = httpx.get(policy_url, follow_redirects=True, headers=headers, timeout=30.0)
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 3]
        return True, "\n".join(lines)
    except Exception:
        return False, ""


def _analyze_site_sync(site: TestSite) -> SiteEvaluation:
    """
    Run the full pipeline on a single site.
    Priority:
      A) site.policy_file  — read text from local file, skip all network fetch
      B) site.policy_url   — fetch HTML from known URL, skip discovery
      C) auto-discovery    — run the full crawler
    """
    import sys

    backend_dir = str(Path(__file__).parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from crawler import crawl_website
    from tracker.detector import detect_trackers_from_html
    from analyzer.policy_analyzer import analyze_policy
    from scoring.privacy_scorer import calculate_score
    from analyzer.mismatch_analyzer import analyze_mismatches

    result = SiteEvaluation(
        url=site.url,
        name=site.name,
        category=site.category,
        region=site.region,
    )
    start_time = time.time()

    try:
        policy_text = ""
        homepage_html = ""
        homepage_cookies: list = []
        tracker_result = None

        # ── Path A: local file — read directly ──────────────────────────────
        if site.policy_file:
            file_path = Path(backend_dir) / site.policy_file
            print(f"  Reading policy from file: {file_path}")
            if file_path.exists():
                policy_text = file_path.read_text(encoding="utf-8", errors="replace")
                result.policy_found = True
                result.policy_url = str(file_path)
                result.policy_discovery_method = "local_file"
                result.policy_word_count = len(policy_text.split())
            else:
                print(f"  File not found: {file_path}")

            # Fetch homepage for tracker detection
            try:
                import httpx
                r = httpx.get(site.url, follow_redirects=True, timeout=15.0,
                              headers={"User-Agent": "Mozilla/5.0"})
                homepage_html = r.text
            except Exception:
                pass

        # ── Path B: pre-known HTML URL ───────────────────────────────────────
        elif site.policy_url:
            print(f"  Using pre-known policy URL: {site.policy_url}")
            ok, policy_text = _fetch_policy_url_html(site.policy_url)
            result.policy_found = ok
            result.policy_url = site.policy_url
            result.policy_discovery_method = "pre-known (html)"
            result.policy_word_count = len(policy_text.split()) if policy_text else 0
            if not ok:
                print(f"  Could not fetch policy URL")

            try:
                import httpx
                r = httpx.get(site.url, follow_redirects=True, timeout=15.0,
                              headers={"User-Agent": "Mozilla/5.0"})
                homepage_html = r.text
            except Exception:
                pass

        # ── Path C: auto-discovery via crawler ──────────────────────────────
        else:
            try:
                crawl = asyncio.run(asyncio.wait_for(crawl_website(site.url), timeout=60.0))
            except asyncio.TimeoutError:
                raise TimeoutError(f"crawl_website timed out after 60s for {site.url}")

            result.policy_found = crawl.policy_found
            result.policy_url = crawl.policy_url
            result.policy_word_count = crawl.word_count
            result.policy_discovery_method = crawl.discovery_method
            policy_text = crawl.policy_text
            homepage_html = crawl.homepage_html
            homepage_cookies = crawl.homepage_cookies

        # 2. Detect trackers from homepage HTML
        if homepage_html:
            tracker_result = detect_trackers_from_html(homepage_html, site.url, homepage_cookies)

        # 3. Dynamic crawl (optional, may fail)
        dynamic_result = None
        try:
            from tracker.dynamic_crawler import run_3_state_crawl
            from urllib.parse import urlparse as _urlparse
            _domain = _urlparse(site.url).netloc.replace("www.", "")
            dynamic_result = asyncio.run(asyncio.wait_for(run_3_state_crawl(_domain, site.url), timeout=90.0))

            if dynamic_result:
                s0 = dynamic_result.get("S0", {})
                s1 = dynamic_result.get("S1", {})
                s2 = dynamic_result.get("S2", {})
                result.s0_trackers = s0.get("total_trackers", 0)
                result.s1_trackers = s1.get("total_trackers", 0)
                result.s2_trackers = s2.get("total_trackers", 0)
                result.s0_cookies = s0.get("total_cookies", 0)
                result.s1_cookies = s1.get("total_cookies", 0)
                result.s2_cookies = s2.get("total_cookies", 0)
                result.banner_detected = dynamic_result.get("banner_found", False)
                result.accept_button_found = dynamic_result.get("accept_clicked", False)
                result.reject_button_found = dynamic_result.get("reject_clicked", False)
        except Exception as e:
            print(f"  Dynamic crawl failed for {site.name}: {e}")

        # 4. Analyze policy if found
        analysis_dict = {}
        if result.policy_found and policy_text and len(policy_text) >= 100:
            from urllib.parse import urlparse
            domain = urlparse(site.url).netloc.replace("www.", "")

            analysis_tuple = analyze_policy(
                policy_text,
                policy_url=result.policy_url,
                domain=domain,
            )
            analysis_dict, data_types, retention, sentiment, dark_patterns, rights, third_parties = analysis_tuple

            # 5. Mismatch analysis
            mismatch_dict = None
            try:
                mismatch_result = analyze_mismatches(
                    policy_text=policy_text,
                    policy_analysis=analysis_dict,
                    dynamic_result=dynamic_result,
                    tracker_result=tracker_result,
                )
                import dataclasses
                mismatch_dict = dataclasses.asdict(mismatch_result)
                result.mismatch_count = mismatch_result.total_count
                result.mismatch_critical = mismatch_result.critical_count
                result.mismatch_high = mismatch_result.high_count
                result.mismatch_score = mismatch_result.mismatch_score
                result.consent_effective = mismatch_result.consent_effective
                result.consent_effectiveness_pct = mismatch_result.consent_effectiveness_pct
                result.pre_consent_tracking = mismatch_result.pre_consent_tracking
                result.undeclared_trackers = mismatch_result.undeclared_tracker_count
            except Exception as e:
                print(f"  Mismatch analysis failed for {site.name}: {e}")

            # 6. Score
            score = calculate_score(
                data_types=data_types,
                third_parties=third_parties,
                retention=retention,
                rights=rights,
                sentiment=sentiment,
                dark_patterns=dark_patterns,
                tracker_result=tracker_result,
                policy_found=True,
                dynamic_crawling=dynamic_result,
                mismatch_analysis=mismatch_dict,
            )
            result.overall_score = score.overall
            result.grade = score.grade
            result.risk_level = score.risk_level

        result.success = True

    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        print(f"  ERROR analyzing {site.name}: {result.error}")
        traceback.print_exc()

    result.analysis_time_seconds = round(time.time() - start_time, 2)
    return result


def evaluate_pipeline(
    sites: Optional[List[TestSite]] = None,
    skip_dynamic: bool = False,
) -> PipelineEvaluation:
    """
    Run the full evaluation suite against a list of test sites.
    
    Args:
        sites: List of TestSite to evaluate. Defaults to ALL_SITES.
        skip_dynamic: If True, skip the dynamic 3-state crawl (faster).
    
    Returns:
        PipelineEvaluation with aggregate metrics.
    """
    if sites is None:
        sites = ALL_SITES
    
    print(f"\n{'='*60}")
    print(f"Privacy Nutrition Label — Pipeline Evaluation")
    print(f"{'='*60}")
    print(f"Sites to evaluate: {len(sites)}")
    print(f"Dynamic crawling: {'enabled' if not skip_dynamic else 'disabled'}")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    all_results: List[SiteEvaluation] = []
    total_start = time.time()
    
    for i, site in enumerate(sites, 1):
        print(f"[{i}/{len(sites)}] Analyzing {site.name} ({site.url})...")
        result = _analyze_site_sync(site)
        all_results.append(result)
        
        status = "✓" if result.success else "✗"
        if result.success:
            s_val = "N/A" if result.overall_score == -1 else f"{result.overall_score}/100"
            score_str = f"Score: {s_val} ({result.grade})"
        else:
            score_str = f"Error: {result.error}"
        print(f"  {status} {score_str} | Time: {result.analysis_time_seconds}s\n")
    
    total_time = round(time.time() - total_start, 2)
    
    # ── Compute aggregate metrics ─────────────────────────────────────────
    successful = [r for r in all_results if r.success]
    n_success = len(successful)
    
    evaluation = PipelineEvaluation(
        timestamp=datetime.now().isoformat(),
        total_sites=len(all_results),
        successful_sites=n_success,
        failed_sites=len(all_results) - n_success,
        total_time_seconds=total_time,
        avg_time_per_site=round(total_time / len(all_results), 2) if all_results else 0.0,
        site_results=all_results,
    )
    
    if n_success == 0:
        return evaluation
    
    # Policy discovery
    policy_found = sum(1 for r in successful if r.policy_found)
    evaluation.policy_discovery_rate = round(policy_found / n_success * 100, 1)
    
    methods: Dict[str, int] = {}
    for r in successful:
        if r.policy_discovery_method:
            methods[r.policy_discovery_method] = methods.get(r.policy_discovery_method, 0) + 1
    evaluation.policy_discovery_by_method = methods
    
    # Banner detection
    banner_sites = [r for r in successful if r.banner_detected or r.accept_button_found or r.reject_button_found]
    evaluation.banner_detection_rate = round(len(banner_sites) / n_success * 100, 1)
    evaluation.accept_button_rate = round(
        sum(1 for r in successful if r.accept_button_found) / n_success * 100, 1
    )
    evaluation.reject_button_rate = round(
        sum(1 for r in successful if r.reject_button_found) / n_success * 100, 1
    )
    
    # Consent effectiveness
    sites_with_tracking = [r for r in successful if r.s0_trackers > 0]
    if sites_with_tracking:
        effective = sum(1 for r in sites_with_tracking if r.consent_effective)
        evaluation.consent_effective_rate = round(effective / len(sites_with_tracking) * 100, 1)
    
    evaluation.pre_consent_tracking_rate = round(
        sum(1 for r in successful if r.pre_consent_tracking) / n_success * 100, 1
    )
    evaluation.avg_s0_trackers = round(sum(r.s0_trackers for r in successful) / n_success, 1)
    evaluation.avg_s1_trackers = round(sum(r.s1_trackers for r in successful) / n_success, 1)
    evaluation.avg_s2_trackers = round(sum(r.s2_trackers for r in successful) / n_success, 1)
    
    # Mismatch frequency
    sites_with_mismatch = sum(1 for r in successful if r.mismatch_count > 0)
    evaluation.mismatch_frequency = round(sites_with_mismatch / n_success * 100, 1)
    evaluation.avg_mismatches = round(
        sum(r.mismatch_count for r in successful) / n_success, 2
    )
    
    # Scores
    evaluation.avg_score = round(sum(r.overall_score for r in successful) / n_success, 1)
    grades: Dict[str, int] = {}
    for r in successful:
        grades[r.grade] = grades.get(r.grade, 0) + 1
    evaluation.grade_distribution = grades
    
    return evaluation


def print_evaluation_report(evaluation: PipelineEvaluation) -> str:
    """Print a formatted evaluation report and return it as a string."""
    lines = []
    
    def p(line=""):
        lines.append(line)
        print(line)
    
    p(f"\n{'='*70}")
    p("PRIVACY NUTRITION LABEL — EVALUATION REPORT")
    p(f"{'='*70}")
    p(f"Timestamp: {evaluation.timestamp}")
    p(f"Sites tested: {evaluation.total_sites} | Successful: {evaluation.successful_sites} | Failed: {evaluation.failed_sites}")
    p(f"Total time: {evaluation.total_time_seconds}s | Avg per site: {evaluation.avg_time_per_site}s")
    
    p(f"\n{'─'*70}")
    p("1. POLICY DISCOVERY")
    p(f"{'─'*70}")
    p(f"  Policy found:    {evaluation.policy_discovery_rate}%")
    p(f"  By method:       {evaluation.policy_discovery_by_method}")
    
    p(f"\n{'─'*70}")
    p("2. CONSENT BANNER DETECTION")
    p(f"{'─'*70}")
    p(f"  Banner detected: {evaluation.banner_detection_rate}%")
    p(f"  Accept button:   {evaluation.accept_button_rate}%")
    p(f"  Reject button:   {evaluation.reject_button_rate}%")
    
    p(f"\n{'─'*70}")
    p("3. CONSENT EFFECTIVENESS")
    p(f"{'─'*70}")
    p(f"  Consent effective:      {evaluation.consent_effective_rate}%")
    p(f"  Pre-consent tracking:   {evaluation.pre_consent_tracking_rate}%")
    p(f"  Avg trackers (S0/S1/S2): {evaluation.avg_s0_trackers} / {evaluation.avg_s1_trackers} / {evaluation.avg_s2_trackers}")
    
    p(f"\n{'─'*70}")
    p("4. POLICY-BEHAVIOR MISMATCHES")
    p(f"{'─'*70}")
    p(f"  Sites with ≥1 mismatch:    {evaluation.mismatch_frequency}%")
    p(f"  Avg mismatches per site:   {evaluation.avg_mismatches}")
    
    p(f"\n{'─'*70}")
    p("5. OVERALL SCORES")
    p(f"{'─'*70}")
    p(f"  Average score:   {evaluation.avg_score}/100")
    p(f"  Grade dist:      {evaluation.grade_distribution}")
    
    p(f"\n{'─'*70}")
    p("SITE-BY-SITE RESULTS")
    p(f"{'─'*70}")
    p(f"  {'Site':<25} {'Score':>5} {'Grade':>5} {'Policy':>7} {'Trackers':>10} {'Mismatches':>10} {'Time':>7}")
    p(f"  {'─'*25} {'─'*5} {'─'*5} {'─'*7} {'─'*10} {'─'*10} {'─'*7}")
    
    for r in evaluation.site_results:
        if r.success:
            s_val = "  N/A" if r.overall_score == -1 else f"{r.overall_score:>5}"
            p(f"  {r.name:<25} {s_val} {r.grade:>5} {'✓' if r.policy_found else '✗':>7} "
              f"{r.s0_trackers}/{r.s1_trackers}/{r.s2_trackers:>10} {r.mismatch_count:>10} {r.analysis_time_seconds:>6.1f}s")
        else:
            p(f"  {r.name:<25}  FAIL                         {r.error or 'Unknown'}")
    
    p(f"\n{'='*70}")
    
    return "\n".join(lines)


def save_evaluation(evaluation: PipelineEvaluation, output_path: Optional[str] = None) -> str:
    """Save evaluation results to JSON."""
    if output_path is None:
        output_path = str(Path(__file__).parent / "results" / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    data = asdict(evaluation)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_path}")
    return output_path
