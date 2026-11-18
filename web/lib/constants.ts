import type { ApplicationStatus, Filters, ResumeTag, RoleCategory } from "./types";

/** Must match SCORING_VERSION in pipeline/ipilot/scoring.py. */
export const SCORING_VERSION = "v1";

export const ROLE_VALUES = ["SDE", "Quant", "Analyst", "ML", "DataScience", "Research"] as const;

export const ROLE_OPTIONS: { value: (typeof ROLE_VALUES)[number]; label: string }[] = [
  { value: "SDE", label: "SDE: Software, Backend, Full Stack" },
  { value: "Quant", label: "Quant: Dev, Research, Analyst" },
  { value: "Analyst", label: "Analyst: Data or Business" },
  { value: "ML", label: "ML and AI Engineering" },
  { value: "DataScience", label: "Data Science" },
  { value: "Research", label: "Research Intern" },
];

export const RESUME_TAGS = ["SDE", "Quant", "Analyst", "ML"] as const satisfies readonly ResumeTag[];

/** Resume preference per role. Mirrors TAG_FOR_CATEGORY in pipeline/ipilot/normalize.py. */
export const TAG_FALLBACK: Record<RoleCategory, ResumeTag[]> = {
  SDE: ["SDE", "ML", "Analyst"],
  Quant: ["Quant", "Analyst", "SDE"],
  Analyst: ["Analyst", "Quant", "SDE"],
  ML: ["ML", "SDE", "Analyst"],
  DataScience: ["ML", "Analyst", "SDE"],
  Research: ["Quant", "ML", "Analyst"],
  Other: ["SDE"],
};

export const APPLICATION_STATUSES = [
  "pending_review",
  "approved_manual",
  "opened",
  "applied",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
] as const satisfies readonly ApplicationStatus[];

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  pending_review: "Pending review",
  approved_manual: "Approved for manual submit",
  opened: "Form opened",
  applied: "Applied (manually)",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const DEFAULT_FILTERS: Filters = {
  min_stipend_inr: 10000,
  locations: ["India"],
  internship_only: true,
  allow_stipend_unverified: true,
  target_start: "Summer 2027",
  duration_months: "2-3",
  roles: [...ROLE_VALUES],
  min_score_to_show: 50,
  auto_queue_score: 70,
};

export const NAV_ITEMS = [
  { href: "/overview", label: "Overview" },
  { href: "/find", label: "Find Internships" },
  { href: "/pending", label: "Pending Applications" },
  { href: "/tracker", label: "Application Tracker" },
  { href: "/profile", label: "My Profile" },
  { href: "/settings", label: "Settings" },
];

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
