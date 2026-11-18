# InternshipPilot AI: complete setup and daily-use guide

This guide takes you from nothing to a working system. It assumes no prior experience with GitHub, Supabase or Vercel. Each step says what to click and what you should see. Budget about 1 to 2 hours for the first setup. Daily use after that takes a few minutes per notification.

---

## 1. What this app does, and what it does not do

**It does:**

- Checks job boards for internships in India, on a schedule (every 2 hours), using only public job-board feeds from Greenhouse, Lever and Ashby.
- Keeps only internships in your target roles that pay at least ₹10,000 a month, or whose stipend isn't published.
- Scores each job from 0 to 100 against your skills and profile, and shows the reasons.
- Adds strong matches (70 or higher) to your **Pending** queue and can send you a phone notification.
- Prepares a cover letter and form answers from **your** verified profile. Anything it cannot know, such as your motivation or work authorisation, is left as a marked `[ADD …]` item for you to write.
- Lets you open a prefilled application on your own computer, where it fills in what it can and stops for you to check and submit.

**It does not:**

- Submit any application. You always press submit yourself.
- Apply through LinkedIn, Naukri, Indeed, Internshala or Unstop, or log in to any site on your behalf. Those sites forbid bots, and an automated login puts your account at risk.
- Solve, skip or get around CAPTCHAs or bot checks. If a page shows one, the helper stops and tells you.
- Guess an answer it cannot support from your profile. Invented answers in an application can get you rejected.

**Why submitting stays with you:** a submitted application cannot be taken back, and the answers that matter most (why this company, your work authorisation, your expected stipend) must come from you. An automatic submit would send placeholders or guesses under your name.

---

## 2. What you need (all free)

- A **GitHub** account (github.com)
- A **Supabase** account (supabase.com), for the database, sign-in and resume storage
- A **Vercel** account (vercel.com), to host the web dashboard. Optional if you only use the helper on your computer, but you need it for the dashboard.
- A computer with **Python 3.12** and **Node.js 20 or newer**. Needed only for the local helper and for running tests yourself.
- Optional: a **Gemini API key** from Google AI Studio, for extra score refinement. The app works without it.
- Optional: the free **ntfy** app on your phone, for notifications.

---

## 3. Create the database (Supabase)

1. Sign in to supabase.com and click **New project**. Choose a name and a database password. Save the password somewhere safe.
2. Wait for the project to finish setting up.
3. Open **Project Settings → API**. Copy these three values somewhere safe:
   - **Project URL** (looks like `https://abcd1234.supabase.co`)
   - **anon public key**
   - **service_role key**. This is a secret. Anyone with it can read all data. Never put it in a browser, a public file or a public repository.
4. Open **SQL Editor → New query**. Open `supabase/migrations/0001_init.sql` from this project, copy the entire file into the editor, and click **Run**. You should see "Success" with no red errors.
5. Open a new query, copy the entire file `supabase/seed/job_sources.sql`, and click **Run**.
6. Open **Table Editor**. You should see 9 tables. Open **Storage**. You should see a private bucket named `resumes`.

### Configure sign-in with an email link

1. Open **Authentication → URL Configuration**. Set **Site URL** to `http://localhost:3000` for now. You will change it after the dashboard is deployed (step 6).
2. Open **Authentication → Email Templates → Magic Link**. Replace the link in the template body with this exact link, so the app can verify the sign-in:

   ```
   {{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=email&next=/overview
   ```

3. Save the template. Supabase's built-in email sender has a daily limit on the free tier, which is enough for personal use.

---

## 4. Put the project on GitHub

1. Unzip `internshippilot-ai-final.zip`. You get one folder named `internshippilot-ai`.
2. On github.com, click **+ → New repository**. Name it `internshippilot-ai`. Choose **Private** (recommended). Do not add a README.
3. Upload the **contents** of the `internshippilot-ai` folder, not the folder itself. After uploading, the repository's first page should show folders named `.github`, `pipeline`, `supabase` and `web`. If you see a folder named `internshippilot-ai` inside the repository, you uploaded one level too deep. Delete the repository and try again.

   If you know Git, you can instead run `git init`, `git add .`, `git commit -m "initial"` and push from the folder.

