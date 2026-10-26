import Link from "next/link";
import { randomUUID } from "node:crypto";
import { rupees } from "@/components/case-workspace";
import type { Job, Policy, RequestSummary } from "@/lib/mvp-api";

export function RequestList({ items }: { items: RequestSummary[] }) {
  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Submitted requests</h2>
      {items.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">
          No requests submitted yet. An analyst and a different approver must first activate a
          policy.
        </p>
      )}
      {items.map((r) => (
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
  );
}

export function PolicyList({ items }: { items: Policy[] }) {
  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Policy versions</h2>
      {items.length === 0 && (
        <p className="mt-3 text-sm text-slate-600">
          No policy versions yet. A policy analyst can create the first proposal.
        </p>
      )}
      {items.map((p) => (
        <article key={p.id} className="mt-4 border-t pt-4 text-sm">
          <Link
            className="font-semibold text-teal-800 underline"
            href={`/workflows/policies/${p.id}`}
          >
            {p.product_id} · {p.version}
          </Link>
          <p className="mt-1 text-slate-500">
            {p.name} · {p.status} ·{" "}
            {p.active
              ? "Currently active"
              : p.status === "approved"
                ? "Awaiting activation by a policy approver"
                : "Not active"}
          </p>
        </article>
      ))}
    </section>
  );
}

export function JobList({ items, operations = false }: { items: Job[]; operations?: boolean }) {
  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Background jobs</h2>
      <p className="mt-2 text-sm text-slate-500">
        Refresh to see progress. Failed processing retries three times before requiring an
        operations review.
      </p>
      {items.length === 0 && <p className="mt-3 text-sm text-slate-600">No background jobs yet.</p>}
      {items.map((j) => (
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
  );
}
