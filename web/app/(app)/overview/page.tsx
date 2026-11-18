import Link from "next/link";
import { Flag, ScoreBadge, StipendFlag } from "@/components/Badges";
import { requireUser } from "@/lib/auth";
import { SCORING_VERSION } from "@/lib/constants";
import { parseFilters } from "@/lib/filters";
import { formatDateTime } from "@/lib/format";
import { getOnboardingChecklist } from "@/lib/onboarding";
import type { JobRow, ScoreRow } from "@/lib/types";

export const dynamic = "force-dynamic";

type TopMatch = ScoreRow & { jobs: JobRow };

interface SourceHealth {
  name: string;
  adapter: string;
  enabled: boolean;
  status: string;
  last_success_at: string | null;
  last_error: string | null;
  last_jobs_found: number;
}

interface RunRow {
  status: string;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  stats: Record<string, unknown>;
}

export default async function OverviewPage() {
  const { supabase, user } = await requireUser();
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  const [checklist, profileRes, appsRes, scoresRes, sourcesRes, runRes, freshRes] = await Promise.all([
    getOnboardingChecklist(supabase, user.id),
    supabase.from("profiles").select("filters").eq("id", user.id).maybeSingle(),
    supabase.from("applications").select("status"),
    supabase
      .from("job_scores")
      .select("id, job_id, score, band, method, reasoning, flags, best_resume_tag, created_at, jobs(*)")
      .eq("scoring_version", SCORING_VERSION)
      .order("score", { ascending: false })
      .limit(25),
    supabase
      .from("job_sources")
      .select("name, adapter, enabled, status, last_success_at, last_error, last_jobs_found")
      .order("name"),
    supabase
      .from("pipeline_runs")
      .select("status, trigger, started_at, finished_at, stats")
      .order("started_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("job_scores")
      .select("id", { count: "exact", head: true })
      .eq("scoring_version", SCORING_VERSION)
      .gte("created_at", since),
  ]);

  const filters = parseFilters(profileRes.data?.filters);
  const apps = appsRes.data ?? [];
  const countOf = (...statuses: string[]) => apps.filter((a) => statuses.includes(a.status)).length;
  const pending = countOf("pending_review", "approved_manual");
  const submitted = countOf("applied", "opened");
  const interviews = countOf("interview", "offer");

  const top = ((scoresRes.data ?? []) as unknown as TopMatch[])
    .filter((s) => s.jobs && s.score >= filters.min_score_to_show)
    .slice(0, 5);
  const sources = (sourcesRes.data ?? []) as SourceHealth[];
  const run = runRes.data as RunRow | null;
  const aiActive = run?.trigger === "score" ? run.stats?.ai_enabled === true : null;

  const stats = [
    { label: "New matches (24h)", value: freshRes.count ?? 0 },
    { label: "Pending review", value: pending },
    { label: "Submitted by you", value: submitted },
    { label: "Interviews or offers", value: interviews },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="h1">Overview</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Summer 2027 internships in India, scored against your profile. Nothing is submitted without your review.
        </p>
      </header>

      {!checklist.complete ? (
        <section className="card">
          <h2 className="h2">Finish onboarding to start matching</h2>
          <ul className="mt-3 space-y-1 text-sm">
            <li>{checklist.hasName ? "Done" : "To do"}: add your full name in My Profile</li>
            <li>{checklist.hasSkills ? "Done" : "To do"}: list at least three skills</li>
            <li>{checklist.hasResume ? "Done" : "To do"}: upload at least one resume PDF</li>
          </ul>
          <Link href="/profile" className="btn btn-primary mt-4">Go to My Profile</Link>
        </section>
      ) : null}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="card py-4">
            <div className="text-xs text-zinc-500">{stat.label}</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">{stat.value}</div>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h2 className="h2">Top matches</h2>
          <Link href="/find" className="text-sm text-zinc-600 underline underline-offset-4">View all</Link>
        </div>
        {top.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-600">
            No matches yet. The daily run scores new listings once your profile is complete.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-zinc-100">
            {top.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
                <ScoreBadge score={item.score} band={item.band} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{item.jobs.title}</div>
                  <div className="truncate text-xs text-zinc-500">
                    {item.jobs.company}{item.jobs.location ? ` · ${item.jobs.location}` : ""}
                  </div>
                </div>
                <StipendFlag status={item.jobs.stipend_status} minInr={item.jobs.stipend_min_inr} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2 className="h2">Source health</h2>
        <p className="mt-1 text-xs text-zinc-500">
          A source that fails repeatedly is disabled automatically. Its last error is shown so you can fix it.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-zinc-500">
              <tr>
                <th className="py-2 font-medium">Source</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Last success</th>
                <th className="py-2 font-medium">Jobs</th>
                <th className="py-2 font-medium">Last error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {sources.map((source) => (
                <tr key={source.name}>
                  <td className="py-2 pr-3 font-mono text-xs">{source.name}</td>
                  <td className="py-2 pr-3">
                    {source.enabled ? <span className="pill">{source.status}</span> : <Flag>disabled</Flag>}
                  </td>
                  <td className="py-2 pr-3 text-xs text-zinc-600">{formatDateTime(source.last_success_at)}</td>
                  <td className="py-2 pr-3 tabular-nums">{source.last_jobs_found}</td>
                  <td className="max-w-xs truncate py-2 text-xs text-zinc-500">{source.last_error ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card text-sm text-zinc-600">
        <h2 className="h2">Last pipeline run</h2>
        {run ? (
          <p className="mt-2">
            {run.status} · {run.trigger} · started {formatDateTime(run.started_at)}
            {" · "}new jobs {String(run.stats?.new ?? "-")}
            {" · "}AI scoring {aiActive === null ? "not run yet" : aiActive ? "enabled" : "off (deterministic only)"}
          </p>
        ) : (
          <p className="mt-2">No runs yet. The first run happens at 09:00 IST, or trigger it manually in GitHub Actions.</p>
        )}
      </section>
    </div>
  );
}
