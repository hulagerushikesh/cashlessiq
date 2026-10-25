import "server-only";
import { cookies } from "next/headers";
import { apiUrl, SESSION_COOKIE } from "./server-api";

export async function mvpApi<T>(path: string): Promise<T | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  try {
    const response = await fetch(`${apiUrl()}/v3/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export type Job = {
  id: string;
  kind: string;
  subject_id: string;
  state: string;
  attempts: number;
  error_code: string | null;
};
export type Policy = {
  id: string;
  product_id: string;
  version: string;
  name: string;
  status: string;
  author_id: string;
};
export type RequestSummary = {
  request_id: string;
  member_reference: string;
  priority: string;
  workflow_state: string;
  assignee_name: string | null;
  due_at: string;
  sla_breached: boolean;
  outcome: string | null;
  payable_inr: number | null;
};
