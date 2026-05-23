# ── filter.py ─────────────────────────────────────────────────────────────────
# Relevance scoring: title + (company OR domain) + skill count ≥ threshold

from config import (
    TARGET_COMPANIES, JOB_TITLES, DOMAIN_KEYWORDS,
    SKILLS, SKILL_MATCH_THRESHOLD,
)


def _lower(text: str) -> str:
    return text.lower()


def match_title(title: str) -> bool:
    t = _lower(title)
    return any(jt in t for jt in JOB_TITLES)


def match_company(company: str) -> tuple[bool, str]:
    """Returns (matched, category_name)."""
    c = _lower(company)
    for category, names in TARGET_COMPANIES.items():
        if any(name in c for name in names):
            return True, category
    return False, ""


def match_domain(combined_text: str) -> bool:
    """True if any domain keyword appears anywhere in the combined job text."""
    t = _lower(combined_text)
    return any(kw in t for kw in DOMAIN_KEYWORDS)


def score_skills(combined_text: str) -> tuple[int, list[str]]:
    """Count how many skills appear in combined text."""
    t = _lower(combined_text)
    matched = [s for s in SKILLS if s in t]
    return len(matched), matched


def is_relevant(job: dict) -> tuple[bool, dict]:
    """
    A job is relevant when ALL three pass:
      1. title  ∈ JOB_TITLES
      2. company ∈ TARGET_COMPANIES  OR  domain keyword found in text
      3. skill match count ≥ SKILL_MATCH_THRESHOLD

    Returns (relevant: bool, reasons: dict)
    """
    combined = f"{job['title']} {job['company']} {job['description']}"

    title_ok            = match_title(job["title"])
    company_ok, cat     = match_company(job["company"])
    # Also scan description for company name mentions
    if not company_ok:
        company_ok, cat = match_company(job["description"])
    domain_ok           = match_domain(combined)
    skill_n, skills     = score_skills(combined)

    relevant = title_ok and (company_ok or domain_ok) and skill_n >= SKILL_MATCH_THRESHOLD

    reasons = {
        "title_match":        title_ok,
        "company_match":      company_ok,
        "company_category":   cat,
        "domain_match":       domain_ok,
        "skill_count":        skill_n,
        "matched_skills":     skills[:8],   # cap for message brevity
    }
    return relevant, reasons
