import type { AgentResult } from "@cashlessiq/api-client";
import { randomUUID } from "node:crypto";
import { mvpApi } from "@/lib/mvp-api";
import { AgentResultPanel } from "./agent-result-panel";
import { AgentRequestForm } from "./agent-request-form";

export async function AgentComparison({ requestId }: { requestId: string }) {
  const result = await mvpApi<AgentResult>(
    `requests/${encodeURIComponent(requestId)}/agent-result`,
  );
  return (
    <>
      <AgentResultPanel result={result} />
      {result?.state === "not_requested" && result.request_context && (
        <AgentRequestForm
          requestId={requestId}
          commandId={randomUUID()}
          context={result.request_context}
        />
      )}
      <a
        href={`/workflows/requests/${encodeURIComponent(requestId)}`}
        className="mt-3 inline-block text-sm text-teal-800 underline"
      >
        Refresh comparison status
      </a>
    </>
  );
}
