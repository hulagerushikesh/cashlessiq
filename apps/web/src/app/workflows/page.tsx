import Link from "next/link";
import { currentIdentity } from "@/lib/server-api";
import { mvpApi, type Job, type Policy, type RequestSummary } from "@/lib/mvp-api";
import { CaseServiceError, rupees } from "@/components/case-workspace";
import { randomUUID } from "node:crypto";

export default async function Workflows({
  searchParams,
}: {
  searchParams: Promise<{ result?: string }>;
}) {
  const session = await currentIdentity();
  if (session.state !== "ready") return <CaseServiceError />;
  const [requests, jobs, policies] = await Promise.all([
    mvpApi<{ items: RequestSummary[] }>("requests"),
    mvpApi<{ items: Job[] }>("jobs"),
    mvpApi<{ items: Policy[] }>("policies"),
  ]);
  if (!requests || !jobs || !policies) return <CaseServiceError />;
  const { result } = await searchParams;
  const role = session.identity.role;
  const operations = ["operations_lead", "tenant_admin"].includes(role);
  const panel = "mt-6 rounded-xl border border-slate-200 bg-white p-6";
  return (
    <>
      <h1 className="text-3xl font-semibold">Testing workspace</h1>
      <p className="mt-3 text-sm text-slate-600">
        Submit synthetic requests, follow background processing and review policy versions.
      </p>
      {result && (
        <p role="status" className="mt-4 rounded-lg bg-amber-50 p-4">
          {result === "saved"
            ? "Action saved."
            : result === "conflict"
              ? "The record changed or a workflow requirement is not met. Refresh and review before retrying."
              : "Action was not saved. Check the form and your role, then retry."}
        </p>
      )}
      <nav
        className="mt-5 flex flex-wrap gap-5 text-sm text-teal-800 underline"
        aria-label="Testing tools"
      >
        {["processor", "medical_officer"].includes(role) && (
          <Link href="/workflows/new">Submit a request</Link>
        )}
        {role === "policy_analyst" && (
          <Link href="/workflows/policies/new">Propose a policy version</Link>
        )}
        {role === "tenant_admin" && <Link href="/workflows/members">Manage tenant access</Link>}
        {["auditor", "operations_lead", "tenant_admin", "policy_approver"].includes(role) && (
          <Link href="/workflows/events">Governance history</Link>
        )}
        <Link href="/cases">Golden case queue</Link>
      </nav>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Submitted requests</h2>
        {requests.items.length === 0 && (
          <p className="mt-3 text-sm text-slate-500">
            No requests submitted yet. An analyst and a different approver must first activate a
            policy.
          </p>
        )}
        {requests.items.map((r) => (
          <article
            key={r.request_id}
            className="mt-4 flex flex-wrap justify-between gap-3 border-t pt-4 text-sm"
          >
            <div>
              <Link
                className="font-semibold text-teal-800 underline"
                href={`/workflows/requests/${r.request_id}`}
              >
                {r.member_reference}
              </Link>
              <p className="mt-1 text-slate-500">
                {r.priority} · {r.workflow_state.replaceAll("_", " ")} ·{" "}
                {r.assignee_name ?? "Unassigned"} ·{" "}
                {r.outcome?.replaceAll("_", " ") ?? "Assessment pending"} · {rupees(r.payable_inr)}
              </p>
            </div>
            <p className={r.sla_breached ? "text-red-800" : "text-slate-500"}>
              {["APPROVED", "APPROVED_WITH_DEDUCTIONS"].includes(r.workflow_state)
                ? "Review completed"
                : `${r.sla_breached ? "SLA overdue" : "Due"} · ${new Date(r.due_at).toISOString()}`}
            </p>
          </article>
        ))}
      </section>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Policy versions</h2>
        {policies.items.map((p) => (
          <article key={p.id} className="mt-4 border-t pt-4 text-sm">
            <Link
              className="font-semibold text-teal-800 underline"
              href={`/workflows/policies/${p.id}`}
            >
              {p.name} · {p.version}
            </Link>
            <p className="mt-1 text-slate-500">
              {p.product_id} · {p.status}
            </p>
          </article>
        ))}
      </section>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Background jobs</h2>
        <p className="mt-2 text-sm text-slate-500">
          Refresh to see progress. Failed processing retries three times before requiring an
          operations review.
        </p>
        {jobs.items.map((j) => (
          <article key={j.id} className="mt-4 border-t pt-4 text-sm">
            <p>
              {j.kind} · {j.state} · {j.attempts} attempts
            </p>
            {j.error_code && (
              <p className="mt-1 text-amber-800">
                Processing could not finish. An operations reviewer can retry after resolving the
                cause.
              </p>
            )}
            {operations && j.state === "dead" && (
              <form action="/workflows/commands" method="post" className="mt-3 flex gap-2">
                <input type="hidden" name="operation" value="retry" />
                <input type="hidden" name="id" value={j.id} />
                <input type="hidden" name="command_id" value={randomUUID()} />
                <input
                  name="reason"
                  required
                  maxLength={2000}
                  placeholder="Reason for retry"
                  className="rounded border p-2"
                  aria-label="Reason for retry"
                />
                <button type="submit" className="rounded bg-teal-800 p-2 text-white">
                  Retry job
                </button>
              </form>
            )}
          </article>
        ))}
      </section>
    </>
  );
}
