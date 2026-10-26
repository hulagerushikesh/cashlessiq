import { FactsEditor } from "@/components/assessment-fields";
import { WorkflowForm } from "@/components/workflow-form";
import { randomUUID } from "node:crypto";
import { mvpApi, type Policy } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";
import { currentIdentity } from "@/lib/server-api";
import Link from "next/link";
import { WorkflowFeedback } from "@/components/workflow-feedback";

export default async function NewRequest({
  searchParams,
}: {
  searchParams: Promise<{ result?: string; error?: string }>;
}) {
  const [policies, session] = await Promise.all([
    mvpApi<{ items: Policy[] }>("policies?active_only=true"),
    currentIdentity(),
  ]);
  if (!policies || session.state !== "ready") return <CaseServiceError />;
  if (!["processor", "medical_officer"].includes(session.identity.role))
    return (
      <p role="alert">
        Only processors and medical officers can submit requests. Use Sign out to select a different
        review role.
      </p>
    );
  const today = new Date().toISOString().slice(0, 10);
  const products = [
    ...new Set(
      policies.items
        .filter(
          (p) =>
            p.status === "approved" &&
            p.active &&
            p.effective_from <= today &&
            (!p.effective_to || p.effective_to >= today),
        )
        .map((p) => p.product_id),
    ),
  ];
  const input = "mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
  return (
    <>
      <h1 className="text-3xl font-semibold">Submit a synthetic request</h1>
      <WorkflowFeedback {...(await searchParams)} />
      <p className="mt-3 text-sm text-slate-600">
        These fictional defaults match the clean golden case. Clear missing clinical fields to test
        an information request. No real patient information.
      </p>
      <WorkflowForm
        action="/workflows/commands"
        method="post"
        className="mt-6 grid max-w-4xl gap-5 rounded-xl border bg-white p-6 sm:grid-cols-2"
      >
        <input type="hidden" name="operation" value="submit" />
        <input type="hidden" name="command_id" value={randomUUID()} />
        <label className="text-sm">
          Policy product
          <select name="product_id" required className={input}>
            {products.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Priority
          <select name="priority" className={input}>
            <option value="normal">Normal · one hour</option>
            <option value="urgent">Urgent · thirty minutes</option>
          </select>
        </label>
        <div className="min-w-0 sm:col-span-2">
          <FactsEditor />
        </div>
        <label className="text-sm sm:col-span-2">
          <input type="checkbox" name="synthetic_data" value="true" required /> I confirm that this
          request contains fictional test data only.
        </label>
        <button
          type="submit"
          disabled={products.length === 0}
          className="rounded-lg bg-teal-800 p-3 text-white disabled:opacity-50"
        >
          Queue assessment
        </button>
        {products.length === 0 && (
          <p className="text-sm text-amber-800 sm:col-span-2">
            No currently effective active policy is available. Approval alone is not enough: a
            policy approver must activate a version in the{" "}
            <Link href="/workflows/policies" className="underline">
              policy library
            </Link>
            .
          </p>
        )}
      </WorkflowForm>
    </>
  );
}
