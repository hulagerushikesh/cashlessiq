import { expect, test } from "@playwright/test";
import { mvpBrowserOptions } from "./runtime";

test("progress route requires a session and refuses arbitrary paths", async ({
  browser,
  request,
}) => {
  const url = "/workflows/progress?kind=policy&id=00000000-0000-4000-8000-000000000001";
  const anonymous = await request.get(url);
  expect(anonymous.status()).toBe(401);
  expect(anonymous.headers()["cache-control"]).toContain("no-store");
  const context = await browser.newContext(mvpBrowserOptions());
  try {
    const page = await context.newPage();
    await page.goto("/login");
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await expect(page).toHaveURL(/\/$/);
    for (const query of ["kind=other&id=abc", "kind=policy&id=..%2Fmembers", "kind=policy&id="]) {
      expect((await context.request.get(`/workflows/progress?${query}`)).status()).toBe(400);
    }
  } finally {
    await context.close();
  }
});

test("regression updates preserve an open decision form and recover from unavailable progress", async ({
  browser,
}) => {
  const context = await browser.newContext(mvpBrowserOptions());
  try {
    const page = await context.newPage();
    await page.goto("/login");
    await page.getByLabel("Review role").selectOption("policy_analyst");
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New policy", exact: true })
      .click();
    await page.getByLabel("Policy product ID").fill(`PROGRESS_${Date.now()}`);
    await page.getByLabel("Proposal reason").fill("Fictional progress test");
    await page.getByRole("button", { name: "Save proposal and run regressions" }).click();
    await expect(page).toHaveURL(/\/workflows\/policies\/[a-f0-9-]+/);
    await expect(page.getByText("succeeded · Passed · 30 cases", { exact: true })).toBeVisible({
      timeout: 30000,
    });
    const policyUrl = new URL(page.url());
    const id = policyUrl.pathname.split("/").at(-1);
    await page.getByRole("button", { name: "Sign out" }).click();
    await page.getByLabel("Review role").selectOption("policy_approver");
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await page.goto(policyUrl.pathname);
    const endpoint = `/workflows/progress?kind=policy&id=${id}`;
    const actual = await context.request.get(endpoint);
    expect(actual.status()).toBe(200);
    expect(actual.headers()["cache-control"]).toContain("no-store");
    const completed = await actual.json();
    expect(Object.keys(completed).sort()).toEqual([
      "regression",
      "regression_job_id",
      "regression_state",
    ]);
    const jobPage = await context.newPage();
    await jobPage.goto(`/workflows/jobs/${completed.regression_job_id}`);
    await expect(
      jobPage.getByRole("heading", { name: "Background job details", exact: true }),
    ).toBeVisible();
    await expect(
      jobPage.getByRole("link", { name: "Open related policy", exact: true }),
    ).toHaveAttribute("href", policyUrl.pathname);
    await expect(jobPage.getByRole("button", { name: "Retry job", exact: true })).toHaveCount(0);
    await jobPage.close();
    const reason = page.getByLabel("Reason", { exact: true });
    await reason.fill("Keep this unsaved independent review reason");
    const command = page.locator("#policy-decision input[name=command_id]");
    const commandId = await command.inputValue();
    await page.evaluate(() => {
      document.documentElement.dataset.progressMarker = "same-page";
    });
    let calls = 0;
    let status = 200;
    await page.route("**/workflows/progress?kind=policy&*", async (route) => {
      calls++;
      await route.fulfill({
        status,
        json:
          calls === 1
            ? {
                regression_job_id: completed.regression_job_id,
                regression_state: "running",
                regression: null,
              }
            : completed,
      });
    });
    await page.getByRole("button", { name: "Check for updates" }).click();
    await expect(page.getByText(/Checking progress every 5 seconds/)).toBeVisible();
    await expect(page.getByText("succeeded · Passed · 30 cases", { exact: true })).toBeVisible({
      timeout: 15000,
    });
    expect(calls).toBe(2);
    await expect(reason).toHaveValue("Keep this unsaved independent review reason");
    await expect(command).toHaveValue(commandId);
    expect(await page.evaluate(() => document.documentElement.dataset.progressMarker)).toBe(
      "same-page",
    );
    status = 503;
    await page.getByRole("button", { name: "Check for updates" }).click();
    await expect(page.getByText(/Progress could not be checked/)).toBeVisible();
    await expect(page.getByText("succeeded · Passed · 30 cases", { exact: true })).toBeVisible();
    status = 200;
    await page.getByRole("button", { name: "Check for updates" }).click();
    await expect(
      page.getByText("Showing the latest loaded results.", { exact: true }),
    ).toBeVisible();
    status = 401;
    await page.getByRole("button", { name: "Check for updates" }).click();
    await expect(page.getByRole("link", { name: "Sign in again", exact: true })).toBeVisible();
    await expect(page.getByText("succeeded · Passed · 30 cases", { exact: true })).toHaveCount(0);
    await expect(reason).toHaveValue("Keep this unsaved independent review reason");
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  } finally {
    await context.close();
  }
});

