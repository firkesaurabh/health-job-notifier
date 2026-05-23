# ── scrapers.py ───────────────────────────────────────────────────────────────
# Six scrapers: Indeed (RSS), Naukri (API), TimesJobs, Wellfound,
#               Instahyre, Cutshort.  Each returns list[dict] with normalised
#               fields; errors are caught so one failure never blocks others.

import json
import logging
import time
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from config import SCRAPE_DELAY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# ── shared HTTP headers ───────────────────────────────────────────────────────
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
}


# ── helpers ───────────────────────────────────────────────────────────────────
def _norm(job: dict) -> dict:
    """Ensure all required keys exist and values are stripped strings."""
    return {
        "title":       str(job.get("title",       "")).strip(),
        "company":     str(job.get("company",     "")).strip(),
        "location":    str(job.get("location",    "India")).strip(),
        "description": str(job.get("description", "")).strip(),
        "url":         str(job.get("url",         "")).strip(),
        "source":      str(job.get("source",      "")).strip(),
        "posted":      str(job.get("posted",      "")).strip(),
    }


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _get(url: str, headers: dict | None = None, **kwargs) -> requests.Response:
    h = {**_BROWSER_HEADERS, **(headers or {})}
    return requests.get(url, headers=h, timeout=REQUEST_TIMEOUT, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Indeed India — RSS feed (most reliable, no auth needed)
# ══════════════════════════════════════════════════════════════════════════════
def scrape_indeed(query: str) -> list[dict]:
    jobs = []
    try:
        url = (
            f"https://in.indeed.com/rss?q={quote_plus(query)}"
            f"&l=India&sort=date&fromage=1"
        )
        logger.info("Indeed  ← %s", url)
        feed = feedparser.parse(url)

        for e in feed.entries:
            desc = _html_to_text(e.get("summary", ""))
            job = _norm({
                "title":       e.get("title", ""),
                "company":     e.get("author", ""),
                "location":    e.get("indeed_formattedlocation", "India"),
                "description": desc,
                "url":         e.get("link", ""),
                "source":      "Indeed",
                "posted":      e.get("published", ""),
            })
            if job["url"]:
                jobs.append(job)

        logger.info("Indeed  → %d jobs for '%s'", len(jobs), query)
    except Exception as exc:
        logger.error("Indeed scraper error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 2. Naukri — internal JSON API (works without auth when correct headers sent)
# ══════════════════════════════════════════════════════════════════════════════
def scrape_naukri(query: str) -> list[dict]:
    jobs = []
    try:
        naukri_headers = {
            **_BROWSER_HEADERS,
            "appid":                     "109",
            "systemid":                  "109",
            "Naukri-Mobile-System-Value": "v2",
            "Accept":                    "application/json, text/plain, */*",
        }
        url = (
            "https://www.naukri.com/jobapi/v4/jobs"
            f"?noOfResults=20&urlType=search_by_key_loc"
            f"&searchType=adv&keyword={quote_plus(query)}"
            f"&location=india&sort=1&experience=3"
        )
        logger.info("Naukri  ← API call for '%s'", query)
        resp = _get(url, headers=naukri_headers)
        resp.raise_for_status()
        data = resp.json()

        for jd in data.get("jobDetails", []):
            # Extract location from placeholders array
            loc = "India"
            for ph in jd.get("placeholders", []):
                if ph.get("type") == "location":
                    loc = ph.get("label", "India")
                    break

            job_url = jd.get("jdURL", "")
            if job_url and not job_url.startswith("http"):
                job_url = "https://www.naukri.com" + job_url

            job = _norm({
                "title":       jd.get("title", ""),
                "company":     jd.get("companyName", ""),
                "location":    loc,
                "description": _html_to_text(jd.get("jobDescription", "")),
                "url":         job_url,
                "source":      "Naukri",
                "posted":      jd.get("footerPlaceholderLabel", ""),
            })
            if job["url"]:
                jobs.append(job)

        logger.info("Naukri  → %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("Naukri scraper error: %s", exc)
        # Fallback: HTML scraping
        jobs = _scrape_naukri_html(query)
    return jobs


def _scrape_naukri_html(query: str) -> list[dict]:
    """Fallback: parse Naukri search-results HTML."""
    jobs = []
    try:
        url = (
            f"https://www.naukri.com/{quote_plus(query).replace('%20', '-')}-jobs-in-india"
            f"?k={quote_plus(query)}&l=india&experience=3&sort=1"
        )
        resp = _get(url)
        soup = BeautifulSoup(resp.text, "lxml")

        # Naukri embeds some data in script tags — try JSON-LD first
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                items = json.loads(script.string or "")
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        org = item.get("hiringOrganization", {})
                        job = _norm({
                            "title":       item.get("title", ""),
                            "company":     org.get("name", ""),
                            "location":    item.get("jobLocation", {}).get("address", {}).get("addressLocality", "India"),
                            "description": _html_to_text(item.get("description", "")),
                            "url":         item.get("url", ""),
                            "source":      "Naukri",
                            "posted":      item.get("datePosted", ""),
                        })
                        if job["url"]:
                            jobs.append(job)
            except Exception:
                continue

        # CSS-selector fallback
        if not jobs:
            for article in soup.select("article.jobTuple, div.srp-jobtuple-wrapper"):
                title_el   = article.select_one(".title, .row1 a")
                company_el = article.select_one(".subTitle, .comp-name")
                desc_el    = article.select_one(".job-description, .job-desc")
                link_el    = article.select_one("a.title, a[href*='job-listings']")
                posted_el  = article.select_one(".date-label, .date")
                job = _norm({
                    "title":       title_el.get_text(strip=True)   if title_el   else "",
                    "company":     company_el.get_text(strip=True) if company_el else "",
                    "description": desc_el.get_text(strip=True)    if desc_el    else "",
                    "url":         link_el["href"]                 if link_el and link_el.get("href") else "",
                    "source":      "Naukri",
                    "posted":      posted_el.get_text(strip=True)  if posted_el  else "",
                })
                if job["url"] and not job["url"].startswith("http"):
                    job["url"] = "https://www.naukri.com" + job["url"]
                if job["title"] and job["url"]:
                    jobs.append(job)

        logger.info("Naukri(HTML) → %d jobs", len(jobs))
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("Naukri HTML fallback error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 3. TimesJobs — HTML scraping
# ══════════════════════════════════════════════════════════════════════════════
def scrape_timesjobs(query: str) -> list[dict]:
    jobs = []
    try:
        url = (
            "https://www.timesjobs.com/candidate/job-search.html"
            f"?searchType=personalizedSearch&from=submit"
            f"&txtKeywords={quote_plus(query)}&txtLocation=india&postWeek=1"
        )
        logger.info("TimesJobs ← '%s'", query)
        resp = _get(url)
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

        logger.info("TimesJobs → %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("TimesJobs scraper error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 4. Wellfound (AngelList) — Next.js __NEXT_DATA__ JSON
# ══════════════════════════════════════════════════════════════════════════════
def scrape_wellfound(query: str) -> list[dict]:
    jobs = []
    try:
        # Only run for health-tech focused queries (avoids unnecessary calls)
        if "tpa" in query.lower() or "cashless" in query.lower():
            return jobs

        url = f"https://wellfound.com/role/l/india?q={quote_plus(query)}"
        logger.info("Wellfound ← '%s'", query)
        resp = _get(url)
        soup = BeautifulSoup(resp.text, "lxml")

        # Try Next.js server-side data
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script:
            try:
                nd = json.loads(next_data_script.string or "")
                # Path varies — walk common paths
                postings = (
                    nd.get("props", {})
                      .get("pageProps", {})
                      .get("jobListings", {})
                      .get("jobListings", [])
                )
                for p in postings:
                    startup  = p.get("startup",  {})
                    job_role = p.get("jobRole",  {})
                    job = _norm({
                        "title":       p.get("title", job_role.get("display", "")),
                        "company":     startup.get("name", ""),
                        "location":    ", ".join(p.get("locationNames", ["India"])),
                        "description": p.get("description", ""),
                        "url":         "https://wellfound.com" + p.get("slug", ""),
                        "source":      "Wellfound",
                        "posted":      p.get("liveStartAt", ""),
                    })
                    if job["title"] and job["url"]:
                        jobs.append(job)
            except Exception as parse_err:
                logger.debug("Wellfound JSON parse: %s", parse_err)

        # CSS fallback
        if not jobs:
            for card in soup.select("[data-test='JobListing'], .styles_jobResult__q_AuN"):
                title_el   = card.select_one("[data-test='JobTitle'], h2")
                company_el = card.select_one("[data-test='StartupName'], .startup-name")
                link_el    = card.select_one("a[href*='/jobs/'], a[href*='/l/']")
                job = _norm({
                    "title":   title_el.get_text(strip=True)   if title_el   else "",
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "url":     ("https://wellfound.com" + link_el["href"]) if link_el and link_el.get("href") else "",
                    "source":  "Wellfound",
                })
                if job["title"] and job["url"]:
                    jobs.append(job)

        logger.info("Wellfound → %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("Wellfound scraper error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 5. Instahyre — public candidate search API
# ══════════════════════════════════════════════════════════════════════════════
def scrape_instahyre(query: str) -> list[dict]:
    jobs = []
    try:
        # Only hit once per run (their API is rate-sensitive)
        if "tpa" in query.lower() or "cashless" in query.lower():
            return jobs

        url = (
            "https://instahyre.com/api/v1/candidate/positions/"
            f"?query={quote_plus(query)}&location=india&experience_min=3"
        )
        logger.info("Instahyre ← '%s'", query)
        resp = _get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

        for pos in data.get("results", data if isinstance(data, list) else []):
            company = pos.get("company", {})
            job = _norm({
                "title":       pos.get("role", pos.get("title", "")),
                "company":     company.get("name", "") if isinstance(company, dict) else str(company),
                "location":    ", ".join(pos.get("locations", ["India"])),
                "description": pos.get("description", pos.get("responsibilities", "")),
                "url":         pos.get("url", pos.get("apply_url", "")),
                "source":      "Instahyre",
                "posted":      pos.get("created", ""),
            })
            if job["title"]:
                # Build URL if not provided
                if not job["url"]:
                    slug = pos.get("slug", pos.get("id", ""))
                    job["url"] = f"https://instahyre.com/job/{slug}" if slug else ""
                if job["url"]:
                    jobs.append(job)

        logger.info("Instahyre → %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("Instahyre scraper error: %s", exc)
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# 6. Cutshort — public jobs API
# ══════════════════════════════════════════════════════════════════════════════
def scrape_cutshort(query: str) -> list[dict]:
    jobs = []
    try:
        if "cashless" in query.lower():
            return jobs

        url = (
            "https://cutshort.io/api/public/jobs"
            f"?q={quote_plus(query)}&location=India&limit=20"
        )
        logger.info("Cutshort ← '%s'", query)
        resp = _get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

        listing = data if isinstance(data, list) else data.get("data", data.get("jobs", []))
        for pos in listing:
            company = pos.get("company", {})
            job = _norm({
                "title":       pos.get("title", pos.get("role", "")),
                "company":     company.get("name", "") if isinstance(company, dict) else str(company),
                "location":    pos.get("location", "India"),
                "description": pos.get("description", pos.get("about", "")),
                "url":         pos.get("url", pos.get("applyUrl", "")),
                "source":      "Cutshort",
                "posted":      pos.get("createdAt", pos.get("posted_at", "")),
            })
            if not job["url"] and pos.get("slug"):
                job["url"] = f"https://cutshort.io/job/{pos['slug']}"
            if job["title"] and job["url"]:
                jobs.append(job)

        logger.info("Cutshort → %d jobs for '%s'", len(jobs), query)
        time.sleep(SCRAPE_DELAY)
    except Exception as exc:
        logger.error("Cutshort scraper error: %s", exc)
    return jobs


# ── public list of all scrapers ───────────────────────────────────────────────
ALL_SCRAPERS = [
    scrape_indeed,
    scrape_naukri,
    scrape_timesjobs,
    scrape_wellfound,
    scrape_instahyre,
    scrape_cutshort,
]
