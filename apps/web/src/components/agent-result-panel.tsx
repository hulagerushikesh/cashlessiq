import type { AgentResult } from "@cashlessiq/api-client";
import { rupees } from "../lib/money";

const messages: Record<AgentResult["state"], string> = {
  not_requested: "No synthetic agent comparison has been requested for this review.",
  unavailable:
    "Comparison unavailable for the current review. Check the assignment, policy approval and latest assessment.",
  stale: "The request, policy or review changed. The earlier comparison is withheld.",
  reserved: "Synthetic comparison reserved; no result is available yet.",
  submitting: "Synthetic comparison submitted; no validated result is available yet.",
  unknown: "Execution status is uncertain. No result is available and automatic retry is blocked.",
  rejected: "The comparison was rejected. Use the deterministic assessment and human review.",
  published: "Synthetic comparison validated against the current assessment and owned evidence.",
  superseded: "This comparison was superseded. No current result is available.",
  expired: "The comparison window expired. No result is available.",
};

export function AgentResultPanel({ result }: { result: AgentResult | null }) {
  const comparison = result?.state === "published" ? result.comparison : null;
  return (
    <section
      className="mt-6 rounded-xl border border-slate-200 bg-white p-6"
      aria-labelledby="agent-comparison-title"
    >
      <h2 id="agent-comparison-title" className="text-xl font-semibold">
        Agent comparison
      </h2>
      <p className="mt-2 text-sm text-amber-900">
        Synthetic testing only · Live AI is not connected. A medical officer owns the final
        decision.
      </p>
      <p className="mt-3 text-sm" role="status">
        {result
          ? messages[result.state]
          : "Comparison service unavailable. The deterministic assessment and reviewer actions remain available."}
      </p>
      {result?.operation_id && (
        <p className="mt-2 break-words text-xs text-slate-500">
          Policy {result.policy_version} · Input revision {result.input_revision} · Review version{" "}
          {result.review_version} · Operation {result.operation_id}
        </p>
      )}
      {result?.created_at && result.deadline && (
        <p className="mt-2 text-xs text-slate-500">
          Started {new Date(result.created_at).toISOString()} · Deadline{" "}
          {new Date(result.deadline).toISOString()}
        </p>
      )}
      {comparison && (
        <div className="mt-4 space-y-4">
          <p className="font-medium">
            {comparison.outcome.replaceAll("_", " ")} · Payable {rupees(comparison.payable_inr)}
          </p>
          <p className="text-sm">Claimed {rupees(comparison.claimed_inr)}</p>
          {comparison.lines.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Validated synthetic comparison amounts</caption>
                <thead>
                  <tr>
                    <th scope="col" className="p-2">
                      Item
                    </th>
                    <th scope="col" className="p-2">
                      Claimed
                    </th>
                    <th scope="col" className="p-2">
                      Deduction
                    </th>
                    <th scope="col" className="p-2">
                      Payable
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.lines.map((line, index) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: Immutable canonical lines may repeat item names.
                    <tr key={`${index}-${line.item}`} className="border-t">
                      <th scope="row" className="p-2 font-normal">
                        {line.item}
                      </th>
                      <td className="p-2">{rupees(line.claimed_inr)}</td>
                      <td className="p-2">{rupees(line.deduction_inr)}</td>
                      <td className="p-2">{rupees(line.payable_inr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-sm">
            Verified evidence:{" "}
            {comparison.citations.map((ref) => `${ref.kind}: ${ref.source_id}`).join("; ")}
          </p>
          <div>
            <h3 className="text-sm font-semibold">Synthetic explanation — requires human review</h3>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm">{comparison.explanation}</p>
          </div>
          {result?.published_at && (
            <p className="text-xs text-slate-500">
              Validated {new Date(result.published_at).toISOString()}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