test("policy wording completion enables selection without replacing the proposal", async ({
  browser,
}) => {
  const context = await browser.newContext(mvpBrowserOptions());
  try {
    const page = await context.newPage();
    await page.goto("/login");
    await page.getByLabel("Review role").selectOption("policy_analyst");
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await page
      .getByRole("navigation", { name: "Workflow navigation" })
      .getByRole("link", { name: "New policy", exact: true })
      .click();
    await page.getByLabel("Policy product ID").fill("KEEP_MY_PROPOSAL");
    await page
      .getByLabel("Proposal reason")
      .fill("Keep this fictional proposal while wording is processed");
    const proposal = page.locator("form").filter({ has: page.getByLabel("Policy product ID") });
    const commandId = await proposal.locator("input[name=command_id]").inputValue();
    const id = "00000000-0000-4000-8000-000000000909";
    const document = {
      id,
      state: "quarantined",
      text: null as string | null,
      digest: "a".repeat(64),
      processing_job: { id: "fake-job", state: "running", attempts: 1 },
    };
    let calls = 0;
    await page.route("**/workflows/progress?kind=policy-documents&*", async (route) => {
      calls++;
      await route.fulfill({
        json: {
          clinical_restricted: false,
          items: [
            calls === 1
              ? document
              : {
                  ...document,
                  state: "extracted",
                  text: "Fictional extracted wording",
                  processing_job: {
                    ...document.processing_job,
                    state: "succeeded",
                  },
                },
          ],
        },
      });
    });
    await page.getByRole("button", { name: "Check for updates" }).click();
    await expect(
      page.getByText("Extraction is pending. This PDF cannot be selected as source wording yet."),
    ).toBeVisible();
    await expect(page.getByLabel("Source wording").locator(`option[value='${id}']`)).toHaveCount(0);
    await expect(page.getByText("Fictional extracted wording", { exact: true })).toBeVisible({
      timeout: 15000,
    });
    await page.getByLabel("Source wording").selectOption(id);
    await expect(page.getByLabel("Policy product ID")).toHaveValue("KEEP_MY_PROPOSAL");
    await expect(page.getByLabel("Proposal reason")).toHaveValue(
      "Keep this fictional proposal while wording is processed",
    );
    await expect(proposal.locator("input[name=command_id]")).toHaveValue(commandId);
    expect(calls).toBe(2);
    // An ordinary role never receives policy wording through the real progress route.
    await page.getByRole("button", { name: "Sign out" }).click();
    await page.getByLabel("Review role").selectOption("processor");
    await page.getByRole("button", { name: "Enter workspace" }).click();
    expect(
      (
        await context.request.get("/workflows/progress?kind=policy-documents&id=POLICY-WORDING")
      ).status(),
    ).toBe(403);
  } finally {
    await context.close();
  }
});
