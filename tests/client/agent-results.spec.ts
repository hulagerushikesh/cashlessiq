import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { AgentResult } from "@cashlessiq/api-client";
import { AgentResultPanel } from "../../apps/web/src/components/agent-result-panel";
import { AgentRequestForm } from "../../apps/web/src/components/agent-request-form";

const view = (state: AgentResult["state"]): AgentResult => ({
  state,
  mode: "synthetic-only",
  execution_profile: "synthetic-executor",
});
const render = (result: AgentResult | null) =>
  renderToStaticMarkup(createElement(AgentResultPanel, { result }));

test("unavailable service preserves a clear fallback and no execution controls", () => {
  const html = render(null);
  expect(html).toContain("Comparison service unavailable");
  expect(html).toContain("deterministic assessment and reviewer actions remain available");
  expect(html).toContain("Live AI is not connected");
  expect(html).not.toMatch(/<button|<form|<script/);
});

for (const state of ["not_requested", "awaiting_executor", "unknown", "stale", "rejected", "expired"] as const) {
  test(`${state} never appears as a completed comparison`, () => {
    const html = render(view(state));
    expect(html).toContain('role="status"');
    expect(html).not.toContain("Validated synthetic comparison amounts");
    expect(html).not.toContain("Synthetic explanation");
    expect(html).not.toContain("comparison validated against");
    if (state === "unknown") expect(html).toContain("automatic retry is blocked");
  });
}

test("held request is explicit about execution and spending", () => {
  const html = render(view("awaiting_executor"));
  expect(html).toContain("nothing has run and no allowance has been consumed");
  expect(html).not.toMatch(/<button|<form/);
});

test("request form carries versions and fictional confirmation, never authority", () => {
  const html = renderToStaticMarkup(createElement(AgentRequestForm, {
    requestId: "REQ-SYNTHETIC", commandId: "00000000-0000-4000-8000-000000000002",
    context: { input_revision: 2, review_version: 3 },
  }));
  expect(html).toContain('action="/workflows/commands"');
  expect(html).toContain('name="expected_input_revision" value="2"');
  expect(html).toContain('name="expected_review_version" value="3"');
  expect(html).toContain('name="synthetic_data"');
  expect(html).toContain("fictional test data only");
  expect(html).toContain("does not run AI, spend money or change your decision");
  expect(html).not.toMatch(/name="(?:tenant_id|actor_id|grant_id|epoch_id|credential|path)"/);
});

const published: AgentResult = {
  ...view("published"),
  operation_id: "00000000-0000-4000-8000-000000000001",
  policy_version: "TEST-v1",
  input_revision: 1,
  review_version: 2,
  created_at: "2026-11-23T00:00:00Z",
  deadline: "2026-11-23T00:02:00Z",
  published_at: "2026-11-23T00:00:01Z",
  comparison: {
    outcome: "APPROVE_WITH_DEDUCTIONS",
    claimed_inr: 100000,
    payable_inr: 95000,
    lines: [
      {
        item: "Synthetic procedure",
        claimed_inr: 100000,
        payable_inr: 95000,
        deduction_inr: 5000,
        citations: [],
      },
    ],
    citations: [
      {
        kind: "clause",
        source_id: "TEST-CLAUSE",
        source_digest: "a".repeat(64),
      },
    ],
    explanation: "<script>private clinical text</script>",
  },
};

test("validated comparison shows amounts, provenance, evidence and escaped explanation", () => {
  const html = render(published);
  expect(html).toContain("₹95,000");
  expect(html).toContain("₹1,00,000");
  expect(html).toContain("₹5,000");
  expect(html).toContain("Input revision 1");
  expect(html).toContain("Review version 2");
  expect(html).toContain("TEST-CLAUSE");
  expect(html).toContain("requires human review");
  expect(html).toContain("&lt;script&gt;");
  expect(html).not.toContain("<script>");
});

test("QUERY keeps unavailable money distinct from a calculated zero", () => {
  const result = structuredClone(published);
  const original = published.comparison;
  if (!original) throw new Error("Published fixture requires a comparison");
  result.comparison = {
    ...original,
    outcome: "QUERY",
    claimed_inr: null,
    payable_inr: null,
    lines: [],
  };
  const html = render(result);
  expect(html).toContain("Payable Not calculated");
  expect(html).not.toContain("₹0");
  expect(html).not.toContain("<table");
});

for (const state of ["not_requested", "reserved", "unknown", "published"] as const) {
  test(`reviewed ${state} view never starts or retries an attempt`, () => {
    const html = render({
      ...(state === "published" ? published : view(state)),
      execution_profile: "reviewed-single-call",
    });
    expect(html).toContain("Refreshing this page never runs AI");
    expect(html).not.toContain("Live AI is not connected");
    expect(html).not.toMatch(/<button|<form|<script/);
    if (state === "reserved") expect(html).toContain("This page cannot start it");
    if (state === "unknown" || state === "published") {
      expect(html).toContain("Provider usage and cost are unverified");
      expect(html).toContain("does not authorize another attempt");
    }
    if (state === "published") expect(html).toContain("₹95,000");
  });
}
