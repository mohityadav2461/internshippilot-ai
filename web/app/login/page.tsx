import { sendMagicLink, signInWithPassword } from "./actions";

const ERRORS: Record<string, string> = {
  email: "Enter a valid email address.",
  send: "We could not send the link. Try again in a minute.",
  link: "That sign-in link is invalid or has expired. Request a new one.",
};

export default function LoginPage({
  searchParams,
}: {
  searchParams: { sent?: string; error?: string; mode?: string };
}) {
  const isMagicLink = searchParams.mode === "magic";

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="h1">InternshipPilot AI</h1>
        <p className="mt-2 text-sm text-zinc-600">
          {isMagicLink
            ? "Sign in with a one-time link sent to your email."
            : "Sign in with your email and password."}
        </p>

        {searchParams.sent ? (
          <p className="mt-6 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Check your inbox for the sign-in link.
          </p>
        ) : isMagicLink ? (
          <form action={sendMagicLink} className="mt-6 space-y-3">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" name="email" type="email" required autoComplete="email" className="input" />
            </div>
            <button type="submit" className="btn btn-primary w-full">Send sign-in link</button>
            <div className="pt-2 text-center">
              <a href="/login" className="text-xs text-zinc-500 hover:text-zinc-900">
                Prefer to sign in with password?
              </a>
            </div>
          </form>
        ) : (
          <form action={signInWithPassword} className="mt-6 space-y-3">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" name="email" type="email" required autoComplete="email" className="input" />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" name="password" type="password" required autoComplete="current-password" className="input" />
            </div>
            <button type="submit" className="btn btn-primary w-full">Sign in</button>
            <div className="pt-2 text-center">
              <a href="/login?mode=magic" className="text-xs text-zinc-500 hover:text-zinc-900">
                Or send a magic link to your email
              </a>
            </div>
          </form>
        )}

        {searchParams.error ? (
          <p className="mt-3 text-sm text-red-600">
            {ERRORS[searchParams.error] ?? decodeURIComponent(searchParams.error)}
          </p>
        ) : null}
      </div>
    </main>
  );
}
