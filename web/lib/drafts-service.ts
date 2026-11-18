import type { SupabaseClient } from "@supabase/supabase-js";
import { TAG_FALLBACK } from "./constants";
import { buildDraft } from "./drafts";
import { parseFilters } from "./filters";
import type { ApplicationRow, JobRow, ProfileRow, ResumeRow, RoleCategory } from "./types";

/** Best resume for a role: the tag preference order, default first, then any default. */
export function pickResume(resumes: ResumeRow[], role: RoleCategory): ResumeRow | null {
  for (const tag of TAG_FALLBACK[role] ?? ["SDE"]) {
    const match = resumes.find((r) => r.tag === tag && r.is_default) ?? resumes.find((r) => r.tag === tag);
    if (match) return match;
  }
  return resumes.find((r) => r.is_default) ?? resumes[0] ?? null;
}

/** Generates the draft once. Idempotent: returns immediately when a draft already exists. */
export async function ensureDraft(
  supabase: SupabaseClient,
  userId: string,
  application: ApplicationRow,
  job: JobRow,
): Promise<void> {
  if (application.draft_generated_at) return;
  const [profileRes, resumesRes] = await Promise.all([
    supabase.from("profiles").select("*").eq("id", userId).maybeSingle(),
    supabase.from("resumes").select("id, tag, label, file_name, storage_path, is_default, created_at").eq("user_id", userId),
  ]);
  const profile = profileRes.data as ProfileRow | null;
  if (!profile) return;
  const resumes = (resumesRes.data ?? []) as ResumeRow[];
  const resume =
    resumes.find((r) => r.id === application.resume_id) ?? pickResume(resumes, job.role_category);
  const schema = application.form_schema;
  const formSchema = schema && schema.status === "inspected" && Array.isArray(schema.fields) ? schema.fields : null;

  const draft = buildDraft({
    profile,
    job,
    resume,
    formSchema,
    filters: parseFilters(profile.filters),
  });

  await supabase
    .from("applications")
    .update({
      cover_letter: draft.coverLetter,
      form_answers: draft.formAnswers,
      unknown_fields: draft.unknownFields,
      resume_id: resume?.id ?? null,
      draft_generated_at: new Date().toISOString(),
    })
    .eq("id", application.id)
    .eq("user_id", userId);
}

/** Ensures drafts exist for every pending application, so the queue is ready when the user opens it. */
export async function ensurePendingDrafts(supabase: SupabaseClient, userId: string): Promise<void> {
  const { data } = await supabase
    .from("applications")
    .select("*, jobs(*)")
    .eq("user_id", userId)
    .in("status", ["pending_review", "approved_manual"])
    .is("draft_generated_at", null);
  for (const row of data ?? []) {
    const { jobs, ...application } = row as ApplicationRow & { jobs: JobRow };
    await ensureDraft(supabase, userId, application as ApplicationRow, jobs);
  }
}
