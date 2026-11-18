"""Static security checks: every table has RLS, no anon grants, and the service key never reaches the web app."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (ROOT / "supabase" / "migrations" / "0001_init.sql").read_text()
PUBLIC_LISTING_TABLES = {"jobs", "job_sources", "pipeline_runs"}


def test_every_public_table_has_rls_enabled():
    tables = re.findall(r"create table if not exists public\.(\w+)", MIGRATION)
    assert len(tables) >= 9
    for table in tables:
        assert f"alter table public.{table} enable row level security;" in MIGRATION, table


def test_no_policy_is_granted_to_anon():
    assert not re.search(r"to\s+anon", MIGRATION, re.IGNORECASE)


def test_only_listing_tables_are_readable_without_ownership_check():
    for match in re.finditer(r"create policy \"(\w+)\" on public\.(\w+)\s+for select to authenticated using \(true\)", MIGRATION):
        assert match.group(2) in PUBLIC_LISTING_TABLES, match.group(1)


def test_ai_ledger_is_service_role_only():
    assert not re.search(r"create policy \"\w+\" on public\.ai_usage_daily", MIGRATION)
    assert "revoke all on public.ai_usage_daily from anon, authenticated;" in MIGRATION


def test_service_role_key_never_referenced_by_web_app():
    web = ROOT / "web"
    offenders = []
    for path in web.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts or ".next" in path.parts:
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".mjs", ".json", ".env", ".md", ""}:
            continue
        if "SERVICE_ROLE" in path.read_text(errors="ignore").upper():
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"service role key must not appear in the web app: {offenders}"
