import { DEFAULT_FILTERS } from "./constants";
import type { Filters, RoleCategory } from "./types";

/** Merge stored filters over the defaults so older rows never break the UI. */
export function parseFilters(raw: unknown): Filters {
  const stored = (raw && typeof raw === "object" ? raw : {}) as Partial<Filters>;
  const roles = Array.isArray(stored.roles) && stored.roles.length
    ? (stored.roles.filter((r) => DEFAULT_FILTERS.roles.includes(r as RoleCategory)) as RoleCategory[])
    : DEFAULT_FILTERS.roles;
  const locations = Array.isArray(stored.locations) && stored.locations.length
    ? stored.locations.map(String)
    : DEFAULT_FILTERS.locations;
  return {
    ...DEFAULT_FILTERS,
    ...stored,
    internship_only: true,
    roles,
    locations,
  };
}
