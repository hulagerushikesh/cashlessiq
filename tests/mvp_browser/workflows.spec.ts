import { expect, test, type Browser, type Page } from "@playwright/test";
import path from "node:path";
import { mvpBrowserOptions } from "./runtime";

async function login(browser: Browser, role: string) {
  const context = await browser.newContext(mvpBrowserOptions());
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByLabel("Review role").selectOption(role);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page).toHaveURL(/\/$/);
  return { context, page };
}

async function waitFor(page: Page, text: string) {
  await expect(async () => {
    await page.reload();
    await expect(page.getByText(text, { exact: true }).first()).toBeVisible();
  }).toPass({ timeout: 30000, intervals: [500, 1000] });
}

test("policy approval, queued assessment, human decision and document visibility", async ({
  browser,
}) => {
  const analyst = await login(browser, "policy_analyst");
  const approver = await login(browser, "policy_approver");
  const processor = await login(browser, "processor");
  const medical = await login(browser, "medical_officer");
  const auditor = await login(browser, "auditor");
  try {
    const product = `MVP_E2E_${Date.now()}`;
    await analyst.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New policy", exact: true })
      .click();
    await analyst.page.getByLabel("Policy product ID").fill(product);
    await analyst.page.getByLabel("Policy version", { exact: true }).fill(product);
    await analyst.page.getByLabel("Proposal reason").fill("Synthetic browser regression policy");
    await analyst.page.getByRole("button", { name: "Save proposal and run regressions" }).click();
    await expect(analyst.page).toHaveURL(/\/workflows\/policies\/[a-f0-9-]+/);
    await waitFor(analyst.page, "succeeded · Passed · 30 cases");
    await approver.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "Policy library", exact: true })
      .click();
    await approver.page.getByRole("link", { name: `${product} · ${product}`, exact: true }).click();
    await approver.page.getByLabel("Review decision").selectOption("approve");
    await approver.page
      .getByLabel("Reason", { exact: true })
      .fill("Different-person review of clauses and regression results");
    await approver.page.getByRole("button", { name: "Save policy decision" }).click();
    await expect(approver.page.getByText("Policy action saved.")).toBeVisible();
    await approver.page.getByLabel("Review decision").selectOption("activate");
    await approver.page
      .getByLabel("Reason", { exact: true })
      .fill("Activate for private synthetic testing");
    await approver.page.getByRole("button", { name: "Save policy decision" }).click();
    await expect(approver.page.getByText(/Currently active/)).toBeVisible();

    await processor.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New request", exact: true })
      .click();
    await processor.page.getByLabel("Policy product").selectOption(product);
    await processor.page
      .getByLabel("Synthetic member reference")
      .fill(`SYN-${product.replaceAll("_", "-")}`);
    await processor.page.getByLabel("I confirm").check();
    await processor.page.getByRole("button", { name: "Queue assessment" }).click();
    await expect(processor.page).toHaveURL(/\/workflows\/requests\/REQ-/);
    const requestUrl = processor.page.url().split("?")[0];
    await waitFor(processor.page, "APPROVE WITH DEDUCTIONS · ₹95,000");
    const requestId = new URL(requestUrl).pathname.split("/").at(-1);
    await medical.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "Submitted requests", exact: true })
      .click();
    await medical.page
      .getByRole("link", { name: `SYN-${product.replaceAll("_", "-")}`, exact: true })
      .click();
    await medical.page.getByRole("link", { name: "Open reviewer workflow" }).click();
    await medical.page
      .getByLabel("Assignee", { exact: true })
      .selectOption("00000000-0000-4000-8000-000000000012");
    await medical.page.getByRole("button", { name: "Save assignment" }).click();
    await expect(medical.page.getByText("Review saved.")).toBeVisible();
    await medical.page
      .getByLabel("Action", { exact: true })
      .selectOption("approve_with_deductions");
    await medical.page
      .getByLabel("Comment or action reason")
      .fill("Verified deterministic calculation and policy evidence");
    await medical.page.getByLabel("Final payable in whole INR").fill("95000");
    await medical.page.getByRole("button", { name: "Save reviewer action" }).click();
    await expect(
      medical.page.getByText(/Synthetic testing · APPROVED WITH DEDUCTIONS · Version 2/),
    ).toBeVisible();
    await medical.page
      .getByLabel("Comment or action reason")
      .fill("Fictional clinical note restricted to medical officers");
    await medical.page.getByLabel("Visibility").selectOption("clinical");
    await medical.page.getByRole("button", { name: "Save reviewer action" }).click();
    await expect(
      medical.page.getByText("Fictional clinical note restricted to medical officers", {
        exact: true,
      }),
    ).toBeVisible();
    await auditor.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "Submitted requests", exact: true })
      .click();
    await auditor.page
      .getByRole("link", { name: `SYN-${product.replaceAll("_", "-")}`, exact: true })
      .click();
    await auditor.page.getByRole("link", { name: "Open reviewer workflow" }).click();
    await expect(auditor.page.getByRole("heading", { name: /Audit history/ })).toBeVisible();
    await expect(auditor.page.getByRole("button", { name: "Save reviewer action" })).toHaveCount(0);
    await expect(
      auditor.page.getByText("Fictional clinical note restricted to medical officers", {
        exact: true,
      }),
    ).toHaveCount(0);

    await processor.page.goto(requestUrl);
    await processor.page
      .getByLabel("PDF document")
      .setInputFiles(path.join(process.cwd(), "tests/fixtures/mvp/synthetic.pdf"));
    await processor.page.getByLabel("This PDF contains fictional").check();
    await processor.page.getByRole("button", { name: "Upload for extraction" }).click();
    await waitFor(processor.page, "extracted");
    await expect(
      processor.page.getByText("Fictional policy wording for synthetic testing.", { exact: true }),
    ).toHaveCount(0);
    await medical.page.goto(requestUrl);
    await expect(
      medical.page.getByText("Fictional policy wording for synthetic testing.", { exact: true }),
    ).toBeVisible();
    const download = await medical.page.request.get(
      (await medical.page
        .getByRole("link", { name: "Download PDF" })
        .getAttribute("href")) as string,
    );
    expect(download.status()).toBe(200);
    expect(download.headers()["content-disposition"]).toContain("attachment;");
    // Exercise the controls beyond the happy path, using the request's own links.
    await medical.page.getByRole("link", { name: "Open reviewer workflow" }).click();
    const act = async (action: string, note: string) => {
      await medical.page.getByLabel("Action", { exact: true }).selectOption(action);
      await medical.page.getByLabel("Comment or action reason").fill(note);
      if (action === "approve_with_deductions")
        await medical.page.getByLabel("Final payable in whole INR").fill("95000");
      await medical.page.getByRole("button", { name: "Save reviewer action" }).click();
      await expect(medical.page.getByText("Review saved.")).toBeVisible();
    };
    await act("reopen", "Reopen fictional review to verify information-request handling");
    const staleTab = await medical.context.newPage();
    await staleTab.goto(medical.page.url()); // Simulate a duplicated, now stale review tab.
    await act("query", "Please verify the fictional clinical note");
    await expect(medical.page.getByText(/Synthetic testing · NEEDS INFORMATION/)).toBeVisible();
    await staleTab
      .getByLabel("Comment or action reason")
      .fill("Stale browser action must not be saved");
    await staleTab.getByRole("button", { name: "Save reviewer action" }).click();
    await expect(staleTab.getByText(/The case changed. Your action was not applied/)).toBeVisible();
    await expect(
      staleTab.getByText("Stale browser action must not be saved", { exact: true }),
    ).toHaveCount(0);
    await staleTab.close();
    await medical.page.getByRole("link", { name: "Supporting documents and assessment" }).click();
    const corrected = JSON.parse(
      await medical.page.getByLabel("Updated structured facts").inputValue(),
    );
    corrected.clinical_note = "Fictional follow-up checked by the medical reviewer";
    await medical.page.getByLabel("Updated structured facts").fill(JSON.stringify(corrected));
    await medical.page
      .getByLabel("Reason", { exact: true })
      .fill("Correct fictional note while retaining previous facts");
    await medical.page.getByRole("button", { name: "Save facts and queue reassessment" }).click();
    await waitFor(medical.page, "APPROVE WITH DEDUCTIONS · ₹95,000");
    await medical.page.getByRole("link", { name: "Open reviewer workflow" }).click();
    await act("resume", "Information received and reassessment reviewed");
    await act("refer", "Verify medical referral journey");
    await expect(medical.page.getByText(/Synthetic testing · REFERRED/)).toBeVisible();
    await act("resume", "Medical referral checked");
    await act(
      "approve_with_deductions",
      "Complete the fictional review after correction and referral",
    );
    await medical.page.reload();
    await expect(
      medical.page.getByText(/Synthetic testing · APPROVED WITH DEDUCTIONS/),
    ).toBeVisible();
    await medical.page.setViewportSize({ width: 390, height: 844 });
    await medical.page.goto(`/reviews/${requestId}`);
    expect(
      await medical.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await medical.page.goto(requestUrl);
    expect(
      await medical.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await medical.page.screenshot({ path: "test-results/mvp/request.png", fullPage: true });
    await approver.page.screenshot({ path: "test-results/mvp/policy.png", fullPage: true });
  } finally {
    await Promise.allSettled(
      [analyst, approver, processor, medical, auditor].map((p) => p.context.close()),
    );
  }
});