4. Check the `.github/workflows/daily-discovery.yml` file is present at the top level. The workflow will not run without it.

### Add your secrets to GitHub

1. In your repository, open **Settings → Secrets and variables → Actions**.
2. On the **Secrets** tab, click **New repository secret** and add each of these:
   - `SUPABASE_URL`: your Project URL from step 3
   - `SUPABASE_SERVICE_ROLE_KEY`: your service_role key from step 3
   - `GEMINI_API_KEY`: optional. Leave it out if you don't have one.
   - `NTFY_TOPIC`: optional. The phone-notification topic from step 9. Leave it out to skip notifications.
3. On the **Variables** tab, click **New repository variable** and add:
   - `SCRAPER_CONTACT_URL`: a web page you control, such as your GitHub profile URL. Job sites use it to contact you if the bot causes a problem.
   - `SCRAPER_CONTACT_EMAIL`: an email address where you can be reached.

Secrets are hidden after saving. You cannot read them back, only replace them.

---

## 5. Run the first discovery

1. Open the **Actions** tab in your repository. If GitHub asks you to enable workflows, click the button to enable them.
2. Click **discovery** in the left column, then **Run workflow**. Set `mode` to `full` and click the green **Run workflow** button.
3. Wait 3 to 5 minutes and click the run. A green tick means it worked. A red cross means a step failed. Click the failed step to read the error.

The first run also installs a browser, so it takes longer than later runs.

---

## 6. Deploy the web dashboard (Vercel)

1. Sign in to vercel.com with your GitHub account. Click **Add New → Project**, and import your `internshippilot-ai` repository.
2. Set **Root Directory** to `web`. Vercel should detect Next.js automatically.
3. Under **Environment Variables**, add exactly these three, and nothing else:
   - `NEXT_PUBLIC_SUPABASE_URL`: your Project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: your **anon** key (not the service_role key)
   - `NEXT_PUBLIC_SITE_URL`: leave a placeholder for now, such as `https://example.vercel.app`, and update it in step 4 below once you know your real address
4. Click **Deploy**. When it finishes, Vercel shows your address, something like `https://internshippilot-ai-yourname.vercel.app`. Open it.
5. Now update the address you used earlier:
   - In Vercel, set `NEXT_PUBLIC_SITE_URL` to your real address, then **Redeploy**.
   - In Supabase, open **Authentication → URL Configuration** and set **Site URL** to the same address.

---

## 7. Sign in and set up your profile

1. Open your Vercel address and enter your email. Open the sign-in link from the email. It only works once. If it says "invalid or expired", request a new link and open it in the same browser.
2. Open **My Profile** and fill in:
   - Your name, phone and city
   - **At least three skills**, each typed as a separate entry (for example `Python`, `SQL`, `Econometrics`)
   - **At least one resume PDF.** It must be a text-based PDF, not a scan. If you get "No selectable text found", export the resume again from Word or Google Docs as a PDF.
   - Your projects, and any achievements you want included
3. Onboarding is complete when name, skills and resume are all filled in. Only completed profiles get scored.
4. Open **Settings** and review the defaults: minimum stipend ₹10,000, India, Summer 2027, 2 to 3 months, and the six target roles. Untick any role you don't want. Decide whether to include postings with no published stipend. Leave **AI refinement** off unless you added a Gemini key, and only turn it on if you're comfortable with the consent wording there.

---

## 8. Check the first results

1. In GitHub, run the workflow again, this time with `mode` set to `scan`, or wait for the next 2-hourly run.
2. Open **Overview**. The **Source health** table shows each company board. A green status means the board resolved. An `error` shows the reason in the "Last error" column. For a board that doesn't resolve, check its name (see step 11).
3. Open **Find Internships**. Matches appear here with their scores, and you can filter them.
4. A match with a score of 70 or higher goes to **Pending Applications**. Open one to review it.

---

## 9. Set up phone notifications (optional, free)

