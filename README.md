# Health Job Notifier 🏥

Hourly job scanner for **Business Analyst** roles in India's Health Insurance ecosystem.
Runs free on GitHub Actions → sends instant Telegram alerts.

## What it scans
| Source | Method |
|---|---|
| Indeed India | RSS feed |
| Naukri | Internal JSON API + HTML fallback |
| TimesJobs | HTML scraping |
| Wellfound | Next.js `__NEXT_DATA__` JSON |
| Instahyre | REST API |
| Cutshort | REST API |

## What fires an alert
A job matches when **all three** conditions pass:
1. **Title** contains: Business Analyst / Technical BA / Product Analyst / Systems Analyst
2. **Company or description** matches: TPA / Insurer / Broker / Health-tech  OR  domain keyword (cashless, pre-auth, mediclaim…)
3. **Skill score ≥ 2** from: REST API, OAuth, JWT, Postman, claims processing, BRD/FRD, SQL, Power BI, Agile, JIRA, RPA, UAT, etc.

---

## One-time setup (15 minutes)

### Step 1 — Telegram Bot
1. Open Telegram → search **@BotFather** → `/newbot`
2. Choose any name, e.g. `HealthJobBot`
3. BotFather gives you a **token** like `1234567890:ABCdef...` — save it
4. Send a message ("hi") to your new bot
5. Run locally:
   ```
   python get_telegram_chat_id.py <YOUR_TOKEN>
   ```
   Copy the **Chat ID** shown.

### Step 2 — GitHub Repo
```bash
cd C:\Users\saura\health-job-notifier
git init
git add .
git commit -m "init: health job notifier"
```
Create a **public** repo on GitHub (public = free unlimited Actions minutes):
```bash
git remote add origin https://github.com/YOUR_USERNAME/health-job-notifier.git
git push -u origin main
```

> **Private repo works too** — free tier has 500 min/month.
> The scanner uses ~1 min/run × 720 runs/month = ~720 min.
> To stay safe on private: change cron to `"0 */2 * * *"` (every 2 h).

### Step 3 — GitHub Secrets
In your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `TELEGRAM_TOKEN` | The BotFather token |
| `TELEGRAM_CHAT_ID` | The number from Step 1 |

### Step 4 — Enable Actions
Go to **Actions tab** in your repo → click **"I understand my workflows, go ahead and enable them"**.

The scanner runs automatically every hour from now. To test immediately:
**Actions → "Health Job Scanner" → Run workflow**.

---

## Local test run
```bash
pip install -r requirements.txt
cp .env.example .env          # fill in your token + chat id
python main.py
```

---

## Customise

**Add/remove companies** → edit `TARGET_COMPANIES` in `config.py`

**Change skill threshold** → `SKILL_MATCH_THRESHOLD = 2` in `config.py`

**Change scan frequency** → edit cron in `.github/workflows/scan.yml`:
- Every 30 min: `"*/30 * * * *"`
- Every 2 hours: `"0 */2 * * *"`

**Add searches** → append to `SEARCHES` list in `config.py`

---

## Telegram alert example
```
🛡️ New Job — INSURER

📌 Technical Business Analyst
🏢 Niva Bupa Health Insurance
📍 Gurugram
📅 Posted today  |  🔎 Naukri

REST API integration required for TPA onboarding...

🔧 #rest_api  #brd  #agile  #sql  #claims_processing

🔗 Open Job
```

---

## Architecture
```
GitHub Actions (cron: every hour)
    └─▶ main.py
          ├─ scrapers.py   ← Indeed RSS + Naukri API + TimesJobs + Wellfound + Instahyre + Cutshort
          ├─ filter.py     ← title + company/domain + skill scoring
          ├─ store.py      ← SHA-256 dedup via seen_jobs.json
          └─ notifier.py   ← Telegram Bot API
    └─▶ git commit seen_jobs.json [skip ci]
```
