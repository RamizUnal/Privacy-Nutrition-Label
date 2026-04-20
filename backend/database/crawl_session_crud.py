"""
CRUD operations for stateful crawl run/session/stage persistence.
Kept separate from privacy analysis CRUD.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CrawlRun, CrawlSession, CrawlStage


async def create_crawl_run(
    db: AsyncSession,
    run_id: str,
    total_sites: int,
    config_json: Optional[Dict[str, Any]] = None,
    environment_json: Optional[Dict[str, Any]] = None,
) -> CrawlRun:
    run = CrawlRun(
        run_id=run_id,
        status="running",
        started_at=datetime.datetime.utcnow(),
        total_sites=total_sites,
        processed_sites=0,
        requires_human_count=0,
        config_json=config_json or {},
        environment_json=environment_json or {},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def finish_crawl_run(
    db: AsyncSession,
    run_id: str,
    status: str,
    processed_sites: int,
    requires_human_count: int,
    error: Optional[str] = None,
) -> Optional[CrawlRun]:
    result = await db.execute(
        select(CrawlRun).where(CrawlRun.run_id == run_id).limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None

    run.status = status
    run.processed_sites = processed_sites
    run.requires_human_count = requires_human_count
    run.finished_at = datetime.datetime.utcnow()
    run.error = error

    await db.commit()
    await db.refresh(run)
    return run


async def get_crawl_run(db: AsyncSession, run_id: str) -> Optional[CrawlRun]:
    result = await db.execute(
        select(CrawlRun)
        .where(CrawlRun.run_id == run_id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_or_get_crawl_session(
    db: AsyncSession,
    crawl_run_id: int,
    site: str,
    domain: Optional[str] = None,
    site_key: Optional[str] = None,
    artifacts_dir: Optional[str] = None,
) -> CrawlSession:
    result = await db.execute(
        select(CrawlSession).where(
            and_(
                CrawlSession.crawl_run_id == crawl_run_id,
                CrawlSession.site == site,
            )
        ).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    session = CrawlSession(
        crawl_run_id=crawl_run_id,
        site=site,
        domain=domain,
        site_key=site_key,
        status="pending",
        requires_human=False,
        human_reasons=[],
        retry_count=0,
        artifacts_dir=artifacts_dir,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def update_crawl_session_state(
    db: AsyncSession,
    crawl_session_id: int,
    status: Optional[str] = None,
    requires_human: Optional[bool] = None,
    human_reasons: Optional[List[str]] = None,
    retry_count: Optional[int] = None,
    first_attempt_at: Optional[datetime.datetime] = None,
    last_attempt_at: Optional[datetime.datetime] = None,
    completed_at: Optional[datetime.datetime] = None,
    storage_state_path: Optional[str] = None,
    context_path: Optional[str] = None,
) -> Optional[CrawlSession]:
    result = await db.execute(
        select(CrawlSession).where(CrawlSession.id == crawl_session_id).limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    if status is not None:
        session.status = status
    if requires_human is not None:
        session.requires_human = requires_human
    if human_reasons is not None:
        session.human_reasons = human_reasons
    if retry_count is not None:
        session.retry_count = retry_count
    if first_attempt_at is not None:
        session.first_attempt_at = first_attempt_at
    if last_attempt_at is not None:
        session.last_attempt_at = last_attempt_at
    if completed_at is not None:
        session.completed_at = completed_at
    if storage_state_path is not None:
        session.storage_state_path = storage_state_path
    if context_path is not None:
        session.context_path = context_path

    await db.commit()
    await db.refresh(session)
    return session


async def upsert_crawl_stage(
    db: AsyncSession,
    crawl_session_id: int,
    stage: str,
    status: str,
    started_at: Optional[datetime.datetime] = None,
    finished_at: Optional[datetime.datetime] = None,
    action_raw: Optional[str] = None,
    action_semantic: Optional[str] = None,
    banner_detected: Optional[bool] = None,
    challenge_json: Optional[Dict[str, Any]] = None,
    metrics_json: Optional[Dict[str, Any]] = None,
    screenshot_path: Optional[str] = None,
    error: Optional[str] = None,
) -> CrawlStage:
    result = await db.execute(
        select(CrawlStage).where(
            and_(
                CrawlStage.crawl_session_id == crawl_session_id,
                CrawlStage.stage == stage,
            )
        ).limit(1)
    )
    stage_row = result.scalar_one_or_none()

    if not stage_row:
        stage_row = CrawlStage(
            crawl_session_id=crawl_session_id,
            stage=stage,
            status=status,
        )
        db.add(stage_row)

    stage_row.status = status
    if started_at is not None:
        stage_row.started_at = started_at
    if finished_at is not None:
        stage_row.finished_at = finished_at
    if action_raw is not None:
        stage_row.action_raw = action_raw
    if action_semantic is not None:
        stage_row.action_semantic = action_semantic
    if banner_detected is not None:
        stage_row.banner_detected = banner_detected
    if challenge_json is not None:
        stage_row.challenge_json = challenge_json
    if metrics_json is not None:
        stage_row.metrics_json = metrics_json
    if screenshot_path is not None:
        stage_row.screenshot_path = screenshot_path
    if error is not None:
        stage_row.error = error

    await db.commit()
    await db.refresh(stage_row)
    return stage_row


async def get_sessions_requiring_human(
    db: AsyncSession,
    run_id: Optional[str] = None,
    limit: int = 100,
) -> List[CrawlSession]:
    stmt = (
        select(CrawlSession)
        .join(CrawlRun, CrawlSession.crawl_run_id == CrawlRun.id)
        .where(CrawlSession.requires_human == True)
        .order_by(desc(CrawlSession.last_attempt_at), desc(CrawlSession.id))
        .limit(limit)
    )
    if run_id:
        stmt = stmt.where(CrawlRun.run_id == run_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())
