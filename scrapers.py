# ── scrapers.py ───────────────────────────────────────────────────────────────
# Working scrapers (tested):
#   1. LinkedIn  — guest jobs API (no login, best Indian coverage)
#   2. TimesJobs — HTML (SSL works on Linux/GitHub Actions)
#   3. Wellfound — Next.js JSON (startups)
#
# Naukri / Indeed are now full SPAs that block non-JS requests — skipped.

import json
import logging
import re
import time
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from config import SCRAPE_DELAY, REQUEST_TIMEOUT, JOB_TITLES

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


def _norm(job: dict) -> dict:
    return {
        "title":       str(job.get("title",       "")).strip(),
        "company":     str(job.get("company",     "")).strip(),
        "location":    str(job.get("location",    "India")).strip(),
        "description": str(job.get("description", "")).strip(),
        "url":         str(job.get("url",         "")).strip(),
        "source":      str(job.get("source",      "")).strip(),
        "posted":      str(job.get("posted",      "")).strip(),
    }


def _get(url: str, extra_headers: dict | None = None, **kwargs) -> requests.Response:
    import sys, platform
    h = {**_BROWSER_HEADERS, **(extra_headers or {})}
    # Windows may lack root certs for some Indian job sites — disable verify locally only
    if platform.system() == "Windows" and "verify" not in kwargs:
        kwargs["verify"] = False
    return requests.get(url, headers=h, timeout=REQUEST_TIMEOUT, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 1. LinkedIn — guest jobs API (no auth needed, works great for India)
# ══════════════════════════════════════════════════════════════════════════════
_LI_SEARCH = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={q}&location=India&sortBy=DD&f_TPR=r86400&start={start}"
)
_LI_DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
_LI_ID_RE  = re.compile(r"-(\d{7,})(?:\?|$)")


def _li_job_id(url: str) -> str:
    m = _LI_ID_RE.search(url)
    return m.group(1) if m else ""


def _li_fetch_description(job_id: str) -> str:
    """Fetch full job description from LinkedIn guest detail API."""
    try:
        url  = _LI_DETAIL.format(job_id=job_id)
        resp = _get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        desc_el = (
            soup.select_one(".show-more-less-html__markup") or
            soup.select_one(".description__text")
        )
        if desc_el:
            return desc_el.get_text(" ", strip=True)
    except Exception as exc:
        logger.debug("LI detail fetch %s: %s", job_id, exc)
    return ""


def _title_matches(title: str) -> bool:
    t = title.lower()
    return any(jt in t for jt in JOB_TITLES)


