import type { AgentResult } from "@cashlessiq/api-client";
import { mvpApi } from "@/lib/mvp-api";
import { AgentResultPanel } from "./agent-result-panel";

export async function AgentComparison({ requestId }: { requestId: string }) {
  const result = await mvpApi<AgentResult>(
    `requests/${encodeURIComponent(requestId)}/agent-result`,
  );
  return (
    <>
      <AgentResultPanel result={result} />
      <a
        href={`/workflows/requests/${encodeURIComponent(requestId)}`}
        className="mt-3 inline-block text-sm text-teal-800 underline"
      >
        Refresh comparison status
      </a>
    </>
  );
}