1. On your phone, install the free **ntfy** app (iOS or Android).
2. Make up a topic name with 16 to 64 letters, digits, hyphens or underscores, for example `pilot-7kq2x9vb4mzt1r8n`. Make it random. Anyone who knows the name can read the messages, so don't use your own name.
3. In the app, subscribe to that topic.
4. In GitHub, add the same name as the secret `NTFY_TOPIC` (step 4).
5. The next run that queues matches will send one notification. The message lists the top matches and their scores, and says that nothing is submitted until you do it.

---

## 10. Set up job alerts on the big platforms (manual, safe)

The app does not search LinkedIn, Naukri, Indeed, Internshala or Unstop, because their terms forbid bots. You can still get alerts from them directly:

1. On each platform, search for an internship in your role, with India as the location.
2. Look for a **create alert**, **save search** or **job alert** button on the results page. Set the frequency to daily, and send alerts to your email.
3. Repeat for each role you care about, such as "Data Analyst Intern", "Quant Research Intern" or "ML Intern".

When an alert arrives, apply on the company's own page if the job suits you. The app only queues jobs its scanner has found, so it cannot take a job link from you. To have the scanner track a company, add its job board (step 11).

---

## 11. Add companies you want to target

The app checks Greenhouse, Lever and Ashby job boards. To check whether a company uses one of them:

- Open the company's careers page and click a job. If the address contains `boards.greenhouse.io`, `job-boards.greenhouse.io`, `jobs.lever.co` or `jobs.ashbyhq.com`, the company can be added.
- The board name is the part of that address right after the platform name. For example, `https://jobs.lever.co/spotify/abc` means the Lever name is `spotify`.

To add a company, open Supabase **SQL Editor** and run one of these, replacing the example name:

```sql
-- Greenhouse
insert into public.job_sources (name, adapter, config, enabled)
values ('greenhouse:exampleco', 'greenhouse', '{"board":"exampleco","company":"Example Co"}', true);

-- Lever (note the key is company_slug)
insert into public.job_sources (name, adapter, config, enabled)
values ('lever:exampleco', 'lever', '{"company_slug":"exampleco","company":"Example Co"}', true);

-- Ashby
insert into public.job_sources (name, adapter, config, enabled)
values ('ashby:exampleco', 'ashby', '{"board":"exampleco","company":"Example Co"}', true);
```

If a company name is already in the table, the insert will fail with a duplicate error. That is harmless. Use a different name if you want a second entry. A board that keeps failing is disabled automatically after 5 failed runs, and the reason is shown in Source health.

---

## 12. Prepare applications on your own computer (the helper)

This step opens a real company application page in a browser window on your computer, fills in what it can, and waits for you. It never submits.

### One-time setup

1. Install **Python 3.12** from python.org, and during install tick "Add Python to PATH".
2. Open a terminal and go into the `pipeline` folder of the project (for example, `cd pipeline`).

3. Create a virtual environment and install the tools:

   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt -r requirements-inspect.txt
   python -m playwright install chromium
   ```

4. Copy the settings file and fill it in:

   ```bash
   cp .env.example .env               # Windows: copy .env.example .env
   ```

   Open `.env` in a text editor and set:

   - `SUPABASE_URL`: your Project URL
   - `SUPABASE_SERVICE_ROLE_KEY`: your service_role key
   - `SCRAPER_CONTACT_URL` and `SCRAPER_CONTACT_EMAIL`: the same values you set in GitHub

   **Warning:** the service_role key can read all data in your database. Keep `.env` on your own computer only. The project's `.gitignore` already stops `.env` from being committed, but never paste the key into a chat, email or screenshot.

### Each time you apply

1. In the dashboard, open the **Pending** item you want to apply to. Copy the id at the end of the address. For example, in `https://your-app.vercel.app/pending/6f1c2a3e-1111-4222-8333-444455556666`, the id is the part after `/pending/`.
2. Check the answers in the dashboard first. Replace every `[ADD …]` placeholder with your own words, and fix anything wrong. The helper uses the answers as saved in the dashboard.
3. In the terminal, with the virtual environment active, run:

   ```bash
   python -m ipilot prefill 6f1c2a3e-1111-4222-8333-444455556666 --resume "/full/path/to/your_resume.pdf"
   ```

   On Windows, use a path like `--resume "C:\Users\you\Documents\resume.pdf"`.

