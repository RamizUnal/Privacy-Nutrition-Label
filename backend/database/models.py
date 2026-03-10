"""
SQLAlchemy models for privacy analysis storage and historical tracking.
"""
from __future__ import annotations
import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, JSON
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
