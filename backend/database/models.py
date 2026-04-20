"""
SQLAlchemy models for privacy analysis storage and historical tracking.
"""
from __future__ import annotations
import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class PolicyVersion(Base):
    """
    Stores each unique version of a privacy policy for a domain.
    Enables historical tracking and diff comparisons.
    """
    __tablename__ = "policy_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False, index=True)
    policy_url = Column(String(1000))
    content_hash = Column(String(64), nullable=False)   # SHA-256 of raw text
    raw_text = Column(Text)
    word_count = Column(Integer)
    fetched_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_current = Column(Boolean, default=True)

    analyses = relationship("AnalysisResult", back_populates="policy_version", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<PolicyVersion domain={self.domain} hash={self.content_hash[:8]}>"


class AnalysisResult(Base):
    """
    Full privacy label analysis result for a specific policy version.
    """
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False, index=True)
    url = Column(String(1000))
    policy_version_id = Column(Integer, ForeignKey("policy_versions.id"), nullable=True)
    analyzed_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Overall score
    overall_score = Column(Integer)       # 0–100
    grade = Column(String(2))             # A/B/C/D/F
    risk_level = Column(String(20))

    # Sub-scores
    data_score = Column(Integer)
    sharing_score = Column(Integer)
    retention_score = Column(Integer)
    rights_score = Column(Integer)
    transparency_score = Column(Integer)
    dark_patterns_score = Column(Integer)
    cookie_score = Column(Integer)
    tracker_score = Column(Integer)

    # Full JSON result
    result_json = Column(JSON)

    policy_version = relationship("PolicyVersion", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<AnalysisResult domain={self.domain} score={self.overall_score} grade={self.grade}>"


class PolicyChange(Base):
    """
    Records detected changes between two policy versions.
    """
    __tablename__ = "policy_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False, index=True)
    old_version_id = Column(Integer, ForeignKey("policy_versions.id"))
    new_version_id = Column(Integer, ForeignKey("policy_versions.id"))
    detected_at = Column(DateTime, default=datetime.datetime.utcnow)
    change_summary = Column(Text)           # Human-readable summary
    added_lines = Column(Integer, default=0)
    removed_lines = Column(Integer, default=0)
    similarity_ratio = Column(Float)        # 0.0–1.0
    diff_json = Column(JSON)                # Structured diff
    score_delta = Column(Integer)           # Change in privacy score

    old_version = relationship("PolicyVersion", foreign_keys=[old_version_id])
    new_version = relationship("PolicyVersion", foreign_keys=[new_version_id])

    def __repr__(self) -> str:
        return f"<PolicyChange domain={self.domain} +{self.added_lines}/-{self.removed_lines}>"


class CrawlRun(Base):
    """
    Tracks one batch crawl execution configuration and lifecycle.
    Kept separate from policy analysis history.
    """
    __tablename__ = "crawl_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default="created", index=True)

    started_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    finished_at = Column(DateTime)

    total_sites = Column(Integer, default=0)
    processed_sites = Column(Integer, default=0)
    requires_human_count = Column(Integer, default=0)

    config_json = Column(JSON)
    environment_json = Column(JSON)
    error = Column(Text)

    sessions = relationship("CrawlSession", back_populates="crawl_run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CrawlRun run_id={self.run_id} status={self.status}>"


class CrawlSession(Base):
    """
    Tracks crawl progress and metadata for one site within a crawl run.
    """
    __tablename__ = "crawl_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_run_id = Column(Integer, ForeignKey("crawl_runs.id"), nullable=False, index=True)

    site = Column(String(1000), nullable=False)
    domain = Column(String(255), index=True)
    site_key = Column(String(255), index=True)

    status = Column(String(32), nullable=False, default="pending", index=True)
    requires_human = Column(Boolean, default=False, index=True)
    human_reasons = Column(JSON)

    retry_count = Column(Integer, default=0)
    first_attempt_at = Column(DateTime)
    last_attempt_at = Column(DateTime)
    completed_at = Column(DateTime)

    artifacts_dir = Column(String(2000))
    storage_state_path = Column(String(2000))
    context_path = Column(String(2000))

    crawl_run = relationship("CrawlRun", back_populates="sessions")
    stages = relationship("CrawlStage", back_populates="crawl_session", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("crawl_run_id", "site", name="uq_crawl_run_site"),
    )

    def __repr__(self) -> str:
        return f"<CrawlSession run={self.crawl_run_id} site={self.site} status={self.status}>"


class CrawlStage(Base):
    """
    Stores per-state (`S0`, `S1`, `S2`) execution metadata and summarized outputs.
    """
    __tablename__ = "crawl_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_session_id = Column(Integer, ForeignKey("crawl_sessions.id"), nullable=False, index=True)

    stage = Column(String(8), nullable=False, index=True)  # S0, S1, S2
    status = Column(String(32), nullable=False, default="pending", index=True)

    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    action_raw = Column(String(128))
    action_semantic = Column(String(128))
    banner_detected = Column(Boolean)
    challenge_json = Column(JSON)

    metrics_json = Column(JSON)
    screenshot_path = Column(String(2000))
    error = Column(Text)

    crawl_session = relationship("CrawlSession", back_populates="stages")

    __table_args__ = (
        UniqueConstraint("crawl_session_id", "stage", name="uq_crawl_session_stage"),
    )

    def __repr__(self) -> str:
        return f"<CrawlStage session={self.crawl_session_id} stage={self.stage} status={self.status}>"
