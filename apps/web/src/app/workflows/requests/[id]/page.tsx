import { WorkflowFeedback } from "@/components/workflow-feedback";
import { randomUUID } from "node:crypto";
import Link from "next/link";
import { mvpApi } from "@/lib/mvp-api";
import { currentIdentity, sessionApi } from "@/lib/server-api";
import { CaseServiceError, rupees } from "@/components/case-workspace";

type RequestDetail = {
  request_id: string;
  facts: Record<string, unknown>;
  assessment: {
    outcome: string;
    payable_inr: number | null;
    policy_version: string;
    policy_id: string;
    input_digest: string;
    rules_digest: string;
    queries?: string[];
    refer_reasons?: string[];
    payable?: {
      lines: {
        item: string;
        payable_inr: number;
        reason: string;
        calc: string;
        citations: { id: string }[];
      }[];
    } | null;
  } | null;
  clinical_restricted: boolean;
};
type Documents = {
  clinical_restricted: boolean;
  items: { id: string; state: string; digest: string; text: string | null }[];
};
type Review = { version: number; state: string; assignee: { id: string } | null };

export default async function RequestPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ result?: string; error?: string }>;
}) {
  const { id } = await params;
  const [record, documents, session, review] = await Promise.all([
    mvpApi<RequestDetail>(`requests/${encodeURIComponent(id)}`),
    mvpApi<Documents>(`requests/${encodeURIComponent(id)}/documents`),
    currentIdentity(),
    mvpApi<Review>(`reviews/${encodeURIComponent(id)}`),
  ]);
  if (!documents || session.state !== "ready") return <CaseServiceError />;
  let golden = false;
  if (!record) {
    const api = await sessionApi();
    const old = await api
      ?.GET("/v1/cases/{request_id}", {
        params: { path: { request_id: id } },
        signal: AbortSignal.timeout(5000),
      })
      .catch(() => null);
    if (!old?.data) return <CaseServiceError />;
    golden = true;
  }
  const feedback = await searchParams;
  const medical = session.identity.role === "medical_officer";
  const write = medical || session.identity.role === "processor";
  const panel = "mt-6 rounded-xl border border-slate-200 bg-white p-6";
  return (
    <>
      <Link href="/workflows" className="text-sm text-teal-800 underline">
        Back to testing workspace
      </Link>
      <h1 className="mt-5 break-words text-3xl font-semibold">Request {id}</h1>
      <WorkflowFeedback
        {...feedback}
        success="Action saved. Background processing may still be pending."
      />
      {(review || golden) && (
        <Link
          className="mt-4 inline-block rounded-lg bg-teal-800 px-4 py-2 text-sm text-white"
          href={`/reviews/${encodeURIComponent(id)}`}
        >
          Open reviewer workflow
        </Link>
      )}
      {record && (
        <section className={panel}>
          <h2 className="text-xl font-semibold">Assessment</h2>
          {record.assessment ? (
            <>
              <p className="mt-3">
                {record.assessment.outcome.replaceAll("_", " ")} ·{" "}
                {rupees(record.assessment.payable_inr)}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Policy {record.assessment.policy_version} · Deterministic calculation · Human review
                required
              </p>
              <Link
                href={`/workflows/policies/${record.assessment.policy_id}`}
                className="mt-3 inline-block text-sm text-teal-800 underline"
              >
                View pinned policy clauses and wording
              </Link>
              {record.assessment.queries?.map((q) => (
                <p key={q} className="mt-3 text-sm text-amber-800">
                  {q}
                </p>
              ))}
              {record.assessment.refer_reasons?.map((q) => (
                <p key={q} className="mt-3 text-sm text-amber-800">
                  {q}
                </p>
              ))}
              {record.assessment.payable?.lines.map((line) => (
                <article key={line.item} className="mt-4 border-t pt-4 text-sm">
                  <h3 className="font-semibold">
                    {line.item} · {rupees(line.payable_inr)}
                  </h3>
                  <p className="mt-2">{line.reason}</p>
                  <p className="mt-2 font-mono text-xs">{line.calc}</p>
                  <p className="mt-2 text-xs text-teal-800">
                    {line.citations.map((c) => c.id).join(" · ")}
                  </p>
                </article>
              ))}
            </>
          ) : (
            <p className="mt-3 text-sm text-slate-600">
              Assessment queued or processing. Refresh shortly. Check background jobs if processing
              cannot finish.
            </p>
          )}
          {record.clinical_restricted && (
            <p className="mt-3 text-sm text-slate-500">
              Clinical facts, detailed policy checks and document text are restricted to medical
              officers.
            </p>
          )}
        </section>
      )}
      {write && (
        <form
          action="/workflows/commands"
          method="post"
          encType="multipart/form-data"
          className={panel}
        >
          <h2 className="text-xl font-semibold">Upload a supporting PDF</h2>
          <p className="mt-2 text-sm text-slate-500">
            Fictional documents only, up to 2 MiB and 20 pages. Encrypted PDFs, scripts, forms and
            attachments are rejected. Scanned files need manual transcription. Extracted text never
            changes assessment facts automatically.
          </p>
          <input type="hidden" name="operation" value="upload" />
          <input type="hidden" name="id" value={id} />
          <input type="hidden" name="command_id" value={randomUUID()} />
          <label className="mt-4 block text-sm">
            PDF document
            <input
              className="mt-2 block"
              name="document"
              type="file"
              accept="application/pdf"
              required
            />
          </label>
          <label className="mt-4 block text-sm">
            <input type="checkbox" name="synthetic_data" value="true" required /> This PDF contains
            fictional test data only.
          </label>
          <button type="submit" className="mt-4 rounded-lg bg-teal-800 p-3 text-white">
            Upload for extraction
          </button>
        </form>
      )}
      <section className={panel}>
        <h2 className="text-xl font-semibold">Supporting documents</h2>
        {documents.items.map((d) => (
          <article key={d.id} className="mt-4 border-t pt-4 text-sm">
            <p>{d.state.replaceAll("_", " ")}</p>
            <p className="mt-1 break-all text-xs text-slate-500">SHA-256 {d.digest}</p>
            {medical && d.state === "extracted" && (
              <a
                href={`/workflows/documents/${d.id}`}
                className="mt-3 inline-block text-teal-800 underline"
              >
                Download PDF
              </a>
            )}
            {d.text && (
              <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 font-sans text-sm">
                {d.text}
              </pre>
            )}
          </article>
        ))}
      </section>
      {record &&
        medical &&
        review?.state === "NEEDS_INFORMATION" &&
        review.assignee?.id === session.identity.user.id && (
          <form action="/workflows/commands" method="post" className={panel}>
            <h2 className="text-xl font-semibold">Correct facts and reassess</h2>
            <p className="mt-2 text-sm text-slate-500">
              Transcribe verified information from the supporting document. The previous facts and
              decision remain in history.
            </p>
            <input type="hidden" name="operation" value="amend" />
            <input type="hidden" name="id" value={id} />
            <input type="hidden" name="command_id" value={randomUUID()} />
            <input type="hidden" name="expected_version" value={review.version} />
            <label className="mt-4 block text-sm">
              Updated structured facts
              <textarea
                name="facts"
                required
                rows={18}
                className="mt-2 w-full rounded border p-3 font-mono text-xs"
                defaultValue={JSON.stringify(record.facts, null, 2)}
              />
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
            <button type="submit" className="mt-4 rounded-lg bg-teal-800 p-3 text-white">
              Save facts and queue reassessment
            </button>
          </form>
        )}
    </>
  );
}
