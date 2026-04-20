"""
CLI runner for the Privacy Nutrition Label evaluation suite.

Usage:
    # Run evaluation on all test sites
    python -m evaluation.run_evaluation

    # Run only the policy-analysis reference sites (Google + Twitter/X)
    python -m evaluation.run_evaluation --policy-analysis

    # Run on specific categories
    python -m evaluation.run_evaluation --category e-commerce

    # Run on specific regions
    python -m evaluation.run_evaluation --region TR

    # Run on a single URL
    python -m evaluation.run_evaluation --url https://www.example.com

    # Skip dynamic crawling (faster)
    python -m evaluation.run_evaluation --no-dynamic

    # Policy-analysis sites without dynamic crawl
    python -m evaluation.run_evaluation --policy-analysis --no-dynamic

    # Save results to specific file
    python -m evaluation.run_evaluation --output results/my_eval.json

    # Run OPP-115 comparison (requires dataset download)
    python -m evaluation.run_evaluation --opp115
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path

# Ensure backend directory is on path
backend_dir = str(Path(__file__).parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Privacy Nutrition Label — Pipeline Evaluation Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--policy-analysis",
        action="store_true",
        help="Evaluate only the policy-analysis reference sites (Google + Twitter/X with known policy URLs)",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Filter test sites by category (e-commerce, social, news, etc.)",
    )
    parser.add_argument(
        "--region",
        type=str,
        help="Filter test sites by region (TR, US, EU, UK, Global)",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Evaluate a single URL instead of the test suite",
    )
    parser.add_argument(
        "--no-dynamic",
        action="store_true",
        help="Skip dynamic 3-state crawling (faster, less comprehensive)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file path for results",
    )
    parser.add_argument(
        "--opp115",
        action="store_true",
        help="Run OPP-115 dataset evaluation (requires dataset download)",
    )
    parser.add_argument(
        "--opp115-dir",
        type=str,
        default=None,
        help="Path to OPP-115 dataset directory",
    )
    parser.add_argument(
        "--max-sites",
        type=int,
        default=None,
        help="Maximum number of sites to evaluate",
    )
    
    args = parser.parse_args()
    
    if args.opp115:
        _run_opp115_evaluation(args)
    else:
        _run_pipeline_evaluation(args)


def _run_pipeline_evaluation(args):
    """Run the standard pipeline evaluation against test sites."""
    from evaluation.test_sites import ALL_SITES, POLICY_ANALYSIS_SITES, TestSite, get_sites_by_category, get_sites_by_region
    from evaluation.evaluator import evaluate_pipeline, print_evaluation_report, save_evaluation
    
    # Determine which sites to evaluate
    if args.policy_analysis:
        sites = POLICY_ANALYSIS_SITES
        print("Running policy-analysis evaluation on reference sites (known policy URLs)...")
    elif args.url:
        sites = [TestSite(
            url=args.url,
            name=args.url.split("//")[-1].split("/")[0],
            category="custom",
            region="unknown",
            expected_policy=True,
        )]
    elif args.category:
        sites = get_sites_by_category(args.category)
        if not sites:
            print(f"No sites found for category: {args.category}")
            sys.exit(1)
    elif args.region:
        sites = get_sites_by_region(args.region)
        if not sites:
            print(f"No sites found for region: {args.region}")
            sys.exit(1)
    else:
        sites = ALL_SITES
    
    if args.max_sites:
        sites = sites[:args.max_sites]
    
    # Run evaluation
    evaluation = evaluate_pipeline(
        sites=sites,
        skip_dynamic=args.no_dynamic,
    )
    
    # Print report
    report = print_evaluation_report(evaluation)
    
    # Save results
    output_path = save_evaluation(evaluation, args.output)
    
    print(f"\n✓ Evaluation complete. Results saved to: {output_path}")


def _run_opp115_evaluation(args):
    """Run the OPP-115 dataset evaluation."""
    from evaluation.opp115_loader import (
        load_opp115_dataset,
        compare_policy,
        compute_evaluation_metrics,
    )
    from analyzer.policy_analyzer import analyze_policy
    
    data_dir = Path(args.opp115_dir) if args.opp115_dir else None
    
    print("\nLoading OPP-115 dataset...")
    policies = load_opp115_dataset(data_dir)
    
    if not policies:
        print("\n❌ No OPP-115 policies found!")
        print("Please download the dataset from https://usableprivacy.org/data")
        print(f"and extract it to: {Path(__file__).parent / 'data' / 'opp115'}")
        print("\nExpected structure:")
        print("  evaluation/data/opp115/")
        print("    policies/       # Raw policy text files (*.txt)")
        print("    annotations/    # annotations.json")
        print("    metadata.json   # Policy URLs and metadata")
        sys.exit(1)
    
    if args.max_sites:
        policies = policies[:args.max_sites]
    
    print(f"Loaded {len(policies)} policies\n")
    
    comparisons = []
    for i, policy in enumerate(policies, 1):
        print(f"[{i}/{len(policies)}] Analyzing {policy.policy_id} ({policy.website_url})...")
        
        try:
            analysis_tuple = analyze_policy(
                policy.full_text,
                policy_url=policy.website_url,
                domain=policy.website_url.split("//")[-1].split("/")[0],
            )
            analysis_dict = analysis_tuple[0]
            
            comparison = compare_policy(policy, analysis_dict)
            comparisons.append(comparison)
            
            print(f"  ✓ Accuracy: {comparison.accuracy:.1%} ({comparison.categories_correct}/{comparison.categories_total})")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    if not comparisons:
        print("\n❌ No policies were successfully analyzed.")
        sys.exit(1)
    
    # Compute metrics
    metrics = compute_evaluation_metrics(comparisons)
    
    # Print report
    print(f"\n{'='*70}")
    print("OPP-115 EVALUATION RESULTS")
    print(f"{'='*70}")
    print(f"Policies analyzed: {metrics.total_policies}")
    print(f"Mean accuracy:     {metrics.mean_accuracy:.1%}")
    print(f"\nMacro Precision:   {metrics.macro_precision:.4f}")
    print(f"Macro Recall:      {metrics.macro_recall:.4f}")
    print(f"Macro F1:          {metrics.macro_f1:.4f}")
    print(f"\nMicro Precision:   {metrics.micro_precision:.4f}")
    print(f"Micro Recall:      {metrics.micro_recall:.4f}")
    print(f"Micro F1:          {metrics.micro_f1:.4f}")
    print(f"\nConfusion Matrix Totals:")
    print(f"  TP: {metrics.total_tp}  FP: {metrics.total_fp}")
    print(f"  FN: {metrics.total_fn}  TN: {metrics.total_tn}")
    
    print(f"\n{'─'*70}")
    print("PER-CATEGORY RESULTS")
    print(f"{'─'*70}")
    print(f"  {'Category':<40} {'Prec':>6} {'Rec':>6} {'F1':>6}")
    print(f"  {'─'*40} {'─'*6} {'─'*6} {'─'*6}")
    for cat in metrics.category_f1:
        print(f"  {cat:<40} {metrics.category_precision[cat]:>6.2f} {metrics.category_recall[cat]:>6.2f} {metrics.category_f1[cat]:>6.2f}")
    
    # Save results
    from dataclasses import asdict
    output = args.output or str(
        Path(__file__).parent / "results" / f"opp115_eval_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, "w") as f:
        json.dump(asdict(metrics), f, indent=2, default=str)
    
    print(f"\n✓ Results saved to: {output}")


if __name__ == "__main__":
    main()
