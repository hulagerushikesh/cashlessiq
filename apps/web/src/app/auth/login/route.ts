import { type NextRequest, NextResponse } from "next/server";
import { apiUrl, SESSION_COOKIE } from "@/lib/server-api";

export async function POST(request: NextRequest) {
  const origin = process.env.CIQ_WEB_ORIGIN ?? "http://localhost:3000";
  if (request.headers.get("origin") !== origin) return new Response("Forbidden", { status: 403 });
  if (process.env.CIQ_ENVIRONMENT !== "local" || process.env.CIQ_AUTH_MODE !== "local") {
    return new Response("Not found", { status: 404 });
  }
  const form = await request.formData();
  const profile = form.get("profile");
  if (
    typeof profile !== "string" ||
    ![
      "processor",
      "medical_officer",
      "auditor",
      ...(process.env.CIQ_SYNTHETIC_WORKFLOWS === "true"
        ? ["policy_analyst", "policy_approver", "operations_lead", "tenant_admin"]
        : []),
    ].includes(profile)
  ) {
    return new Response("Invalid profile", { status: 400 });
  }
  try {
    const response = await fetch(`${apiUrl()}/v1/auth/local/session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Local-Auth-Key": process.env.CIQ_LOCAL_AUTH_SECRET ?? "",
      },
      body: JSON.stringify({ profile }),
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error("Session unavailable");
    const token: { access_token: string; expires_in: number } = await response.json();
    const result = NextResponse.redirect(new URL("/", origin), 303);
    result.headers.set("Cache-Control", "no-store");
    result.cookies.set(SESSION_COOKIE, token.access_token, {
      httpOnly: true,
      sameSite: "strict",
      secure: origin.startsWith("https://"),
      path: "/",
      maxAge: token.expires_in,
    });
    return result;
  } catch {
    return NextResponse.redirect(new URL("/login?error=session", origin), 303);
  }
}
