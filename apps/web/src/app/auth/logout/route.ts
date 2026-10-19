import { type NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/server-api";

export async function POST(request: NextRequest) {
  const origin = process.env.CIQ_WEB_ORIGIN ?? "http://localhost:3000";
  if (request.headers.get("origin") !== origin) return new Response("Forbidden", { status: 403 });
  const result = NextResponse.redirect(new URL("/login", origin), 303);
  result.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "strict",
    secure: origin.startsWith("https://"),
    path: "/",
    maxAge: 0,
  });
  result.headers.set("Cache-Control", "no-store");
  return result;
}
