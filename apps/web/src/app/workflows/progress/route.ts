import { type NextRequest, NextResponse } from "next/server";
import { currentIdentity } from "@/lib/server-api";
import { mvpApi } from "@/lib/mvp-api";
import type { Documents, PolicyProgress, RequestProgress } from "@/lib/workflow-progress";

const headers = { "Cache-Control": "private, no-store", Vary: "Cookie" };
const error = (status: number) => NextResponse.json({ unavailable: true }, { status, headers });

export async function GET(request: NextRequest) {
  const session = await currentIdentity();
  if (session.state !== "ready") return error(session.state === "anonymous" ? 401 : 503);
  const kind = request.nextUrl.searchParams.get("kind");
  const id = request.nextUrl.searchParams.get("id") ?? "";
  // Fixed routes only: no arbitrary API paths or caller-selected tenant/role.
  if (!/^[A-Za-z0-9-]{1,120}$/.test(id)) return error(400);
  if (kind === "policy-documents" && id === "POLICY-WORDING") {
    if (!["policy_analyst", "policy_approver"].includes(session.identity.role)) return error(403);
    const documents = await mvpApi<Pick<Documents, "items">>("policy-documents");
    if (!documents) return error(503);
    return NextResponse.json({ ...documents, clinical_restricted: false } satisfies Documents, {
      headers,
    });
  }
  if (kind === "request") {
    const [record, documents] = await Promise.all([
      mvpApi<Omit<RequestProgress, "documents">>(`requests/${encodeURIComponent(id)}`),
      mvpApi<Documents>(`requests/${encodeURIComponent(id)}/documents`),
    ]);
    if (!record || !documents) return error(503);
    return NextResponse.json(
      {
        assessment: record.assessment,
        assessment_job: record.assessment_job,
        clinical_restricted: record.clinical_restricted,
        documents,
      } satisfies RequestProgress,
      { headers },
    );
  }
  if (kind === "policy") {
    const policy = await mvpApi<PolicyProgress>(`policies/${encodeURIComponent(id)}`);
    if (!policy) return error(503);
    return NextResponse.json(
      {
        regression_job_id: policy.regression_job_id,
        regression_state: policy.regression_state,
        regression: policy.regression,
      },
      { headers },
    );
  }
  return error(400);
}
