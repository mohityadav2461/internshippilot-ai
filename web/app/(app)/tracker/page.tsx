import Link from "next/link";
import { setStatus } from "@/app/actions/applications";
import { StatusBadge } from "@/components/Badges";
import { requireUser } from "@/lib/auth";
import { APPLICATION_STATUSES, STATUS_LABELS } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import type { ApplicationStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

interface TrackerRow {
  id: string;
  status: ApplicationStatus;
  score: number | null;
  applied_at: string | null;
  updated_at: string;
  jobs: { company: string; title: string; location: string } | null;
}

export default async function TrackerPage({ searchParams }: { searchParams: { status?: string } }) {
  const { supabase, user } = await requireUser();
  const filter = (APPLICATION_STATUSES as readonly string[]).includes(searchParams.status ?? "")
    ? (searchParams.status as ApplicationStatus)
    : null;

  let query = supabase
    .from("applications")
    .select("id, status, score, applied_at, updated_at, jobs(company, title, location)")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })
    .limit(500);
  if (filter) query = query.eq("status", filter);
  const { data } = await query;
  const rows = (data ?? []) as unknown as TrackerRow[];

  const { data: all } = await supabase.from("applications").select("status").eq("user_id", user.id);
  const counts = new Map<string, number>();
  for (const item of all ?? []) counts.set(item.status, (counts.get(item.status) ?? 0) + 1);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="h1">Application Tracker</h1>
        <p className="mt-1 text-sm text-zinc-600">Every application, its status, and when you last touched it.</p>
      </header>

      <nav className="flex flex-wrap gap-2 text-sm">
        <Link href="/tracker" className={`pill ${!filter ? "border-zinc-900 text-zinc-900" : ""}`}>
          All ({all?.length ?? 0})
        </Link>
        {APPLICATION_STATUSES.map((status) => (
          <Link
            key={status}
            href={`/tracker?status=${status}`}
            className={`pill ${filter === status ? "border-zinc-900 text-zinc-900" : ""}`}
          >
            {STATUS_LABELS[status]} ({counts.get(status) ?? 0})
          </Link>
        ))}
      </nav>

      {rows.length === 0 ? (
        <p className="text-sm text-zinc-600">No applications here yet.</p>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-200 text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Score</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Submitted by you</th>
                <th className="px-4 py-3 font-medium">Updated</th>
                <th className="px-4 py-3 font-medium">Change status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((row) => (
                <tr key={row.id} className="align-top">
                  <td className="px-4 py-3">
                    <Link href={`/pending/${row.id}`} className="font-medium hover:underline">
                      {row.jobs?.title}
                    </Link>
                    <div className="text-xs text-zinc-500">{row.jobs?.company} · {row.jobs?.location}</div>
                  </td>
                  <td className="px-4 py-3 tabular-nums">{row.score ?? "-"}</td>
                  <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
                  <td className="px-4 py-3 text-xs text-zinc-600">{formatDate(row.applied_at)}</td>
                  <td className="px-4 py-3 text-xs text-zinc-600">{formatDate(row.updated_at)}</td>
                  <td className="px-4 py-3">
                    <form action={setStatus} className="flex gap-2">
                      <input type="hidden" name="id" value={row.id} />
                      <select name="status" defaultValue={row.status} className="input w-auto py-1 text-xs">
                        {APPLICATION_STATUSES.map((status) => (
                          <option key={status} value={status}>{STATUS_LABELS[status]}</option>
                        ))}
                      </select>
                      <button type="submit" className="btn py-1 text-xs">Save</button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
