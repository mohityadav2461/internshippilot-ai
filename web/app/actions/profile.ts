"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { ROLE_VALUES } from "@/lib/constants";
import { requireUser } from "@/lib/auth";
import { refreshOnboarding } from "@/lib/onboarding";
import {
  filtersSchema,
  parseLines,
  parseList,
  parseProjects,
  profileSchema,
  str,
} from "@/lib/validation";

export async function saveProfile(formData: FormData) {
  const { supabase, user } = await requireUser();
  const parsed = profileSchema.safeParse({
    full_name: str(formData, "full_name", 120),
    phone: str(formData, "phone", 20),
    city: str(formData, "city", 80),
    linkedin_url: str(formData, "linkedin_url", 300),
    github_url: str(formData, "github_url", 300),
    portfolio_url: str(formData, "portfolio_url", 300),
    college: str(formData, "college", 120),
    degree: str(formData, "degree", 120),
    graduation_year: Number(str(formData, "graduation_year", 4)),
  });
  if (!parsed.success) redirect("/profile?error=invalid");

  const { error } = await supabase
    .from("profiles")
    .update({
      ...parsed.data,
      skills: parseList(str(formData, "skills", 2000), 80, 60),
      projects: parseProjects(str(formData, "projects", 8000)),
      achievements: parseLines(str(formData, "achievements", 4000), 20, 300),
    })
    .eq("id", user.id);
  if (error) redirect("/profile?error=save");

  await refreshOnboarding(supabase, user.id);
  revalidatePath("/profile");
  revalidatePath("/overview");
  redirect("/profile?saved=1");
}

export async function saveFilters(formData: FormData) {
  const roles = formData.getAll("roles").map(String).filter((r) => (ROLE_VALUES as readonly string[]).includes(r));
  const locations = parseList(str(formData, "locations", 300), 10, 60);
  const parsed = filtersSchema.safeParse({
    min_stipend_inr: Number(str(formData, "min_stipend_inr", 10)),
    locations: locations.length ? locations : ["India"],
    allow_stipend_unverified: formData.get("allow_stipend_unverified") === "on",
    roles,
    min_score_to_show: Number(str(formData, "min_score_to_show", 3)),
    auto_queue_score: Number(str(formData, "auto_queue_score", 3)),
    target_start: str(formData, "target_start", 40),
    duration_months: str(formData, "duration_months", 10),
  });
  if (!parsed.success) redirect("/settings?error=invalid");

  const { supabase, user } = await requireUser();
  await supabase
    .from("profiles")
    .update({
      filters: { ...parsed.data, internship_only: true },
      ai_consent: formData.get("ai_consent") === "on",
    })
    .eq("id", user.id);
  revalidatePath("/settings");
  revalidatePath("/find");
  revalidatePath("/overview");
  redirect("/settings?saved=1");
}

export async function setDefaultResume(formData: FormData) {
  const id = str(formData, "id", 60);
  const { supabase, user } = await requireUser();
  const { data: resume } = await supabase
    .from("resumes")
    .select("id, tag")
    .eq("id", id)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!resume) return;
  await supabase.from("resumes").update({ is_default: false }).eq("user_id", user.id).eq("tag", resume.tag);
  await supabase.from("resumes").update({ is_default: true }).eq("id", resume.id).eq("user_id", user.id);
  revalidatePath("/profile");
}

export async function deleteResume(formData: FormData) {
  const id = str(formData, "id", 60);
  const { supabase, user } = await requireUser();
  const { data: resume } = await supabase
    .from("resumes")
    .select("id, storage_path")
    .eq("id", id)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!resume) return;
  await supabase.storage.from("resumes").remove([resume.storage_path]);
  await supabase.from("resumes").delete().eq("id", resume.id).eq("user_id", user.id);
  await refreshOnboarding(supabase, user.id);
  revalidatePath("/profile");
  revalidatePath("/overview");
}
