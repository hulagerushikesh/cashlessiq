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

async function saveAndNavigate(page: Page, label: string) {
  // Successful WorkflowForm commands use a full document navigation, even when
  // the URL is unchanged. Do not mistake an old visible result/success banner
  // for the newly saved state before that navigation has committed.
  await Promise.all([
    page.waitForEvent("framenavigated", (frame) => frame === page.mainFrame()),
    page.getByRole("button", { name: label, exact: true }).click(),
  ]);
  await page.waitForLoadState("domcontentloaded");
}

async function waitFor(page: Page, text: string) {
  // Processing panels update themselves; the owner must not have to reload.
  await expect(page.getByText(text, { exact: true }).first()).toBeVisible({ timeout: 30000 });
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
    await saveAndNavigate(analyst.page, "Save proposal and run regressions");
    await expect(analyst.page).toHaveURL(/\/workflows\/policies\/[a-f0-9-]+/);
    await waitFor(analyst.page, "succeeded · Passed · 30 cases");
    await approver.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "Policy library", exact: true })
      .click();
    await approver.page.getByLabel("Search product, version or policy name").fill(product);
    await approver.page.getByRole("button", { name: "Search", exact: true }).click();
    await approver.page.getByRole("link", { name: `${product} · ${product}`, exact: true }).click();
    await approver.page.getByLabel("Review decision").selectOption("approve");
    await approver.page
      .getByLabel("Reason", { exact: true })
      .fill("Different-person review of clauses and regression results");
    await saveAndNavigate(approver.page, "Save policy decision");
    await expect(approver.page.getByText("Policy action saved.")).toBeVisible();
    await approver.page.getByLabel("Review decision").selectOption("activate");
    await approver.page
      .getByLabel("Reason", { exact: true })
      .fill("Activate for private synthetic testing");
    await saveAndNavigate(approver.page, "Save policy decision");
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
    await saveAndNavigate(processor.page, "Queue assessment");
    await expect(processor.page).toHaveURL(/\/workflows\/requests\/REQ-/);
    const requestUrl = processor.page.url().split("?")[0];
    await waitFor(processor.page, "APPROVE WITH DEDUCTIONS · ₹95,000");
    const progressResponse = await processor.page.request.get(
      `/workflows/progress?kind=request&id=${new URL(requestUrl).pathname.split("/").at(-1)}`,
    );
    expect(progressResponse.status()).toBe(200);
    expect(progressResponse.headers()["cache-control"]).toContain("no-store");
    const progress = await progressResponse.json();
    expect(progress.facts).toBeUndefined();
    expect(progress.clinical_restricted).toBe(true);
    expect(progress.assessment.payable).toBeUndefined();
    expect(Object.keys(progress.assessment_job).sort()).toEqual(["attempts", "id", "state"]);
    const requestId = new URL(requestUrl).pathname.split("/").at(-1);
    await medical.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "Submitted requests", exact: true })
      .click();
    await medical.page
      .getByLabel("Search synthetic member reference or request ID")
      .fill(product.replaceAll("_", "-"));
    await medical.page.getByRole("button", { name: "Search", exact: true }).click();
    await medical.page
      .getByRole("link", { name: `SYN-${product.replaceAll("_", "-")}`, exact: true })
      .click();
    await medical.page.getByRole("link", { name: "Open reviewer workflow" }).click();
    await medical.page
      .getByLabel("Assignee", { exact: true })
      .selectOption("00000000-0000-4000-8000-000000000012");
    await saveAndNavigate(medical.page, "Save assignment");
    await expect(medical.page.getByText("Review saved.")).toBeVisible();
    await medical.page
      .getByLabel("Action", { exact: true })
      .selectOption("approve_with_deductions");
    await medical.page
      .getByLabel("Comment or action reason")
      .fill("Verified deterministic calculation and policy evidence");
    await medical.page.getByLabel("Final payable in whole INR").fill("95000");
    await saveAndNavigate(medical.page, "Save reviewer action");
    await expect(
      medical.page.getByText(/Synthetic testing · APPROVED WITH DEDUCTIONS · Version 2/),
    ).toBeVisible();
    await medical.page
      .getByLabel("Comment or action reason")
      .fill("Fictional clinical note restricted to medical officers");
    await medical.page.getByLabel("Visibility").selectOption("clinical");
    await saveAndNavigate(medical.page, "Save reviewer action");
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
      .getByLabel("Search synthetic member reference or request ID")
      .fill(product.replaceAll("_", "-"));
    await auditor.page.getByRole("button", { name: "Search", exact: true }).click();
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
    await saveAndNavigate(processor.page, "Upload for extraction");
    await waitFor(processor.page, "extracted");
    await expect(
      processor.page.getByText("Fictional policy wording for synthetic testing.", { exact: true }),
    ).toHaveCount(0);
    const restrictedProgress = await processor.page.request.get(`/workflows/progress?kind=request&id=${requestId}`);
    expect((await restrictedProgress.json()).documents.items[0].text).toBeNull();
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
      await saveAndNavigate(medical.page, "Save reviewer action");
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
    await medical.page
      .getByLabel("Clinical note", { exact: true })
      .fill("Fictional follow-up checked by the medical reviewer");
    await medical.page
      .getByLabel("Reason", { exact: true })
      .fill("Correct fictional note while retaining previous facts");
    await saveAndNavigate(medical.page, "Save facts and queue reassessment");
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
    await approver.page.getByLabel("Search product, version or policy name").fill(product);
    await approver.page.getByRole("button", { name: "Search", exact: true }).click();
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
    await expect(analyst.page.getByLabel("Policy product ID")).toHaveValue(product);
    await expect(analyst.page.getByLabel("Proposal reason")).toHaveValue(
      "Synthetic unactivated policy test",
    );
    await expect(analyst.page).toHaveURL(/\/workflows\/policies\/new$/);
    await expect(analyst.page.getByRole("alert", { name: "Form error" })).toHaveText(
      /This product and version already exist/,
    );
  } finally {
    await Promise.allSettled([analyst, approver, processor].map((p) => p.context.close()));
  }
});

