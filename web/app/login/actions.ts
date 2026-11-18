"use server";

import { redirect } from "next/navigation";
import { z } from "zod";
import { siteUrl } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

const emailSchema = z.string().trim().toLowerCase().email().max(254);

/** Sends a one-time sign-in link. The link lands on /auth/confirm, which verifies the token. */
export async function sendMagicLink(formData: FormData) {
  const parsed = emailSchema.safeParse(formData.get("email"));
  if (!parsed.success) redirect("/login?error=email");
  const supabase = createClient();
  const { error } = await supabase.auth.signInWithOtp({
    email: parsed.data,
    options: { emailRedirectTo: `${siteUrl()}/auth/confirm?next=/overview` },
  });
  if (error) redirect("/login?error=send");
  redirect("/login?sent=1");
}
