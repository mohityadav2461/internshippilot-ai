import { saveFilters } from "@/app/actions/profile";
import { signOut } from "@/app/actions/auth";
import { requireUser } from "@/lib/auth";
import { ROLE_OPTIONS } from "@/lib/constants";
import { parseFilters } from "@/lib/filters";
import { formatDateTime } from "@/lib/format";
import type { RoleCategory } from "@/lib/types";

export const dynamic = "force-dynamic";

const ERRORS: Record<string, string> = {
  invalid: "Some filter values are out of range. Check them and save again.",
};

export default async function SettingsPage({ searchParams }: { searchParams: { saved?: string; error?: string } }) {
  const { supabase, user } = await requireUser();
  const [profileRes, runRes] = await Promise.all([
    supabase.from("profiles").select("filters, ai_consent").eq("id", user.id).maybeSingle(),
    supabase
      .from("pipeline_runs")
      .select("status, started_at, stats")
      .eq("trigger", "score")
      .order("started_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
  ]);
  const filters = parseFilters(profileRes.data?.filters);
  const aiConsent = profileRes.data?.ai_consent === true;
  const lastScore = runRes.data as { status: string; started_at: string; stats: Record<string, unknown> } | null;
  const aiActive = lastScore?.stats?.ai_enabled === true;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <h1 className="h1">Settings</h1>
        <p className="mt-1 text-sm text-zinc-600">Strict filters decide what appears in your queue. Defaults follow the brief.</p>
      </header>

      {searchParams.saved ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Settings saved. Changes apply on the next run, and Find Internships updates now.</p> : null}
      {searchParams.error && ERRORS[searchParams.error] ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{ERRORS[searchParams.error]}</p>
      ) : null}

      <form action={saveFilters} className="card space-y-6">
        <section className="space-y-4">
          <h2 className="h2">Strict filters</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="label" htmlFor="min_stipend_inr">Minimum stipend (Rs per month)</label>
              <input id="min_stipend_inr" name="min_stipend_inr" type="number" min={0} step={500} defaultValue={filters.min_stipend_inr} className="input" />
            </div>
            <div>
              <label className="label" htmlFor="locations">Locations (within India, comma separated)</label>
              <input id="locations" name="locations" defaultValue={filters.locations.join(", ")} className="input" />
            </div>
            <div>
              <label className="label" htmlFor="target_start">Target start</label>
              <input id="target_start" name="target_start" defaultValue={filters.target_start} className="input" />
            </div>
            <div>
              <label className="label" htmlFor="duration_months">Duration in months</label>
              <input id="duration_months" name="duration_months" defaultValue={filters.duration_months} className="input" />
            </div>
            <div>
              <label className="label" htmlFor="min_score_to_show">Show matches scoring at least</label>
              <input id="min_score_to_show" name="min_score_to_show" type="number" min={0} max={100} defaultValue={filters.min_score_to_show} className="input" />
            </div>
            <div>
              <label className="label" htmlFor="auto_queue_score">Auto-queue for review at or above</label>
              <input id="auto_queue_score" name="auto_queue_score" type="number" min={50} max={100} defaultValue={filters.auto_queue_score} className="input" />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="allow_stipend_unverified" defaultChecked={filters.allow_stipend_unverified} />
            Include internships whose stipend is not disclosed (they are flagged &quot;Stipend not verified&quot;)
          </label>
          <p className="text-xs text-zinc-500">Internships only, always. Remote roles outside India are excluded.</p>
        </section>

        <section className="space-y-2">
          <h2 className="h2">Target roles</h2>
          <div className="grid gap-2 md:grid-cols-2">
            {ROLE_OPTIONS.map((option) => (
              <label key={option.value} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  name="roles"
                  value={option.value}
                  defaultChecked={filters.roles.includes(option.value as RoleCategory)}
                />
                {option.label}
              </label>
            ))}
          </div>
        </section>

        <section className="space-y-2 border-t border-zinc-100 pt-5">
          <h2 className="h2">AI assistance (optional)</h2>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" name="ai_consent" defaultChecked={aiConsent} className="mt-1" />
            <span>
              Allow Gemini to refine scores for my strongest matches. Only skills, projects, and the posting text are sent. Your name,
              email, phone, links, and resume text are never sent. Turning this off keeps scoring fully deterministic.
            </span>
          </label>
          <p className="text-xs text-zinc-500">
            Last scoring run: {lastScore ? `${formatDateTime(lastScore.started_at)} · AI ${aiActive ? "active" : "off"}` : "no run yet"}.
          </p>
        </section>

        <div className="flex justify-end">
          <button type="submit" className="btn btn-primary">Save settings</button>
        </div>
      </form>

      <section className="card flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="h2">Session</h2>
          <p className="mt-1 text-xs text-zinc-600">Signed in as {user.email}</p>
        </div>
        <form action={signOut}>
          <button type="submit" className="btn">Sign out</button>
        </form>
      </section>
    </div>
  );
}
