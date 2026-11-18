import { deleteResume, saveProfile, setDefaultResume } from "@/app/actions/profile";
import ResumeUpload from "@/components/ResumeUpload";
import { requireUser } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { getOnboardingChecklist } from "@/lib/onboarding";
import { serializeProjects } from "@/lib/validation";
import type { ProfileRow, ResumeRow } from "@/lib/types";

export const dynamic = "force-dynamic";

const ERRORS: Record<string, string> = {
  invalid: "Some fields are invalid. Check the phone number and links, then save again.",
  save: "Could not save your profile. Try again.",
};

export default async function ProfilePage({ searchParams }: { searchParams: { saved?: string; error?: string } }) {
  const { supabase, user } = await requireUser();
  const [checklist, profileRes, resumesRes] = await Promise.all([
    getOnboardingChecklist(supabase, user.id),
    supabase.from("profiles").select("*").eq("id", user.id).maybeSingle(),
    supabase
      .from("resumes")
      .select("id, tag, label, file_name, storage_path, is_default, created_at")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false }),
  ]);
  const profile = profileRes.data as ProfileRow | null;
  const resumes = (resumesRes.data ?? []) as ResumeRow[];

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <header>
        <h1 className="h1">My Profile</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Drafts use only what you enter here. Anything missing is flagged for you to answer, never invented.
        </p>
      </header>

      <section className="card">
        <h2 className="h2">Onboarding</h2>
        <ul className="mt-2 grid gap-1 text-sm md:grid-cols-3">
          <li>{checklist.hasName ? "Done" : "To do"}: name</li>
          <li>{checklist.hasSkills ? "Done" : "To do"}: three or more skills</li>
          <li>{checklist.hasResume ? "Done" : "To do"}: resume uploaded</li>
        </ul>
        <p className="mt-2 text-xs text-zinc-500">
          {checklist.complete ? "Your profile is complete and will be scored on the next run." : "Matching starts once all three are done."}
        </p>
      </section>

      {searchParams.saved ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Profile saved.</p> : null}
      {searchParams.error && ERRORS[searchParams.error] ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{ERRORS[searchParams.error]}</p>
      ) : null}

      <form action={saveProfile} className="card space-y-5">
        <h2 className="h2">Identity and education</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Full name" name="full_name" value={profile?.full_name} required />
          <Field label="Email (from sign-in)" name="email_display" value={profile?.email} disabled />
          <Field label="Phone" name="phone" value={profile?.phone} placeholder="+91 ..." />
          <Field label="Current city" name="city" value={profile?.city} />
          <Field label="College" name="college" value={profile?.college} required />
          <Field label="Degree" name="degree" value={profile?.degree} required />
          <Field label="Graduation year" name="graduation_year" type="number" value={profile?.graduation_year ?? 2028} required />
          <Field label="LinkedIn (https)" name="linkedin_url" value={profile?.linkedin_url} />
          <Field label="GitHub (https)" name="github_url" value={profile?.github_url} />
          <Field label="Portfolio (https)" name="portfolio_url" value={profile?.portfolio_url} />
        </div>

        <div>
          <label className="label" htmlFor="skills">Skills (comma or line separated)</label>
          <textarea id="skills" name="skills" rows={3} defaultValue={(profile?.skills ?? []).join(", ")} className="input" />
        </div>

        <div>
          <label className="label" htmlFor="projects">
            Projects: one block per project. Line 1 name, line 2 tech stack, then a summary. Leave a blank line between projects.
          </label>
          <textarea
            id="projects"
            name="projects"
            rows={8}
            defaultValue={serializeProjects(profile?.projects ?? [])}
            className="input font-mono text-[13px]"
          />
        </div>

        <div>
          <label className="label" htmlFor="achievements">Achievements (one per line)</label>
          <textarea id="achievements" name="achievements" rows={3} defaultValue={(profile?.achievements ?? []).join("\n")} className="input" />
        </div>

        <div className="flex justify-end">
          <button type="submit" className="btn btn-primary">Save profile</button>
        </div>
      </form>

      <section className="card space-y-4">
        <div>
          <h2 className="h2">Resume vault</h2>
          <p className="mt-1 text-xs text-zinc-600">
            Upload one PDF per role type. Text is extracted on the server and stored privately. It is never sent to an AI service.
            Scanned PDFs without selectable text are rejected.
          </p>
        </div>
        <ResumeUpload />
        {resumes.length === 0 ? (
          <p className="text-sm text-zinc-600">No resumes yet.</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {resumes.map((resume) => (
              <li key={resume.id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="pill">{resume.tag}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{resume.label}</div>
                  <div className="truncate text-xs text-zinc-500">{resume.file_name} · added {formatDate(resume.created_at)}</div>
                </div>
                {resume.is_default ? (
                  <span className="pill border-emerald-200 text-emerald-700">Default for {resume.tag}</span>
                ) : (
                  <form action={setDefaultResume}>
                    <input type="hidden" name="id" value={resume.id} />
                    <button type="submit" className="btn">Make default</button>
                  </form>
                )}
                <form action={deleteResume}>
                  <input type="hidden" name="id" value={resume.id} />
                  <button type="submit" className="btn">Delete</button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Field({
  label,
  name,
  value,
  type = "text",
  required,
  placeholder,
  disabled,
}: {
  label: string;
  name: string;
  value?: string | number | null;
  type?: string;
  required?: boolean;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <div>
      <label className="label" htmlFor={name}>{label}</label>
      <input
        id={name}
        name={disabled ? undefined : name}
        type={type}
        defaultValue={value ?? ""}
        required={required}
        placeholder={placeholder}
        disabled={disabled}
        className="input"
      />
    </div>
  );
}
