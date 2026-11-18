# Development status

Honest accounting of what was built, what was verified, and what has not been exercised against live services yet.

## Repository audit (Milestone 1)

| Repository | Licence | Stack | Verdict |
|---|---|---|---|
| `Abhi-420bytes/autoapply-agent` | MIT | FastAPI backend, Next.js frontend, PyInstaller desktop packaging | **Rejected.** The `PREPARED` application state carries an `auto_submit_at` timer, and the worker submits when it expires unless the user cancels. That breaks the manual-approval rule. It is also desktop-first and not cloud-friendly. |
| `fahadNoufal/job-application-agent` | MIT | Python CLI, LangGraph, Playwright, Gemini, SQLite | **Rejected as a base.** It has a useful semi-automated review concept and covers Internshala and Naukri. However, it is local-only and CLI-based. The repository also commits session-state files, a SQLite application database and a personal profile JSON, which is a privacy and security problem. Its Internshala flow includes a "blind submit" path when no questions are found. |
| `humancto/mr-jobs` | MIT | FastAPI, APScheduler, Docker, jobspy, Stagehand | **Rejected as a base.** It is a local service with no cloud deployment path. Its `--live` mode submits without a per-application approval queue. It has no robots.txt handling and no Indian portal adapters. jobspy scrapes LinkedIn and Indeed, which conflicts with their terms. |

**Decision:** build a clean Next.js and Python/Playwright monorepo from scratch. No code was copied from the three repositories. The one idea adopted is a dry-run default with an explicit live opt-in, which mr-jobs does well. The approval model here is stricter: nothing submits at all.

## Phase 1: audit, schema, structure, env

- [x] Repository audit with the verdict above, based on file inspection and grep, not on running the repositories.
- [x] `supabase/migrations/0001_init.sql`: 9 tables, indexes, check constraints, RLS on every table, storage bucket with per-user folder policies, and a signup trigger that creates a profile.
- [x] `supabase/seed/job_sources.sql`: 18 sources. 14 are enabled, and 4 aggregator or feed sources ship disabled.
- [x] Directory structure, `.env.example` (root, web and pipeline variants), `.gitignore`.

**Verified:** applied to PostgreSQL 16 with local stand-ins for the `auth` and `storage` schemas. The migration and seed both re-apply cleanly (idempotent). The RLS and constraint suite (`supabase/tests/rls_smoke.sql`) passes all 32 checks. These cover cross-user isolation, anon denial, service-role writes, the AI ledger being write-protected, default-resume uniqueness, the resume tag and score constraints, storage folder confinement, and the seed count.

**Not verified:** the migration has not been run on a hosted Supabase project. The local stand-ins approximate Supabase's `auth.uid()` and `storage.foldername()` but are not identical.

## Phase 2: database client, auth, resume parser, profile and onboarding

- [x] Server Supabase client (`@supabase/ssr`) with explicitly typed cookie adapters.
- [x] Middleware: redirects unauthenticated pages to `/login`, returns JSON 401 for `/api`, and refreshes the session.
- [x] Magic-link sign-in (`signInWithOtp`) with a `verifyOtp` confirm route. The route only redirects to same-origin paths.
- [x] Resume vault: PDF magic-byte check, 5 MB cap, server-side text extraction with `unpdf`, private storage, per-tag defaults, and a rejection for scanned PDFs.
- [x] Profile and onboarding: name, skills, resume, with a completion checklist. Matching only runs for completed profiles.

**Verified:** `tsc --noEmit` passes. `next build` passes (12 routes and the middleware compile). The live server returns 307 to `/login` for every protected route and 200 for `/login`. Security headers are present, `X-Powered-By` is removed, and the confirm route rejects a bad token. The open-redirect guard (`safeNext`) is verified by code review only: it runs on the success branch, which needs a live `verifyOtp`, so it was not exercised end to end.

**Not verified:** the email link round-trip with a real Supabase project. Text extraction on a real resume PDF: the route is compiled and wired up, but no PDF has been pushed through it.

## Phase 3: discovery, deduplication, hybrid scoring

