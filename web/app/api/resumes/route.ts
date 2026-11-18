import { revalidatePath } from "next/cache";
import { NextResponse } from "next/server";
import { extractText, getDocumentProxy } from "unpdf";
import { MAX_RESUME_BYTES, RESUME_TAGS } from "@/lib/constants";
import { refreshOnboarding } from "@/lib/onboarding";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PDF_MAGIC = [0x25, 0x50, 0x44, 0x46, 0x2d]; // "%PDF-"
const MAX_TEXT = 60000;

function fail(message: string, status: number) {
  return NextResponse.json({ error: message }, { status });
}

/**
 * Resume vault upload. Text is extracted on the server with unpdf. Nothing is sent to an AI service.
 * Only scanned PDFs with no selectable text are rejected.
 */
export async function POST(request: Request) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return fail("Sign in required", 401);

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return fail("Upload could not be read", 400);
  }

  const file = form.get("file");
  const tag = String(form.get("tag") ?? "");
  const label = String(form.get("label") ?? "").trim().slice(0, 80);

  if (!(file instanceof File) || file.size === 0) return fail("Choose a PDF file", 400);
  if (file.size > MAX_RESUME_BYTES) return fail("PDF must be 5 MB or smaller", 413);
  if (!file.name.toLowerCase().endsWith(".pdf")) return fail("Only PDF files are accepted", 415);
  if (!(RESUME_TAGS as readonly string[]).includes(tag)) return fail("Choose a resume tag", 400);

  const bytes = new Uint8Array(await file.arrayBuffer());
  if (!PDF_MAGIC.every((byte, index) => bytes[index] === byte)) return fail("File is not a valid PDF", 415);

  let text = "";
  try {
    const pdf = await getDocumentProxy(bytes);
    const out = await extractText(pdf, { mergePages: true });
    text = Array.isArray(out.text) ? out.text.join("\n") : String(out.text ?? "");
  } catch {
    return fail("Could not read this PDF", 422);
  }
  text = text.replace(/\s+/g, " ").trim().slice(0, MAX_TEXT);
  if (text.length < 80) return fail("No selectable text found. Upload a text-based PDF, not a scan.", 422);

  const safeName = file.name.replace(/[^\w.\- ]/g, "_").slice(0, 200);
  const path = `${user.id}/${crypto.randomUUID()}.pdf`;
  const { error: uploadError } = await supabase.storage
    .from("resumes")
    .upload(path, bytes, { contentType: "application/pdf", upsert: false });
  if (uploadError) return fail("Storage is unavailable. Try again.", 500);

  const { count } = await supabase
    .from("resumes")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id)
    .eq("tag", tag);

  const { data: row, error } = await supabase
    .from("resumes")
    .insert({
      user_id: user.id,
      tag,
      label: label || `${tag} resume`,
      file_name: safeName,
      storage_path: path,
      extracted_text: text,
      is_default: (count ?? 0) === 0,
    })
    .select("id")
    .single();
  if (error || !row) {
    await supabase.storage.from("resumes").remove([path]);
    return fail("Could not save the resume", 500);
  }

  await refreshOnboarding(supabase, user.id);
  revalidatePath("/profile");
  revalidatePath("/overview");
  return NextResponse.json({ ok: true, id: row.id, characters: text.length });
}
