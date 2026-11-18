import { notFound } from "next/navigation";
import { z } from "zod";
import { saveApplication, setResume, setStatus } from "@/app/actions/applications";
import CopyButton from "@/components/CopyButton";
import { Flag, ScoreBadge, StatusBadge } from "@/components/Badges";
import { requireUser } from "@/lib/auth";
import { SCORING_VERSION } from "@/lib/constants";
import { ensureDraft } from "@/lib/drafts-service";
import { formatDate } from "@/lib/format";
import type { ApplicationRow, FormAnswer, JobRow, ResumeRow, ScoreReasoning } from "@/lib/types";

export const dynamic = "force-dynamic";

const SOURCE_LABEL: Record<FormAnswer["source"], string> = {
  profile: "From your profile",
  settings: "From settings, confirm",
  draft: "Drafted",
  resume_upload: "Upload needed",
  human_required: "Your answer",
};

type Joined = ApplicationRow & { jobs: JobRow };

export default async function PendingDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { saved?: string };
}) {
  const { supabase, user } = await requireUser();
  if (!z.string().uuid().safeParse(params.id).success) notFound();

  const load = () =>
    supabase.from("applications").select("*, jobs(*)").eq("id", params.id).eq("user_id", user.id).maybeSingle();
  let { data: row } = await load();
  if (!row) notFound();
  if (!row.draft_generated_at) {
    await ensureDraft(supabase, user.id, row as ApplicationRow, row.jobs as JobRow);
    ({ data: row } = await load());
  }
  const app = row as unknown as Joined;

  const [{ data: resumes }, { data: scoreRow }] = await Promise.all([
    supabase.from("resumes").select("id, tag, label, file_name, is_default, created_at").eq("user_id", user.id).order("created_at"),
    supabase
      .from("job_scores")
      .select("score, band, reasoning, flags")
      .eq("user_id", user.id)
      .eq("job_id", app.job_id)
      .eq("scoring_version", SCORING_VERSION)
      .maybeSingle(),
  ]);
  const resumeList = (resumes ?? []) as ResumeRow[];
  const reasoning = (scoreRow?.reasoning ?? {}) as ScoreReasoning;
  const components = Object.entries(reasoning.components ?? {});
  const job = app.jobs;
  const answers = app.form_answers ?? [];
  const copyAll = answers.map((a) => `${a.label}: ${a.answer ?? "(your answer)"}`).join("\n");
  const schemaStatus = app.form_schema?.status;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-xs text-zinc-500">{job.company} · {job.location}</div>
          <h1 className="h1 mt-0.5">{job.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            {scoreRow ? <ScoreBadge score={scoreRow.score} band={scoreRow.band} /> : null}
            <StatusBadge status={app.status} />
            {app.applied_at ? <span className="pill">Submitted by you {formatDate(app.applied_at)}</span> : null}
          </div>
        </div>
        <div className="flex flex-col items-stretch gap-2">
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="btn btn-primary">
            Open application ↗
          </a>
          <p className="max-w-[16rem] text-xs text-zinc-500">
            Opens the company&apos;s own page. You fill in and submit the form there.
          </p>
        </div>
      </header>

      {searchParams.saved ? (
        <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Saved.</p>
      ) : null}

      {app.unknown_fields.length ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="font-medium">Needs your input before you open the form</div>
          <div className="mt-1 text-xs">{app.unknown_fields.join(" · ")}</div>
          <div className="mt-2 text-xs">Anything marked &quot;[ADD ...]&quot; is a placeholder you must replace. Nothing is guessed for you.</div>
        </section>
      ) : null}

      <section className="grid gap-6 md:grid-cols-2">
        <div className="card">
          <h2 className="h2">Why this match</h2>
          {components.length ? (
            <ul className="mt-3 space-y-1.5 text-sm">
              {components.map(([key, value]) => (
                <li key={key} className="flex justify-between gap-3">
                  <span className="capitalize text-zinc-700">{key.replace("_", " ")}</span>
                  <span className="tabular-nums text-zinc-500">{value.points}/{value.max}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-zinc-600">Score details are not available for this listing.</p>
          )}
          {reasoning.matched_skills?.length ? (
            <p className="mt-3 text-xs text-zinc-600">Matched skills: {reasoning.matched_skills.join(", ")}</p>
          ) : null}
          {reasoning.ai ? (
            <div className="mt-3 border-t border-zinc-100 pt-3 text-sm">
              <p className="text-zinc-700">{reasoning.ai.summary}</p>
              {reasoning.ai.gaps.length ? <p className="mt-1 text-xs text-zinc-500">Gaps: {reasoning.ai.gaps.join("; ")}</p> : null}
            </div>
          ) : null}
        </div>

        <div className="card space-y-3">
          <h2 className="h2">Resume and form status</h2>
          <form action={setResume} className="space-y-2">
            <input type="hidden" name="id" value={app.id} />
            <label className="label" htmlFor="resume_id">Resume to attach</label>
            <div className="flex gap-2">
              <select id="resume_id" name="resume_id" defaultValue={app.resume_id ?? ""} className="input">
                <option value="">None selected</option>
                {resumeList.map((r) => (
                  <option key={r.id} value={r.id}>{r.tag} · {r.label}{r.is_default ? " (default)" : ""}</option>
                ))}
              </select>
              <button type="submit" className="btn">Set</button>
            </div>
            {resumeList.length === 0 ? (
              <p className="text-xs text-amber-700">No resume uploaded yet. Add one in My Profile.</p>
            ) : null}
          </form>
          <p className="text-xs text-zinc-600">
            {schemaStatus === "inspected"
              ? `Form read on ${formatDate(app.form_schema?.inspected_at ?? null)}: ${app.form_schema?.fields.length ?? 0} fields.`
              : schemaStatus === "challenge_detected"
                ? "This site shows a CAPTCHA. Fill the form yourself."
                : "Form not read yet. Answers use the standard field set."}
          </p>
        </div>
      </section>

      <form action={saveApplication} className="card space-y-5">
        <input type="hidden" name="id" value={app.id} />
        <section>
          <div className="flex items-center justify-between gap-3">
            <h2 className="h2">Cover letter</h2>
            <CopyButton value={app.cover_letter} label="Copy saved letter" />
          </div>
          <textarea name="cover_letter" defaultValue={app.cover_letter} rows={14} className="input mt-2 font-mono text-[13px] leading-relaxed" />
        </section>

        <section>
          <div className="flex items-center justify-between gap-3">
            <h2 className="h2">Form answers</h2>
            <CopyButton value={copyAll} label="Copy all answers" />
          </div>
          <div className="mt-2 divide-y divide-zinc-100">
            {answers.map((a, index) => (
              <div key={`${a.key}-${index}`} className="grid gap-2 py-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto] md:items-start">
                <div>
                  <div className="text-sm font-medium">
                    {a.label}
                    {a.required ? <span className="text-red-600"> *</span> : null}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {a.needs_human ? <Flag>Needs you</Flag> : <span className="pill">{SOURCE_LABEL[a.source]}</span>}
                    <span className="pill">{a.type}</span>
                  </div>
                </div>
                {a.type === "file" ? (
                  <p className="text-xs text-zinc-500">Upload your resume on the company page.</p>
                ) : a.type === "textarea" || (a.answer ?? "").length > 90 ? (
                  <textarea name={`answer_${index}`} defaultValue={a.answer ?? ""} rows={3} className="input" />
                ) : (
                  <input name={`answer_${index}`} defaultValue={a.answer ?? ""} className="input" />
                )}
                <div>
                  <CopyButton value={a.answer ?? ""} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <label className="label" htmlFor="notes">Private notes</label>
          <textarea id="notes" name="notes" defaultValue={app.notes} rows={2} className="input" />
        </section>

        <div className="flex justify-end">
          <button type="submit" className="btn btn-primary">Save draft</button>
        </div>
      </form>

      <section className="card space-y-3">
        <h2 className="h2">Decide</h2>
        <p className="text-xs text-zinc-600">
          Every change here is recorded by you. InternshipPilot never clicks submit on any site.
        </p>
        <div className="flex flex-wrap gap-2">
          <form action={setStatus}>
            <input type="hidden" name="id" value={app.id} />
            <input type="hidden" name="status" value="approved_manual" />
            <button type="submit" className="btn" disabled={app.status === "approved_manual"}>
              Approve for manual submit
            </button>
          </form>
          <form action={setStatus}>
            <input type="hidden" name="id" value={app.id} />
            <input type="hidden" name="status" value="opened" />
            <button type="submit" className="btn">I opened the form</button>
          </form>
          <form action={setStatus}>
            <input type="hidden" name="id" value={app.id} />
            <input type="hidden" name="status" value="applied" />
            <button type="submit" className="btn btn-primary">I submitted it myself</button>
          </form>
          <form action={setStatus}>
            <input type="hidden" name="id" value={app.id} />
            <input type="hidden" name="status" value="withdrawn" />
            <button type="submit" className="btn">Not interested</button>
          </form>
        </div>
      </section>
    </div>
  );
}