- [x] Adapters: Greenhouse, Lever and Ashby public job-board APIs, a generic RSS/Atom adapter, and a JSON-LD `JobPosting` adapter that reads only listed seed URLs.
- [x] Robots.txt enforced on every request (robots fetch failure is treated as disallowed). Per-host throttling, Retry-After backoff, and CAPTCHA/challenge refusal.
- [x] Global gate: internship and India location, both required.
- [x] Deduplication by canonical URL and by `(company, title)` key. Location, season and year decorations are removed from titles, while role suffixes like "- Backend" are kept so distinct roles stay distinct. Duplicates merge into one job, and their URLs are recorded in `duplicate_urls`.
- [x] Source health: consecutive failures recorded, source auto-disabled at the limit, last error stored.
- [x] Deterministic 0–100 scoring with per-component reasoning and the brief's bands.
- [x] Optional Gemini refinement: consent-gated, PII-redacted input, daily ledger plus per-run cap, deterministic fallback with the reason recorded.
- [x] Idempotent scoring: `(user, job, scoring_version)` is scored once, and the queue never re-adds a job the user has acted on.

**Verified:** 64 pytest tests pass. They cover normalization, the stipend parser (annual, monthly, unpaid, ranges, years excluded), internship and role detection, filters, banding, the HTTP client (robots disallow, challenge refusal, 429 retry, non-HTTP refusal), all five adapters parsing realistic payloads through `httpx.MockTransport`, end-to-end discovery with cross-source dedupe, idempotent re-runs, auto-disable, scoring idempotency, the Gemini blend, AI fallback with reason flags, consent enforcement, quota-guard blocking before any HTTP call, PII redaction, and error classification.

**Not verified:** no live request has been made to Greenhouse, Lever or Ashby. The sandbox egress allowlist does not include those hosts. Board slugs in the seed are starting points, and the health table is the check. robots.txt for those API hosts has not been fetched. No live Gemini call has been made, so free-tier quotas are unconfirmed, and the defaults (40 per day, 25 per run) are deliberately conservative. The PostgREST query shapes (filters, `on_conflict`, embedded selects) are unit-tested through the store helpers, but no PostgREST instance was run.

## Phase 4: drafts, form inspection, dashboard

- [x] Draft generator (`web/lib/drafts.ts`): deterministic, no model calls. It builds the cover letter from verified skills, project and degree. The motivation is always a placeholder. Work authorization, expected stipend, EEO questions, referral source and unrecognised custom questions are all flagged for the human.
- [x] Application queue: Pending list, a detail page with Review, Edit (cover letter, per-answer edits, notes, resume choice) and Open Application (opens the company page in a new tab with `noopener`). Copy-to-clipboard for the letter, each answer and all answers. Status actions only record what the user did.
- [x] Find Internships: ranked list with score components, matched skills, stipend and flag badges, and filters by role, stipend, search text and minimum score.
- [x] Application Tracker with status filters and per-row status changes.
- [x] Overview with onboarding checklist, stat cards, top matches, source health and last-run summary.
- [x] Settings: strict filters, AI consent, sign-out. Filters are editable and apply on the next run.
- [x] Playwright form inspector (`pipeline/ipilot/form_inspector.py`): allowlisted Greenhouse, Lever and Ashby hosts only, robots-checked, stops on CAPTCHA, reads labels and types, never fills or submits.

**Verified:** the draft invariants pass (`web/scripts/verify-drafts.sh`, 12 checks). These confirm no invented employers or awards, no assumed work authorization or stipend, flagged empty links, and flagged unrecognised questions. The web build compiles all pages.

**Not verified:** the dashboard has never been opened in a browser, so visual layout and the copy and form interactions are untested. The Playwright inspector has never run, because no browser is installed in the sandbox and the test suite covers only its pure functions (host allowlist and challenge detection).

## Phase 5: workflow, security checks, tests, status

