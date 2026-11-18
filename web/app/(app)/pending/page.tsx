import Link from "next/link";
import { Flag, ScoreBadge } from "@/components/Badges";
import { requireUser } from "@/lib/auth";
import { ensurePendingDrafts } from "@/lib/drafts-service";
import { formatDate } from "@/lib/format";
import type { ScoreBand } from "@/lib/types";

function bandFor(score: number): ScoreBand {
  if (score >= 85) return "Excellent";
  if (score >= 70) return "Good";
  if (score >= 50) return "Moderate";
  return "Low";
}

export const dynamic = "force-dynamic";

interface PendingRow {
  id: string;
  status: string;
  score: number | null;
  created_at: string;
  unknown_fields: string[];
  jobs: { company: string; title: string; location: string; apply_url: string } | null;
}

export default async function PendingPage() {
  const { supabase, user } = await requireUser();
  await ensurePendingDrafts(supabase, user.id);

  const { data } = await supabase
    .from("applications")
    .select("id, status, score, created_at, unknown_fields, jobs(company, title, location, apply_url)")
    .eq("user_id", user.id)
    .in("status", ["pending_review", "approved_manual"])
    .order("score", { ascending: false, nullsFirst: false });
  const rows = (data ?? []) as unknown as PendingRow[];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="h1">Pending Applications</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Drafts waiting for your review. InternshipPilot never submits a form. You review the draft, open the company page, and submit it yourself.
        </p>
      </header>

      {rows.length === 0 ? (
        <section className="card text-sm text-zinc-600">
          Nothing is waiting for review. Strong matches (Good or Excellent) are queued automatically. You can also add any listing from Find Internships.
        </section>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id} className="card">
              <div className="flex flex-wrap items-center gap-3">
                {row.score !== null ? <ScoreBadge score={row.score} band={bandFor(row.score)} /> : null}
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-zinc-500">{row.jobs?.company} · {row.jobs?.location}</div>
                  <div className="truncate font-medium">{row.jobs?.title}</div>
                </div>
                {row.unknown_fields.length ? (
                  <Flag>{row.unknown_fields.length} field{row.unknown_fields.length === 1 ? "" : "s"} need you</Flag>
                ) : (
                  <span className="pill">Ready for review</span>
                )}
                <span className="pill">{row.status === "approved_manual" ? "Approved for manual submit" : "Pending review"}</span>
                <Link href={`/pending/${row.id}`} className="btn btn-primary">Review</Link>
              </div>
              <div className="mt-2 text-xs text-zinc-500">Queued {formatDate(row.created_at)}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
