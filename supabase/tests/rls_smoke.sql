-- =====================================================================
-- RLS and constraint smoke tests. Run against a database where
-- local_stubs.sql, 0001_init.sql and seed/job_sources.sql have been applied.
-- Every check raises an exception on failure, so a clean run exits 0.
-- =====================================================================
\set ON_ERROR_STOP on
begin;

create or replace function pg_temp.as_user(uid uuid) returns void
language sql as $$
  select set_config('request.jwt.claims', json_build_object('sub', uid, 'role', 'authenticated')::text, true),
         set_config('role', 'authenticated', true)
$$;

create or replace function pg_temp.as_anon() returns void
language sql as $$
  select set_config('request.jwt.claims', '{"role":"anon"}', true),
         set_config('role', 'anon', true)
$$;

create or replace function pg_temp.as_admin() returns void
language sql as $$
  select set_config('role', 'none', true)
$$;

-- Runs a statement that must be refused by RLS, a grant, or a constraint.
create or replace function pg_temp.expect_denied(stmt text, label text) returns void
language plpgsql as $$
begin
  execute stmt;
  raise exception 'FAIL (expected denial, but it succeeded): %', label;
exception
  when insufficient_privilege or check_violation or unique_violation or raise_exception then
    if sqlstate = 'P0001' and sqlerrm like 'FAIL%' then raise; end if;
    raise notice 'ok (denied): %', label;
end $$;

-- Runs a statement that must affect exactly the expected number of rows.
create or replace function pg_temp.expect_rows(stmt text, expected int, label text) returns void
language plpgsql as $$
declare n int;
begin
  execute stmt;
  get diagnostics n = row_count;
  if n <> expected then
    raise exception 'FAIL (% rows, expected %): %', n, expected, label;
  end if;
  raise notice 'ok (% rows): %', n, label;
end $$;

-- ---------- fixtures (as owner, bypassing RLS) ----------
select pg_temp.as_admin();
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'alice@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'bob@example.test');

do $$
begin
  if (select count(*) from public.profiles) <> 2 then
    raise exception 'FAIL: signup trigger did not create both profiles';
  end if;
  raise notice 'ok: signup trigger created a profile per auth user';
end $$;

insert into public.jobs (source_name, canonical_url, dedupe_key, company, title, normalized_company,
  normalized_title, location, is_internship, role_category, apply_url, stipend_status)
values ('greenhouse:test', 'https://boards.greenhouse.io/acme/jobs/1', repeat('a', 40), 'Acme', 'SDE Intern',
  'acme', 'sde intern', 'Bengaluru, India', true, 'SDE', 'https://boards.greenhouse.io/acme/jobs/1', 'verified');

insert into public.resumes (user_id, tag, file_name, storage_path, is_default)
values ('11111111-1111-1111-1111-111111111111', 'SDE', 'a.pdf', '11111111-1111-1111-1111-111111111111/r1.pdf', true);

-- ---------- Alice (authenticated) ----------
select pg_temp.as_user('11111111-1111-1111-1111-111111111111');
select pg_temp.expect_rows($q$select id from public.profiles$q$, 1, 'alice sees only her profile');
select pg_temp.expect_rows($q$update public.profiles set full_name = 'Alice' where id = '11111111-1111-1111-1111-111111111111'$q$, 1, 'alice updates her own profile');
select pg_temp.expect_rows($q$update public.profiles set full_name = 'Hacked' where id = '22222222-2222-2222-2222-222222222222'$q$, 0, 'alice cannot update bob profile');
select pg_temp.expect_denied($q$insert into public.profiles (id, email) values ('33333333-3333-3333-3333-333333333333', 'x@y.test')$q$, 'alice cannot insert a profile for someone else');
select pg_temp.expect_rows($q$select id from public.jobs$q$, 1, 'authenticated users can read shared job listings');
select pg_temp.expect_denied($q$insert into public.jobs (source_name, canonical_url, dedupe_key, company, title, normalized_company, normalized_title, apply_url) values ('x','https://e.test/1',repeat('b',40),'X','Y','x','y','https://e.test/1')$q$, 'users cannot write job listings');
select pg_temp.expect_denied($q$insert into public.job_scores (user_id, job_id, score, band, method, scoring_version) select '11111111-1111-1111-1111-111111111111', id, 99, 'Excellent', 'deterministic', 'v1' from public.jobs$q$, 'users cannot write scores directly');
select pg_temp.expect_rows($q$insert into public.applications (user_id, job_id) select '11111111-1111-1111-1111-111111111111', id from public.jobs$q$, 1, 'alice can queue her own application');
select pg_temp.expect_denied($q$insert into public.applications (user_id, job_id) select '22222222-2222-2222-2222-222222222222', id from public.jobs$q$, 'alice cannot create an application for bob');
select pg_temp.expect_rows($q$update public.applications set status = 'applied' where user_id = '11111111-1111-1111-1111-111111111111'$q$, 1, 'alice records her manual submission');
select pg_temp.expect_denied($q$insert into public.application_events (application_id, user_id, to_status) select id, '22222222-2222-2222-2222-222222222222', 'applied' from public.applications$q$, 'events cannot be written for another user');
select pg_temp.expect_denied($q$select * from public.ai_usage_daily$q$, 'alice cannot read the AI quota ledger');
select pg_temp.expect_denied($q$insert into public.pipeline_runs (trigger) values ('forged')$q$, 'alice cannot forge pipeline runs');
select pg_temp.expect_rows($q$select id from public.resumes$q$, 1, 'alice sees only her resumes');
select pg_temp.expect_denied($q$insert into public.resumes (user_id, tag, file_name, storage_path) values ('22222222-2222-2222-2222-222222222222', 'ML', 'b.pdf', 'x/y.pdf')$q$, 'alice cannot attach a resume to bob');
select pg_temp.expect_denied($q$insert into public.resumes (user_id, tag, file_name, storage_path, is_default) values ('11111111-1111-1111-1111-111111111111', 'SDE', 'dup.pdf', 'x/dup.pdf', true)$q$, 'only one default resume per tag');
select pg_temp.expect_denied($q$insert into public.resumes (user_id, tag, file_name, storage_path) values ('11111111-1111-1111-1111-111111111111', 'Marketing', 'z.pdf', 'x/z.pdf')$q$, 'resume tag is restricted to the vault set');
select pg_temp.expect_rows($q$insert into storage.objects (bucket_id, name, owner) values ('resumes', '11111111-1111-1111-1111-111111111111/new.pdf', '11111111-1111-1111-1111-111111111111')$q$, 1, 'alice can upload into her own storage folder');
select pg_temp.expect_denied($q$insert into storage.objects (bucket_id, name, owner) values ('resumes', '22222222-2222-2222-2222-222222222222/evil.pdf', '11111111-1111-1111-1111-111111111111')$q$, 'alice cannot upload into bobs folder');
select pg_temp.expect_rows($q$select id from storage.objects where bucket_id = 'resumes'$q$, 1, 'alice sees only objects in her folder');

