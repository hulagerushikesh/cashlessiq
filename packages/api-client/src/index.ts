import createClient from "openapi-fetch";
import type { paths, components } from "./schema";

export type Identity = components["schemas"]["MeResponse"];
export type CaseDetail = components["schemas"]["CaseDetail"];
export type CaseQueue = components["schemas"]["CaseQueue"];
export type Outcome = components["schemas"]["CaseSummary"]["outcome"];

export function createApiClient(baseUrl: string, token: string) {
  return createClient<paths>({
    baseUrl,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
}
