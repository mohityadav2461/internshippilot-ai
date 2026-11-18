import { type CookieMethodsServer, createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { supabaseEnv } from "@/lib/env";

/** Server-side Supabase client bound to the signed-in user's cookies. RLS applies to every query. */
export function createClient() {
  const cookieStore = cookies();
  const { url, anonKey } = supabaseEnv();
  const cookieMethods: CookieMethodsServer = {
    getAll() {
      return cookieStore.getAll();
    },
    setAll(cookiesToSet) {
      try {
        cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
      } catch {
        // Called from a Server Component, where cookies are read-only. Middleware refreshes the session.
      }
    },
  };
  return createServerClient(url, anonKey, { cookies: cookieMethods });
}
