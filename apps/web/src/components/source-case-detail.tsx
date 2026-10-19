import { LockKeyhole } from "lucide-react";
import type { SourceCaseDetail } from "@cashlessiq/api-client";
import { OutcomeBadge, rupees } from "@/components/case-workspace";
import { SourceClauseRegister } from "@/components/source-clause-register";

export function SourceUnavailable() {
  return (
    <section
      role="alert"
      aria-labelledby="source-error-title"
      className="rounded-xl border border-amber-200 bg-white p-6"
    >
      <h2 id="source-error-title" className="text-lg font-semibold">
        Source unavailable
      </h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        The source could not be read or validated. Recommendation status is unknown, not missing. No
        demo recommendation was substituted and no action was saved.
      </p>
    </section>
  );
}

/** Presentation only: accepts the v2 contract; never fetches or computes money. */
export function SourceCaseView({ record }: { record: SourceCaseDetail }) {
  const recommendation = record.recommendation;
  const history = record.member_history;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="break-all text-3xl font-semibold">{record.case.request_id}</h1>
        {recommendation.state === "SAVED" && <OutcomeBadge outcome={recommendation.outcome} />}
      </div>
      <p className="text-sm text-slate-600">
        Read-only recommendation summary. A human makes the final decision.
      </p>
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">Recommendation</h2>
        {recommendation.state === "MISSING" ? (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-5">
            <h3 className="font-semibold">No saved recommendation</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              The successful scoped read returned no saved recommendation. This is not a query,
              referral, rejection or zero payable. No assessment has been generated here.
            </p>
          </div>
        ) : (
          <>
            <p className="mt-3 text-sm text-slate-600">Saved draft · Not a final decision</p>
            <dl className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 p-4">
                <dt className="text-xs text-slate-500">
                  {recommendation.amount_basis === "saved_calculation"
                    ? "Saved claimed amount"
                    : "Supplied estimate in saved draft"}
                </dt>
                <dd className="mt-2 text-2xl font-semibold">
                  {rupees(recommendation.claimed_inr)}
                </dd>
              </div>
              <div className="rounded-lg bg-teal-50 p-4">
                <dt className="text-xs text-teal-800">Draft payable</dt>
                <dd className="mt-2 text-2xl font-semibold text-teal-900">
                  {rupees(recommendation.payable_inr)}
                </dd>
              </div>
            </dl>
            {recommendation.payable_inr === null && (
              <p className="mt-4 text-sm text-slate-600">
                This saved query or referral has no payable calculation. Not calculated does not
                mean zero. Query text and referral reasons are not included in this contract.
              </p>
            )}
          </>
        )}
        <p className="mt-5 text-xs leading-5 text-slate-500">
          Full calculation trace and clinical narrative are not included in this read model.
        </p>
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">Request & member history</h2>
        <dl className="mt-5 grid gap-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Policy", `${record.case.policy_id} · ${record.case.policy_version}`],
            ["Member reference", history.member_id],
            ["Admission", record.case.admission_date],
            ["Continuous cover since", record.case.continuous_cover_since],
            ["Supplied request estimate", rupees(record.case.estimated_total_inr)],
            ["Policy status", history.status],
            ["Sum insured", rupees(history.sum_insured_inr)],
            ["Cumulative bonus", rupees(history.cumulative_bonus_inr)],
            ["Recorded claims", String(history.claim_count)],
            ["Recorded paid total", rupees(history.total_paid_inr)],
            ["Last claim admission", history.last_admission_date ?? "No recorded claim admission"],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="mt-1.5 break-words font-medium">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-5 text-xs text-slate-500">
          Recorded amounts only; remaining cover and eligibility are not calculated here.
        </p>
        <h3 className="mt-6 font-semibold">Member conditions</h3>
        {!history.conditions_visible ? (
          <p className="mt-3 flex gap-2 text-sm text-slate-500">
            <LockKeyhole size={16} className="shrink-0" /> Conditions are restricted for this role.
          </p>
        ) : history.conditions?.length ? (
          <ul className="mt-3 space-y-3 text-sm">
            {history.conditions.map((condition) => (
              <li key={condition.icd10_code} className="rounded-lg bg-slate-50 p-3">
                {condition.icd10_code} · {condition.condition_name}
                <p className="mt-1 text-xs text-slate-500">
                  First diagnosed {condition.first_diagnosed_on} · Declared at proposal:{" "}
                  {condition.declared_at_proposal ? "Yes" : "No"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No recorded member conditions.</p>
        )}
      </section>
      <SourceClauseRegister productName={record.case.product_name} clauses={record.evidence} />
    </div>
  );
}
