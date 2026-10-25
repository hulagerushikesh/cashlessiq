import { type NextRequest, NextResponse } from "next/server";
import { apiUrl, SESSION_COOKIE } from "@/lib/server-api";
import { boundedForm } from "@/lib/bounded-form";

export async function POST(request: NextRequest) {
  const origin = process.env.CIQ_WEB_ORIGIN ?? "http://localhost:3000";
  if (request.headers.get("origin") !== origin) return new Response("Forbidden", { status: 403 });
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.redirect(new URL("/login", origin), 303);
  let destination = new URL("/workflows", origin);
  try {
    const form = await boundedForm(request, 3 * 1024 * 1024);
    const operation = form.get("operation");
    const id = encodeURIComponent(String(form.get("id") ?? ""));
    let path: string;
    let body: BodyInit;
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
    const command_id = form.get("command_id");
    const reason = form.get("reason");
    if (operation === "propose") {
      path = "policies";
      const proposal = JSON.parse(String(form.get("proposal")));
      body = JSON.stringify({
        ...proposal,
        command_id,
        reason,
        wording_document_id: form.get("wording_document_id") || null,
      });
    } else if (operation === "submit") {
      path = "requests";
      const integer = (name: string) => {
        const value = form.get(name);
        if (
          typeof value !== "string" ||
          !/^\d+$/.test(value) ||
          !Number.isSafeInteger(Number(value))
        )
          throw new Error("Invalid integer");
        return Number(value);
      };
      body = JSON.stringify({
        command_id,
        product_id: form.get("product_id"),
        synthetic_data: form.get("synthetic_data") === "true",
        priority: form.get("priority"),
        facts: {
          member_reference: form.get("member_reference"),
          inception_date: form.get("inception_date"),
          continuous_cover_since: form.get("continuous_cover_since"),
          admission_date: form.get("admission_date") || null,
          sum_insured_inr: integer("sum_insured_inr"),
          si_remaining_inr: integer("si_remaining_inr"),
          diagnosis: form.get("diagnosis") || null,
          procedure: form.get("procedure") || null,
          room_category: form.get("room_category") || null,
          room_rent_per_day_inr: form.get("room_rent_per_day_inr")
            ? integer("room_rent_per_day_inr")
            : null,
          planned_los_days: form.get("planned_los_days") ? integer("planned_los_days") : null,
          cost_breakup: JSON.parse(String(form.get("cost_breakup"))),
          estimated_total_inr: form.get("estimated_total_inr")
            ? integer("estimated_total_inr")
            : null,
          clinical_note: form.get("clinical_note") || null,
        },
      });
    } else if (operation === "amend") {
      path = `requests/${id}/amend`;
      destination = new URL(`/workflows/requests/${id}`, origin);
      body = JSON.stringify({
        command_id,
        reason,
        expected_version: Number(form.get("expected_version")),
        facts: JSON.parse(String(form.get("facts"))),
      });
    } else if (operation === "policy") {
      path = `policies/${id}/commands`;
      destination = new URL(`/workflows/policies/${id}`, origin);
      body = JSON.stringify({
        command_id,
        reason,
        action: form.get("action"),
        expected_activation: form.get("expected_activation") || null,
      });
    } else if (operation === "retry") {
      path = `jobs/${id}/retry`;
      body = JSON.stringify({ command_id, reason });
    } else if (operation === "member") {
      path = `admin/memberships/${id}`;
      destination = new URL("/workflows/members", origin);
      body = JSON.stringify({
        command_id,
        reason,
        expected_role: form.get("expected_role"),
        role: form.get("role"),
        expected_active: form.get("expected_active") === "true",
        active: form.get("active") === "true",
      });
    } else if (operation === "upload" || operation === "policy-upload") {
      const file = form.get("document");
      if (!(file instanceof File) || file.size > 2 * 1024 * 1024 || file.type !== "application/pdf")
        throw new Error("Unsupported upload");
      path = operation === "policy-upload" ? "policy-documents" : `requests/${id}/documents`;
      destination = new URL(
        operation === "policy-upload" ? "/workflows/policies/new" : `/workflows/requests/${id}`,
        origin,
      );
      headers["Content-Type"] = "application/pdf";
      headers["Idempotency-Key"] = String(command_id);
      headers["X-Synthetic-Data"] = form.get("synthetic_data") === "true" ? "true" : "false";
      body = await file.arrayBuffer();
    } else {
      throw new Error("Unsupported operation");
    }
    const response = await fetch(`${apiUrl()}/v3/${path}`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (response.ok && (operation === "submit" || operation === "propose")) {
      const result = await response.json();
      destination = new URL(
        operation === "submit"
          ? `/workflows/requests/${encodeURIComponent(result.request_id)}`
          : `/workflows/policies/${encodeURIComponent(result.policy_id)}`,
        origin,
      );
    }
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
