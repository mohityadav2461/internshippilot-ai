/**
 * Draft generator. Pure and deterministic: no model is called, and every fact comes from the
 * verified profile. Anything the profile cannot answer becomes an explicit "needs human" item.
 */
import type { Filters, FormAnswer, FormField, JobRow, Project, ProfileRow, ResumeRow } from "./types";

export const MOTIVATION_PLACEHOLDER =
  "[ADD YOUR OWN MOTIVATION: why this company and role? Write this yourself, it is not generated]";
const ADD_MARK = "[ADD";

export const STANDARD_FIELDS: FormField[] = [
  { key: "full_name", label: "Full name", type: "text", required: true },
  { key: "email", label: "Email", type: "email", required: true },
  { key: "phone", label: "Phone", type: "tel", required: true },
  { key: "city", label: "Current city", type: "text", required: false },
  { key: "college", label: "College or university", type: "text", required: true },
  { key: "degree", label: "Degree", type: "text", required: true },
  { key: "graduation_year", label: "Graduation year", type: "text", required: true },
  { key: "linkedin", label: "LinkedIn URL", type: "url", required: false },
  { key: "github", label: "GitHub URL", type: "url", required: false },
  { key: "portfolio", label: "Portfolio URL", type: "url", required: false },
  { key: "skills", label: "Skills", type: "text", required: false },
  { key: "resume", label: "Resume", type: "file", required: true },
  { key: "cover_letter", label: "Cover letter", type: "textarea", required: false },
  { key: "availability", label: "Availability or start date", type: "text", required: true },
  { key: "work_authorization", label: "Are you authorized to work in India?", type: "text", required: true },
  { key: "compensation", label: "Expected stipend", type: "text", required: false },
  { key: "motivation", label: "Why are you interested in this role?", type: "textarea", required: true },
];

interface Ctx {
  profile: ProfileRow;
  job: JobRow;
  resume: ResumeRow | null;
  coverLetter: string;
  filters: Filters;
}

interface Resolution {
  value: string | null;
  source: FormAnswer["source"];
  needsHuman?: boolean;
}

interface Resolver {
  pattern: RegExp;
  resolve: (ctx: Ctx) => Resolution;
}

const HUMAN: Resolution = { value: null, source: "human_required", needsHuman: true };

function fromProfile(value: string | number | null | undefined): Resolution {
  const text = value === null || value === undefined ? "" : String(value).trim();
  return { value: text || null, source: "profile" };
}

const RESOLVERS: Resolver[] = [
  { pattern: /cover letter/i, resolve: (c) => ({ value: c.coverLetter || null, source: "draft" }) },
  {
    pattern: /\bwhy\b|motivat|interested in|what excites|about yourself/i,
    resolve: () => ({ value: MOTIVATION_PLACEHOLDER, source: "draft", needsHuman: true }),
  },
  { pattern: /full name|your name|^name$|first and last name/i, resolve: (c) => fromProfile(c.profile.full_name) },
  { pattern: /e-?mail/i, resolve: (c) => fromProfile(c.profile.email) },
  { pattern: /phone|mobile|contact number/i, resolve: (c) => fromProfile(c.profile.phone) },
  { pattern: /linkedin/i, resolve: (c) => fromProfile(c.profile.linkedin_url) },
  { pattern: /github/i, resolve: (c) => fromProfile(c.profile.github_url) },
  { pattern: /portfolio|personal site|personal website/i, resolve: (c) => fromProfile(c.profile.portfolio_url) },
  { pattern: /college|university|institution|school name/i, resolve: (c) => fromProfile(c.profile.college) },
  { pattern: /degree|program of study|course of study|\bmajor\b/i, resolve: (c) => fromProfile(c.profile.degree) },
  {
    pattern: /graduation|graduating|passing year|year of (completion|passing|graduation)/i,
    resolve: (c) => fromProfile(c.profile.graduation_year),
  },
  { pattern: /current city|\bcity\b|current location|where are you (based|located)/i, resolve: (c) => fromProfile(c.profile.city) },
  { pattern: /skills|tech stack|technologies/i, resolve: (c) => fromProfile(c.profile.skills.join(", ")) },
  {
    pattern: /start date|availability|available to start|when can you (start|join)|notice period/i,
    resolve: (c) => ({
      value: `${c.filters.target_start} (${c.filters.duration_months} months), please confirm`,
      source: "settings",
    }),
  },
  { pattern: /authori[sz]ed to work|work authori[sz]ation|visa|sponsorship|work permit/i, resolve: () => HUMAN },
  { pattern: /expected (salary|stipend|ctc|compensation)|salary expectation|stipend expectation|current ctc/i, resolve: () => HUMAN },
  { pattern: /gender|pronoun|ethnic|\brace\b|disabilit|veteran|sexual orientation/i, resolve: () => HUMAN },
  { pattern: /how did you hear|referr|source of/i, resolve: () => HUMAN },
];

