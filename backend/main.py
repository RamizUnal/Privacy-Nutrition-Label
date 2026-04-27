"""
Privacy Nutrition Label Generator – FastAPI Backend
"""
from __future__ import annotations
import asyncio
import dataclasses
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, get_db
from database.crud import (
    get_or_create_policy_version,
    save_analysis,
    get_latest_analysis,
    get_analysis_history,
    get_policy_changes,
    get_all_analyzed_domains,
    get_policy_text,
)
from crawler import crawl_website, debug_policy_discovery, extract_domain
from analyzer.policy_analyzer import analyze_policy
from tracker.detector import detect_trackers_from_html
from scoring.privacy_scorer import calculate_score
from ai.policy_ai import analyze_policy_ai, stream_chat_response
from ai.policy_extraction import (
    AI_POLICY_EXTRACTION_VERSION,
    ai_policy_extraction_enabled,
    extract_policy_entities_ai,
)
from ai.third_party_researcher import research_ecosystem
from ai.claude_client import is_available as ai_available
from tracker.stateful_adapter import run_integrated_state_crawl
from analyzer.mismatch_analyzer import analyze_mismatches


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Privacy Lens API",
    description="Analyzes websites and generates comprehensive privacy labels.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: str
    force_refresh: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            v = "https://" + v.lstrip("/")
        try:
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError("Invalid URL")
        except Exception:
            raise ValueError("Invalid URL provided")
        return v


class AIAnalyzeRequest(BaseModel):
    domain: str


class EcosystemRequest(BaseModel):
    domain: str
    max_parties: int = 12


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    domain: str
    messages: List[ChatMessage]


def _dc(obj) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dc(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dc(v) for k, v in obj.items()}
    return obj


def _cached_result_matches_enabled_features(result_json: dict) -> bool:
    if ai_policy_extraction_enabled():
        meta = result_json.get("ai_extraction") or {}
        if meta.get("version") != AI_POLICY_EXTRACTION_VERSION:
            return False
        if meta.get("complete") is not True:
            return False

    # Score-breakdown schema check: older cached results don't contain the
    # per-dimension `baselines` / `clamped` fields, and they're missing the
    # additional penalty entries (high/medium sensitivity, mid-range tracker
    # counts, etc.). Without these the UI can't show the math line and the
    # numbers don't add up. Treat such cache entries as stale and re-analyze.
    sb = result_json.get("score_breakdown") or {}
    if not isinstance(sb.get("baselines"), dict):
        return False
    if "clamped" not in sb:
        return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/recent")
async def get_recent_analyses(db: AsyncSession = Depends(get_db)):
    """Return recently analyzed domains."""
    domains = await get_all_analyzed_domains(db, limit=20)
    return {"domains": domains}


