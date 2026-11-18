import { z } from "zod";
import { ROLE_VALUES } from "./constants";
import type { Project } from "./types";

/** Read one text field from a FormData, trimmed and length-capped. */
export function str(formData: FormData, key: string, max = 500): string {
  const value = formData.get(key);
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

export function parseList(text: string, max = 80, itemMax = 60): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of text.split(/[\n,]/)) {
    const item = raw.trim().slice(0, itemMax);
    if (!item) continue;
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= max) break;
  }
  return out;
}

export function parseLines(text: string, max = 20, itemMax = 300): string[] {
  return text
    .split("\n")
    .map((line) => line.trim().slice(0, itemMax))
    .filter(Boolean)
    .slice(0, max);
}

/** Projects are written as blocks separated by a blank line: name, comma-separated tech, then summary lines. */
export function parseProjects(text: string): Project[] {
  return text
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .filter(Boolean)
    .slice(0, 20)
    .map((block) => {
      const [name = "", techLine = "", ...rest] = block.split("\n");
      return {
        name: name.trim().slice(0, 120),
        tech: parseList(techLine, 15, 30),
        summary: rest.join(" ").trim().slice(0, 600),
      };
    })
    .filter((project) => project.name.length > 0);
}

export function serializeProjects(projects: Project[]): string {
  return projects
    .map((p) => [p.name, p.tech.join(", "), p.summary].join("\n"))
    .join("\n\n");
}

export function isHttpsOrEmpty(value: string): boolean {
  if (!value) return true;
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

export const profileSchema = z.object({
  full_name: z.string().max(120),
  phone: z.string().max(20).regex(/^[+0-9 ()-]*$/, "Phone may contain digits, spaces, +, - and brackets"),
  city: z.string().max(80),
  linkedin_url: z.string().max(300).refine(isHttpsOrEmpty, "LinkedIn must be an https:// link"),
  github_url: z.string().max(300).refine(isHttpsOrEmpty, "GitHub must be an https:// link"),
  portfolio_url: z.string().max(300).refine(isHttpsOrEmpty, "Portfolio must be an https:// link"),
  college: z.string().min(2).max(120),
  degree: z.string().min(2).max(120),
  graduation_year: z.number().int().min(2024).max(2035),
});

export const filtersSchema = z.object({
  min_stipend_inr: z.number().int().min(0).max(1_000_000),
  locations: z.array(z.string().min(2).max(60)).min(1).max(10),
  allow_stipend_unverified: z.boolean(),
  roles: z.array(z.enum(ROLE_VALUES)).min(1),
  min_score_to_show: z.number().int().min(0).max(100),
  auto_queue_score: z.number().int().min(50).max(100),
  target_start: z.string().min(3).max(40),
  duration_months: z.string().regex(/^\d+(-\d+)?$/, "Use a form like 2-3"),
});
