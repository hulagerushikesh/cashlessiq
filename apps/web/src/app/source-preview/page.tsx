import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { SourceCaseDetail } from "@cashlessiq/api-client";
import { CaseServiceError, CaseWorkspace } from "@/components/case-workspace";
import { SourceCaseView, SourceUnavailable } from "@/components/source-case-detail";
import { currentIdentity } from "@/lib/server-api";

export const dynamic = "force-dynamic";

/** Authenticated local UI fixtures only. Never a source or demo fallback. */
export default async function SourcePreview({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  if (process.env.CIQ_ENVIRONMENT !== "local" || process.env.CIQ_AUTH_MODE !== "local") notFound();
  const session = await currentIdentity();
  if (session.state === "anonymous") redirect("/login");
  if (session.state !== "ready") return <CaseServiceError />;
  const state = (await searchParams).state ?? "missing";
  if (!["saved", "missing", "query", "refer", "unavailable"].includes(state)) notFound();
  const record: SourceCaseDetail = {
    schema_version: 2,
    data_mode: "synthetic_source",
    tenant_id: session.identity.tenant.id,
    case: {
      request_id: "UI-FIXTURE-001",
      policy_id: "UI-POLICY-001",
      product_id: "UI-PRODUCT-001",
      product_name: "Fictional UI policy · Not a source record",
      policy_version: "fixture-v1",
      continuous_cover_since: "2022-01-01",
      admission_date: "2026-01-01",
      estimated_total_inr: 100000,
    },
    member_history: {
      member_id: "UI-MEMBER-001",
      sum_insured_inr: 500000,
      cumulative_bonus_inr: 0,
      status: "ACTIVE",
      claim_count: 0,
      total_paid_inr: 0,
      last_admission_date: null,
      conditions_visible: false,
      conditions: null,
    },
    recommendation:
      state === "missing"
        ? { state: "MISSING" }
        : {
            state: "SAVED",
            outcome:
              state === "query" ? "QUERY" : state === "refer" ? "REFER" : "APPROVE_WITH_DEDUCTIONS",
            claimed_inr: 100000,
            payable_inr: state === "query" || state === "refer" ? null : 95000,
            amount_basis:
              state === "query" || state === "refer" ? "supplied_estimate" : "saved_calculation",
          },
    evidence_kind: "product_clause_register",
    evidence: [],
  };
  return (
    <CaseWorkspace identity={session.identity}>
      <div className="mb-7 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <p className="font-semibold">Local UI fixture preview · No Snowflake reads</p>
        <p className="mt-2 text-sm leading-6">
          Fictional presentation examples, not saved source records. These states do not describe
          GOL001, GOL024 or GOL027. All roles see the same nonclinical fixtures; this is not a
          tenant-isolation or medical-access test.
        </p>
        <nav aria-label="Fixture states" className="mt-4 flex flex-wrap gap-4 text-sm">
          {["saved", "missing", "query", "refer", "unavailable"].map((value) => (
            <Link
              key={value}
              href={`/source-preview?state=${value}`}
              aria-current={state === value ? "page" : undefined}
              className="text-teal-900 underline"
            >
              {value.charAt(0).toUpperCase() + value.slice(1)}
            </Link>
          ))}
        </nav>
      </div>
      {state === "unavailable" ? <SourceUnavailable /> : <SourceCaseView record={record} />}
    </CaseWorkspace>
  );
}