test("request validation and connection errors retain all entries until a successful retry", async ({
  browser,
}) => {
  const actor = await login(browser, "processor");
  try {
    const page = actor.page;
    await page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New request", exact: true })
      .click();
    const member = `SYN-RETAIN-${Date.now()}`;
    await page.getByLabel("Synthetic member reference").fill(member);
    await page.getByLabel("Clinical note", { exact: true }).fill("Fictional retained note");
    await page.getByRole("button", { name: "Add expense", exact: true }).click();
    await page.getByLabel("Expense 4", { exact: true }).fill("Fictional additional charge");
    await page.getByLabel("Claimed INR", { exact: true }).nth(3).fill("100");
    await page.getByRole("button", { name: "Add declared condition" }).click();
    await page.getByLabel("Condition name 1", { exact: true }).fill("Fictional prior condition");
    await page.getByLabel("First diagnosed on 1", { exact: true }).fill("2020-01-01");
    await page.getByLabel("Declared at proposal 1", { exact: true }).check();
    await page.getByLabel("I confirm").check();
    await page.getByRole("button", { name: "Queue assessment" }).click();
    await expect(page.getByRole("alert", { name: "Form error" })).toContainText(
      "cost lines must add up",
    );
    await expect(page.getByLabel("Synthetic member reference")).toHaveValue(member);
    await expect(page.getByLabel("Clinical note", { exact: true })).toHaveValue(
      "Fictional retained note",
    );
    await expect(page.getByLabel("Expense 4", { exact: true })).toHaveValue(
      "Fictional additional charge",
    );
    await expect(page.getByLabel("Claimed INR", { exact: true }).nth(3)).toHaveValue("100");
    await expect(page.getByLabel("Condition name 1", { exact: true })).toHaveValue(
      "Fictional prior condition",
    );
    await expect(page.getByLabel("Declared at proposal 1", { exact: true })).toBeChecked();
    await expect(page).toHaveURL(/\/workflows\/new$/);
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
    await page.getByRole("button", { name: "Remove expense 1", exact: true }).click();
    await expect(page.getByLabel("Expense 1", { exact: true })).toHaveValue(
      "Procedure and professional fees",
    );
    await page.getByLabel("Estimated total in INR").fill("88100");
    const commandId = await page.locator('input[name="command_id"]').inputValue();
    await page.route("**/workflows/commands", (route) => route.abort("failed"));
    await page.getByRole("button", { name: "Queue assessment" }).click();
    await expect(page.getByRole("alert", { name: "Form error" })).toContainText(
      "save could not be confirmed",
    );
    await expect(page.getByLabel("Clinical note", { exact: true })).toHaveValue(
      "Fictional retained note",
    );
    await expect(page.locator('input[name="command_id"]')).toHaveValue(commandId);
    await page.unroute("**/workflows/commands");
    await page.getByRole("button", { name: "Queue assessment" }).click();
    await expect(page).toHaveURL(/\/workflows\/requests\/REQ-/);
    const withoutScripts = await browser.newContext({
      ...mvpBrowserOptions(),
      storageState: await actor.context.storageState(),
      javaScriptEnabled: false,
    });
    try {
      const plain = await withoutScripts.newPage();
      await plain.goto("/workflows/new");
      await expect(
        plain.getByText("Enable JavaScript to edit and submit this form safely."),
      ).toBeVisible();
      await expect(plain.getByRole("button", { name: "Queue assessment" })).toBeDisabled();
    } finally {
      await withoutScripts.close();
    }
  } finally {
    await actor.context.close();
  }
});