test("web mutation routes reject foreign origins", async ({ request }) => {
  for (const url of ["/workflows/commands", "/reviews/GOL001/commands"]) {
    const result = await request.post(url, {
      headers: { Origin: "https://foreign.invalid" },
      form: { operation: "submit" },
    });
    expect(result.status()).toBe(403);
  }
});

for (const role of [
  "processor",
  "medical_officer",
  "policy_analyst",
  "policy_approver",
  "auditor",
  "operations_lead",
  "tenant_admin",
]) {
  test(`${role} can discover workflows from home on mobile`, async ({ browser }) => {
    const actor = await login(browser, role);
    try {
      await actor.page.setViewportSize({ width: 390, height: 844 });
      const nav = actor.page.getByRole("navigation", { name: "Workflow navigation" });
      await expect(actor.page.getByText("Read-only alpha", { exact: true })).toHaveCount(0);
      await expect(nav.getByRole("link", { name: "New policy", exact: true })).toHaveCount(
        role === "policy_analyst" ? 1 : 0,
      );
      await expect(nav.getByRole("link", { name: "New request", exact: true })).toHaveCount(
        ["processor", "medical_officer"].includes(role) ? 1 : 0,
      );
      for (const [link, heading] of [
        ["Testing workspace", "Testing workspace"],
        ["Policy library", "Policy library"],
        ["Submitted requests", "Submitted request queue"],
        ["Background jobs", "Background processing"],
      ]) {
        await actor.page
          .getByRole("navigation", { name: "Workflow navigation" })
          .getByRole("link", { name: link, exact: true })
          .click();
        await expect(
          actor.page.getByRole("heading", { name: heading, exact: true, level: 1 }),
        ).toBeVisible();
        expect(
          await actor.page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        ).toBe(true);
      }
      if (["auditor", "operations_lead", "tenant_admin", "policy_approver"].includes(role)) {
        await actor.page
          .getByRole("navigation", { name: "Workflow navigation" })
          .getByRole("link", { name: "Governance history", exact: true })
          .click();
        await expect(
          actor.page.getByRole("heading", { name: "Governance and reporting", exact: true }),
        ).toBeVisible();
      }
      if (role === "tenant_admin") {
        await actor.page
          .getByRole("navigation", { name: "Workflow navigation" })
          .getByRole("link", { name: "Manage tenant access", exact: true })
          .click();
        await expect(
          actor.page.getByRole("heading", { name: "Tenant access", exact: true }),
        ).toBeVisible();
      }
      if (role === "policy_analyst") {
        await actor.page
          .getByRole("navigation", { name: "Workflow navigation" })
          .getByRole("link", { name: "New policy", exact: true })
          .click();
        await expect(actor.page.getByLabel("Policy product ID")).toBeVisible();
        await expect(actor.page.getByLabel("Policy version", { exact: true })).toBeVisible();
      }
    } finally {
      await actor.context.close();
    }
  });
}

