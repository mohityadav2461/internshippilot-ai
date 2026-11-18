"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { MAX_RESUME_BYTES, RESUME_TAGS } from "@/lib/constants";

export default function ResumeUpload() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setMessage("Choose a PDF first.");
      return;
    }
    if (file.size > MAX_RESUME_BYTES) {
      setMessage("PDF must be 5 MB or smaller.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch("/api/resumes", { method: "POST", body: data });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(body.error ?? "Upload failed. Try again.");
      } else {
        setMessage(`Saved. ${body.characters} characters were extracted on the server.`);
        form.reset();
        router.refresh();
      }
    } catch {
      setMessage("Network error. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[1fr_140px]">
        <div>
          <label className="label" htmlFor="resume-file">PDF file (text-based, up to 5 MB)</label>
          <input id="resume-file" name="file" type="file" accept="application/pdf,.pdf" required className="input" />
        </div>
        <div>
          <label className="label" htmlFor="resume-tag">Role tag</label>
          <select id="resume-tag" name="tag" required defaultValue="SDE" className="input">
            {RESUME_TAGS.map((tag) => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="label" htmlFor="resume-label">Label</label>
        <input id="resume-label" name="label" maxLength={80} placeholder="For example: Quant resume, Nov 2026" className="input" />
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy} className="btn btn-primary">
          {busy ? "Extracting text..." : "Upload resume"}
        </button>
        {message ? <span className="text-sm text-zinc-600">{message}</span> : null}
      </div>
    </form>
  );
}