-- ---------- anonymous visitors ----------
select pg_temp.as_anon();
-- RLS filters SELECT silently, so an anonymous read returns zero rows rather than an error.
select pg_temp.expect_rows($q$select id from public.profiles$q$, 0, 'anon sees no profiles');
select pg_temp.expect_rows($q$select id from public.jobs$q$, 0, 'anon sees no job listings');
select pg_temp.expect_rows($q$select id from public.applications$q$, 0, 'anon sees no applications');

-- ---------- Bob sees nothing of Alice ----------
select pg_temp.as_user('22222222-2222-2222-2222-222222222222');
select pg_temp.expect_rows($q$select id from public.applications$q$, 0, 'bob cannot see alice applications');
select pg_temp.expect_rows($q$select id from public.resumes$q$, 0, 'bob cannot see alice resumes');

-- ---------- service role (pipeline) ----------
select pg_temp.as_admin();
set local role service_role;
select pg_temp.expect_rows($q$insert into public.job_scores (user_id, job_id, score, band, method, scoring_version) select '11111111-1111-1111-1111-111111111111', id, 80, 'Good', 'deterministic', 'v1' from public.jobs$q$, 1, 'service role writes scores');
select pg_temp.expect_rows($q$insert into public.ai_usage_daily (day, calls) values (current_date, 1)$q$, 1, 'service role writes the AI ledger');
reset role;

-- ---------- constraints ----------
select pg_temp.as_admin();
select pg_temp.expect_denied($q$insert into public.jobs (source_name, canonical_url, dedupe_key, company, title, normalized_company, normalized_title, apply_url, role_category) values ('x','https://e.test/2',repeat('c',40),'X','Y','x','y','https://e.test/2','Bogus')$q$, 'role category is constrained');
select pg_temp.expect_denied($q$insert into public.job_scores (user_id, job_id, score, band, method, scoring_version) select '11111111-1111-1111-1111-111111111111', id, 101, 'Excellent', 'deterministic', 'v1' from public.jobs$q$, 'score must be between 0 and 100');
insert into auth.users (id, email) values ('55555555-5555-5555-5555-555555555555', 'h@x.test');
select pg_temp.expect_denied($q$update public.profiles set graduation_year = 1999 where id = '55555555-5555-5555-5555-555555555555'$q$, 'graduation year is bounded');

-- ---------- seed registry and idempotency ----------
do $$
declare total int; disabled int;
begin
  select count(*), count(*) filter (where not enabled) into total, disabled from public.job_sources;
  if total < 18 then raise exception 'FAIL: expected at least 18 seeded sources, found %', total; end if;
  if disabled < 4 then raise exception 'FAIL: aggregator sources must ship disabled, found % disabled', disabled; end if;
  raise notice 'ok: % sources seeded, % disabled by default', total, disabled;
end $$;

rollback;
\echo 'ALL RLS AND CONSTRAINT SMOKE TESTS PASSED (transaction rolled back)'
