import { expect, test } from "@playwright/test";

test("source preview requires authentication", async ({ page }) => {
  await page.goto("/source-preview");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("UI-FIXTURE-001", { exact: true })).toHaveCount(0);
});

test.describe("authenticated local fixture presentation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await expect(page.getByTestId("identity-verified")).toBeVisible();
    await page.goto("/source-preview");
  });

  test("missing is neither a query, referral nor zero payable", async ({ page }) => {
    await expect(page.getByText("Local UI fixture preview · No Snowflake reads")).toBeVisible();
    await expect(page.getByRole("heading", { name: "No saved recommendation" })).toBeVisible();
    await expect(page.getByText("Draft payable", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Information needed", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Medical referral", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Conditions are restricted for this role.")).toBeVisible();
    await expect(page.getByRole("button", { name: /approve|refer|query|generate/i })).toHaveCount(
      0,
    );
  });

  test("saved values are displayed without a fabricated trace", async ({ page }) => {
    await page.getByRole("link", { name: "Saved", exact: true }).click();
    await expect(page.getByText("Deductions draft", { exact: true })).toBeVisible();
    await expect(page.getByText("₹95,000", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Full calculation trace and clinical narrative", {
        exact: false,
      }),
    ).toBeVisible();
    await expect(page.getByText("No clause references returned.")).toBeVisible();
  });

  for (const [state, badge] of [
    ["Query", "Information needed"],
    ["Refer", "Medical referral"],
  ]) {
    test(`${state} remains a saved draft with uncalculated payable`, async ({ page }) => {
      await page.getByRole("link", { name: state, exact: true }).click();
      await expect(page.getByText(badge, { exact: true })).toBeVisible();
      await expect(page.getByText("Not calculated", { exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "No saved recommendation" })).toHaveCount(0);
    });
  }

  test("failure never falls back to a missing or demo recommendation", async ({ page }) => {
    await page.getByRole("link", { name: "Unavailable", exact: true }).click();
    await expect(page.getByRole("alert", { name: "Source unavailable" })).toContainText(
      "Recommendation status is unknown, not missing",
    );
    await expect(page.getByRole("heading", { name: "No saved recommendation" })).toHaveCount(0);
    await expect(page.getByText("₹95,000", { exact: true })).toHaveCount(0);
  });

  test("mobile preview fits and unknown fixture is rejected", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.goto("/source-preview?state=DENY");
    await expect(page.getByRole("heading", { name: "404" })).toBeVisible();
  });
});
