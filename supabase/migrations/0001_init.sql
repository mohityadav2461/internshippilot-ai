-- =====================================================================
-- InternshipPilot AI · 0001_init.sql
-- Run in the Supabase SQL Editor (or `supabase db push`). Re-runnable.
--
-- Security model
--   * RLS is enabled on EVERY public table (enforced by pipeline/tests).
--   * Browser clients (anon / authenticated) only see their own rows, plus
--     the shared public-listing tables jobs, job_sources and pipeline_runs
--     (read-only).
--   * The pipeline writes with SUPABASE_SERVICE_ROLE_KEY, which bypasses RLS.
--     That key lives only in GitHub Actions secrets and never ships to a browser.
-- =====================================================================

create extension if not exists pgcrypto;

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------
-- profiles: one row per auth user (created by trigger at the bottom)
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text not null default '' check (char_length(full_name) <= 120),
  email text not null default '' check (char_length(email) <= 254),
  phone text not null default '' check (char_length(phone) <= 20),
  city text not null default '' check (char_length(city) <= 80),
  linkedin_url text not null default '' check (char_length(linkedin_url) <= 300),
  github_url text not null default '' check (char_length(github_url) <= 300),
  portfolio_url text not null default '' check (char_length(portfolio_url) <= 300),
  college text not null default 'Indian Institute of Technology Kanpur' check (char_length(college) <= 120),
  degree text not null default 'BS Economics' check (char_length(degree) <= 120),
  graduation_year integer not null default 2028 check (graduation_year between 2024 and 2035),
  skills text[] not null default '{}',
  projects jsonb not null default '[]'::jsonb check (jsonb_typeof(projects) = 'array'),
  achievements text[] not null default '{}',
  -- Strict filters. Defaults match the brief and are editable in Settings.
  filters jsonb not null default '{
    "min_stipend_inr": 10000,
    "locations": ["India"],
    "internship_only": true,
    "allow_stipend_unverified": true,
    "target_start": "Summer 2027",
    "duration_months": "2-3",
    "roles": ["SDE", "Quant", "Analyst", "ML", "DataScience", "Research"],
    "min_score_to_show": 50,
    "auto_queue_score": 70
  }'::jsonb check (jsonb_typeof(filters) = 'object'),
  ai_consent boolean not null default false,
  onboarding_complete boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------
-- resumes: metadata for the multi-resume vault (PDF lives in Storage)
-- ---------------------------------------------------------------------
create table if not exists public.resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  tag text not null check (tag in ('SDE', 'Quant', 'Analyst', 'ML')),
  label text not null default '' check (char_length(label) <= 80),
  file_name text not null check (char_length(file_name) <= 200),
  storage_path text not null unique check (char_length(storage_path) <= 300),
  extracted_text text not null default '' check (char_length(extracted_text) <= 60000),
  is_default boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists resumes_user_tag_idx on public.resumes (user_id, tag);
create unique index if not exists resumes_one_default_per_tag
  on public.resumes (user_id, tag) where is_default;

-- ---------------------------------------------------------------------
-- job_sources: registry + live health for every discovery adapter
-- ---------------------------------------------------------------------
create table if not exists public.job_sources (
  id uuid primary key default gen_random_uuid(),
  name text not null unique check (char_length(name) between 2 and 80),
  adapter text not null check (adapter in ('greenhouse', 'lever', 'ashby', 'rss', 'jsonld_pages')),
  config jsonb not null default '{}'::jsonb check (jsonb_typeof(config) = 'object'),
  enabled boolean not null default true,
  status text not null default 'never_run'
    check (status in ('never_run', 'ok', 'error', 'blocked', 'disabled')),
  last_run_at timestamptz,
  last_success_at timestamptz,
  last_jobs_found integer not null default 0 check (last_jobs_found >= 0),
  consecutive_failures integer not null default 0 check (consecutive_failures >= 0),
  last_error text check (char_length(last_error) <= 500),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- jobs: shared public-listing data, deduplicated across sources
-- ---------------------------------------------------------------------
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  source_name text not null,
  source_job_id text,
  canonical_url text not null unique check (char_length(canonical_url) <= 2000),
  dedupe_key text not null unique check (char_length(dedupe_key) = 40),
  company text not null check (char_length(company) <= 200),
  title text not null check (char_length(title) <= 300),
  normalized_company text not null,
  normalized_title text not null,
  location text not null default '' check (char_length(location) <= 300),
  is_remote boolean not null default false,
  is_internship boolean not null default false,
  role_category text not null default 'Other'
    check (role_category in ('SDE', 'Quant', 'Analyst', 'ML', 'DataScience', 'Research', 'Other')),
  description text not null default '' check (char_length(description) <= 20000),
  apply_url text not null check (char_length(apply_url) <= 2000),
  posted_at timestamptz,
  stipend_text text check (char_length(stipend_text) <= 300),
  stipend_min_inr integer check (stipend_min_inr is null or stipend_min_inr >= 0),
  stipend_status text not null default 'not_verified'
    check (stipend_status in ('verified', 'not_verified', 'unpaid')),
  is_active boolean not null default true,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  duplicate_urls text[] not null default '{}'
);
create index if not exists jobs_active_seen_idx on public.jobs (is_active, last_seen_at desc);
create index if not exists jobs_role_idx on public.jobs (role_category);

