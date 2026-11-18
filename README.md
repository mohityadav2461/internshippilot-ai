# InternshipPilot AI

A zero-cost (₹0/month) platform that finds Summer 2027 internships in India, scores them against your profile, drafts your applications, and queues them for **your** approval. It never submits an application for you.

| Layer | Stack | Cost |
|---|---|---|
| Web app | Next.js 14 (App Router, TypeScript, Tailwind) on Vercel Hobby | ₹0 |
| Database, auth, resume storage | Supabase Free (PostgreSQL, Auth, Storage, RLS) | ₹0 |
| Discovery, scoring, inspection | Python 3.12 pipeline run by GitHub Actions every 2 hours | ₹0 |
| Optional scoring refinement | Gemini `gemini-2.5-flash` free tier, with a self-imposed daily cap | ₹0 |

## Guarantees

- **Manual approval, always.** No code path submits a form. The Playwright inspector only reads field labels. It never fills, clicks or submits. Each application ends with you pressing submit on the company's own page.
- **Verified data only.** Cover letters and form answers come from your profile. Anything the profile can't answer, such as work authorization, expected stipend, a custom question, or your motivation, becomes an explicit `[ADD …]` placeholder or a "Needs you" flag. Nothing is guessed.
- **Strict filters.** Internships only. India only. Stipend at least ₹10,000/month. Undisclosed stipends are shown as **"Stipend not verified"**, not hidden or assumed.
- **Respectful scraping.** robots.txt is honoured on every host. Requests are throttled and identify the bot. CAPTCHAs and bot challenges are refused, never bypassed.
- **Row Level Security everywhere.** Each user sees only their own profile, resumes, applications and scores. The pipeline alone holds the service-role key, and it lives only in GitHub Actions secrets.
- **Resumes stay private.** Text is extracted on the server. Resume text is never sent to any AI service.

---

> For a full step-by-step walkthrough, read **SETUP_GUIDE.md** first. This README is the reference.

## 1. Prerequisites

- Node.js 20+ and npm
- Python 3.12
- A free Supabase account, a GitHub account, and optionally a Vercel account and a Gemini API key

## 2. Create the Supabase project (free)

1. Create a project at supabase.com. Save the **Project URL**, the **anon key**, and the **service_role key** (Project Settings → API).
2. Open **SQL Editor** and run these two files, in order:
   - `supabase/migrations/0001_init.sql` (tables, indexes, RLS, storage bucket, signup trigger)
   - `supabase/seed/job_sources.sql` (starter source registry)
3. Confirm: **Table Editor** lists 9 tables and **Storage** shows a private `resumes` bucket.

### Configure sign-in (magic link)

1. **Authentication → URL Configuration**: set **Site URL** to `http://localhost:3000` for local work. Change it to your Vercel URL when you deploy.
2. **Authentication → Email Templates → Magic Link**: replace the link in the body with this one. The app verifies the token from this URL.

   ```
   {{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=email&next=/overview
   ```

3. Supabase's built-in email sender is rate-limited on the free tier. That is fine for personal use.

## 3. Run the web app locally

```bash
cd web
cp .env.example .env.local          # fill in the two NEXT_PUBLIC values only
npm install
npm run dev                         # http://localhost:3000
```

Sign in with your email, open the link, and you will land on Overview.

## 4. Run the pipeline locally (optional)

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                                 # 85 tests, no network needed (browser tests run only if Playwright is installed)
cp .env.example .env                                # add SUPABASE_URL and the service key

python -m ipilot health                             # list sources and their live status
python -m ipilot discover                           # fetch, filter, dedupe, store
python -m ipilot score                              # score onboarded users, queue strong matches

