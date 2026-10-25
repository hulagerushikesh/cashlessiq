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
    await analyst.page.goto("/workflows/policies/new");
    const definition = analyst.page.getByLabel("Versioned policy definition");
    const proposal = JSON.parse(await definition.inputValue());
    proposal.product_id = product;
    proposal.version = product;
    await definition.fill(JSON.stringify(proposal));
    await analyst.page.getByLabel("Proposal reason").fill("Synthetic browser regression policy");
    await analyst.page.getByRole("button", { name: "Save proposal and run regressions" }).click();
    await expect(analyst.page).toHaveURL(/\/workflows\/policies\/[a-f0-9-]+/);
    await waitFor(analyst.page, "succeeded · Passed · 30 cases");
    const policyUrl = analyst.page.url();
    await approver.page.goto(policyUrl);
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

    await processor.page.goto("/workflows/new");
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
    await medical.page.goto(`/reviews/${requestId}`);
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
    await auditor.page.goto(`/reviews/${requestId}`);
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
