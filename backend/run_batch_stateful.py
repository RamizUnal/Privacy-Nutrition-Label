from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from crawler import crawl_website
from database import AsyncSessionLocal, init_db
from database.crawl_session_crud import (
    create_crawl_run,
    create_or_get_crawl_session,
    finish_crawl_run,
    update_crawl_session_state,
    upsert_crawl_stage,
)
from stateful_crawler import crawl_site_states


def _read_sites(path: str) -> List[str]:
    output: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                output.append(value)
    return output


def _safe_name(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", url.replace("https://", "").replace("http://", "")).strip("_")


def _append_jsonl(path: str, row: Dict) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _domain_from_site(site: str) -> str | None:
    url = site if site.startswith(("http://", "https://")) else f"https://{site}"
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None


def _s0_semantic_action(raw_action: str | None) -> str:
    return raw_action if isinstance(raw_action, str) and raw_action else "unknown"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Stateful S0/S1/S2 batch crawler with human-in-the-loop queue")
    parser.add_argument("--sites", required=True, help="Input text file with one domain/url per line")
    parser.add_argument("--outdir", required=True, help="Output directory for jsonl files and artifacts")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of sites to process")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between sites to reduce rate limiting")
    parser.add_argument("--headful", action="store_true", help="Run browser in headed mode")
    parser.add_argument("--without-policy", action="store_true", help="Skip policy discovery crawl step")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    artifacts_root = os.path.join(args.outdir, "artifacts")
    os.makedirs(artifacts_root, exist_ok=True)

    results_path = os.path.join(args.outdir, "results.jsonl")
    human_queue_path = os.path.join(args.outdir, "human_queue.jsonl")

    sites = _read_sites(args.sites)
    if args.limit:
        sites = sites[: args.limit]

    total = len(sites)
    human_count = 0
    error_count = 0

    await init_db()

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    run_config = {
        "sites_file": args.sites,
        "outdir": args.outdir,
        "limit": args.limit,
        "delay": args.delay,
        "headful": args.headful,
        "without_policy": args.without_policy,
    }
    environment = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "runner": "run_batch_stateful.py",
    }

    async with AsyncSessionLocal() as db:
        crawl_run = await create_crawl_run(
            db=db,
            run_id=run_id,
            total_sites=total,
            config_json=run_config,
            environment_json=environment,
        )

        try:
            for index, site in enumerate(sites, 1):
                print(f"[{index}/{total}] Crawling {site}")
                site_id = _safe_name(site)
                artifacts_dir = os.path.join(artifacts_root, site_id)
                attempt_at = datetime.utcnow()

                session = await create_or_get_crawl_session(
                    db=db,
                    crawl_run_id=crawl_run.id,
                    site=site,
                    domain=_domain_from_site(site),
                    site_key=site_id,
                    artifacts_dir=artifacts_dir,
                )

                await update_crawl_session_state(
                    db=db,
                    crawl_session_id=session.id,
                    status="running",
                    first_attempt_at=session.first_attempt_at or attempt_at,
                    last_attempt_at=attempt_at,
                )

                try:
                    stateful = await crawl_site_states(
                        site,
                        artifacts_dir=artifacts_dir,
                        headless=(not args.headful),
                    )

                    policy_info = None
                    if not args.without_policy:
                        try:
                            policy = await crawl_website(site)
                            policy_info = {
                                "found": policy.policy_found,
                                "url": policy.policy_url,
                                "word_count": policy.word_count,
                                "discovery_method": policy.discovery_method,
                                "error": policy.error,
                            }
                        except Exception as exc:
                            policy_info = {
                                "found": False,
                                "url": None,
                                "word_count": 0,
                                "discovery_method": None,
                                "error": f"policy_crawl_error: {exc}",
                            }

                    row = {
                        **stateful,
                        "run_id": run_id,
                        "run_ts": datetime.now(timezone.utc).isoformat(),
                        "policy": policy_info,
                    }

                    _append_jsonl(results_path, row)

                    s0 = ((stateful.get("states") or {}).get("S0") or {})
                    s0_screenshot = os.path.join(artifacts_dir, "S0.png")
                    s0_screenshot_path = s0_screenshot if os.path.exists(s0_screenshot) else None

                    s0_metrics = {
                        "request_count_total": s0.get("request_count_total"),
                        "unique_etld1_total": s0.get("unique_etld1_total"),
                        "unique_third_party_etld1": s0.get("unique_third_party_etld1"),
                        "third_party_request_count": s0.get("third_party_request_count"),
                        "cookies_total": s0.get("cookies_total"),
                        "cookies_third_party_est": s0.get("cookies_third_party_est"),
                        "cookie_httpOnly_false_pct": s0.get("cookie_httpOnly_false_pct"),
                        "cookie_secure_false_pct": s0.get("cookie_secure_false_pct"),
                        "cookie_samesite_none_pct": s0.get("cookie_samesite_none_pct"),
                    }

                    await upsert_crawl_stage(
                        db=db,
                        crawl_session_id=session.id,
                        stage="S0",
                        status="completed" if s0 else "failed",
                        started_at=attempt_at,
                        finished_at=datetime.utcnow(),
                        action_raw=s0.get("action"),
                        action_semantic=_s0_semantic_action(s0.get("action")),
                        banner_detected=s0.get("banner_detected"),
                        challenge_json=s0.get("challenge") or {},
                        metrics_json=s0_metrics,
                        screenshot_path=s0_screenshot_path,
                        error=None if s0 else "missing_s0_state",
                    )

                    session_status = "pending_human" if row.get("requires_human") else "s0_persisted"
                    await update_crawl_session_state(
                        db=db,
                        crawl_session_id=session.id,
                        status=session_status,
                        requires_human=bool(row.get("requires_human")),
                        human_reasons=row.get("human_reasons", []),
                        last_attempt_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                    )

                    if row.get("requires_human"):
                        human_count += 1
                        queue_row = {
                            "site": row.get("site"),
                            "run_id": run_id,
                            "run_ts": row.get("run_ts"),
                            "reasons": row.get("human_reasons", []),
                            "artifacts_dir": row.get("artifacts_dir"),
                            "status": "pending",
                            "next_action": "Open screenshots and continue with manual/assisted browser session",
                        }
                        _append_jsonl(human_queue_path, queue_row)

                except Exception as exc:
                    error_count += 1
                    row = {
                        "site": site,
                        "run_id": run_id,
                        "run_ts": datetime.now(timezone.utc).isoformat(),
                        "error": str(exc),
                    }
                    _append_jsonl(results_path, row)

                    await update_crawl_session_state(
                        db=db,
                        crawl_session_id=session.id,
                        status="failed",
                        requires_human=True,
                        human_reasons=["run_error"],
                        last_attempt_at=datetime.utcnow(),
                    )

                    await upsert_crawl_stage(
                        db=db,
                        crawl_session_id=session.id,
                        stage="S0",
                        status="failed",
                        started_at=attempt_at,
                        finished_at=datetime.utcnow(),
                        action_semantic="unknown",
                        challenge_json={},
                        metrics_json={},
                        error=str(exc),
                    )

                await asyncio.sleep(max(args.delay, 0.0))

            await finish_crawl_run(
                db=db,
                run_id=run_id,
                status="completed" if error_count == 0 else "completed_with_errors",
                processed_sites=total,
                requires_human_count=human_count,
            )
        except Exception as exc:
            await finish_crawl_run(
                db=db,
                run_id=run_id,
                status="failed",
                processed_sites=total,
                requires_human_count=human_count,
                error=str(exc),
            )
            raise

    print(f"Done. results={results_path}")
    print(f"Run ID: {run_id}")
    print(f"Human review queued: {human_count}")
    print(f"Errors: {error_count}")
    if human_count > 0:
        print(f"Queue file: {human_queue_path}")


if __name__ == "__main__":
    asyncio.run(main())