pip install -r requirements-inspect.txt
python -m playwright install --with-deps chromium
python -m ipilot inspect --limit 3                  # read-only form inspection
```

`python -m ipilot pipeline --mode full` runs discover, score and inspect in order. The scheduled job uses `--mode scan` (discover and score only, no browser). See the setup guide for the local prefill helper.

## 5. Deploy the web app to Vercel (free)

1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to `web`. The framework is detected as Next.js.
3. Add environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_SITE_URL` (your `https://…vercel.app` URL). Use **only** these three.
4. Deploy. Then update Supabase **Site URL** to the same Vercel URL.

## 6. Enable the daily pipeline (GitHub Actions)

In your repository, open **Settings → Secrets and variables → Actions**:

- **Secrets:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optionally `GEMINI_API_KEY` and `NTFY_TOPIC` (see Phone notifications below)
- **Variables:** `SCRAPER_CONTACT_URL` (a page you control) and `SCRAPER_CONTACT_EMAIL`

The workflow `.github/workflows/daily-discovery.yml` runs every 2 hours in `scan` mode (discover and score). You can run it on demand from the **Actions** tab with `mode` set to `full` (includes the read-only browser inspection), `scan`, `discover`, `score` or `inspect`. The test suite runs before every run, and a failing test stops the pipeline.

If the repository is private, GitHub's free tier includes 2,000 Actions minutes per month. A daily run takes a few minutes.

## 7. First-run checklist

1. Sign in. Open **My Profile** and complete name, skills (three or more), and at least one resume PDF. Onboarding turns complete when all three are done.
2. Open **Settings**. Confirm the defaults: ₹10,000 minimum stipend, India, Summer 2027, 2–3 months, six target roles. Decide whether to include undisclosed stipends and whether to allow AI refinement.
3. Trigger the workflow once with `mode = full`. Check **Overview → Source health**. Any source that shows `error` has a readable reason. Fix the board slug or disable the source.
4. Review **Find Internships** and **Pending Applications**. Open a draft, check every flagged field, replace each `[ADD …]` placeholder, then open the application and submit it yourself.

## Configuration reference

| Variable | Where | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | web | Public Supabase client config (safe for browsers) |
| `NEXT_PUBLIC_SITE_URL` | web | Base URL used in sign-in links |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | pipeline only | Bypass RLS. Server and CI only |
| `AI_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL` | pipeline | Optional Gemini refinement. Empty key means deterministic scoring only |
| `GEMINI_DAILY_CALL_CAP` (40), `GEMINI_RUN_CALL_CAP` (25) | pipeline | Self-imposed caps, kept below the free-tier limit. Counted in UTC |
| `REQUEST_MIN_INTERVAL_SECONDS` (2) | pipeline | Minimum gap between requests to one host |
| `SOURCE_FAILURE_LIMIT` (5) | pipeline | Consecutive failures before a source is disabled automatically |
| `STALE_JOB_DAYS` (21) | pipeline | Postings not seen for this long are marked inactive |
| `NTFY_TOPIC` (empty) | pipeline | Optional. Phone notification topic. Empty means no notifications |

## Phone notifications (optional)

