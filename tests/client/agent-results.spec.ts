import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { AgentResult } from "@cashlessiq/api-client";
import { AgentResultPanel } from "../../apps/web/src/components/agent-result-panel";

const view = (state: AgentResult["state"]): AgentResult => ({
  state,
  mode: "synthetic-only",
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

for (const state of ["not_requested", "unknown", "stale", "rejected", "expired"] as const) {
  test(`${state} never appears as a completed comparison`, () => {
    const html = render(view(state));
    expect(html).toContain('role="status"');
    expect(html).not.toContain("Validated synthetic comparison amounts");
    expect(html).not.toContain("Synthetic explanation");
    expect(html).not.toContain("comparison validated against");
    if (state === "unknown") expect(html).toContain("automatic retry is blocked");
  });
}

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
