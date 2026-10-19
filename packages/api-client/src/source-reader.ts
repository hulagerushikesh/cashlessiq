import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import contract from "../../contracts/openapi.json";
import type { createApiClient, Identity, SourceCaseDetail, SourceCaseQueue } from "./index";

type Api = ReturnType<typeof createApiClient>;
export type SourceRead<T> =
  | { state: "ready"; data: T }
  | { state: "anonymous" | "forbidden" | "not_found" | "unavailable" };

// Validate the exported API schema, not a hand-maintained copy. OpenAPI's
// discriminator annotations are ignored; oneOf still validates each branch.
// Never coerce, strip unexpected properties, default fields or log payloads.
const ajv = new Ajv2020({
  strict: false,
  coerceTypes: false,
  useDefaults: false,
  removeAdditional: false,
});
addFormats(ajv);
const validateQueue = ajv.compile<SourceCaseQueue>({
  $ref: "#/components/schemas/SourceCaseQueue",
  components: contract.components,
});
const validateDetail = ajv.compile<SourceCaseDetail>({
  $ref: "#/components/schemas/SourceCaseDetail",
  components: contract.components,
});

function safeIntegers(value: unknown): boolean {
  if (typeof value === "number") return Number.isSafeInteger(value);
  if (Array.isArray(value)) return value.every(safeIntegers);
  if (value !== null && typeof value === "object") return Object.values(value).every(safeIntegers);
  return true;
}

function errorState(status: number, detail: boolean): SourceRead<never> {
  if (status === 401) return { state: "anonymous" };
  if (status === 403) return { state: "forbidden" };
  if (status === 404 && detail) return { state: "not_found" };
  return { state: "unavailable" };
}

/** Offline-testable HTTP boundary. No fallback, source credentials or activation. */
export async function readSourceQueue(
  api: Api,
  identity: Identity,
  query: { search?: string; page?: number; page_size?: number } = {},
): Promise<SourceRead<SourceCaseQueue>> {
  if (!identity.capabilities.includes("case:read")) return { state: "forbidden" };
  const { search = "", page = 1, page_size = 20 } = query;
  if (
    search.length > 80 ||
    !Number.isInteger(page) ||
    page < 1 ||
    page > 10000 ||
    !Number.isInteger(page_size) ||
    page_size < 1 ||
    page_size > 50
  )
    return { state: "unavailable" };
  try {
    const result = await api.GET("/v2/cases", {
      params: { query: { search: search.trim(), page, page_size } },
      signal: AbortSignal.timeout(5000),
      redirect: "error",
    });
    if (!result.response.ok) return errorState(result.response.status, false);
    const data: unknown = result.data;
    if (
      !validateQueue(data) ||
      !safeIntegers(data) ||
      data.tenant_id !== identity.tenant.id ||
      data.page !== page ||
      data.page_size !== page_size ||
      data.total < 0 ||
      data.items.length > page_size ||
      data.items.length > data.total ||
      new Set(data.items.map((item) => item.request_id)).size !== data.items.length
    ) {
      return { state: "unavailable" };
    }
    return { state: "ready", data };
  } catch {
    return { state: "unavailable" };
  }
}

export async function readSourceCase(
  api: Api,
  identity: Identity,
  requestId: string,
): Promise<SourceRead<SourceCaseDetail>> {
  if (!identity.capabilities.includes("case:read")) return { state: "forbidden" };
  if (!requestId || requestId.length > 80) return { state: "unavailable" };
  try {
    const result = await api.GET("/v2/cases/{request_id}", {
      params: { path: { request_id: requestId } },
      signal: AbortSignal.timeout(5000),
      redirect: "error",
    });
    if (!result.response.ok) return errorState(result.response.status, true);
    const data: unknown = result.data;
    if (
      !validateDetail(data) ||
      !safeIntegers(data) ||
      data.tenant_id !== identity.tenant.id ||
      data.case.request_id !== requestId
    )
      return { state: "unavailable" };
    const history = data.member_history;
    if (
      (!history.conditions_visible && history.conditions !== null) ||
      (history.conditions_visible &&
        (identity.role !== "medical_officer" || history.conditions === null))
    ) {
      return { state: "unavailable" };
    }
    const recommendation = data.recommendation;
    if (recommendation.state === "SAVED") {
      const uncomputed = recommendation.outcome === "QUERY" || recommendation.outcome === "REFER";
      if (
        uncomputed !== (recommendation.payable_inr === null) ||
        recommendation.amount_basis !== (uncomputed ? "supplied_estimate" : "saved_calculation")
      ) {
        return { state: "unavailable" };
      }
    }
    if (
      new Set(data.evidence.map((clause) => clause.clause_id)).size !== data.evidence.length ||
      data.evidence.some(
        (clause) => !["https:", "http:"].includes(new URL(clause.source_url).protocol),
      )
    ) {
      return { state: "unavailable" };
    }
    return { state: "ready", data };
  } catch {
    return { state: "unavailable" };
  }
}
