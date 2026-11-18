"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { APPLICATION_STATUSES, SCORING_VERSION } from "@/lib/constants";
import { requireUser } from "@/lib/auth";
import { ensureDraft } from "@/lib/drafts-service";
import type { ApplicationRow, FormAnswer, JobRow } from "@/lib/types";
import { str } from "@/lib/validation";
import type { SupabaseClient } from "@supabase/supabase-js";

const idSchema = z.string().uuid();

async function logEvent(
  supabase: SupabaseClient,
  userId: string,
  applicationId: string,
  from: string | null,
  to: string,
  note = "",
) {
  await supabase.from("application_events").insert({
    application_id: applicationId,
    user_id: userId,
    from_status: from,
    to_status: to,
    note,
  });
}

function revalidateQueue(applicationId?: string) {
  revalidatePath("/pending");
  if (applicationId) revalidatePath(`/pending/${applicationId}`);
  revalidatePath("/tracker");
  revalidatePath("/overview");
  revalidatePath("/find");
}

/** Adds a scored job to the human review queue. Never submits anything. */
export async function addToPending(formData: FormData) {
  const parsed = idSchema.safeParse(str(formData, "job_id", 60));
  if (!parsed.success) redirect("/find?error=invalid");
  const jobId = parsed.data;

  const { supabase, user } = await requireUser();
  const { data: existing } = await supabase
    .from("applications")
    .select("id")
    .eq("user_id", user.id)
    .eq("job_id", jobId)
    .maybeSingle();
  if (existing) redirect(`/pending/${existing.id}`);

  const [{ data: job }, { data: score }] = await Promise.all([
    supabase.from("jobs").select("*").eq("id", jobId).maybeSingle(),
    supabase
      .from("job_scores")
      .select("score")
      .eq("user_id", user.id)
      .eq("job_id", jobId)
      .eq("scoring_version", SCORING_VERSION)
      .maybeSingle(),
  ]);
  if (!job) redirect("/find?error=missing");

  const { data: created, error } = await supabase
    .from("applications")
    .insert({ user_id: user.id, job_id: jobId, status: "pending_review", score: score?.score ?? null })
    .select("*")
    .single();
  if (error || !created) redirect("/find?error=save");

  await logEvent(supabase, user.id, created.id, null, "pending_review", "Added to pending review");
  await ensureDraft(supabase, user.id, created as ApplicationRow, job as JobRow);
  revalidateQueue();
  redirect(`/pending/${created.id}`);
}

/** Saves the user's edits to the cover letter, form answers and notes. Re-derives the unknown-field list. */
export async function saveApplication(formData: FormData) {
  const parsed = idSchema.safeParse(str(formData, "id", 60));
  if (!parsed.success) return;
  const { supabase, user } = await requireUser();

  const { data: app } = await supabase
    .from("applications")
    .select("form_answers")
    .eq("id", parsed.data)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!app) return;

  const coverLetter = str(formData, "cover_letter", 20000);
  const existing = (app.form_answers ?? []) as FormAnswer[];
  const answers: FormAnswer[] = existing.map((item, index) => {
    const answer = str(formData, `answer_${index}`, 4000) || null;
    const needsHuman = answer === null || answer.includes("[ADD");
    return { ...item, answer, needs_human: needsHuman };
  });
  const unknown = answers.filter((a) => a.needs_human).map((a) => a.label);
  if (coverLetter.includes("[ADD")) unknown.push("Cover letter");

  await supabase
    .from("applications")
    .update({
      cover_letter: coverLetter,
      notes: str(formData, "notes", 2000),
      form_answers: answers,
      unknown_fields: [...new Set(unknown)],
    })
    .eq("id", parsed.data)
    .eq("user_id", user.id);
  revalidateQueue(parsed.data);
}

/** Chooses which resume to attach. Ownership is checked so a foreign resume id is ignored. */
export async function setResume(formData: FormData) {
  const id = idSchema.safeParse(str(formData, "id", 60));
  if (!id.success) return;
  const { supabase, user } = await requireUser();
  const requested = str(formData, "resume_id", 60);
  let resumeId: string | null = null;
  if (requested && idSchema.safeParse(requested).success) {
    const { data: owned } = await supabase
      .from("resumes")
      .select("id")
      .eq("id", requested)
      .eq("user_id", user.id)
      .maybeSingle();
    resumeId = owned?.id ?? null;
  }
  await supabase.from("applications").update({ resume_id: resumeId }).eq("id", id.data).eq("user_id", user.id);
  revalidateQueue(id.data);
}

const statusSchema = z.object({
  id: z.string().uuid(),
  status: z.enum(APPLICATION_STATUSES),
});

/**
 * Moves an application through its lifecycle. The user performs every real submission on the
 * company's site, and this action only records what they did.
 */
export async function setStatus(formData: FormData) {
  const parsed = statusSchema.safeParse({ id: str(formData, "id", 60), status: str(formData, "status", 30) });
  if (!parsed.success) return;
  const { supabase, user } = await requireUser();
  const { data: app } = await supabase
    .from("applications")
    .select("status")
    .eq("id", parsed.data.id)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!app || app.status === parsed.data.status) return;

  const patch: Record<string, string> = { status: parsed.data.status };
  const now = new Date().toISOString();
  if (parsed.data.status === "applied") patch.applied_at = now;
  if (parsed.data.status === "opened") patch.opened_at = now;

  await supabase.from("applications").update(patch).eq("id", parsed.data.id).eq("user_id", user.id);
  await logEvent(supabase, user.id, parsed.data.id, app.status, parsed.data.status, str(formData, "note", 300));
  revalidateQueue(parsed.data.id);
}
