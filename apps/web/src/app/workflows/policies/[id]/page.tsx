import { randomUUID } from "node:crypto";
import Link from "next/link";
import { mvpApi } from "@/lib/mvp-api";
import { currentIdentity } from "@/lib/server-api";
import { CaseServiceError } from "@/components/case-workspace";

type Rule = {
  rule_id: string;
  rule_type: string;
  clause_id: string;
  params: Record<string, unknown>;
};
type Clause = { clause_id: string; title: string; text: string; page: number };
type PolicyDetail = {
  id: string;
  author_id: string;
  version: string;
  status: string;
  active: boolean;
  activation_id: string | null;
  regression_state: string;
  regression: {
    passed: boolean;
    count: number;
    checks: {
      name: string;
      passed: boolean;
      actual_outcome: string;
      actual_payable_inr: number | null;
    }[];
  } | null;
  proposal: {
    name: string;
    reason: string;
    effective_from: string;
    effective_to: string | null;
    wording_document_id?: string | null;
    rules: Rule[];
    clauses: Clause[];
  };
  previous_rules: Rule[];
  previous_clauses: Clause[];
};

export default async function PolicyPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ result?: string }>;
}) {
  const { id } = await params;
  const [policy, session] = await Promise.all([
    mvpApi<PolicyDetail>(`policies/${encodeURIComponent(id)}`),
    currentIdentity(),
  ]);
  if (!policy || session.state !== "ready") return <CaseServiceError />;
  const { result } = await searchParams;
  const canApprove =
    session.identity.role === "policy_approver" && session.identity.user.id !== policy.author_id;
  const panel = "mt-6 rounded-xl border border-slate-200 bg-white p-6";
  return (
    <>
      <Link href="/workflows" className="text-sm text-teal-800 underline">
        Back to testing workspace
      </Link>
      <h1 className="mt-5 text-3xl font-semibold">{policy.proposal.name}</h1>
      <p className="mt-3 text-sm">
        {policy.version} · {policy.status} · {policy.active ? "Currently active" : "Not active"}
      </p>
      <p className="mt-2 text-sm text-slate-600">
        Effective {policy.proposal.effective_from} to{" "}
        {policy.proposal.effective_to ?? "no end date"}
      </p>
      {result && (
        <p role="status" className="mt-4 rounded bg-amber-50 p-4">
          {result === "saved"
            ? "Policy action saved."
            : "Policy action was not saved. Check the review decision, regression results, effective dates and current active version."}
        </p>
      )}
      <section className={panel}>
        <h2 className="text-xl font-semibold">Proposal reason</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm">{policy.proposal.reason}</p>
        {policy.proposal.wording_document_id && (
          <a
            className="mt-3 inline-block text-sm text-teal-800 underline"
            href={`/workflows/documents/${policy.proposal.wording_document_id}`}
          >
            Download source policy wording
          </a>
        )}
      </section>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Rules compared with the active version</h2>
        {policy.proposal.rules.map((rule) => {
          const before = policy.previous_rules.find((r) => r.rule_id === rule.rule_id);
          return (
            <article key={rule.rule_id} className="mt-4 border-t pt-4 text-sm">
              <h3 className="font-semibold">
                {rule.rule_type.replaceAll("_", " ")} · {rule.clause_id}
              </h3>
              <p className="mt-2 break-words">Proposed: {JSON.stringify(rule.params)}</p>
              <p className="mt-1 break-words text-slate-500">
                Active: {before ? JSON.stringify(before.params) : "New rule"}
              </p>
            </article>
          );
        })}
        {policy.previous_rules
          .filter((r) => !policy.proposal.rules.some((p) => p.rule_id === r.rule_id))
          .map((r) => (
            <p key={r.rule_id} className="mt-4 text-sm text-red-800">
              Removed rule: {r.rule_type} · {r.clause_id}
            </p>
          ))}
      </section>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Versioned clauses</h2>
        {policy.proposal.clauses.map((c) => (
          <article key={c.clause_id} className="mt-4 border-t pt-4 text-sm">
            <h3 className="font-semibold">
              {c.clause_id} · {c.title} · Page {c.page}
            </h3>
            <p className="mt-2 whitespace-pre-wrap">{c.text}</p>
            {policy.previous_clauses.find((p) => p.clause_id === c.clause_id)?.text !== c.text && (
              <p className="mt-2 text-amber-800">New or changed wording</p>
            )}
          </article>
        ))}
      </section>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Regression results</h2>
        <p className="mt-3 text-sm">
          {policy.regression_state} ·{" "}
          {policy.regression
            ? `${policy.regression.passed ? "Passed" : "Failed"} · ${policy.regression.count} cases`
            : "Refresh after background processing finishes."}
        </p>
        {policy.regression?.checks.map((c) => (
          <p key={c.name} className="mt-2 text-sm">
            {c.passed ? "Pass" : "Fail"} · {c.name} · {c.actual_outcome} ·{" "}
            {c.actual_payable_inr === null ? "Not calculated" : `INR ${c.actual_payable_inr}`}
          </p>
        ))}
      </section>
      {canApprove && (
        <form action="/workflows/commands" method="post" className={panel}>
          <input type="hidden" name="operation" value="policy" />
          <input type="hidden" name="id" value={id} />
          <input type="hidden" name="command_id" value={randomUUID()} />
          <input type="hidden" name="expected_activation" value={policy.activation_id ?? ""} />
          <label className="block text-sm">
            Review decision
            <select name="action" className="mt-2 block w-full rounded border p-2">
              {policy.status === "proposed" && (
                <>
                  <option value="approve">Approve version</option>
                  <option value="reject">Reject version</option>
                </>
              )}
              {policy.status === "approved" && (
                <option value="activate">Activate this version (or roll back to it)</option>
              )}
            </select>
          </label>
          <label className="mt-4 block text-sm">
            Reason
            <textarea
              name="reason"
              required
              maxLength={2000}
              className="mt-2 w-full rounded border p-2"
            />
          </label>
          <button
            type="submit"
            disabled={policy.status === "rejected"}
            className="mt-4 rounded-lg bg-teal-800 p-3 text-white disabled:opacity-50"
          >
            Save policy decision
          </button>
        </form>
      )}
    </>
  );
}
