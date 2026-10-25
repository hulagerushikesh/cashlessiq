import { randomUUID } from "node:crypto";
import { mvpApi } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";

export default async function NewPolicy() {
  const documents = await mvpApi<{
    items: { id: string; state: string; text: string | null; digest: string }[];
  }>("policy-documents");
  const template = await mvpApi<Record<string, unknown>>("policy-template");
  if (!template) return <CaseServiceError />;
  return (
    <>
      <h1 className="text-3xl font-semibold">Propose a policy version</h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
        Start from the reviewed synthetic baseline. Change the product, version, clauses, supported
        rule parameters and expected test results. Unsupported rules are rejected. A different
        person must review the diff and passing regression results before activation.
      </p>
      <form
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
          <input type="checkbox" name="synthetic_data" value="true" required /> Fictional test data
          only, up to 2 MiB and 20 pages.
        </label>
        <button type="submit" className="rounded-lg bg-teal-800 p-3 text-white">
          Upload wording for extraction
        </button>
      </form>
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
      <form
        action="/workflows/commands"
        method="post"
        className="mt-6 max-w-5xl space-y-5 rounded-xl border bg-white p-6"
      >
        <input type="hidden" name="operation" value="propose" />
        <input type="hidden" name="command_id" value={randomUUID()} />
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
        <label className="block text-sm">
          Versioned policy definition
          <textarea
            name="proposal"
            required
            spellCheck={false}
            rows={24}
            className="mt-2 w-full rounded-lg border p-3 font-mono text-xs"
            defaultValue={JSON.stringify(template, null, 2)}
          />
        </label>
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
      </form>
    </>
  );
}
