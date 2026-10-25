import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { randomUUID } from "node:crypto";
import { currentIdentity, sessionApi } from "@/lib/server-api";
import { CaseServiceError, rupees } from "@/components/case-workspace";

export default async function ReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ requestId: string }>;
  searchParams: Promise<{ result?: string; page?: string }>;
}) {
  const { requestId } = await params;
  const query = await searchParams;
  const page = Math.max(1, Math.min(10000, Number(query.page) || 1));
  const api = await sessionApi();
  if (!api) redirect("/login");
  const session = await currentIdentity();
  if (session.state !== "ready") return <CaseServiceError />;
  const [review, people] = await Promise.all([
    api
      .GET("/v3/reviews/{request_id}", {
        params: { path: { request_id: requestId }, query: { history_page: page } },
        signal: AbortSignal.timeout(5000),
      })
      .catch(() => null),
    api.GET("/v3/reviews/people", { signal: AbortSignal.timeout(5000) }).catch(() => null),
  ]);
  if (review?.response.status === 401 || review?.response.status === 403) redirect("/login");
  if (review?.response.status === 404) notFound();
  if (!review?.data || !people?.data) return <CaseServiceError />;
  const record = review.data;
  const medical = session.identity.role === "medical_officer";
  const manager = medical || session.identity.role === "operations_lead";
  const writable = manager || session.identity.role === "processor";
  const final = ["APPROVED", "APPROVED_WITH_DEDUCTIONS"].includes(record.state);
  const assigned = record.assignee?.id === session.identity.user.id;
  const hidden = (
    <>
      <input type="hidden" name="expected_version" value={record.version} />
      <input type="hidden" name="command_id" value={randomUUID()} />
    </>
  );
  const input = "mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
  const panel = "mt-6 rounded-xl border border-slate-200 bg-white p-6";
  return (
    <>
      <Link
        href={
          requestId.startsWith("REQ-")
            ? `/workflows/requests/${encodeURIComponent(requestId)}`
            : `/cases/${encodeURIComponent(requestId)}`
        }
        className="text-sm text-teal-800 underline"
      >
        View recommendation and evidence
      </Link>
      <Link
        href={`/workflows/requests/${encodeURIComponent(requestId)}`}
        className="ml-4 text-sm text-teal-800 underline"
      >
        Supporting documents and assessment
      </Link>
      <h1 className="mt-5 text-3xl font-semibold">Review {record.request_id}</h1>
      <p className="mt-2 text-sm text-slate-600">
        Synthetic testing · {record.state.replaceAll("_", " ")} · Version {record.version}
      </p>
      <p className="mt-2">
        Assigned to {record.assignee?.display_name ?? "nobody"} · Final payable:{" "}
        {rupees(record.final_payable_inr)}
      </p>
      {query.result && (
        <p role="status" className="mt-4 rounded-lg bg-amber-50 p-4">
          {query.result === "saved"
            ? "Review saved."
            : query.result === "conflict"
              ? "The case changed. Your action was not applied. Review the latest state and submit again."
              : "Action was not saved. Check your role, assignment, state, amount and reason, then retry."}
        </p>
      )}
      {writable && (
        <section className={panel} aria-labelledby="commands-title">
          <h2 id="commands-title" className="text-lg font-semibold">
            Reviewer actions
          </h2>
          {!final && (
            <form
              action={`/reviews/${encodeURIComponent(requestId)}/commands`}
              method="post"
              className="mt-4 grid gap-3 sm:grid-cols-2"
            >
              {hidden}
              <input type="hidden" name="action" value="assign" />
              <label className="text-sm">
                Assignee
                <select
                  aria-label="Assignee"
                  name="assignee_id"
                  className={input}
                  defaultValue={manager ? (record.assignee?.id ?? "") : session.identity.user.id}
                >
                  {manager && <option value="">Unassigned</option>}
                  {people.data.items
                    .filter((p) => manager || p.id === session.identity.user.id)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="text-sm">
                Assignment reason
                <input name="note" maxLength={2000} className={input} />
              </label>
              <button type="submit" className="rounded-lg bg-teal-800 p-2 text-white">
                {manager ? "Save assignment" : "Claim case"}
              </button>
            </form>
          )}
          <form
            action={`/reviews/${encodeURIComponent(requestId)}/commands`}
            method="post"
            className="mt-6 grid gap-3"
          >
            {hidden}
            <label className="text-sm">
              Action
              <select aria-label="Action" name="action" className={input} defaultValue="comment">
                <option value="comment">Add comment</option>
                {assigned && record.state === "IN_REVIEW" && (
                  <>
                    <option value="query">Request information</option>
                    <option value="refer">Refer for medical review</option>
                    {medical && (
                      <>
                        <option value="approve">Approve full claimed amount</option>
                        <option value="approve_with_deductions">Approve with deductions</option>
                      </>
                    )}
                  </>
                )}
                {assigned &&
                  (record.state === "NEEDS_INFORMATION" ||
                    (medical && record.state === "REFERRED")) && (
                    <option value="resume">Resume review</option>
                  )}
                {medical && final && <option value="reopen">Reopen completed review</option>}
              </select>
            </label>
            <label className="text-sm">
              Comment or action reason
              <textarea name="note" required maxLength={2000} className={input} />
            </label>
            {medical && (
              <>
                <label className="text-sm">
                  Visibility
                  <select aria-label="Visibility" name="visibility" className={input}>
                    <option value="team">Review team</option>
                    <option value="clinical">Medical officers only</option>
                  </select>
                </label>
                {assigned && record.state === "IN_REVIEW" && (
                  <label className="text-sm">
                    Final payable in whole INR (approvals only)
                    <input type="number" name="payable_inr" min={0} step={1} className={input} />
                  </label>
                )}
              </>
            )}
            <p className="text-xs text-slate-500">
              A human owns the final decision. Every saved action records your identity and reason.
              This does not initiate a payment.
            </p>
            <button type="submit" className="rounded-lg bg-teal-800 p-2 text-white">
              Save reviewer action
            </button>
          </form>
        </section>
      )}
      <section className={panel}>
        <h2 className="text-lg font-semibold">Comments ({record.comments_total})</h2>
        {record.clinical_notes_restricted && (
          <p className="mt-2 text-sm text-slate-500">
            Clinical comments are visible only to medical officers.
          </p>
        )}
        {record.comments.map((c) => (
          <article key={c.id} className="mt-4 border-t pt-3">
            <p className="text-xs text-slate-500">
              {c.actor.display_name} · {new Date(c.created_at).toISOString()} · {c.visibility}
            </p>
            <p className="mt-2 whitespace-pre-wrap text-sm">{c.body}</p>
          </article>
        ))}
      </section>
      <section className={panel}>
        <h2 className="text-lg font-semibold">Audit history ({record.audit_total})</h2>
        {record.audit.map((e) => (
          <article key={e.event_id} className="mt-4 border-t pt-3 text-sm">
            <p>
              Version {e.aggregate_version} · {e.action.replaceAll("_", " ")} ·{" "}
              {e.actor.display_name}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {new Date(e.occurred_at).toISOString()} · {e.event_id}
            </p>
            {typeof e.payload.payable_inr === "number" && (
              <p>Final payable {rupees(e.payload.payable_inr)}</p>
            )}
          </article>
        ))}
        <nav aria-label="History pages" className="mt-4 flex gap-4">
          {page > 1 && <Link href={`?page=${page - 1}`}>Newer history</Link>}
          {Math.max(record.audit_total, record.comments_total) > page * 50 && (
            <Link href={`?page=${page + 1}`}>Older history</Link>
          )}
        </nav>
      </section>
    </>
  );
}
