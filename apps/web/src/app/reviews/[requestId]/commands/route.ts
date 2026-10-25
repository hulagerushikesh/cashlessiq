import { type NextRequest, NextResponse } from "next/server";
import { boundedForm } from "@/lib/bounded-form";
import { apiUrl, SESSION_COOKIE } from "@/lib/server-api";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ requestId: string }> },
) {
  const origin = process.env.CIQ_WEB_ORIGIN ?? "http://localhost:3000";
  if (request.headers.get("origin") !== origin) return new Response("Forbidden", { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 16384)
    return new Response("Too large", { status: 413 });
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.redirect(new URL("/login", origin), 303);
  const { requestId } = await context.params;
  const destination = new URL(`/reviews/${encodeURIComponent(requestId)}`, origin);
  try {
    const form = await boundedForm(request, 16384);
    const amount = form.get("payable_inr");
    const version = form.get("expected_version");
    if (typeof version !== "string" || !/^\d+$/.test(version)) throw new Error("Invalid version");
    if (
      amount &&
      (typeof amount !== "string" || !/^\d+$/.test(amount) || !Number.isSafeInteger(Number(amount)))
    )
      throw new Error("Invalid amount");
    const response = await fetch(
      `${apiUrl()}/v3/reviews/${encodeURIComponent(requestId)}/commands`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          command_id: form.get("command_id"),
          expected_version: Number(version),
          action: form.get("action"),
          assignee_id: form.get("assignee_id") || null,
          note: form.get("note") ?? "",
          visibility: form.get("visibility") ?? "team",
          payable_inr: amount ? Number(amount) : null,
        }),
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      },
    );
    destination.searchParams.set(
      "result",
      response.ok ? "saved" : response.status === 409 ? "conflict" : "failed",
    );
  } catch {
    destination.searchParams.set("result", "failed");
  }
  const result = NextResponse.redirect(destination, 303);
  result.headers.set("Cache-Control", "no-store");
  return result;
}