-- ---------------------------------------------------------------------
-- job_scores: per-user, versioned, transparent scoring output
-- ---------------------------------------------------------------------
create table if not exists public.job_scores (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  job_id uuid not null references public.jobs (id) on delete cascade,
  score integer not null check (score between 0 and 100),
  band text not null check (band in ('Excellent', 'Good', 'Moderate', 'Low')),
  method text not null check (method in ('deterministic', 'hybrid_gemini')),
  scoring_version text not null check (char_length(scoring_version) <= 20),
  reasoning jsonb not null default '{}'::jsonb check (jsonb_typeof(reasoning) = 'object'),
  flags text[] not null default '{}',
  best_resume_tag text check (best_resume_tag in ('SDE', 'Quant', 'Analyst', 'ML')),
  created_at timestamptz not null default now(),
  unique (user_id, job_id, scoring_version)
);
create index if not exists job_scores_user_score_idx on public.job_scores (user_id, score desc);

-- ---------------------------------------------------------------------
-- applications: the human-approval queue. The app never submits forms.
-- ---------------------------------------------------------------------
create table if not exists public.applications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  job_id uuid not null references public.jobs (id) on delete cascade,
  status text not null default 'pending_review'
    check (status in ('pending_review', 'approved_manual', 'opened', 'applied',
                      'interview', 'offer', 'rejected', 'withdrawn')),
  score integer check (score between 0 and 100),
  resume_id uuid references public.resumes (id) on delete set null,
  cover_letter text not null default '' check (char_length(cover_letter) <= 20000),
  form_answers jsonb not null default '[]'::jsonb check (jsonb_typeof(form_answers) = 'array'),
  form_schema jsonb check (form_schema is null or jsonb_typeof(form_schema) = 'object'),
  unknown_fields text[] not null default '{}',
  notes text not null default '' check (char_length(notes) <= 2000),
  draft_generated_at timestamptz,
  opened_at timestamptz,
  applied_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, job_id)
);
create index if not exists applications_user_status_idx on public.applications (user_id, status);

drop trigger if exists applications_touch on public.applications;
create trigger applications_touch before update on public.applications
  for each row execute function public.touch_updated_at();

create table if not exists public.application_events (
  id uuid primary key default gen_random_uuid(),
  application_id uuid not null references public.applications (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  from_status text,
  to_status text not null,
  note text not null default '' check (char_length(note) <= 500),
  created_at timestamptz not null default now()
);
create index if not exists application_events_app_idx
  on public.application_events (application_id, created_at);

-- ---------------------------------------------------------------------
-- pipeline_runs: audit log for every scheduled or manual run
-- ---------------------------------------------------------------------
create table if not exists public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  trigger text not null default 'schedule' check (char_length(trigger) <= 40),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running', 'success', 'partial', 'failed')),
  stats jsonb not null default '{}'::jsonb check (jsonb_typeof(stats) = 'object'),
  errors jsonb not null default '[]'::jsonb check (jsonb_typeof(errors) = 'array')
);

-- ---------------------------------------------------------------------
-- ai_usage_daily: Gemini quota guard (service role only)
-- ---------------------------------------------------------------------
create table if not exists public.ai_usage_daily (
  day date primary key,
  calls integer not null default 0 check (calls >= 0),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.resumes enable row level security;
alter table public.job_sources enable row level security;
alter table public.jobs enable row level security;
alter table public.job_scores enable row level security;
alter table public.applications enable row level security;
alter table public.application_events enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.ai_usage_daily enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select to authenticated using (id = (select auth.uid()));

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
  for insert to authenticated with check (id = (select auth.uid()));

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

drop policy if exists "resumes_all_own" on public.resumes;
create policy "resumes_all_own" on public.resumes
  for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "applications_all_own" on public.applications;
create policy "applications_all_own" on public.applications
  for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "application_events_select_own" on public.application_events;
create policy "application_events_select_own" on public.application_events
  for select to authenticated using (user_id = (select auth.uid()));

drop policy if exists "application_events_insert_own" on public.application_events;
create policy "application_events_insert_own" on public.application_events
  for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and exists (
      select 1 from public.applications a
      where a.id = application_id and a.user_id = (select auth.uid())
    )
  );

drop policy if exists "job_scores_select_own" on public.job_scores;
create policy "job_scores_select_own" on public.job_scores
  for select to authenticated using (user_id = (select auth.uid()));

drop policy if exists "jobs_select_authenticated" on public.jobs;
create policy "jobs_select_authenticated" on public.jobs
  for select to authenticated using (true);

drop policy if exists "job_sources_select_authenticated" on public.job_sources;
create policy "job_sources_select_authenticated" on public.job_sources
  for select to authenticated using (true);

drop policy if exists "pipeline_runs_select_authenticated" on public.pipeline_runs;
create policy "pipeline_runs_select_authenticated" on public.pipeline_runs
  for select to authenticated using (true);

-- No policies on ai_usage_daily: service role only.
revoke all on public.ai_usage_daily from anon, authenticated;
revoke all on public.pipeline_runs from anon, authenticated;
grant select on public.pipeline_runs to authenticated;

-- ---------------------------------------------------------------------
-- Auto-create a profile for every new auth user
-- ---------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    coalesce(new.email, ''),
    coalesce(new.raw_user_meta_data ->> 'full_name', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------
-- Storage: private 'resumes' bucket, each user confined to their own folder
-- ---------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes', 'resumes', false, 5242880, array['application/pdf'])
on conflict (id) do update
  set public = false,
      file_size_limit = 5242880,
      allowed_mime_types = array['application/pdf'];

drop policy if exists "resume_files_select_own" on storage.objects;
create policy "resume_files_select_own" on storage.objects
  for select to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "resume_files_insert_own" on storage.objects;
create policy "resume_files_insert_own" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "resume_files_delete_own" on storage.objects;
create policy "resume_files_delete_own" on storage.objects
  for delete to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