@app.post("/analyze")
async def analyze_website(
    req: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main endpoint: crawl a website, analyze its privacy policy,
    detect trackers, compute score, store result.
    """
    domain = extract_domain(req.url)

    # ── Check cache unless force refresh ──────────────────────────────────────
    if not req.force_refresh:
        cached = await get_latest_analysis(db, domain)
        if cached and cached.result_json and _cached_result_matches_enabled_features(cached.result_json):
            return {
                "cached": True,
                "domain": domain,
                **cached.result_json,
            }

    # ── Crawl ─────────────────────────────────────────────────────────────────
    try:
        crawl = await asyncio.wait_for(crawl_website(req.url), timeout=60.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Crawl timed out while looking for the privacy policy.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")

    # ── Tracker detection from homepage HTML ──────────────────────────────────
    tracker_result = None
    if crawl.homepage_html:
        try:
            tracker_result = detect_trackers_from_html(
                crawl.homepage_html,
                domain,
                crawl.homepage_cookies,
            )
        except Exception:
            pass

    # ── Dynamic Crawl (Playwright) ───────────────────────────────────────────
    dynamic_result = None
    if os.getenv("ENABLE_DYNAMIC_CRAWL", "").lower() in {"1", "true", "yes"}:
        try:
            dynamic_result = await asyncio.wait_for(
                run_integrated_state_crawl(domain, req.url),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            print(f"Dynamic crawl timed out for {domain}")
        except Exception as e:
            print(f"Dynamic crawl failed: {e}")

    # ── Policy analysis ────────────────────────────────────────────────────────
    policy_text = crawl.policy_text or ""

    if not crawl.policy_found:
        # ── PATH A: No privacy policy found at all ─────────────────────────
        score_breakdown = calculate_score(
            data_types=[],
            third_parties=_empty_third_parties(),
            retention=_empty_retention(),
            rights=_empty_rights(),
            sentiment=_empty_sentiment(),
            dark_patterns=_empty_dark_patterns(),
            tracker_result=tracker_result,
            policy_found=False,
            dynamic_crawling=dynamic_result,
            mismatch_analysis=None,
        )
        result = _build_result(
            url=req.url,
            domain=domain,
            crawl=crawl,
            analysis={},
            tracker_result=tracker_result,
            score=score_breakdown,
            dynamic_result=dynamic_result,
            mismatch_result=None,
        )

    elif len(policy_text) < 100:
        # ── PATH B: Policy URL found but text is unreadable ────────────────
        # Typical for JS-rendered SPAs (Next.js, React, etc.)
        # The crawler found the privacy page URL, but the actual content is
        # loaded via JavaScript and isn't in the static HTML.
        # → We still give credit for HAVING a policy
        # → Tracker/cookie analysis is fully available (homepage HTML)
        # → Policy dimensions get neutral "unknown" scores (not 0)
        score_breakdown = _score_js_rendered_policy(tracker_result, dynamic_result)
        result = _build_result(
            url=req.url,
            domain=domain,
            crawl=crawl,
            analysis={
                "js_rendered_note": (
                    "Privacy policy page was found but its content is loaded via "
                    "JavaScript and could not be extracted for analysis. "
                    "Tracker and cookie analysis is still fully available."
                ),
            },
            tracker_result=tracker_result,
            score=score_breakdown,
            dynamic_result=dynamic_result,
            mismatch_result=None,
        )

    else:
        # ── PATH C: Full analysis with extracted text ──────────────────────
        try:
            analysis_tuple = analyze_policy(
                policy_text,
                policy_url=crawl.policy_url,
                domain=domain,
            )
            analysis_dict, data_types, retention, sentiment, dark_patterns, rights, third_parties = analysis_tuple
            ai_entities = await extract_policy_entities_ai(
                domain=domain,
                policy_text=policy_text,
                fallback_data_types=data_types,
                fallback_third_parties=third_parties,
                fallback_retention=retention,
                fallback_dark_patterns=dark_patterns,
                fallback_rights=rights,
                fallback_sentiment=sentiment,
            )
            data_types = ai_entities.data_types
            third_parties = ai_entities.third_parties
            retention = ai_entities.retention
            dark_patterns = ai_entities.dark_patterns
            rights = ai_entities.rights
            sentiment = ai_entities.sentiment
            analysis_dict["data_types"] = _dc(data_types)
            analysis_dict["third_parties"] = _dc(third_parties)
            analysis_dict["retention"] = _dc(retention)
            analysis_dict["dark_patterns"] = _dc(dark_patterns)
            analysis_dict["rights"] = _dc(rights)
            analysis_dict["sentiment"] = _dc(sentiment)
            analysis_dict["ai_extraction"] = ai_entities.meta
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

        # ── Policy-Behaviour Mismatch Analysis ─────────────────────────────
        mismatch_result = None
        mismatch_dict = None
        try:
            import dataclasses as _dc_mod
            mismatch_result = analyze_mismatches(
                policy_text=policy_text,
                policy_analysis=analysis_dict,
                dynamic_result=dynamic_result,
                tracker_result=tracker_result,
            )
            mismatch_dict = _dc(mismatch_result)
        except Exception as e:
            print(f"Mismatch analysis failed: {e}")

        score_breakdown = calculate_score(
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

        result = _build_result(
            url=req.url,
            domain=domain,
            crawl=crawl,
            analysis=analysis_dict,
            tracker_result=tracker_result,
            score=score_breakdown,
            dynamic_result=dynamic_result,
            mismatch_result=mismatch_dict,
        )

    # ── Persist ────────────────────────────────────────────────────────────────
    try:
        policy_version_id = None
        if crawl.policy_found and policy_text:
            version, _ = await get_or_create_policy_version(
                db, domain, crawl.policy_url or "", policy_text
            )
            policy_version_id = version.id

        scores_dict = {
            "overall": score_breakdown.overall,
            "grade": score_breakdown.grade,
            "risk_level": score_breakdown.risk_level,
            "data": score_breakdown.data_collection_score,
            "sharing": score_breakdown.sharing_score,
            "transparency": score_breakdown.transparency_score,
            "rights": score_breakdown.rights_score,
            "retention": score_breakdown.retention_score,
            "dark_patterns": score_breakdown.dark_patterns_score,
            "cookie": score_breakdown.technical_score,
            "tracker": score_breakdown.technical_score,
        }

        await save_analysis(db, domain, req.url, policy_version_id, scores_dict, result)
    except Exception:
        pass  # Don't fail the request if persistence fails

    return {"cached": False, "domain": domain, **result}


@app.get("/history/{domain}")
async def get_domain_history(domain: str, db: AsyncSession = Depends(get_db)):
    """Return analysis history for a domain."""
    analyses = await get_analysis_history(db, domain, limit=10)
    changes = await get_policy_changes(db, domain, limit=10)

    return {
        "domain": domain,
        "analyses": [
            {
                "id": a.id,
                "analyzed_at": a.analyzed_at.isoformat(),
                "overall_score": a.overall_score,
                "grade": a.grade,
                "risk_level": a.risk_level,
            }
            for a in analyses
        ],
        "policy_changes": [
            {
                "id": c.id,
                "detected_at": c.detected_at.isoformat(),
                "summary": c.change_summary,
                "added_lines": c.added_lines,
                "removed_lines": c.removed_lines,
                "similarity_ratio": c.similarity_ratio,
                "diff_snippets": c.diff_json,
            }
            for c in changes
        ],
    }


@app.get("/compare/{domain}")
async def compare_policies(domain: str, db: AsyncSession = Depends(get_db)):
    """Return the latest two analyses for comparison."""
    analyses = await get_analysis_history(db, domain, limit=2)
    if len(analyses) < 2:
        return {"message": "Not enough history for comparison", "domain": domain}

    newer, older = analyses[0], analyses[1]
    return {
        "domain": domain,
        "newer": {
            "analyzed_at": newer.analyzed_at.isoformat(),
            "score": newer.overall_score,
            "grade": newer.grade,
            "result": newer.result_json,
        },
        "older": {
            "analyzed_at": older.analyzed_at.isoformat(),
            "score": older.overall_score,
            "grade": older.grade,
            "result": older.result_json,
        },
        "score_delta": newer.overall_score - older.overall_score,
    }


@app.get("/policy/text/{domain}")
async def get_policy_text_for_domain(domain: str, db: AsyncSession = Depends(get_db)):
    """
    Return the stored raw policy text for a domain, plus metadata.
    """
    from database.models import PolicyVersion
    from sqlalchemy import select, desc

    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.domain == domain)
        .where(PolicyVersion.is_current == True)
        .order_by(desc(PolicyVersion.fetched_at))
        .limit(1)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail=f"No policy stored for '{domain}'")

    return {
        "domain": domain,
        "policy_url": version.policy_url,
        "word_count": version.word_count,
        "fetched_at": version.fetched_at.isoformat() if version.fetched_at else None,
        "content_hash": version.content_hash,
        "is_current": version.is_current,
        "text": version.raw_text or "",
    }


@app.get("/debug/policy-discovery")
async def debug_policy_discovery_for_domain(domain: str = Query(..., min_length=1)):
    """
    Return the policy discovery trace: known URL status, Brave raw results,
    Claude-reranked candidates, heuristic fallback, and combined candidate order.
    """
    return await debug_policy_discovery(domain)


# ─────────────────────────────────────────────────────────────────────────────
# AI endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/ai/status")
async def ai_status():
    """Check if AI features are available."""
    return {"available": ai_available(), "model": "claude-haiku-4-5"}


@app.post("/ai/analyze")
async def ai_analyze_policy(req: AIAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """Run AI-powered deep analysis on a previously analyzed domain."""
    cached = await get_latest_analysis(db, req.domain)
    if not cached or not cached.result_json:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for '{req.domain}'. Analyze the website first via /analyze."
        )

    result_json = cached.result_json

    # Try to get policy text from policy version
    policy_text = ""
    if cached.policy_version_id:
        try:
            policy_text = await get_policy_text(db, cached.policy_version_id) or ""
        except Exception:
            pass

    ai_result = await analyze_policy_ai(req.domain, policy_text, result_json)
    return dataclasses.asdict(ai_result)


@app.post("/ai/research-ecosystem")
async def ai_research_ecosystem(req: EcosystemRequest, db: AsyncSession = Depends(get_db)):
    """Research all third parties and trackers for a domain using AI."""
    cached = await get_latest_analysis(db, req.domain)
    if not cached or not cached.result_json:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for '{req.domain}'. Analyze the website first."
        )

    result_json = cached.result_json
    third_parties = result_json.get("third_parties", {}).get("parties", [])
    trackers = result_json.get("trackers", {}).get("trackers", [])

    try:
        ecosystem = await research_ecosystem(
            req.domain,
            third_parties,
            trackers,
            max_parties=req.max_parties,
        )
        return dataclasses.asdict(ecosystem)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ecosystem research failed: {str(e)}")


@app.post("/ai/chat")
async def ai_chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Stream a privacy assistant chat response using SSE."""
    cached = await get_latest_analysis(db, req.domain)
    result_json = cached.result_json if (cached and cached.result_json) else {}
    policy_text = ""
    if cached and cached.policy_version_id:
        try:
            policy_text = await get_policy_text(db, cached.policy_version_id) or ""
        except Exception:
            policy_text = ""

    conversation = [{"role": m.role, "content": m.content} for m in req.messages]

    async def generate():
        try:
            async for chunk in stream_chat_response(req.domain, result_json, conversation, policy_text):
                # Escape newlines in SSE data
                safe_chunk = chunk.replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"
        except Exception as e:
            yield f"data: [ERROR: {str(e)[:100]}]\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Result builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_result(url, domain, crawl, analysis, tracker_result, score, dynamic_result=None, mismatch_result=None) -> dict:
    tr = _dc(tracker_result) if tracker_result else {}
    runtime_observations = _build_runtime_observations(dynamic_result)
    return {
        "url": url,
        "domain": domain,
        "policy_found": crawl.policy_found,
        "policy_url": crawl.policy_url,
        "policy_word_count": crawl.word_count,
        "policy_discovery_method": crawl.discovery_method,
        "overall_score": score.overall,
        "grade": score.grade,
        "risk_level": score.risk_level,
        "summary": score.summary,
        "score_breakdown": {
            "data_collection": score.data_collection_score,
            "sharing": score.sharing_score,
            "transparency": score.transparency_score,
            "rights": score.rights_score,
            "retention": score.retention_score,
            "dark_patterns": score.dark_patterns_score,
            "technical": score.technical_score,
            "mismatch": score.mismatch_score,
            "weights": score.weights,
            "baselines": score.baselines,
            "clamped": score.clamped,
        },
        "penalties": score.penalties,
        "bonuses": score.bonuses,
        "data_types": analysis.get("data_types", []),
        "retention": analysis.get("retention", {}),
        "sentiment": analysis.get("sentiment", {}),
        "dark_patterns": analysis.get("dark_patterns", {}),
        "rights": analysis.get("rights", {}),
        "third_parties": analysis.get("third_parties", {}),
        "ai_extraction": analysis.get("ai_extraction"),
        "trackers": tr,
        "tracker_detection_source": "static_html",
        "static_detection": tr,
        "dynamic_crawling": dynamic_result,
        "runtime_observations": runtime_observations,
        "mismatch_analysis": mismatch_result,
    }


def _extract_cookie_names(cookies: Any) -> List[str]:
    names: List[str] = []
    if isinstance(cookies, list):
        for item in cookies:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
    return sorted(set(names))


def _extract_known_tracker_names(state: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    raw = state.get("known_tracker_names")
    if isinstance(raw, list):
        names.extend([name for name in raw if isinstance(name, str) and name])

    detected = state.get("trackers_detected")
    if isinstance(detected, list):
        for item in detected:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    names.append(name)

    return sorted(set(names))


def _normalize_runtime_state(label: str, state: Dict[str, Any]) -> Dict[str, Any]:
    third_party_domains = state.get("third_party_domains")
    if not isinstance(third_party_domains, list):
        top_domains = state.get("top_third_party_domains_by_req")
        if isinstance(top_domains, list):
            third_party_domains = [item[0] for item in top_domains if isinstance(item, (list, tuple)) and item and isinstance(item[0], str)]
        else:
            third_party_domains = []

    known_tracker_count = state.get("known_tracker_count")
    if not isinstance(known_tracker_count, int):
        known_tracker_count = None

    known_tracker_domains = state.get("known_tracker_domains")
    if not isinstance(known_tracker_domains, list):
        known_tracker_domains = []

    known_trackers = state.get("known_trackers")
    if not isinstance(known_trackers, list):
        known_trackers = []

    known_tracker_matching_available = state.get("known_tracker_matching_available")
    if not isinstance(known_tracker_matching_available, bool):
        known_tracker_matching_available = isinstance(known_tracker_count, int)

    action_value = state.get("action")
    if not isinstance(action_value, str):
        action_value = state.get("action_taken") if isinstance(state.get("action_taken"), str) else None

    return {
        "label": label,
        "action": action_value,
        "ok": state.get("ok") if isinstance(state.get("ok"), bool) else None,
        "banner_detected": state.get("banner_detected") if isinstance(state.get("banner_detected"), bool) else None,
        "total_requests": state.get("request_count_total", state.get("total_requests", 0)),
        "third_party_request_count": state.get("third_party_request_count", 0),
        "third_party_domains": third_party_domains,
        "total_cookies": state.get("cookies_total", state.get("total_cookies", 0)),
        "cookie_names": state.get("cookie_names") if isinstance(state.get("cookie_names"), list) else _extract_cookie_names(state.get("cookies") or []),
        "known_tracker_count": known_tracker_count,
        "known_tracker_names": _extract_known_tracker_names(state),
        "known_tracker_domains": known_tracker_domains,
        "known_trackers": known_trackers,
        "known_tracker_matching_available": known_tracker_matching_available,
        "click_verification": state.get("click_verification"),
    }


def _build_runtime_observations(dynamic_result: Optional[dict]) -> Dict[str, Any]:
    if not dynamic_result:
        return {
            "available": False,
            "source": "stateful_dynamic_crawl",
            "known_tracker_matching_available": False,
            "states": {},
        }

    stateful = dynamic_result.get("_stateful") if isinstance(dynamic_result, dict) else None
    source_states = (stateful or {}).get("states") if isinstance(stateful, dict) else None
    source_states = source_states if isinstance(source_states, dict) else {}

    if not source_states:
        source_states = {
            "S0": dynamic_result.get("S0") or {},
            "S1": dynamic_result.get("S1") or {},
            "S2": dynamic_result.get("S2") or {},
        }

    states = {
        "S0": _normalize_runtime_state("Pre-Consent", source_states.get("S0") or {}),
        "S1": _normalize_runtime_state("Reject", source_states.get("S1") or {}),
        "S2": _normalize_runtime_state("Accept", source_states.get("S2") or {}),
    }

    known_tracker_matching_available = any(
        bool(state.get("known_tracker_matching_available"))
        for state in states.values()
    )

    quality = dynamic_result.get("state_quality") if isinstance(dynamic_result, dict) else None
    requires_human = bool(dynamic_result.get("requires_human")) if isinstance(dynamic_result, dict) else False
    human_reasons = list(dynamic_result.get("human_reasons") or []) if isinstance(dynamic_result, dict) else []

    return {
        "available": True,
        "source": "stateful_dynamic_crawl",
        "quality": quality,
        "requires_human": requires_human,
        "human_reasons": human_reasons,
        "known_tracker_matching_available": known_tracker_matching_available,
        "states": states,
        "derived": (stateful or {}).get("derived") if isinstance(stateful, dict) else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Empty fallbacks
# ─────────────────────────────────────────────────────────────────────────────

def _empty_third_parties():
    from analyzer.third_party_analyzer import ThirdPartyAnalysis
    return ThirdPartyAnalysis(count=0, named_count=0, unnamed_count=0, parties=[],
                               sharing_purposes={}, data_sold=False, cross_border_transfers=False,
                               transfer_safeguards=[], advertising_partners=0, analytics_partners=0,
                               risk_level="unknown", sharing_score=0)

def _empty_retention():
    from analyzer.retention_parser import RetentionAnalysis
    return RetentionAnalysis(items=[], overall_rating="unknown", has_vague_retention=False,
                              has_indefinite_retention=False, has_event_based_deletion=False,
                              has_specific_periods=False, has_deletion_policy=False,
                              deletion_on_request=False, shortest_days=None, longest_days=None,
                              storage_limitation_mentioned=False)

def _empty_rights():
    from analyzer.rights_checker import RightsAnalysis
    return RightsAnalysis(gdpr={}, gdpr_score=0, gdpr_grade="F", ccpa={}, ccpa_score=0,
                           ccpa_grade="F", frameworks_mentioned=[], cookie_compliance={},
                           dnt_mentioned=False, dnt_honored=False, global_privacy_control=False,
                           overall_rights_score=0)

def _empty_sentiment():
    from analyzer.sentiment_analyzer import SentimentResult
    return SentimentResult(vagueness_score=100, specificity_score=0, passive_voice_ratio=1.0,
                            active_voice_count=0, passive_voice_count=0, named_third_parties=[],
                            named_third_party_count=0, vague_term_examples=[], hedging_examples=[],
                            specific_purpose_count=0, accountability={}, accountability_score=0,
                            overall_transparency="very_low", transparency_score=0,
                            avg_sentence_length=0, readability_rating="unknown", flesch_kincaid_words=0)

def _empty_dark_patterns():
    from analyzer.dark_pattern_detector import DarkPatternAnalysis
    return DarkPatternAnalysis(detected=[], count=0, high_severity_count=0,
                                medium_severity_count=0, low_severity_count=0,
                                overall_risk="none", consent_mechanism_quality="unclear")


def _score_js_rendered_policy(tracker_result, dynamic_result=None) -> "ScoreBreakdown":
    """
    Score a site whose privacy policy was found but text couldn't be extracted
    (JavaScript-rendered SPA).

    - Policy EXISTS → don't penalise as "no policy" (which gives 5/100)
    - Text UNAVAILABLE → policy dimensions get neutral "unknown" scores
    - Trackers still analysed from homepage HTML → technical score is real
    """
    from scoring.privacy_scorer import ScoreBreakdown

    # ── Technical score from real tracker data ────────────────────────────
    tech_score = 50  # neutral default
    penalties = []
    bonuses = [{"dimension": "general", "reason": "Privacy policy page exists and is accessible", "bonus": 10}]

    total_trackers = 0
    if tracker_result:
        tr = tracker_result if isinstance(tracker_result, dict) else (
            {k: getattr(tracker_result, k, None) for k in vars(tracker_result)} if hasattr(tracker_result, '__dict__') else {}
        )
        total_trackers = tr.get("total_trackers", 0) if isinstance(tr, dict) else getattr(tracker_result, "total_trackers", 0)
        
    if total_trackers == 0:
        tech_score = 90
        bonuses.append({"dimension": "technical", "reason": "No trackers detected", "bonus": 10})
    elif total_trackers <= 3:
        tech_score = 70
    elif total_trackers <= 8:
        tech_score = 45
        penalties.append({"dimension": "technical", "reason": f"{total_trackers} trackers detected", "penalty": 15})
    else:
        tech_score = 20
        penalties.append({"dimension": "technical", "reason": f"{total_trackers} trackers detected", "penalty": 30})

    if dynamic_result:
        s0 = dynamic_result.get("S0", {})
        s1 = dynamic_result.get("S1", {})
        s0_trackers = s0.get("total_trackers", 0)
        s1_trackers = s1.get("total_trackers", 0)
        mismatch = dynamic_result.get("mismatch_detected", False)

        if mismatch:
            tech_score -= 25
            penalties.append({"dimension": "technical", "reason": f"Consent mismatch: Tracking behavior unchanged or worsened after explicitly rejecting consent (S0: {s0_trackers}, S1: {s1_trackers})", "penalty": 25})
        elif s0_trackers > 0 and s1_trackers < s0_trackers:
            bonuses.append({"dimension": "technical", "reason": f"Trackers successfully reduced after rejecting consent (S0: {s0_trackers} -> S1: {s1_trackers})", "bonus": 10})

    tech_score = max(0, tech_score)

    penalties.append({
        "dimension": "transparency",
        "reason": "Policy page is JavaScript-rendered — full text analysis unavailable",
        "penalty": 20,
    })

    # Neutral scores for text-dependent dimensions
    data_score = 50        # can't tell what data is collected
    sharing_score = 50     # can't tell what's shared
    transparency_score = 25  # low: we literally can't read the policy
    rights_score = 50      # can't verify rights coverage
    retention_score = 50   # can't verify retention periods
    dark_patterns_score = 70  # no dark patterns detectable (benefit of the doubt)
    mismatch_score = 50    # can't assess mismatch without policy text

    weights = {
        "data_collection": 0.18,
        "sharing": 0.18,
        "transparency": 0.13,
        "rights": 0.13,
        "retention": 0.10,
        "dark_patterns": 0.08,
        "technical": 0.08,
        "mismatch": 0.12,
    }
    overall = int(
        data_score * weights["data_collection"]
        + sharing_score * weights["sharing"]
        + transparency_score * weights["transparency"]
        + rights_score * weights["rights"]
        + retention_score * weights["retention"]
        + dark_patterns_score * weights["dark_patterns"]
        + tech_score * weights["technical"]
        + mismatch_score * weights["mismatch"]
    )

    from scoring.privacy_scorer import _grade, _risk_level

    return ScoreBreakdown(
        overall=overall,
        grade=_grade(overall),
        risk_level=_risk_level(overall),
        summary=(
            "Privacy policy page found but rendered via JavaScript — "
            "full text analysis was not possible. Tracker and cookie "
            "analysis is available. Score reflects partial data."
        ),
        data_collection_score=data_score,
        sharing_score=sharing_score,
        transparency_score=transparency_score,
        rights_score=rights_score,
        retention_score=retention_score,
        dark_patterns_score=dark_patterns_score,
        technical_score=tech_score,
        mismatch_score=mismatch_score,
        weights=weights,
        penalties=penalties,
        bonuses=bonuses,
    )
