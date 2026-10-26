import { PolicyEditor, type PolicyDefinition } from "@/components/policy-editor";
import { WorkflowForm } from "@/components/workflow-form";
import { randomUUID } from "node:crypto";
import { mvpApi } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";
import { currentIdentity } from "@/lib/server-api";
import { WorkflowFeedback } from "@/components/workflow-feedback";

export default async function NewPolicy({
  searchParams,
}: {
  searchParams: Promise<{ result?: string; error?: string }>;
}) {
  const session = await currentIdentity();
  if (session.state !== "ready") return <CaseServiceError />;
  if (session.identity.role !== "policy_analyst")
    return (
      <p role="alert">
        Only policy analysts can propose policies. Use the policy library to review versions, or
        Sign out to choose the analyst role.
      </p>
    );
  const documents = await mvpApi<{
    items: { id: string; state: string; text: string | null; digest: string }[];
  }>("policy-documents");
  const template = await mvpApi<PolicyDefinition>("policy-template");
  if (!template) return <CaseServiceError />;
  return (
    <>
      <h1 className="text-3xl font-semibold">Propose a policy version</h1>
      <WorkflowFeedback
        {...(await searchParams)}
        success="PDF uploaded. Refresh shortly to check extraction progress."
      />
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
        Enter a product ID and version to test the synthetic baseline. Rule editing and a wording
        PDF are optional; use the labelled fields below to make changes. A different person must
        review the diff and passing regression results before activation.
      </p>
      <details className="mt-6 max-w-5xl rounded-xl border bg-white p-4">
        <summary className="cursor-pointer text-sm font-medium">
          Optional: upload fictional policy wording PDF
        </summary>
        <WorkflowForm
          action="/workflows/commands"
          method="post"
          encType="multipart/form-data"
          className="mt-6 max-w-5xl space-y-4 rounded-xl border bg-white p-6"
        >
          <h2 className="text-lg font-semibold">Extract synthetic policy wording</h2>
          <input type="hidden" name="operation" value="policy-upload" />
          <input type="hidden" name="command_id" value={randomUUID()} />
          <label className="block text-sm">
            Policy PDF
            <input
              type="file"
              name="document"
              required
              accept="application/pdf"
              className="mt-2 block"
            />
          </label>
          <label className="block text-sm">
            <input type="checkbox" name="synthetic_data" value="true" required /> Fictional test
            data only, up to 2 MiB and 20 pages.
          </label>
          <button type="submit" className="rounded-lg bg-teal-800 p-3 text-white">
            Upload wording for extraction
          </button>
        </WorkflowForm>
      </details>
      {documents?.items.map((d) => (
        <article key={d.id} className="mt-4 max-w-5xl rounded-xl border bg-white p-4 text-sm">
          <p>{d.state.replaceAll("_", " ")}</p>
          <p className="mt-2 break-all text-xs text-slate-500">SHA-256 {d.digest}</p>
          {d.text && (
            <pre className="mt-3 max-h-60 overflow-auto whitespace-pre-wrap font-sans">
              {d.text}
            </pre>
          )}
        </article>
      ))}
      <WorkflowForm
        action="/workflows/commands"
        method="post"
        className="mt-6 max-w-5xl space-y-5 rounded-xl border bg-white p-6"
      >
        <input type="hidden" name="operation" value="propose" />
        <input type="hidden" name="command_id" value={randomUUID()} />
        <label className="block text-sm">
          Policy product ID
          <input
            name="product_id"
            required
            maxLength={80}
            pattern="[A-Za-z0-9_-]+"
            placeholder="HUMAN_TEST_20261026"
            className="mt-2 block w-full rounded border p-2"
          />
        </label>
        <label className="block text-sm">
          Policy version
          <input
            name="version"
            required
            maxLength={80}
            defaultValue="V1"
            className="mt-2 block w-full rounded border p-2"
          />
        </label>
        <label className="block text-sm">
          Source wording
          <select name="wording_document_id" className="mt-2 block w-full rounded border p-2">
            <option value="">Synthetic baseline reference only</option>
            {documents?.items
              .filter((d) => d.state === "extracted")
              .map((d) => (
                <option key={d.id} value={d.id}>
                  Extracted PDF · {d.digest.slice(0, 12)}
                </option>
              ))}
          </select>
        </label>
        <PolicyEditor initial={template} />
        <label className="block text-sm">
          Proposal reason
          <textarea
            name="reason"
            required
            maxLength={2000}
            className="mt-2 w-full rounded-lg border p-3 text-sm"
          />
        </label>
        <button type="submit" className="rounded-lg bg-teal-800 p-3 text-white">
          Save proposal and run regressions
        </button>
      </WorkflowForm>
    </>
  );
}
