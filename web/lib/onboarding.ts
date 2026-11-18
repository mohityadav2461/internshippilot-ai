import type { SupabaseClient } from "@supabase/supabase-js";

export interface OnboardingChecklist {
  hasName: boolean;
  hasSkills: boolean;
  hasResume: boolean;
  complete: boolean;
}

/** Onboarding is complete when name, three skills, and one resume exist. The pipeline only scores completed profiles. */
export async function getOnboardingChecklist(supabase: SupabaseClient, userId: string): Promise<OnboardingChecklist> {
  const [{ data: profile }, { count }] = await Promise.all([
    supabase.from("profiles").select("full_name, skills").eq("id", userId).maybeSingle(),
    supabase.from("resumes").select("id", { count: "exact", head: true }).eq("user_id", userId),
  ]);
  const hasName = Boolean(profile?.full_name?.trim());
  const hasSkills = (profile?.skills?.length ?? 0) >= 3;
  const hasResume = (count ?? 0) > 0;
  return { hasName, hasSkills, hasResume, complete: hasName && hasSkills && hasResume };
}

export async function refreshOnboarding(supabase: SupabaseClient, userId: string): Promise<boolean> {
  const checklist = await getOnboardingChecklist(supabase, userId);
  await supabase.from("profiles").update({ onboarding_complete: checklist.complete }).eq("id", userId);
  return checklist.complete;
}