When a run queues new strong matches, the pipeline sends one push notification through [ntfy.sh](https://ntfy.sh), a free service that needs no account. The message lists the top matches with their scores and reminds you that nothing is submitted. It never includes contact details, resume text or cover letters.

1. Install the free ntfy app on your phone, then subscribe to a topic name that you make up. Use 16 to 64 letters, digits, hyphens or underscores, and make it random, because anyone who knows the name can read the messages.
2. Add the same name as the GitHub Actions secret `NTFY_TOPIC`. For local runs, put it in `pipeline/.env`.
3. The next run that queues a match sends the notification. If the topic is empty or malformed, no notification is sent and nothing else changes.

Notifications are built for one person's account. Every user on the deployment shares one topic, so give each user their own deployment before adding more people.

## How scoring works

Every score is 0–100 and shows its parts. Role fit is worth 30 points, skill match 35, IITK BS Economics background 15 (econometrics, statistics, finance and similar terms), logistics 10 (India verified, plus summer, 2–3 month and 2027 signals), and stipend 10. Bands: 85–100 Excellent, 70–84 Good, 50–69 Moderate, below 50 Low.

If AI is enabled and you consent in Settings, Gemini refines the score of your strongest matches, blended 60/40 with the deterministic score. Only skills, projects and the posting text are sent. Your name, email, phone, links and resume text are never sent. If Gemini is unavailable or the cap is reached, the score falls back to deterministic and the reason is recorded.

## Sources

Enabled by default: Greenhouse, Lever and Ashby public job-board APIs for a starter list of companies. Each board slug is a starting point. The health table shows which ones resolve. A source that fails repeatedly is disabled automatically.

Disabled by default: Internshala, Wellfound and Unstop (generic JSON-LD adapter with no seed URLs), and a generic RSS adapter with no feeds. They stay off until you add listing URLs you have confirmed are permitted by the site's terms. Add seed URLs to `job_sources.config` and set `enabled = true`.

Adding a company: insert a row into `job_sources` with `adapter` set to `greenhouse`, `lever` or `ashby`, and `config` set to `{"board": "slug", "company": "Name"}` (or `company_slug` for Lever).

## Testing

```bash
# Python: normalization, filters, scoring, HTTP politeness, adapters, discovery, scoring, Gemini guard, schema security
cd pipeline && python -m pytest -q

# Draft invariants: cover letters and answers never invent facts
cd web && bash scripts/verify-drafts.sh

# Database: RLS and constraints against a real PostgreSQL (local stand-ins for Supabase auth and storage)
psql -d your_test_db -f supabase/tests/local_stubs.sql
psql -d your_test_db -f supabase/migrations/0001_init.sql
psql -d your_test_db -f supabase/seed/job_sources.sql
psql -d your_test_db -v ON_ERROR_STOP=1 -f supabase/tests/rls_smoke.sql
```

Never run `local_stubs.sql` on a hosted Supabase project. Hosted projects already provide those schemas.

## Troubleshooting

- **The sign-in link opens the login page with "invalid or expired".** Check that the email template uses `{{ .TokenHash }}` (step 2), and that Site URL matches the URL you are visiting. Links can only be used once.
- **Resume upload says "No selectable text found".** The PDF is a scan. Export a text-based PDF from Word or Google Docs.
- **Overview shows a source with status `error` or `blocked`.** Read the "Last error" column. For `blocked`, the site's robots.txt disallows the URL, or it presented a challenge. Either way, the tool deliberately stops.
- **Most runs show "Stipend not verified" on postings.** That is expected. Most listings don't publish a stipend. Enable "Include undisclosed stipends" in Settings to see them, or turn it off to hide them.
- **Supabase project paused.** Free projects pause after a week of inactivity. The scheduled job keeps the project active. Unpause it in the dashboard if needed.

## Layout

```
web/                       Next.js app (5 views + Settings), middleware, server actions
  app/(app)/                overview, find, pending, pending/[id], tracker, profile, settings
  app/actions/              server actions (applications, profile, auth)
  app/api/resumes/          PDF upload and server-side text extraction
  lib/drafts.ts             deterministic draft generator (no model calls)
pipeline/                   Python discovery, scoring and inspection
  ipilot/sources/           Greenhouse, Lever, Ashby, RSS, JSON-LD adapters
  ipilot/discovery.py       gate, dedupe, persist, source health
  ipilot/scoring.py         deterministic 0-100 scoring with reasoning
  ipilot/gemini.py          optional refinement with quota guard and PII redaction
  ipilot/form_inspector.py  read-only Playwright inspection (never submits)
  ipilot/prefill.py         local helper: fills verified answers in a visible browser, never submits
supabase/migrations/        schema, RLS, storage, signup trigger
supabase/seed/              starter job_sources registry
supabase/tests/             local stubs and RLS smoke tests
.github/workflows/          daily-discovery.yml
DEVELOPMENT_STATUS.md       what was verified, and what was not
```

## Licence and use

Intended for personal job search. Respect each job site's terms of service. You are responsible for what you submit and for the accuracy of your profile.
