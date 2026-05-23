# ── store.py ──────────────────────────────────────────────────────────────────
# Persistent deduplication: seen job IDs stored in seen_jobs.json

import hashlib
import json
import logging

from config import SEEN_JOBS_FILE, MAX_SEEN_JOBS

logger = logging.getLogger(__name__)


def _job_id(job: dict) -> str:
    """Stable 16-char hex ID based on job URL (or title+company fallback)."""
    key = job.get("url") or f"{job['title']}|{job['company']}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def load_seen() -> set[str]:
    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            seen = set(data.get("seen", []))
            logger.info("Loaded %d seen IDs from %s", len(seen), SEEN_JOBS_FILE)
            return seen
    except FileNotFoundError:
        logger.info("%s not found — starting fresh", SEEN_JOBS_FILE)
        return set()
    except json.JSONDecodeError as exc:
        logger.warning("Corrupt %s (%s) — starting fresh", SEEN_JOBS_FILE, exc)
        return set()


def save_seen(seen: set[str]) -> None:
    # Keep only the most-recent MAX_SEEN_JOBS entries to prevent unbounded growth
    trimmed = list(seen)[-MAX_SEEN_JOBS:]
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as fh:
        json.dump({"seen": trimmed}, fh)
    logger.info("Saved %d seen IDs to %s", len(trimmed), SEEN_JOBS_FILE)


def deduplicate(jobs: list[dict], seen: set[str]) -> tuple[list[dict], set[str]]:
    """Return only jobs not in seen, and the updated seen set."""
    new_jobs: list[dict] = []
    for job in jobs:
        jid = _job_id(job)
        if jid not in seen:
            new_jobs.append(job)
            seen.add(jid)
    return new_jobs, seen
