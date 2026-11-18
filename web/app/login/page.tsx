import { sendMagicLink } from "./actions";

const ERRORS: Record<string, string> = {
  email: "Enter a valid email address.",
  send: "We could not send the link. Try again in a minute.",
  link: "That sign-in link is invalid or has expired. Request a new one.",
};

export default function LoginPage({ searchParams }: { searchParams: { sent?: string; error?: string } }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="h1">InternshipPilot AI</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Sign in with a one-time link sent to your email. There is no password to store.
        </p>
        {searchParams.sent ? (
          <p className="mt-6 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Check your inbox for the sign-in link.
          </p>
        ) : (
          <form action={sendMagicLink} className="mt-6 space-y-3">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" name="email" type="email" required autoComplete="email" className="input" />
            </div>
            <button type="submit" className="btn btn-primary w-full">Send sign-in link</button>
          </form>
        )}
        {searchParams.error ? (
          <p className="mt-3 text-sm text-red-600">{ERRORS[searchParams.error] ?? "Something went wrong."}</p>
        ) : null}
      </div>
    </main>
  );
}