test("unactivated policies are excluded from intake and duplicate proposals explain recovery", async ({
  browser,
}) => {
  const analyst = await login(browser, "policy_analyst");
  const approver = await login(browser, "policy_approver");
  const processor = await login(browser, "processor");
  const product = `MVP_PENDING_${Date.now()}`;
  try {
    const newPolicy = async () => {
      await analyst.page
        .getByRole("navigation", { name: "Workflow navigation" })
        .getByRole("link", { name: "New policy", exact: true })
        .click();
      await analyst.page.getByLabel("Policy product ID").fill(product);
      await analyst.page.getByLabel("Policy version", { exact: true }).fill("V1");
      await analyst.page.getByLabel("Proposal reason").fill("Synthetic unactivated policy test");
      await analyst.page.getByRole("button", { name: "Save proposal and run regressions" }).click();
    };
    await newPolicy();
    await waitFor(analyst.page, "succeeded · Passed · 30 cases");
    await approver.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "Policy library", exact: true })
      .click();
    await approver.page.getByRole("link", { name: `${product} · V1`, exact: true }).click();
    await approver.page
      .getByLabel("Reason", { exact: true })
      .fill("Approve but deliberately do not activate");
    await approver.page.getByRole("button", { name: "Save policy decision" }).click();
    await expect(approver.page.getByText(/Approved, awaiting activation/)).toBeVisible();
    await expect(
      approver.page.getByRole("link", { name: "Activate this version below" }),
    ).toBeVisible();
    await processor.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New request", exact: true })
      .click();
    await expect(
      processor.page
        .getByLabel("Policy product")
        .getByRole("option", { name: product, exact: true }),
    ).toHaveCount(0);
    // A stale/forged form still receives authoritative denial with actionable, fixed feedback.
    const stale = await processor.page.request.post("/workflows/commands", {
      headers: { Origin: new URL(processor.page.url()).origin },
      form: {
        operation: "submit",
        command_id: crypto.randomUUID(),
        product_id: product,
        synthetic_data: "true",
        priority: "normal",
        member_reference: "SYN-INACTIVE",
        inception_date: "2023-01-01",
        continuous_cover_since: "2023-01-01",
        admission_date: "2026-10-02",
        sum_insured_inr: "500000",
        si_remaining_inr: "500000",
        diagnosis: "Fictional diagnosis",
        procedure: "Fictional procedure",
        room_category: "Twin sharing",
        room_rent_per_day_inr: "4000",
        planned_los_days: "3",
        cost_breakup: "[]",
        estimated_total_inr: "100000",
      },
      maxRedirects: 0,
    });
    expect(stale.status()).toBe(303);
    expect(stale.headers().location).toContain(
      "/workflows/new?result=conflict&error=inactive_policy",
    );
    await newPolicy();
    await expect(analyst.page).toHaveURL(/\/workflows\/policies\/new\?/);
    await expect(analyst.page.getByRole("alert")).toHaveText(
      /This product and version already exist/,
    );
  } finally {
    await Promise.allSettled([analyst, approver, processor].map((p) => p.context.close()));
  }
});
