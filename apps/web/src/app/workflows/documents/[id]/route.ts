import type { NextRequest } from "next/server";
import { apiUrl, SESSION_COOKIE } from "@/lib/server-api";

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Authentication required", { status: 401 });
  const { id } = await context.params;
  try {
    const result = await fetch(`${apiUrl()}/v3/documents/${encodeURIComponent(id)}/content`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (!result.ok)
      return new Response("Document unavailable", {
        status: result.status,
        headers: { "Cache-Control": "no-store" },
      });
    return new Response(result.body, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="synthetic-document.pdf"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
      },
    });
  } catch {
    return new Response("Document unavailable", { status: 503 });
  }
}
