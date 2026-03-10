"""
Database CRUD operations for privacy analysis.
"""
from __future__ import annotations
import hashlib
import difflib
import datetime
import json
from typing import List, Optional, Tuple, Dict

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PolicyVersion, AnalysisResult, PolicyChange


# ─────────────────────────────────────────────────────────────────────────────
# Policy Version Management
# ─────────────────────────────────────────────────────────────────────────────

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


async def get_or_create_policy_version(
    db: AsyncSession,
    domain: str,
    policy_url: str,
    raw_text: str,
) -> Tuple[PolicyVersion, bool]:
    """
    Returns (version, is_new) – creates a new version only if content changed.
    Also detects and records changes vs. the previous version.
    """
    content_hash = _hash_text(raw_text)

    # Check if this exact hash exists
    result = await db.execute(
        select(PolicyVersion).where(
            and_(PolicyVersion.domain == domain, PolicyVersion.content_hash == content_hash)
        ).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    # Get previous version for change detection
    prev_result = await db.execute(
        select(PolicyVersion).where(
            and_(PolicyVersion.domain == domain, PolicyVersion.is_current == True)
        ).order_by(desc(PolicyVersion.fetched_at)).limit(1)
    )
    prev_version = prev_result.scalar_one_or_none()

    # Mark old version as no longer current
    if prev_version:
        prev_version.is_current = False
        await db.flush()

    # Create new version
    new_version = PolicyVersion(
        domain=domain,
        policy_url=policy_url,
        content_hash=content_hash,
        raw_text=raw_text,
        word_count=len(raw_text.split()),
        fetched_at=datetime.datetime.utcnow(),
        is_current=True,
    )
    db.add(new_version)
    await db.flush()

    # Record change if there was a previous version
    if prev_version and prev_version.raw_text:
        await _record_policy_change(db, domain, prev_version, new_version)

    await db.commit()
    await db.refresh(new_version)
    return new_version, True


async def _record_policy_change(
    db: AsyncSession,
    domain: str,
    old_version: PolicyVersion,
    new_version: PolicyVersion,
) -> PolicyChange:
    """Compute diff and save change record."""
    old_lines = (old_version.raw_text or "").splitlines()
    new_lines = (new_version.raw_text or "").splitlines()

    differ = difflib.SequenceMatcher(None, old_lines, new_lines)
    ratio = differ.ratio()

    added = 0
    removed = 0
    diff_snippets = []
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == "replace":
            removed += i2 - i1
            added += j2 - j1
            if len(diff_snippets) < 5:
                diff_snippets.append({
                    "type": "changed",
                    "old": " ".join(old_lines[i1:i2])[:200],
                    "new": " ".join(new_lines[j1:j2])[:200],
                })
        elif tag == "delete":
            removed += i2 - i1
            if len(diff_snippets) < 5:
                diff_snippets.append({
                    "type": "removed",
                    "text": " ".join(old_lines[i1:i2])[:200],
                })
        elif tag == "insert":
            added += j2 - j1
            if len(diff_snippets) < 5:
                diff_snippets.append({
                    "type": "added",
                    "text": " ".join(new_lines[j1:j2])[:200],
                })

    summary = f"Policy updated: +{added} lines added, -{removed} lines removed ({ratio:.0%} similar)"

    change = PolicyChange(
        domain=domain,
        old_version_id=old_version.id,
        new_version_id=new_version.id,
        detected_at=datetime.datetime.utcnow(),
        change_summary=summary,
        added_lines=added,
        removed_lines=removed,
        similarity_ratio=round(ratio, 4),
        diff_json=diff_snippets,
        score_delta=0,  # Updated after analysis
    )
    db.add(change)
    return change


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Result Storage
# ─────────────────────────────────────────────────────────────────────────────

async def save_analysis(
    db: AsyncSession,
    domain: str,
    url: str,
    policy_version_id: Optional[int],
    scores: Dict[str, int],
    full_result: dict,
) -> AnalysisResult:
    result = AnalysisResult(
        domain=domain,
        url=url,
        policy_version_id=policy_version_id,
        analyzed_at=datetime.datetime.utcnow(),
        overall_score=scores.get("overall", 0),
        grade=scores.get("grade", "F"),
        risk_level=scores.get("risk_level", "unknown"),
        data_score=scores.get("data", 0),
        sharing_score=scores.get("sharing", 0),
        retention_score=scores.get("retention", 0),
        rights_score=scores.get("rights", 0),
        transparency_score=scores.get("transparency", 0),
        dark_patterns_score=scores.get("dark_patterns", 0),
        cookie_score=scores.get("cookie", 0),
        tracker_score=scores.get("tracker", 0),
        result_json=full_result,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


async def get_latest_analysis(
    db: AsyncSession, domain: str
) -> Optional[AnalysisResult]:
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.domain == domain)
        .order_by(desc(AnalysisResult.analyzed_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_analysis_history(
    db: AsyncSession, domain: str, limit: int = 10
) -> List[AnalysisResult]:
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.domain == domain)
        .order_by(desc(AnalysisResult.analyzed_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_policy_changes(
    db: AsyncSession, domain: str, limit: int = 10
) -> List[PolicyChange]:
    result = await db.execute(
        select(PolicyChange)
        .where(PolicyChange.domain == domain)
        .order_by(desc(PolicyChange.detected_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_policy_text(db: AsyncSession, policy_version_id: int) -> Optional[str]:
    """Retrieve the raw policy text for a policy version ID."""
    result = await db.execute(
        select(PolicyVersion.raw_text).where(PolicyVersion.id == policy_version_id).limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def get_all_analyzed_domains(
    db: AsyncSession, limit: int = 50
) -> List[Dict]:
    result = await db.execute(
        select(AnalysisResult.domain, AnalysisResult.overall_score, AnalysisResult.grade, AnalysisResult.analyzed_at)
        .order_by(desc(AnalysisResult.analyzed_at))
        .limit(limit)
    )
    rows = result.all()
    return [
        {"domain": r.domain, "score": r.overall_score, "grade": r.grade, "analyzed_at": r.analyzed_at.isoformat()}
        for r in rows
    ]