4. A browser window opens on the company's application page. The helper fills in the fields it can match, attaches your resume, and outlines in red the required fields it could not fill.
5. **Read every field.** Write the answers marked for you. Check the form matches what you want to send.
6. Press the company's **Submit** button yourself.
7. Close the browser window. Back in the dashboard, open the application and set its status to **Applied (manually)**. This keeps your tracker accurate.

If the page shows a CAPTCHA or a bot check, the helper stops and tells you. Complete it yourself in the browser, or apply directly on the company's site.

The helper waits up to an hour for you to review. If you go longer, the window closes and you start again.

---

## 13. Your daily routine

- Read the phone notification, or check **Pending Applications** once a day.
- For each strong match: read the job, decide whether you want it, check the drafted answers, write your own motivation, run the helper, review, submit, and mark the status.
- Once a week, look at **Source health** in the dashboard. Fix or remove any board showing errors.
- Keep the GitHub repository active. For a public repository, GitHub pauses scheduled runs after 60 days with no activity, so make a small commit if you go quiet for a long time.

---

## 14. Costs and limits (free plan)

- **GitHub Actions:** a private repository includes 2,000 minutes a month. These figures assume about 3 minutes per scan run, which is an estimate; the first runs will show the real time. At that estimate, running every 2 hours uses roughly 1,000 minutes a month, and running every hour would exceed the free limit.
- **Supabase:** free projects pause after a week with no activity. The scheduled runs keep the project active. If it does pause, unpause it in the Supabase dashboard.
- **Vercel:** the free Hobby plan is enough for personal use.
- **Gemini:** optional. The app caps its own usage at 40 calls a day, below the free limit.
- **Supabase email:** the built-in sender is rate-limited. That's fine for personal sign-in.

---

## 15. Troubleshooting

- **The sign-in link says "invalid or expired".** Check that the email template uses `{{ .TokenHash }}`, and that the Site URL matches the address you're visiting. Each link works only once. Request a new one.
- **Resume upload says "No selectable text found".** The PDF is a scan. Export a text-based PDF from Word or Google Docs.
- **A source shows `error` or `blocked`.** Read the "Last error" column. `blocked` means the site's robots.txt disallows the page or the site showed a challenge. The app stops on purpose. Remove that source, or leave it for a different board.
- **A GitHub run is red.** Click the failed step. A failing test stops the run before any network work, so fix the reported test or contact the person who changed the code.
- **No matches appear.** That can be normal on any given day. Check Source health first, then check the role and stipend settings. Very strict settings hide most postings.
- **`prefill` says the host is not allowed.** The helper only works on Greenhouse, Lever and Ashby application pages. For other sites, apply on the company's page yourself.
- **`prefill` says the application is already marked something else.** The helper only works on pending applications. You don't need it for one you have already submitted.
- **The browser window closes straight away.** Check that `python -m playwright install chromium` finished without errors.

---

## 16. Honest status: what has and hasn't been tested

- **Tested in the development environment:** 85 automated tests pass. They cover the scoring, filtering, deduplication, notification logic, the helper's answer matching and safety rules, and two browser tests on a local practice form. The database rules were tested in an earlier version against a local PostgreSQL database.
- **Not tested yet:** the GitHub workflow has not run on GitHub. The notifications have not reached a phone. The helper has not been run on a real Greenhouse, Lever or Ashby page. Email sign-in has not been tried against a live Supabase project. Gemini has not been called live.

Expect some problems on the first real run, and treat the first full week as a test period. Check each run's result in the Actions tab, and watch the first real application closely.

---

## 17. Adding more companies, or changing the code

The layout of the project is:

- `web/`: the Next.js dashboard
- `pipeline/ipilot/`: the scanner, scoring, notifications, form reader and the local helper
- `pipeline/tests/`: the automated tests
- `supabase/`: the database schema and the starter list of companies
- `.github/workflows/`: the schedule

If you change the pipeline, run `python -m pytest -q` inside `pipeline` before pushing, and make sure all tests pass.
