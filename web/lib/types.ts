export type RoleCategory = "SDE" | "Quant" | "Analyst" | "ML" | "DataScience" | "Research" | "Other";
export type ResumeTag = "SDE" | "Quant" | "Analyst" | "ML";
export type ApplicationStatus =
  | "pending_review"
  | "approved_manual"
  | "opened"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";
export type ScoreBand = "Excellent" | "Good" | "Moderate" | "Low";
export type StipendStatus = "verified" | "not_verified" | "unpaid";

export interface Filters {
  min_stipend_inr: number;
  locations: string[];
  internship_only: boolean;
  allow_stipend_unverified: boolean;
  target_start: string;
  duration_months: string;
  roles: RoleCategory[];
  min_score_to_show: number;
  auto_queue_score: number;
}

export interface Project {
  name: string;
  tech: string[];
  summary: string;
}

export interface ProfileRow {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  city: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
  college: string;
  degree: string;
  graduation_year: number;
  skills: string[];
  projects: Project[];
  achievements: string[];
  filters: Filters;
  ai_consent: boolean;
  onboarding_complete: boolean;
}

export interface JobRow {
  id: string;
  source_name: string;
  company: string;
  title: string;
  location: string;
  is_remote: boolean;
  role_category: RoleCategory;
  description: string;
  apply_url: string;
  canonical_url: string;
  posted_at: string | null;
  stipend_text: string | null;
  stipend_min_inr: number | null;
  stipend_status: StipendStatus;
  last_seen_at: string;
}

export interface ResumeRow {
  id: string;
  tag: ResumeTag;
  label: string;
  file_name: string;
  storage_path: string;
  is_default: boolean;
  created_at: string;
}

export interface FormField {
  key: string;
  label: string;
  type: string;
  required: boolean;
  options?: string[];
}

export interface FormSchema {
  status: string;
  fields: FormField[];
  inspected_at?: string;
  host?: string;
}

export interface FormAnswer {
  key: string;
  label: string;
  type: string;
  required: boolean;
  answer: string | null;
  source: "profile" | "settings" | "draft" | "resume_upload" | "human_required";
  needs_human: boolean;
}

export interface ApplicationRow {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  score: number | null;
  resume_id: string | null;
  cover_letter: string;
  form_answers: FormAnswer[];
  form_schema: FormSchema | null;
  unknown_fields: string[];
  notes: string;
  draft_generated_at: string | null;
  opened_at: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScoreReasoning {
  components?: Record<string, { points: number; max: number; note: string }>;
  matched_skills?: string[];
  background_terms?: string[];
  ai?: { fit_score: number; summary: string; strengths: string[]; gaps: string[] };
}

export interface ScoreRow {
  id: string;
  job_id: string;
  score: number;
  band: ScoreBand;
  method: string;
  reasoning: ScoreReasoning;
  flags: string[];
  best_resume_tag: ResumeTag | null;
  created_at: string;
}
