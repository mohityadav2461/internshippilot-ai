import { STATUS_LABELS } from "@/lib/constants";
import { formatRupees } from "@/lib/format";
import type { ApplicationStatus, ScoreBand, StipendStatus } from "@/lib/types";

const BAND_CLASS: Record<ScoreBand, string> = {
  Excellent: "border-emerald-200 bg-emerald-50 text-emerald-700",
  Good: "border-sky-200 bg-sky-50 text-sky-700",
  Moderate: "border-amber-200 bg-amber-50 text-amber-700",
  Low: "border-zinc-200 bg-zinc-50 text-zinc-500",
};

export function ScoreBadge({ score, band }: { score: number; band: ScoreBand }) {
  return (
    <span className={`pill ${BAND_CLASS[band]}`}>
      <span className="font-semibold tabular-nums">{score}</span>
      <span className="ml-1">{band}</span>
    </span>
  );
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  const tone =
    status === "applied" || status === "interview" || status === "offer"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "rejected" || status === "withdrawn"
        ? "border-zinc-200 bg-zinc-50 text-zinc-500"
        : "border-zinc-300 bg-white text-zinc-700";
  return <span className={`pill ${tone}`}>{STATUS_LABELS[status]}</span>;
}

export function StipendFlag({ status, minInr }: { status: StipendStatus; minInr: number | null }) {
  if (status === "verified") {
    return <span className="pill border-emerald-200 text-emerald-700">{formatRupees(minInr)} / month</span>;
  }
  if (status === "unpaid") {
    return <span className="pill border-red-200 text-red-700">Unpaid</span>;
  }
  return <span className="pill border-amber-200 bg-amber-50 text-amber-700">Stipend not verified</span>;
}

export function Flag({ children }: { children: React.ReactNode }) {
  return <span className="pill border-amber-200 bg-amber-50 text-amber-700">{children}</span>;
}
