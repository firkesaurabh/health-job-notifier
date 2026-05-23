# ── notifier.py ───────────────────────────────────────────────────────────────
# Telegram Bot notifications for matched jobs.
# Env vars required: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

import logging
import os
import textwrap

import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN",   "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

_CATEGORY_EMOJI = {
    "tpa":        "🏥",
    "insurer":    "🛡️",
    "broker":     "💼",
    "healthtech": "🚀",
    "":           "💊",
}


# ── low-level send ────────────────────────────────────────────────────────────
def _send(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping send")
        print("[DRY-RUN]", text[:200])
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":                  TELEGRAM_CHAT_ID,
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Telegram send error: %s", exc)
        return False


# ── message formatting ────────────────────────────────────────────────────────
def _format_job(job: dict, reasons: dict) -> str:
    cat     = reasons.get("company_category", "")
    emoji   = _CATEGORY_EMOJI.get(cat, "💊")
    cat_lbl = cat.upper() if cat else "HEALTH DOMAIN"

    skills_raw = reasons.get("matched_skills", [])
    skills_txt = "  ".join(f"#{s.replace(' ', '_')}" for s in skills_raw[:6])

    # Truncate description to first 150 chars for preview
    desc = job.get("description", "")
    desc_preview = textwrap.shorten(desc, width=150, placeholder="…") if desc else ""

    lines = [
        f"{emoji} <b>New Job — {cat_lbl}</b>",
        "",
        f"📌 <b>{job['title']}</b>",
        f"🏢 {job['company']}",
        f"📍 {job['location']}",
        f"📅 {job['posted'] or 'Recently posted'}  |  🔎 {job['source']}",
    ]
    if desc_preview:
        lines += ["", f"<i>{desc_preview}</i>"]
    if skills_txt:
        lines += ["", f"🔧 {skills_txt}"]
    lines += ["", f"🔗 <a href='{job['url']}'>Open Job</a>"]

    return "\n".join(lines)


# ── public API ────────────────────────────────────────────────────────────────
def notify_jobs(matched: list[tuple[dict, dict]]) -> None:
    """Send one Telegram message per matched job (with optional summary header)."""
    if not matched:
        logger.info("No new matches — nothing to send")
        return

    if len(matched) > 1:
        _send(f"🔔 <b>{len(matched)} new job match{'es' if len(matched)>1 else ''}</b> for your profile!")

    for job, reasons in matched:
        msg = _format_job(job, reasons)
        ok  = _send(msg)
        if ok:
            logger.info("Notified: %s @ %s", job["title"], job["company"])


def notify_error(err: str) -> None:
    _send(f"⚠️ <b>Job Scanner Error</b>\n<code>{err[:300]}</code>")