def scrape_linkedin(query: str) -> list[dict]:
    """
    LinkedIn guest API.
    Pass 1: fetch search listing (title + company + location).
    Pass 2: for jobs whose title matches our targets, fetch full description.
    This keeps request count low while ensuring skill scoring works.
    """
    jobs = []
    try:
        for start in (0, 25):
            url = _LI_SEARCH.format(q=quote_plus(query), start=start)
            logger.info("LinkedIn <- '%s' (start=%d)", query, start)
            resp = _get(url, extra_headers={"Accept": "text/html,application/xhtml+xml"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            cards = soup.select("li")
            if not cards:
                break

            for card in cards:
                title_el   = card.select_one(".base-search-card__title, h3")
                company_el = card.select_one(".base-search-card__subtitle, h4")
                loc_el     = card.select_one(".job-search-card__location, .base-search-card__metadata")
                link_el    = card.select_one("a.base-card__full-link, a[href*='linkedin.com/jobs/view']")
                posted_el  = card.select_one("time")

                raw_loc = loc_el.get_text(strip=True) if loc_el else "India"
                loc = raw_loc.split("Actively")[0].split("Easy")[0].strip()

                job = _norm({
                    "title":   title_el.get_text(strip=True)   if title_el   else "",
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "location": loc,
                    "url":     link_el["href"].split("?")[0]   if link_el and link_el.get("href") else "",
                    "source":  "LinkedIn",
                    "posted":  posted_el.get("datetime", "")   if posted_el  else "",
                })
                if not job["title"] or not job["url"]:
                    continue

                # Pass 2: fetch description only for title-matching jobs
                if _title_matches(job["title"]):
                    jid = _li_job_id(job["url"])
                    if jid:
                        time.sleep(1)
                        job["description"] = _li_fetch_description(jid)

                jobs.append(job)

            time.sleep(SCRAPE_DELAY)
            if len(cards) < 10:
                break   # no more pages

        logger.info("LinkedIn -> %d jobs for '%s'", len(jobs), query)
    except Exception as exc:
        logger.error("LinkedIn scraper error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 2. TimesJobs — HTML scraping (SSL fine on Linux / GitHub Actions)
# ══════════════════════════════════════════════════════════════════════════════
def scrape_timesjobs(query: str) -> list[dict]:
    jobs = []
    try:
        url = (
            "https://www.timesjobs.com/candidate/job-search.html"
            f"?searchType=personalizedSearch&from=submit"
            f"&txtKeywords={quote_plus(query)}&txtLocation=india&postWeek=1"
        )
        logger.info("TimesJobs <- '%s'", query)
        resp = _get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for li in soup.select("li.clearfix.job-bx"):
            try:
                title_el   = li.select_one("h2 a, .job-bx-title a")
                company_el = li.select_one("h3 a, .joblist-comp-info strong")
                desc_el    = li.select_one("ul.top-jd-dtl li, .list-job-dtl")
                posted_el  = li.select_one(".sim-posted span")
                link_el    = li.select_one("h2 a, .job-bx-title a")

                job = _norm({
                    "title":       title_el.get_text(strip=True)   if title_el   else "",
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "description": desc_el.get_text(strip=True)    if desc_el    else "",
                    "url":         link_el["href"]                 if link_el and link_el.get("href") else "",
                    "source":      "TimesJobs",
                    "posted":      posted_el.get_text(strip=True)  if posted_el  else "",
                })
                if job["title"] and job["url"]:
                    jobs.append(job)
            except Exception:
                continue

        logger.info("TimesJobs -> %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("TimesJobs scraper error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 3. Wellfound (AngelList) — Next.js __NEXT_DATA__ JSON (best for startups)
# ══════════════════════════════════════════════════════════════════════════════
def scrape_wellfound(query: str) -> list[dict]:
    jobs = []
    try:
        # Skip TPA-specific queries — Wellfound is startup-focused
        if any(w in query.lower() for w in ("tpa", "cashless", "claims cashless")):
            return jobs

        url = f"https://wellfound.com/role/l/india?q={quote_plus(query)}"
        logger.info("Wellfound <- '%s'", query)
        resp = _get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Try Next.js server-side data
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script:
            try:
                nd = json.loads(next_data_script.string or "")
                postings = (
                    nd.get("props", {})
                      .get("pageProps", {})
                      .get("jobListings", {})
                      .get("jobListings", [])
                )
                for p in postings:
                    startup = p.get("startup", {})
                    job = _norm({
                        "title":   p.get("title", ""),
                        "company": startup.get("name", ""),
                        "location": ", ".join(p.get("locationNames", ["India"])),
                        "description": p.get("description", ""),
                        "url":     "https://wellfound.com" + p.get("slug", ""),
                        "source":  "Wellfound",
                        "posted":  p.get("liveStartAt", ""),
                    })
                    if job["title"] and job["url"]:
                        jobs.append(job)
            except Exception as e:
                logger.debug("Wellfound JSON parse: %s", e)

        # CSS fallback
        if not jobs:
            for card in soup.select("[data-test='JobListing'], .styles_jobResult__q_AuN"):
                title_el   = card.select_one("[data-test='JobTitle'], h2")
                company_el = card.select_one("[data-test='StartupName']")
                link_el    = card.select_one("a[href*='/jobs/'], a[href*='/l/']")
                job = _norm({
                    "title":   title_el.get_text(strip=True)   if title_el   else "",
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "url":     ("https://wellfound.com" + link_el["href"]) if link_el and link_el.get("href") else "",
                    "source":  "Wellfound",
                })
                if job["title"] and job["url"]:
                    jobs.append(job)

        logger.info("Wellfound -> %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("Wellfound scraper error: %s", exc)
    return jobs


# ── public list ───────────────────────────────────────────────────────────────
ALL_SCRAPERS = [
    scrape_linkedin,
    scrape_timesjobs,
    scrape_wellfound,
]
