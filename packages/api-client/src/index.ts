import createClient from "openapi-fetch";
import type { paths, components } from "./schema";

export type Identity = components["schemas"]["MeResponse"];

export function createApiClient(baseUrl: string, token: string) {
  return createClient<paths>({
    baseUrl,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
}
