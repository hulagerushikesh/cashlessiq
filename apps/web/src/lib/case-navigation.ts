import type { Outcome } from "@cashlessiq/api-client";

type SearchParams = Record<string, string | string[] | undefined>;
const outcomes = new Set<string>(["APPROVE", "APPROVE_WITH_DEDUCTIONS", "QUERY", "REFER"]);

/** Carry only bounded queue filters; never accept a return URL from the browser. */
export function caseQueueState(params: SearchParams) {
  const search = typeof params.search === "string" ? params.search.slice(0, 80) : "";
  const outcome =
    typeof params.outcome === "string" && outcomes.has(params.outcome)
      ? (params.outcome as Outcome)
      : undefined;
  const parsed = typeof params.page === "string" ? Number(params.page) : 1;
  const page = Number.isInteger(parsed) && parsed > 0 && parsed <= 10000 ? parsed : 1;
  return { search, outcome, page };
}

export function caseQueueQuery(state: ReturnType<typeof caseQueueState>) {
  return new URLSearchParams({
    ...(state.search ? { search: state.search } : {}),
    ...(state.outcome ? { outcome: state.outcome } : {}),
    ...(state.page > 1 ? { page: String(state.page) } : {}),
  }).toString();
}

export function caseQueueUrl(state: ReturnType<typeof caseQueueState>) {
  const query = caseQueueQuery(state);
  return `/cases${query ? `?${query}` : ""}`;
}