- [x] `.github/workflows/daily-discovery.yml`: cron at 03:30 UTC (09:00 IST), manual dispatch with a mode choice, read-only token permissions, a non-overlapping concurrency group, and the test suite as a gate before any network work.
- [x] Security checks in code: the security-invariant test fails if any table lacks RLS, if any policy is granted to `anon`, if a non-listing table is readable without an ownership check, or if the service-role key name appears anywhere in `web/`. Server actions re-check ownership with `user_id` filters and never trust a client-supplied foreign ID. Resume uploads validate type, size and magic bytes. Output is HTML-escaped by React (no `dangerouslySetInnerHTML`). Security headers are set.
- [x] Tests: 64 pytest tests, 32 database checks, 12 draft invariants, and HTTP-level smoke tests against the production server.

**Not verified:** the GitHub Actions workflow has not been executed on GitHub. The YAML was reviewed, but Actions expression evaluation (`env` in step `if:`) should be confirmed on the first manual dispatch.

## Known limitations and follow-ups

1. Live verification is needed for: Supabase auth email round-trip, the first pipeline run against real APIs, board slugs, Gemini quota behaviour, and the Playwright inspector.
2. The scoring weights are heuristic. Calibrate them from a few weeks of your own accept and reject decisions.
3. Aggregator sources (Internshala, Wellfound, Unstop) are off. Enabling them requires a review of their current terms of service, and you should do that yourself.
4. There is no "delete my account" control yet. Deleting the user in Supabase Auth cascades to all of their data.
5. The source-enable toggle lives only in the database. A UI control would be a reasonable addition.
6. Supabase free projects pause after a week of inactivity. The daily job prevents this in normal use.

## Version 2: phone notifications

- [x] `pipeline/ipilot/notify.py`: one ntfy.sh push per run that queues matches. The message lists up to 8 matches, states that nothing is submitted, and never includes personal data. The topic must be 16 to 64 URL-safe characters, and delivery failures are logged and never stop the pipeline.
- [x] `scoring_runner` sends one notification per run, only when `NTFY_TOPIC` is set and matches were queued. `stats["notified"]` records the outcome.

**Verified:** 11 new unit tests (75 in total, all passing). They cover topic validation, message wording and capping, header sanitising, the HTTP request (through a mock transport), failure handling, and the runner's notify-once behaviour.

**Not verified:** no notification has been sent to ntfy.sh, and no phone has received one. The first real check is a manual workflow run with `NTFY_TOPIC` set.

**Deliberately not built:** automatic form submission. Submitting without a person reviewing each answer would send unverified or placeholder text under the user's name, and many application forms prohibit bot submissions or use CAPTCHAs, which this project does not bypass. The manual-submit model stays.

## Version 3: final package

- [x] `pipeline/ipilot/prefill.py`: a local helper run from your own computer. It opens one pending application on a Greenhouse, Lever or Ashby page in a visible browser, fills only the answers the profile can support, attaches your resume PDF from disk, highlights required fields it could not fill, and never clicks submit. It refuses CAPTCHA and bot-check pages, refuses other hosts before any browser starts, and respects robots.txt.
- [x] `python -m ipilot prefill <application-id> --resume <file.pdf>`.
- [x] Scheduled runs changed to every 2 hours in `scan` mode (discover and score, no browser install). The browser inspection runs on manual `full` or `inspect` runs, so the free Actions minutes stay within 2,000 a month for a private repository.
- [x] `SETUP_GUIDE.md`: a complete setup and daily-use guide.

**Verified:** 85 tests pass (75 before, plus 10 new). The 10 new tests cover answer filtering, field matching, resume validation, the host refusal, bad-input handling, mode mapping, and two browser tests. The browser tests run a headless Chromium against a local form page and check that flagged answers stay empty, that no answer is guessed, that the resume is attached, and that the form is never submitted. They skip automatically where Playwright is not installed, including the GitHub test step.

**Not verified:** the helper has not been run against a real Greenhouse, Lever or Ashby page. Those pages can differ from the local fixture (for example, custom dropdowns and multi-step forms). The first real use should be one application you watch closely. The workflow change to every 2 hours has not run on GitHub yet.

**Deliberately not built:** automatic form submission, and any automation of LinkedIn, Naukri, Indeed, Internshala or Unstop. See the setup guide for the reasons.

