import { expect, test } from "@playwright/test";
import createClient from "openapi-fetch";
import type { paths } from "../../packages/api-client/src/schema";
import type { Identity, SourceCaseDetail, SourceCaseQueue } from "@cashlessiq/api-client";
import { readSourceCase, readSourceQueue } from "@cashlessiq/api-client/source";

const identity: Identity = {
  schema_version: 1,
  identity_mode: "local",
  role: "processor",
  capabilities: ["case:read"],
  tenant: { id: "00000000-0000-4000-8000-000000000101", name: "Fictional client test" },
  user: { id: "00000000-0000-4000-8000-000000000111", display_name: "Test only" },
};
function detail(): SourceCaseDetail {
  return {
    schema_version: 2,
    data_mode: "synthetic_source",
    tenant_id: identity.tenant.id,
    case: {
      request_id: "HTTP-TEST-001",
      policy_id: "TEST-POLICY",
      product_id: "TEST-PRODUCT",
      product_name: "Fictional client test",
      policy_version: "test-v1",
      continuous_cover_since: "2022-01-01",
      admission_date: "2026-01-01",
      estimated_total_inr: 100000,
    },
    member_history: {
      member_id: "TEST-MEMBER",
      sum_insured_inr: 500000,
      cumulative_bonus_inr: 0,
      status: "ACTIVE",
      claim_count: 0,
      total_paid_inr: 0,
      last_admission_date: null,
      conditions_visible: false,
      conditions: null,
    },
    recommendation: { state: "MISSING" },
    evidence_kind: "product_clause_register",
    evidence: [
      {
        clause_id: "TEST-CLAUSE",
        title: "Fictional reference",
        page: 7,
        source_url: "https://example.org/test.pdf",
      },
    ],
  };
}
function queue(): SourceCaseQueue {
  return {
    schema_version: 2,
    data_mode: "synthetic_source",
    tenant_id: identity.tenant.id,
    recommendations_loaded: false,
    items: [detail().case],
    total: 1,
    page: 1,
    page_size: 20,
  };
}
function fake(payload: unknown, status = 200, raw = false) {
  const requests: Request[] = [];
  const api = createClient<paths>({
    baseUrl: "https://never-contact.invalid",
    cache: "no-store",
    headers: { Authorization: "Bearer fictional-test-token" },
    fetch: async (request: Request) => {
      requests.push(request);
      return new Response(raw ? String(payload) : JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  return { api, requests };
}

test("source queue uses bearer/no-store, bounded query and no tenant header", async () => {
  const { api, requests } = fake(queue());
  expect(await readSourceQueue(api, identity, { search: "  HTTP  " })).toEqual({
    state: "ready",
    data: queue(),
  });
  expect(requests).toHaveLength(1);
  const request = requests[0];
  expect(request.method).toBe("GET");
  expect(new URL(request.url).pathname).toBe("/v2/cases");
  expect(new URL(request.url).searchParams.get("search")).toBe("HTTP");
  expect(new URL(request.url).searchParams.get("page_size")).toBe("20");
  expect(request.headers.get("authorization")).toBe("Bearer fictional-test-token");
  expect(request.headers.has("x-tenant-id")).toBe(false);
  expect(request.cache).toBe("no-store");
  expect(request.redirect).toBe("error");
  expect(request.signal.aborted).toBe(false);
});

test("successful detail preserves MISSING as-is, with no invented decision", async () => {
  const { api, requests } = fake(detail());
  expect(await readSourceCase(api, identity, "HTTP-TEST-001")).toEqual({
    state: "ready",
    data: detail(),
  });
  expect(requests).toHaveLength(1);
  expect(new URL(requests[0].url).pathname).toBe("/v2/cases/HTTP-TEST-001");
});

for (const [status, state] of [
  [401, "anonymous"],
  [403, "forbidden"],
  [404, "not_found"],
  [422, "unavailable"],
  [503, "unavailable"],
  [500, "unavailable"],
  [302, "unavailable"],
] as const) {
  test(`HTTP ${status} is ${state}, never a missing recommendation`, async () => {
    const { api, requests } = fake(detail(), status);
    expect(await readSourceCase(api, identity, "HTTP-TEST-001")).toEqual({ state });
    expect(requests).toHaveLength(1); // No retries or v1/demo fallback.
  });
}

test("queue 404 is service failure, not an empty queue", async () => {
  expect(await readSourceQueue(fake(queue(), 404).api, identity)).toEqual({ state: "unavailable" });
});

for (const fault of [
  "tenant",
  "request",
  "missing-field",
  "extra-field",
  "decimal",
  "string-amount",
  "unsafe-integer",
  "date",
  "url",
  "ftp-url",
  "duplicate-clause",
  "hidden-condition",
  "nonmedical-condition",
  "deny",
  "partial-missing",
  "query-zero",
  "approval-null",
  "basis",
]) {
  test(`rejects invalid source detail: ${fault}`, async () => {
    const value = detail();
    const unsafe = value as unknown as Record<string, unknown>;
    if (fault === "tenant") value.tenant_id = "00000000-0000-4000-8000-000000000103";
    if (fault === "request") value.case.request_id = "OTHER-REQUEST";
    if (fault === "missing-field") delete unsafe.member_history;
    if (fault === "extra-field") unsafe.decision_json = { summary: "Must not be exposed" };
    if (fault === "decimal") value.case.estimated_total_inr = 1.5;
    if (fault === "string-amount")
      (value.case as unknown as Record<string, unknown>).estimated_total_inr = "100000";
    if (fault === "unsafe-integer") value.case.estimated_total_inr = Number.MAX_SAFE_INTEGER + 1;
    if (fault === "date") value.case.admission_date = "2026-02-30";
    if (fault === "url") value.evidence[0].source_url = "javascript:alert(1)";
    if (fault === "ftp-url") value.evidence[0].source_url = "ftp://example.org/test.pdf";
    if (fault === "duplicate-clause") value.evidence.push({ ...value.evidence[0] });
    if (fault === "hidden-condition" || fault === "nonmedical-condition") {
      value.member_history.conditions_visible = fault === "nonmedical-condition";
      value.member_history.conditions = [
        {
          icd10_code: "TEST",
          condition_name: "Restricted client fixture",
          first_diagnosed_on: "2020-01-01",
          declared_at_proposal: true,
        },
      ];
    }
    if (fault === "deny")
      unsafe.recommendation = {
        state: "SAVED",
        outcome: "DENY",
        claimed_inr: 100000,
        payable_inr: 0,
        amount_basis: "saved_calculation",
      };
    if (fault === "partial-missing") unsafe.recommendation = { state: "MISSING", payable_inr: 0 };
    if (["query-zero", "approval-null", "basis"].includes(fault))
      value.recommendation = {
        state: "SAVED",
        outcome: fault === "query-zero" ? "QUERY" : "APPROVE",
        claimed_inr: 100000,
        payable_inr: fault === "approval-null" ? null : 0,
        amount_basis: fault === "basis" ? "supplied_estimate" : "saved_calculation",
      };
    const before = structuredClone(value);
    expect(await readSourceCase(fake(value).api, identity, "HTTP-TEST-001")).toEqual({
      state: "unavailable",
    });
    expect(value).toEqual(before);
  });
}

test("medical condition and saved QUERY/REFER remain unchanged", async () => {
  for (const outcome of ["QUERY", "REFER"] as const) {
    const value = detail();
    value.recommendation = {
      state: "SAVED",
      outcome,
      claimed_inr: 100000,
      payable_inr: null,
      amount_basis: "supplied_estimate",
    };
    value.member_history.conditions_visible = true;
    value.member_history.conditions = [
      {
        icd10_code: "TEST",
        condition_name: "Fictional medical fixture",
        first_diagnosed_on: "2020-01-01",
        declared_at_proposal: true,
      },
    ];
    expect(
      await readSourceCase(
        fake(value).api,
        { ...identity, role: "medical_officer" },
        "HTTP-TEST-001",
      ),
    ).toEqual({ state: "ready", data: value });
  }
});

test("saved approval displays a recorded zero distinctly from uncalculated", async () => {
  for (const payable of [0, 95000]) {
    const value = detail();
    value.recommendation = {
      state: "SAVED",
      outcome: "APPROVE_WITH_DEDUCTIONS",
      claimed_inr: 100000,
      payable_inr: payable,
      amount_basis: "saved_calculation",
    };
    expect(await readSourceCase(fake(value).api, identity, "HTTP-TEST-001")).toEqual({
      state: "ready",
      data: value,
    });
  }
});

for (const fault of [
  "tenant",
  "loaded-decisions",
  "extra-outcome",
  "page",
  "size",
  "negative-total",
  "duplicate",
  "missing-field",
]) {
  test(`rejects invalid source queue: ${fault}`, async () => {
    const value = queue();
    if (fault === "tenant") value.tenant_id = "00000000-0000-4000-8000-000000000103";
    if (fault === "loaded-decisions")
      (value as unknown as Record<string, unknown>).recommendations_loaded = true;
    if (fault === "extra-outcome")
      (value.items[0] as unknown as Record<string, unknown>).outcome = "QUERY";
    if (fault === "page") value.page = 2;
    if (fault === "size") value.page_size = 50;
    if (fault === "negative-total") value.total = -1;
    if (fault === "duplicate") {
      value.items.push({ ...value.items[0] });
      value.total = 2;
    }
    if (fault === "missing-field") delete (value as unknown as Record<string, unknown>).items;
    expect(await readSourceQueue(fake(value).api, identity)).toEqual({ state: "unavailable" });
  });
}

test("empty successful queue is ready, not a source failure", async () => {
  const value = { ...queue(), items: [], total: 0 };
  expect(await readSourceQueue(fake(value).api, identity)).toEqual({ state: "ready", data: value });
});

test("invalid input or missing capability causes no HTTP I/O", async () => {
  const { api, requests } = fake(detail());
  for (const query of [
    { page: 0 },
    { page: 1.5 },
    { page: 10001 },
    { page_size: 51 },
    { page_size: 0 },
    { search: "x".repeat(81) },
  ]) {
    expect(await readSourceQueue(api, identity, query)).toEqual({ state: "unavailable" });
  }
  expect(await readSourceCase(api, identity, "")).toEqual({ state: "unavailable" });
  expect(await readSourceCase(api, { ...identity, capabilities: [] }, "HTTP-TEST-001")).toEqual({
    state: "forbidden",
  });
  expect(await readSourceQueue(api, { ...identity, capabilities: [] })).toEqual({
    state: "forbidden",
  });
  expect(requests).toHaveLength(0);
});

test("malformed JSON and transport errors are unavailable with no fallback", async () => {
  expect(await readSourceCase(fake("{bad", 200, true).api, identity, "HTTP-TEST-001")).toEqual({
    state: "unavailable",
  });
  let calls = 0;
  const api = createClient<paths>({
    baseUrl: "https://never-contact.invalid",
    fetch: async () => {
      calls++;
      throw new Error("private transport details");
    },
  });
  expect(await readSourceQueue(api, identity)).toEqual({ state: "unavailable" });
  expect(calls).toBe(1);
});
