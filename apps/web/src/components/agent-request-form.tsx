import type { AgentResult } from "@cashlessiq/api-client";
import { WorkflowForm } from "./workflow-form";

export function AgentRequestForm({
  requestId,
  commandId,
  context,
}: {
  requestId: string;
  commandId: string;
  context: NonNullable<AgentResult["request_context"]>;
}) {
  return (
    <WorkflowForm action="/workflows/commands" method="post" className="mt-4 space-y-3">
      <p className="text-sm text-slate-600">
        Save a request for this assigned review. The dedicated synthetic executor is not active
        yet. Saving does not run AI, spend money or change your decision.
      </p>
      <input type="hidden" name="operation" value="agent-request" />
      <input type="hidden" name="id" value={requestId} />
      <input type="hidden" name="command_id" value={commandId} />
      <input type="hidden" name="expected_input_revision" value={context.input_revision} />
      <input type="hidden" name="expected_review_version" value={context.review_version} />
      <label className="block text-sm">
        <input type="checkbox" name="synthetic_data" value="true" required /> This comparison
        contains fictional test data only.
      </label>
      <button type="submit" className="rounded-lg bg-teal-800 p-3 text-white">
        Request synthetic comparison
      </button>
    </WorkflowForm>
  );
}
