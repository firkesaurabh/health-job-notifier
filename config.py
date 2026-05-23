# ── config.py ─────────────────────────────────────────────────────────────────
# All targets, skills, search queries for Saurabh Firke — Health Insurance BA

TARGET_COMPANIES = {
    "tpa": [
        "medi assist", "mediassist", "md india", "paramount health",
        "health india", "vidal health", "genins", "raksha tpa",
        "family health plan", "fhpl", "ericson", "medsave", "good health",
        "heritage health", "alankit health", "anmol medcare",
        "dedicated healthcare", "united health care parekh",
        "cholamandalam ms", "safeway tpa", "grand tpa", "park mediclaim",
    ],
    "insurer": [
        "star health", "niva bupa", "hdfc ergo", "care health", "care insurance",
        "bajaj allianz", "oriental insurance", "national insurance",
        "united india insurance", "united india", "new india assurance",
        "iffco tokio", "tata aig", "icici lombard", "aditya birla health",
        "manipalcigna", "manipal cigna", "reliance health", "royal sundaram",
        "sbi general", "future generali", "go digit", "digit insurance",
        "magma hdi", "raheja qbe",
    ],
    "broker": [
        "policybazaar", "pb fintech", "pbfintech", "ditto", "ditto insurance",
        "coverfox", "acko", "turtlemint", "renewbuy", "insurancedekho",
        "easypolicy", "gramcover", "bimaplan", "quickinsure",
    ],
    "healthtech": [
        "fluent health", "hilabs", "plum", "onsurity", "loop health",
        "kenko", "nova benefits", "eka care", "practo", "mfine",
        "niramai", "healthplix", "remedo", "medgenome", "innovaccer",
        "sagility", "m3 india", "doceree", "healthians", "1mg", "tata 1mg",
        "pharmeasy", "medi buddy", "medibuddy", "rx mortar", "rx propellant",
        "plum hq", "nowfloats", "prognocis", "doxy.me", "karkinos",
        "curefit", "cure.fit", "healthifyme", "wellthy therapeutics",
    ],
}

# All target company names flattened (for fast lookup)
ALL_TARGET_NAMES = [
    name for names in TARGET_COMPANIES.values() for name in names
]

# Job titles to match (case-insensitive substring)
JOB_TITLES = [
    "business analyst",
    "technical business analyst",
    "product analyst",
    "systems analyst",
    "business systems analyst",
    "it business analyst",
    "functional analyst",
    "process analyst",
]

# Domain keywords — at least one must appear in the combined text
DOMAIN_KEYWORDS = [
    "health insurance", "tpa", "mediclaim", "cashless", "claims processing",
    "pre-authorization", "pre-auth", "pre auth", "insurer", "reimbursement",
    "nhcx", "rohini", "isnp", "health-tech", "healthtech",
    "third party administrator", "group health", "corporate health",
    "health cover", "medical insurance", "claims management",
]

# Skills to score — ≥ SKILL_MATCH_THRESHOLD triggers a notification
SKILLS = [
    # API / integration
    "rest api", "restful", "api integration", "api documentation",
    "oauth", "jwt", "postman", "swagger",
    # Claims / insurance domain
    "claims processing", "cashless claims", "pre-auth", "pre-authorization",
    "tpa", "insurer onboarding", "policy administration",
    # Requirements
    "brd", "business requirement document", "frd", "functional requirement",
    "user stories", "user story", "use case", "use cases",
    # Analytics
    "sql", "power bi", "powerbi", "tableau", "data analysis",
    # Agile / tools
    "agile", "scrum", "sprint", "jira", "confluence",
    # Automation
    "rpa", "uipath", "automation anywhere", "process automation",
    # QA / delivery
    "uat", "user acceptance testing", "gap analysis",
    "stakeholder management", "stakeholder",
    "process mapping", "workflow automation", "process improvement",
]

SKILL_MATCH_THRESHOLD = 2   # min skill matches to fire notification

# Search queries sent to each scraper
SEARCHES = [
    "business analyst health insurance India",
    "business analyst TPA India",
    "technical business analyst insurance India",
    "product analyst health insurance India",
    "BA claims cashless health insurer India",
]

SEEN_JOBS_FILE = "seen_jobs.json"
MAX_SEEN_JOBS   = 8000    # trim older entries beyond this
SCRAPE_DELAY    = 2       # seconds between HTTP requests (be polite)
REQUEST_TIMEOUT = 20      # seconds
