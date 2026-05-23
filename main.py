#!/usr/bin/env python3
# ── main.py ───────────────────────────────────────────────────────────────────
# Orchestrator: process bot commands → collect → dedup → filter → notify → log

import logging
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import SEARCHES
from filter import is_relevant
from notifier import notify_jobs, notify_error
from scrapers import ALL_SCRAPERS
from store import deduplicate, load_seen, save_seen
from bot import process_commands, log_scan_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(
        open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)
    )],
)
logger = logging.getLogger(__name__)


def collect_all_jobs() -> list[dict]:
    all_jobs: list[dict] = []
    seen_urls: set[str]  = set()
    total_raw = 0

    for scraper in ALL_SCRAPERS:
        for query in SEARCHES:
            try:
                jobs = scraper(query)
                total_raw += len(jobs)
                for job in jobs:
                    url = job.get("url", "")
                    if url and url not in seen_urls:
                        all_jobs.append(job)
                        seen_urls.add(url)
            except Exception as exc:
                logger.error("Scraper %s / '%s' failed: %s", scraper.__name__, query, exc)

    logger.info("Collected %d raw -> %d unique", total_raw, len(all_jobs))
    return all_jobs


def main() -> None:
    logger.info("=== Health Job Scanner starting ===")

    try:
        # 1. Process any pending Telegram commands first
        logger.info("Checking Telegram commands...")
        process_commands()   # /scan here just acks; scan always runs in this job

        # 2. Load dedup store
        seen = load_seen()

        # 3. Scrape all sources
        all_jobs = collect_all_jobs()

        # 4. Dedup against seen
        new_jobs, updated_seen = deduplicate(all_jobs, seen)
        logger.info("New (unseen) jobs: %d", len(new_jobs))

        # 5. Score relevance
        matched: list[tuple[dict, dict]] = []
        for job in new_jobs:
            relevant, reasons = is_relevant(job)
            if relevant:
                matched.append((job, reasons))
                logger.info(
                    "[MATCH] %s @ %s | cat=%s skills=%d: %s",
                    job["title"], job["company"],
                    reasons["company_category"] or "domain",
                    reasons["skill_count"],
                    ", ".join(reasons["matched_skills"][:4]),
                )
            else:
                logger.debug(
                    "[skip]  %s @ %s | title=%s dom=%s skills=%d",
                    job["title"], job["company"],
                    reasons["title_match"], reasons["domain_match"],
                    reasons["skill_count"],
                )

        logger.info("Matches this run: %d", len(matched))

        # 6. Notify Telegram
        notify_jobs(matched)

        # 7. Persist dedup store
        save_seen(updated_seen)

        # 8. Log results for /status command
        log_scan_result(
            jobs_collected=len(all_jobs),
            new_jobs=len(new_jobs),
            matches=matched,
        )

    except Exception as exc:
        logger.exception("Scanner crashed: %s", exc)
        notify_error(str(exc))
        sys.exit(1)

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()
