import { addToPending } from "@/app/actions/applications";
import { Flag, ScoreBadge, StatusBadge, StipendFlag } from "@/components/Badges";
import { requireUser } from "@/lib/auth";
import { ROLE_OPTIONS, SCORING_VERSION } from "@/lib/constants";
import { parseFilters } from "@/lib/filters";
import { formatDate } from "@/lib/format";
import type { ApplicationStatus, JobRow, RoleCategory, ScoreReasoning, ScoreRow } from "@/lib/types";

export const dynamic = "force-dynamic";

type Row = Omit<ScoreRow, "created_at"> & { jobs: JobRow };

const ERRORS: Record<string, string> = {
  invalid: "That job could not be added. Refresh and try again.",
  missing: "That listing is no longer available.",
  save: "Could not add it to pending. Try again.",
};

export default async function FindPage({
  searchParams,
}: {
  searchParams: { min?: string; role?: string; stipend?: string; q?: string; error?: string };
}) {
  const { supabase, user } = await requireUser();
  const { data: profile } = await supabase.from("profiles").select("filters").eq("id", user.id).maybeSingle();
  const filters = parseFilters(profile?.filters);

  const minRaw = Number(searchParams.min);
  const minScore = Number.isFinite(minRaw) && searchParams.min !== undefined
    ? Math.max(0, Math.min(100, Math.round(minRaw)))
    : filters.min_score_to_show;
  const role = searchParams.role ?? "all";
  const stipend = searchParams.stipend ?? "all";
  const query = (searchParams.q ?? "").trim().toLowerCase().slice(0, 80);

  const [{ data: scores }, { data: applications }] = await Promise.all([
    supabase
      .from("job_scores")
      .select("id, job_id, score, band, method, reasoning, flags, best_resume_tag, jobs(*)")
      .eq("scoring_version", SCORING_VERSION)
      .gte("score", minScore)
      .order("score", { ascending: false })
      .limit(300),
    supabase.from("applications").select("id, job_id, status"),
  ]);

  const statusByJob = new Map<string, { id: string; status: ApplicationStatus }>();
  for (const app of applications ?? []) statusByJob.set(app.job_id, { id: app.id, status: app.status });

  const rows = ((scores ?? []) as unknown as Row[]).filter((row) => {
    if (!row.jobs) return false;
    if (role !== "all" && row.jobs.role_category !== role) return false;
    if (stipend === "verified" && row.jobs.stipend_status !== "verified") return false;
    if (stipend === "unverified" && row.jobs.stipend_status !== "not_verified") return false;
    if (query && !`${row.jobs.company} ${row.jobs.title}`.toLowerCase().includes(query)) return false;
    return true;
  });

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="h1">Find Internships</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Ranked by fit. Showing scores of {minScore} or higher. Adding a role to pending creates a draft for your review. It does not apply.
        </p>
      </header>

      {searchParams.error && ERRORS[searchParams.error] ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {ERRORS[searchParams.error]}
        </p>
      ) : null}

      <form method="get" className="card grid gap-3 md:grid-cols-[1fr_1fr_1fr_1fr_auto] md:items-end">
        <div>
          <label className="label" htmlFor="q">Search</label>
          <input id="q" name="q" defaultValue={searchParams.q ?? ""} placeholder="Company or role" className="input" />
        </div>
        <div>
          <label className="label" htmlFor="role">Role</label>
          <select id="role" name="role" defaultValue={role} className="input">
            <option value="all">All target roles</option>
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="stipend">Stipend</label>
          <select id="stipend" name="stipend" defaultValue={stipend} className="input">
            <option value="all">Any</option>
            <option value="verified">Verified only</option>
            <option value="unverified">Not verified only</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="min">Minimum score</label>
          <input id="min" name="min" type="number" min={0} max={100} defaultValue={minScore} className="input" />
        </div>
        <button type="submit" className="btn">Apply filters</button>
      </form>

      {rows.length === 0 ? (
        <p className="text-sm text-zinc-600">
          Nothing matches these filters yet. Try a lower minimum score, or widen the role filter in Settings.
        </p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => {
            const existing = statusByJob.get(row.job_id);
            const reasoning = (row.reasoning ?? {}) as ScoreReasoning;
            const components = reasoning.components ?? {};
            const matched = (reasoning.matched_skills ?? []).slice(0, 6);
            const roleLabel = ROLE_OPTIONS.find((o) => o.value === row.jobs.role_category)?.label.split(":")[0] ??
              (row.jobs.role_category as RoleCategory);
            return (
              <li key={row.id} className="card">
                <div className="flex flex-wrap items-start gap-3">
                  <ScoreBadge score={row.score} band={row.band} />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs text-zinc-500">{row.jobs.company}{row.jobs.location ? ` · ${row.jobs.location}` : ""}</div>
                    <h2 className="mt-0.5 text-base font-semibold">{row.jobs.title}</h2>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="pill">{roleLabel}</span>
                      <StipendFlag status={row.jobs.stipend_status} minInr={row.jobs.stipend_min_inr} />
                      {row.jobs.posted_at ? <span className="pill">Posted {formatDate(row.jobs.posted_at)}</span> : null}
                      {(row.flags ?? []).filter((f) => !f.startsWith("ai_fallback") && f !== "Stipend not verified").map((f) => (
                        <Flag key={f}>{f}</Flag>
                      ))}
                      {row.method === "hybrid_gemini" ? <span className="pill">AI-assisted score</span> : null}
                    </div>
                    {Object.keys(components).length ? (
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600">
                        {Object.entries(components).map(([key, value]) => (
                          <span key={key}>
                            <span className="capitalize">{key.replace("_", " ")}</span> {value.points}/{value.max}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {matched.length ? (
                      <div className="mt-2 text-xs text-zinc-600">Skills in this posting: {matched.join(", ")}</div>
                    ) : null}
                    {reasoning.ai?.summary ? (
                      <p className="mt-2 text-sm text-zinc-700">{reasoning.ai.summary}</p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <a href={row.jobs.apply_url} target="_blank" rel="noopener noreferrer" className="btn">
                      View listing
                    </a>
                    {existing ? (
                      <div className="flex flex-col items-end gap-1">
                        <StatusBadge status={existing.status} />
                        <a href={`/pending/${existing.id}`} className="text-xs text-zinc-600 underline underline-offset-4">
                          Open in pending
                        </a>
                      </div>
                    ) : (
                      <form action={addToPending}>
                        <input type="hidden" name="job_id" value={row.job_id} />
                        <button type="submit" className="btn btn-primary">Add to pending</button>
                      </form>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
