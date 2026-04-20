"""
OPP-115 Dataset Loader and Comparator
Loads the Usable Privacy Project's OPP-115 human-annotated dataset and
compares our pipeline's extracted information against the ground truth.

Dataset reference:
  Wilson et al. "The Creation and Analysis of a Website Privacy Policy Corpus"
  ACL 2016. https://usableprivacy.org/data

The OPP-115 corpus has 115 website privacy policies annotated by law students
with 10 high-level data practice categories:
  1. First Party Collection/Use
  2. Third Party Sharing/Collection
  3. User Choice/Control
  4. User Access, Edit, & Deletion
  5. Data Retention
  6. Data Security
  7. Policy Change
  8. Do Not Track
  9. International & Specific Audiences
  10. Other
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Category mapping: OPP-115 categories → our pipeline's data structures
# ─────────────────────────────────────────────────────────────────────────────

OPP115_TO_PIPELINE = {
    "First Party Collection/Use": {
        "pipeline_modules": ["data_categories"],
        "pipeline_fields": ["data_types"],
        "description": "What data the company collects and how it uses it",
    },
    "Third Party Sharing/Collection": {
        "pipeline_modules": ["third_party_analyzer"],
        "pipeline_fields": ["third_parties"],
        "description": "Third parties that collect or receive user data",
    },
    "User Choice/Control": {
        "pipeline_modules": ["rights_checker", "dark_pattern_detector"],
        "pipeline_fields": ["rights.gdpr.withdraw_consent", "rights.gdpr.objection"],
        "description": "Choices the user can make about data collection and use",
    },
    "User Access, Edit, & Deletion": {
        "pipeline_modules": ["rights_checker"],
        "pipeline_fields": ["rights.gdpr.access", "rights.gdpr.rectification", "rights.gdpr.erasure"],
        "description": "Whether the user can access, edit, or delete their data",
    },
    "Data Retention": {
        "pipeline_modules": ["retention_parser"],
        "pipeline_fields": ["retention"],
        "description": "How long data is stored and retention policies",
    },
    "Data Security": {
        "pipeline_modules": ["sentiment_analyzer"],
        "pipeline_fields": ["sentiment.accountability"],
        "description": "Security measures described in the policy",
    },
    "Policy Change": {
        "pipeline_modules": ["sentiment_analyzer"],
        "pipeline_fields": [],
        "description": "How changes to the policy are communicated",
    },
    "Do Not Track": {
        "pipeline_modules": ["rights_checker"],
        "pipeline_fields": ["rights.dnt_mentioned", "rights.dnt_honored"],
        "description": "Whether the site honors DNT signals",
    },
    "International & Specific Audiences": {
        "pipeline_modules": ["rights_checker"],
        "pipeline_fields": ["rights.frameworks_mentioned"],
        "description": "International data transfers and age-specific policies",
    },
    "Other": {
        "pipeline_modules": [],
        "pipeline_fields": [],
        "description": "Miscellaneous privacy-related information",
    },
}


@dataclass
class OPP115Annotation:
    """A single annotation from the OPP-115 dataset."""
    policy_id: str          # unique policy identifier
    segment_text: str       # the annotated policy text segment
    category: str           # one of the 10 OPP-115 categories
    attributes: Dict[str, str]  # annotation attributes (varies by category)


@dataclass
class OPP115Policy:
    """A complete policy from the OPP-115 dataset."""
    policy_id: str
    website_url: str
    full_text: str
    annotations: List[OPP115Annotation]
    categories_present: Set[str]


@dataclass
class CategoryComparison:
    """Comparison result for a single OPP-115 category."""
    category: str
    ground_truth_present: bool    # annotator says this category is in the policy
    pipeline_detected: bool       # our pipeline detected this category
    true_positive: bool           # both agree it's present
    true_negative: bool           # both agree it's absent
    false_positive: bool          # pipeline says present, annotator says absent
    false_negative: bool          # pipeline says absent, annotator says present
    ground_truth_segments: int    # number of annotated segments for this category
    pipeline_evidence_count: int  # number of evidence items our pipeline found


@dataclass
class PolicyComparison:
    """Full comparison for one policy."""
    policy_id: str
    website_url: str
    category_results: Dict[str, CategoryComparison]
    categories_correct: int
    categories_total: int
    accuracy: float


@dataclass
class EvaluationMetrics:
    """Aggregate evaluation metrics across all policies."""
    total_policies: int
    
    # Per-category metrics
    category_precision: Dict[str, float]
    category_recall: Dict[str, float]
    category_f1: Dict[str, float]
    
    # Aggregate metrics
    macro_precision: float
    macro_recall: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    
    # Per-policy results
    per_policy_accuracy: List[Tuple[str, float]]
    mean_accuracy: float
    
    # Confusion matrix totals
    total_tp: int
    total_fp: int
    total_fn: int
    total_tn: int


# ─────────────────────────────────────────────────────────────────────────────
# Dataset loading
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data" / "opp115"


def load_opp115_dataset(data_dir: Optional[Path] = None) -> List[OPP115Policy]:
    """
    Load the OPP-115 dataset from local files.
    
    Expected directory structure:
        data/opp115/
            policies/          # Raw policy text files
                policy_001.txt
                ...
            annotations/       # Annotation CSV/JSON files
                annotations.json
            metadata.json      # Policy metadata (URLs, etc.)
    
    Returns list of OPP115Policy objects.
    """
    base = data_dir or DATA_DIR
    policies_dir = base / "policies"
    annotations_file = base / "annotations" / "annotations.json"
    metadata_file = base / "metadata.json"
    
    if not base.exists():
        print(f"OPP-115 dataset not found at {base}")
        print("Please download from https://usableprivacy.org/data")
        print(f"and extract to {base}")
        return []
    
    # Load metadata
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
    
    # Load annotations
    all_annotations: Dict[str, List[OPP115Annotation]] = {}
    if annotations_file.exists():
        with open(annotations_file, "r") as f:
            raw = json.load(f)
            for ann in raw:
                pid = ann.get("policy_id", "")
                annotation = OPP115Annotation(
                    policy_id=pid,
                    segment_text=ann.get("segment_text", ""),
                    category=ann.get("category", "Other"),
                    attributes=ann.get("attributes", {}),
                )
                all_annotations.setdefault(pid, []).append(annotation)
    
    # Load policies
    policies: List[OPP115Policy] = []
    if policies_dir.exists():
        for policy_file in sorted(policies_dir.glob("*.txt")):
            pid = policy_file.stem
            text = policy_file.read_text(encoding="utf-8", errors="replace")
            anns = all_annotations.get(pid, [])
            cats = {a.category for a in anns}
            url = metadata.get(pid, {}).get("url", f"https://unknown.example.com/{pid}")
            
            policies.append(OPP115Policy(
                policy_id=pid,
                website_url=url,
                full_text=text,
                annotations=anns,
                categories_present=cats,
            ))
    
    return policies


# ─────────────────────────────────────────────────────────────────────────────
# Comparison logic
# ─────────────────────────────────────────────────────────────────────────────

def _pipeline_detects_category(category: str, analysis: dict) -> Tuple[bool, int]:
    """
    Check if our pipeline detected a given OPP-115 category.
    Returns (detected: bool, evidence_count: int).
    """
    mapping = OPP115_TO_PIPELINE.get(category, {})
    
    if category == "First Party Collection/Use":
        data_types = analysis.get("data_types", [])
        if data_types:
            return True, len(data_types)
        return False, 0
    
    elif category == "Third Party Sharing/Collection":
        tp = analysis.get("third_parties", {})
        count = tp.get("count", 0) if isinstance(tp, dict) else 0
        return count > 0, count
    
    elif category == "User Choice/Control":
        rights = analysis.get("rights", {})
        gdpr = rights.get("gdpr", {})
        withdraw = gdpr.get("withdraw_consent", {})
        objection = gdpr.get("objection", {})
        covered = (
            (withdraw.get("covered", False) if isinstance(withdraw, dict) else False) or
            (objection.get("covered", False) if isinstance(objection, dict) else False)
        )
        return covered, 1 if covered else 0
    
    elif category == "User Access, Edit, & Deletion":
        rights = analysis.get("rights", {})
        gdpr = rights.get("gdpr", {})
        access = gdpr.get("access", {})
        rectification = gdpr.get("rectification", {})
        erasure = gdpr.get("erasure", {})
        count = sum([
            access.get("covered", False) if isinstance(access, dict) else False,
            rectification.get("covered", False) if isinstance(rectification, dict) else False,
            erasure.get("covered", False) if isinstance(erasure, dict) else False,
        ])
        return count > 0, count
    
    elif category == "Data Retention":
        retention = analysis.get("retention", {})
        if isinstance(retention, dict):
            has_specific = retention.get("has_specific_periods", False)
            has_event = retention.get("has_event_based_deletion", False)
            has_vague = retention.get("has_vague_retention", False)
            items = retention.get("items", [])
            detected = has_specific or has_event or has_vague or len(items) > 0
            return detected, len(items)
        return False, 0
    
    elif category == "Data Security":
        sentiment = analysis.get("sentiment", {})
        accountability = sentiment.get("accountability", {})
        if isinstance(accountability, dict):
            security_mentioned = any(
                v for k, v in accountability.items()
                if "security" in k.lower() or "encrypt" in k.lower()
            )
            return security_mentioned, 1 if security_mentioned else 0
        return False, 0
    
    elif category == "Policy Change":
        # Check if policy mentions update notifications
        sentiment = analysis.get("sentiment", {})
        accountability = sentiment.get("accountability", {})
        if isinstance(accountability, dict):
            has_change = accountability.get("change_notification", False)
            return has_change, 1 if has_change else 0
        return False, 0
    
    elif category == "Do Not Track":
        rights = analysis.get("rights", {})
        dnt = rights.get("dnt_mentioned", False)
        return dnt, 1 if dnt else 0
    
    elif category == "International & Specific Audiences":
        rights = analysis.get("rights", {})
        frameworks = rights.get("frameworks_mentioned", [])
        has_intl = len(frameworks) > 0
        return has_intl, len(frameworks)
    
    else:  # "Other"
        return False, 0


def compare_policy(
    ground_truth: OPP115Policy,
    pipeline_analysis: dict,
) -> PolicyComparison:
    """
    Compare our pipeline's analysis against ground truth annotations.
    """
    all_categories = list(OPP115_TO_PIPELINE.keys())
    results: Dict[str, CategoryComparison] = {}
    correct = 0
    
    for cat in all_categories:
        gt_present = cat in ground_truth.categories_present
        gt_segments = sum(1 for a in ground_truth.annotations if a.category == cat)
        
        pipe_detected, evidence_count = _pipeline_detects_category(cat, pipeline_analysis)
        
        tp = gt_present and pipe_detected
        tn = not gt_present and not pipe_detected
        fp = not gt_present and pipe_detected
        fn = gt_present and not pipe_detected
        
        results[cat] = CategoryComparison(
            category=cat,
            ground_truth_present=gt_present,
            pipeline_detected=pipe_detected,
            true_positive=tp,
            true_negative=tn,
            false_positive=fp,
            false_negative=fn,
            ground_truth_segments=gt_segments,
            pipeline_evidence_count=evidence_count,
        )
        
        if tp or tn:
            correct += 1
    
    accuracy = correct / len(all_categories) if all_categories else 0.0
    
    return PolicyComparison(
        policy_id=ground_truth.policy_id,
        website_url=ground_truth.website_url,
        category_results=results,
        categories_correct=correct,
        categories_total=len(all_categories),
        accuracy=accuracy,
    )


def compute_evaluation_metrics(
    comparisons: List[PolicyComparison],
) -> EvaluationMetrics:
    """
    Compute aggregate precision, recall, F1 across all policies.
    """
    all_categories = list(OPP115_TO_PIPELINE.keys())
    
    # Per-category counts
    cat_tp: Dict[str, int] = {c: 0 for c in all_categories}
    cat_fp: Dict[str, int] = {c: 0 for c in all_categories}
    cat_fn: Dict[str, int] = {c: 0 for c in all_categories}
    cat_tn: Dict[str, int] = {c: 0 for c in all_categories}
    
    per_policy: List[Tuple[str, float]] = []
    
    for comp in comparisons:
        per_policy.append((comp.policy_id, comp.accuracy))
        for cat, res in comp.category_results.items():
            if res.true_positive:
                cat_tp[cat] += 1
            if res.false_positive:
                cat_fp[cat] += 1
            if res.false_negative:
                cat_fn[cat] += 1
            if res.true_negative:
                cat_tn[cat] += 1
    
    # Per-category precision/recall/F1
    cat_precision: Dict[str, float] = {}
    cat_recall: Dict[str, float] = {}
    cat_f1: Dict[str, float] = {}
    
    for cat in all_categories:
        tp, fp, fn = cat_tp[cat], cat_fp[cat], cat_fn[cat]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        cat_precision[cat] = round(prec, 4)
        cat_recall[cat] = round(rec, 4)
        cat_f1[cat] = round(f1, 4)
    
    # Macro averages (average of per-category scores)
    macro_prec = sum(cat_precision.values()) / len(all_categories) if all_categories else 0.0
    macro_rec = sum(cat_recall.values()) / len(all_categories) if all_categories else 0.0
    macro_f1 = sum(cat_f1.values()) / len(all_categories) if all_categories else 0.0
    
    # Micro averages (pooled TP/FP/FN)
    total_tp = sum(cat_tp.values())
    total_fp = sum(cat_fp.values())
    total_fn = sum(cat_fn.values())
    total_tn = sum(cat_tn.values())
    
    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = 2 * micro_prec * micro_rec / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0.0
    
    mean_acc = sum(a for _, a in per_policy) / len(per_policy) if per_policy else 0.0
    
    return EvaluationMetrics(
        total_policies=len(comparisons),
        category_precision=cat_precision,
        category_recall=cat_recall,
        category_f1=cat_f1,
        macro_precision=round(macro_prec, 4),
        macro_recall=round(macro_rec, 4),
        macro_f1=round(macro_f1, 4),
        micro_precision=round(micro_prec, 4),
        micro_recall=round(micro_rec, 4),
        micro_f1=round(micro_f1, 4),
        per_policy_accuracy=per_policy,
        mean_accuracy=round(mean_acc, 4),
        total_tp=total_tp,
        total_fp=total_fp,
        total_fn=total_fn,
        total_tn=total_tn,
    )