test("policy clauses, typed rules and regression examples can be edited without JSON", async ({
  browser,
}) => {
  const actor = await login(browser, "policy_analyst");
  try {
    const page = actor.page;
    await page.setViewportSize({ width: 390, height: 844 });
    await page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New policy", exact: true })
      .click();
    await page.getByLabel("Policy product ID").fill(`MVP_EDIT_${Date.now()}`);
    await page.getByLabel("Policy name", { exact: true }).fill("Synthetic edited policy");
    await page.getByLabel("Proposal reason").fill("Verify ordinary authoring controls");
    await page.getByText("Policy clauses", { exact: true }).click();
    await page.getByLabel("Clause ID", { exact: true }).fill("UI-ROOM");
    await page.getByLabel("Clause title", { exact: true }).fill("Synthetic edited room clause");
    await expect(page.getByRole("button", { name: "Remove selected clause" })).toBeDisabled();
    await page.getByRole("button", { name: "Add clause", exact: true }).click();
    await page.getByRole("button", { name: "Remove selected clause" }).click();
    await page.getByText("Policy rules", { exact: true }).click();
    await expect(page.getByLabel("Supporting clause")).toHaveValue("UI-ROOM");
    await page.getByLabel("Maximum INR per day").fill("5001");
    await page.getByLabel("Maximum INR per day").fill("5000");
    await page
      .getByLabel("Rule to edit")
      .selectOption({ label: "RULE_PROP · Proportionate deduction" });
    const applies = page.getByLabel("Applies to (one item per line)");
    const originalItems = await applies.inputValue();
    await applies.fill(`${originalItems}\nfictional unmatched expense`);
    await page
      .getByLabel("Rule to edit")
      .selectOption({ label: "RULE_INITIAL · Initial waiting period" });
    await page.getByLabel("Accidents exempt").selectOption("false");
    await page.getByLabel("Accidents exempt").selectOption("true");
    await page.getByRole("button", { name: "Add rule", exact: true }).click();
    await page.getByRole("button", { name: "Remove selected rule" }).click();
    await page.getByText("Regression examples", { exact: true }).click();
    await page.getByRole("button", { name: "Duplicate selected example" }).click();
    await page.getByLabel("Example name").fill("UI-FICTIONAL-COPY");
    await page
      .getByLabel("Clinical note", { exact: true })
      .fill("Fictional regression note edited through the form");
    await page.getByLabel("Example to edit").selectOption({ label: "GOL001" });
    await page.getByLabel("Example to edit").selectOption({ label: "UI-FICTIONAL-COPY" });
    await expect(page.getByLabel("Clinical note", { exact: true })).toHaveValue(
      "Fictional regression note edited through the form",
    );
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.getByRole("button", { name: "Save proposal and run regressions" }).click();
    await expect(page).toHaveURL(/\/workflows\/policies\/[a-f0-9-]+/);
    await waitFor(page, "succeeded · Passed · 31 cases");
    await expect(page.getByText(/Synthetic edited room clause · Page 7/)).toBeVisible();
    await expect(page.getByText(/fictional unmatched expense/)).toBeVisible();
    await page.screenshot({ path: "test-results/mvp/edited-policy.png", fullPage: true });
  } finally {
    await actor.context.close();
  }
});

