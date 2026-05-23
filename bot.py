# ── bot.py ────────────────────────────────────────────────────────────────────
# Telegram bot command handler.
# Reads pending messages via getUpdates, responds to slash commands.
# Returns True if /scan was requested (caller should then run main.py).

import json
import logging
import os
import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN",   "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

OFFSET_FILE   = "bot_offset.json"
SCAN_LOG_FILE = "scan_log.json"

BOT_USERNAME  = "lazySuzyy_bot"   # used to strip @mention from commands


# ── Telegram helpers ──────────────────────────────────────────────────────────
def _tg(method: str, **params):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}",
            params=params, timeout=15
        )
        return r.json()
    except Exception as exc:
        logger.error("TG %s error: %s", method, exc)
        return {}


def send(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[BOT DRY-RUN]", text[:120])
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id":                  TELEGRAM_CHAT_ID,
                "text":                     text,
                "parse_mode":               "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except Exception as exc:
        logger.error("send error: %s", exc)


# ── persistence helpers ───────────────────────────────────────────────────────
def _load(path: str, default: dict) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save(path: str, data: dict):
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_offset() -> int:
    return _load(OFFSET_FILE, {"offset": 0}).get("offset", 0)


def save_offset(offset: int):
    _save(OFFSET_FILE, {"offset": offset})


def load_log() -> dict:
    return _load(SCAN_LOG_FILE, {
        "total_runs":    0,
        "total_matches": 0,
        "last_run":      None,
        "jobs_collected": 0,
        "new_jobs":       0,
        "matches":        0,
        "last_matches":  [],
    })


def save_log(log: dict):
    _save(SCAN_LOG_FILE, log)


# ── command handlers ──────────────────────────────────────────────────────────
def _cmd_help():
    send(
        "🤖 <b>Health Job Bot — Commands</b>\n\n"
        "/scan    — Run a scan right now\n"
        "/status  — Last run stats + next auto-scan time\n"
        "/stats   — All-time totals\n"
        "/help    — This message\n\n"
        "Auto-scans every hour. Alerts fire only for new matching jobs."
    )


def _cmd_status():
    log = load_log()

    if not log.get("last_run"):
        send("No scan data yet. Send /scan to run one now.")
        return

    # Time until next :00 run
    now       = datetime.datetime.utcnow()
    next_run  = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    mins_left = int((next_run - now).total_seconds() / 60)

    matches_block = ""
    for m in log.get("last_matches", [])[:3]:
        matches_block += f"\n  • {m.get('title','')} @ {m.get('company','')}"

    send(
        f"📊 <b>Scanner Status</b>\n\n"
        f"🕐 Last run:       {log['last_run']} UTC\n"
        f"📋 Jobs found:     {log.get('jobs_collected', 0)}\n"
        f"🆕 New (unseen):   {log.get('new_jobs', 0)}\n"
        f"✅ Matches:        {log.get('matches', 0)}\n"
        f"📈 All-time total: {log.get('total_matches', 0)} matches "
        f"over {log.get('total_runs', 0)} runs\n"
        + (f"\n<b>Last matches:</b>{matches_block}\n" if matches_block else "")
        + f"\n⏰ Next auto-scan in ~{mins_left} min"
    )


def _cmd_stats():
    log = load_log()
    send(
        f"📈 <b>All-time Stats</b>\n\n"
        f"Total scans run:  {log.get('total_runs', 0)}\n"
        f"Total matches:    {log.get('total_matches', 0)}\n"
        f"Last scan:        {log.get('last_run', 'never')} UTC"
    )


def _cmd_scan_ack():
    send("🔍 Scanning now... results in ~2 min. You'll get alerts if matches found.")


# ── main entry point ──────────────────────────────────────────────────────────
def process_commands() -> bool:
    """
    Poll getUpdates and handle all pending commands.
    Returns True if the caller should run a scan (user sent /scan).
    """
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN not set — skipping command check")
        return False

    offset        = load_offset()
    scan_requested = False

    data = _tg("getUpdates", offset=offset, timeout=5)
    if not data.get("ok"):
        logger.warning("getUpdates not ok: %s", data)
        return False

    for update in data.get("result", []):
        offset = update["update_id"] + 1
        msg  = update.get("message", {})
        text = (msg.get("text") or "").strip().lower()

        # Strip @mention (e.g. /scan@lazySuzyy_bot → /scan)
        cmd = text.split("@")[0]

        logger.info("Bot command received: %s", cmd)

        if cmd in ("/start", "/help"):
            _cmd_help()
        elif cmd == "/scan":
            _cmd_scan_ack()
            scan_requested = True
        elif cmd == "/status":
            _cmd_status()
        elif cmd == "/stats":
            _cmd_stats()
        # ignore non-commands silently

    save_offset(offset)
    return scan_requested


# ── scan result logger (called by main.py after each run) ────────────────────
def log_scan_result(jobs_collected: int, new_jobs: int, matches: list[tuple]):
    """Persist scan results so /status can report them."""
    log = load_log()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    log["last_run"]       = now
    log["jobs_collected"] = jobs_collected
    log["new_jobs"]       = new_jobs
    log["matches"]        = len(matches)
    log["total_runs"]     = log.get("total_runs", 0) + 1
    log["total_matches"]  = log.get("total_matches", 0) + len(matches)
    log["last_matches"]   = [
        {"title": j["title"], "company": j["company"], "url": j["url"]}
        for j, _ in matches[:5]
    ]

    save_log(log)
    logger.info("Scan result logged to %s", SCAN_LOG_FILE)
