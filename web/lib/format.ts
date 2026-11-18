const IST = "Asia/Kolkata";

export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: IST })
    .format(new Date(value));
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: IST,
  }).format(new Date(value));
}

export function formatRupees(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `Rs ${value.toLocaleString("en-IN")}`;
}