export function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function skillMentioned(lowerText: string, skill: string): boolean {
  const key = skill.trim().toLowerCase();
  if (!key) return false;
  return new RegExp(`(^|[^a-z0-9])${escapeRegExp(key)}([^a-z0-9]|$)`).test(lowerText);
}

function joinList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function buildCoverLetter(profile: ProfileRow, job: JobRow, filters: Filters): string {
  const jobText = `${job.title}\n${job.description}`.toLowerCase();
  const matched = profile.skills.filter((skill) => skillMentioned(jobText, skill));
  const skills = (matched.length ? matched : profile.skills).slice(0, 5);
  const project: Project | undefined =
    profile.projects.find((p) => p.tech.some((t) => skillMentioned(jobText, t))) ?? profile.projects[0];
  const location = job.location ? ` in ${job.location}` : "";

  const lines: string[] = [
    `Dear ${job.company} hiring team,`,
    "",
    `I am applying for the ${job.title} internship${location}. I am a ${profile.degree} student at ${profile.college}, graduating in ${profile.graduation_year}.`,
  ];
  if (skills.length) lines.push(`My relevant skills include ${joinList(skills)}.`);
  if (project) {
    const tech = project.tech.length ? ` (${joinList(project.tech.slice(0, 5))})` : "";
    lines.push(`One project I am proud of is ${project.name}${tech}: ${project.summary || "[ADD a one-line summary of this project]"}`);
  }
  lines.push(MOTIVATION_PLACEHOLDER);
  lines.push(`I am available for ${filters.target_start} (${filters.duration_months} months).`);
  lines.push("", "Thank you for your time and consideration.", "", "Sincerely,");
  lines.push(profile.full_name.trim() || "[ADD YOUR FULL NAME]");
  const contact = [profile.email, profile.phone].filter(Boolean).join(" | ");
  if (contact) lines.push(contact);
  return lines.join("\n");
}

export function answerField(field: FormField, ctx: Ctx): FormAnswer {
  const base = {
    key: field.key || field.label,
    label: field.label || field.key,
    type: field.type,
    required: field.required,
  };
  if (field.type === "file") {
    return { ...base, answer: null, source: "resume_upload", needs_human: true };
  }
  const haystack = `${field.label} ${field.key}`;
  const resolver = RESOLVERS.find((r) => r.pattern.test(haystack));
  if (!resolver) {
    return { ...base, answer: null, source: "human_required", needs_human: true };
  }
  const out = resolver.resolve(ctx);
  const answer = out.value;
  const needsHuman = out.needsHuman === true || answer === null || answer.includes(ADD_MARK);
  return { ...base, answer, source: out.source, needs_human: needsHuman };
}

export interface DraftInput {
  profile: ProfileRow;
  job: JobRow;
  resume: ResumeRow | null;
  formSchema: FormField[] | null;
  filters: Filters;
}

export interface DraftOutput {
  coverLetter: string;
  formAnswers: FormAnswer[];
  unknownFields: string[];
}

export function buildDraft(input: DraftInput): DraftOutput {
  const coverLetter = buildCoverLetter(input.profile, input.job, input.filters);
  const ctx: Ctx = { ...input, coverLetter };
  const fields = input.formSchema && input.formSchema.length ? input.formSchema : STANDARD_FIELDS;
  const formAnswers = fields.map((field) => answerField(field, ctx));
  const unknown = formAnswers.filter((a) => a.needs_human).map((a) => a.label);
  if (coverLetter.includes(ADD_MARK) && !unknown.includes("Cover letter")) unknown.push("Cover letter");
  return { coverLetter, formAnswers, unknownFields: [...new Set(unknown)] };
}