test("policy and request searches span multiple pages and keep the search on navigation", async ({
  browser,
}) => {
  const analyst = await login(browser, "policy_analyst");
  const processor = await login(browser, "processor");
  const prefix = `PAGING-${Date.now()}`;
  try {
    await analyst.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New policy", exact: true })
      .click();
    const proposal = await analyst.page.locator('input[name="proposal"]').inputValue();
    await processor.page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New request", exact: true })
      .click();
    const product = await processor.page.getByLabel("Policy product").inputValue();
    expect(product).not.toBe("");
    const facts = JSON.parse(await processor.page.locator('input[name="facts"]').inputValue());
    // Create owned fictional fixtures through real mutation routes; pagination itself is exercised in the UI.
    for (let index = 0; index < 21; index++) {
      const post = async (page: Page, form: Record<string, string>) => {
        const response = await page.request.post("/workflows/commands", {
          headers: { Origin: new URL(page.url()).origin, Accept: "application/json" },
          form,
        });
        expect((await response.json()).result).toBe("saved");
      };
      await post(analyst.page, {
        operation: "propose",
        command_id: crypto.randomUUID(),
        product_id: `${prefix}-${index}`,
        version: "V1",
        proposal,
        reason: "Synthetic pagination fixture",
      });
      await post(processor.page, {
        operation: "submit",
        command_id: crypto.randomUUID(),
        product_id: product,
        synthetic_data: "true",
        priority: "normal",
        facts: JSON.stringify({ ...facts, member_reference: `SYN-${prefix}-${index}` }),
      });
    }
    for (const [actor, link, label] of [
      [analyst, "Policy library", "Search product, version or policy name"],
      [processor, "Submitted requests", "Search synthetic member reference or request ID"],
    ] as const) {
      await actor.page.setViewportSize({ width: 390, height: 844 });
      await actor.page
        .getByRole("navigation", { name: "Workflow navigation" })
        .getByRole("link", { name: link, exact: true })
        .click();
      await actor.page.getByLabel(label).fill(prefix);
      await actor.page.getByRole("button", { name: "Search", exact: true }).click();
      await expect(actor.page.getByRole("navigation", { name: "List pagination" })).toContainText(
        "21 results · Page 1 of 2",
      );
      await actor.page.getByRole("link", { name: "Next page", exact: true }).click();
      await expect(actor.page.getByRole("navigation", { name: "List pagination" })).toContainText(
        "21 results · Page 2 of 2",
      );
      await expect(actor.page.getByLabel(label)).toHaveValue(prefix);
      await expect(actor.page.getByRole("link", { name: "Next page", exact: true })).toHaveCount(0);
      await actor.page.getByRole("link", { name: "Previous page", exact: true }).click();
      await expect(actor.page.getByRole("navigation", { name: "List pagination" })).toContainText(
        "Page 1 of 2",
      );
      await actor.page.getByLabel(label).fill("NO-SUCH-FICTIONAL-RECORD");
      await actor.page.getByRole("button", { name: "Search", exact: true }).click();
      await expect(actor.page.getByRole("navigation", { name: "List pagination" })).toContainText(
        "0 results",
      );
      expect(
        await actor.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      ).toBe(true);
      await actor.page.getByRole("link", { name: "Clear search", exact: true }).click();
      await expect(actor.page.getByLabel(label)).toHaveValue("");
    }
  } finally {
    await Promise.allSettled([analyst.context.close(), processor.context.close()]);
  }
});
