import "server-only";
import { cookies } from "next/headers";
import { createApiClient, type Identity } from "@cashlessiq/api-client";

export const SESSION_COOKIE = "ciq_session";
export const apiUrl = () => process.env.CIQ_API_URL ?? "http://127.0.0.1:8000";

export async function currentIdentity(): Promise<
  { state: "ready"; identity: Identity } | { state: "anonymous" | "unavailable" }
> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return { state: "anonymous" };
  try {
    const { data, response } = await createApiClient(apiUrl(), token).GET("/v1/me", {
      signal: AbortSignal.timeout(5000),
    });
    if (response.status === 401 || response.status === 403) return { state: "anonymous" };
    return data ? { state: "ready", identity: data } : { state: "unavailable" };
  } catch {
    return { state: "unavailable" };
  }
}
