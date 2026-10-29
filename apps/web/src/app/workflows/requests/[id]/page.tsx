import { FactsEditor, type Facts } from "@/components/assessment-fields";
import { WorkflowForm } from "@/components/workflow-form";
import { WorkflowFeedback } from "@/components/workflow-feedback";
import { randomUUID } from "node:crypto";
import Link from "next/link";
import { mvpApi } from "@/lib/mvp-api";
import { currentIdentity, sessionApi } from "@/lib/server-api";
import { CaseServiceError } from "@/components/case-workspace";

import { RequestResults, SupportingDocuments } from "@/components/background-progress";
import type { RequestProgress, Documents } from "@/lib/workflow-progress";

type RequestDetail = Omit<RequestProgress, "documents"> & {
  request_id: string;
  facts: Facts;
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
      {golden && (
        <Link
          className="mt-4 inline-block text-teal-800 underline"
          href={`/reviews/${encodeURIComponent(id)}`}
        >
          Open reviewer workflow
        </Link>
      )}
      {record && (
        <RequestResults
          id={id}
          initial={{
            assessment: record.assessment,
            assessment_job: record.assessment_job,
            clinical_restricted: record.clinical_restricted,
            documents,
          }}
        />
      )}
      {write && (
        <WorkflowForm
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
        </WorkflowForm>
      )}
      {golden && <SupportingDocuments documents={documents} />}
      {record &&
        medical &&
        review?.state === "NEEDS_INFORMATION" &&
        review.assignee?.id === session.identity.user.id && (
          <WorkflowForm action="/workflows/commands" method="post" className={panel}>
            <h2 className="text-xl font-semibold">Correct facts and reassess</h2>
            <p className="mt-2 text-sm text-slate-500">
              Transcribe verified information from the supporting document. The previous facts and
              decision remain in history.
            </p>
            <input type="hidden" name="operation" value="amend" />
            <input type="hidden" name="id" value={id} />
            <input type="hidden" name="command_id" value={randomUUID()} />
            <input type="hidden" name="expected_version" value={review.version} />
            <div className="mt-4">
              <FactsEditor initial={record.facts} />
            </div>
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
          </WorkflowForm>
        )}
    </>
  );
}
