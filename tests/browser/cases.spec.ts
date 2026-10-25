import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page, profile: string) {
  await page.goto("/login");
  await page.getByLabel("Review role").selectOption(profile);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page.getByTestId("identity-verified")).toBeVisible();
  await page.getByRole("link", { name: "Open case queue" }).click();
  await expect(page.getByRole("heading", { name: "Case queue", exact: true })).toBeVisible();
}

for (const profile of ["processor", "medical_officer", "auditor"]) {
  test(`${profile} cannot reopen a protected case after sign-out`, async ({ page, context }) => {
    await signIn(page, profile);
    await page.getByRole("link", { name: "Open GOL001" }).click();
    await expect(page.getByText("₹95,000", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect((await context.cookies()).find((cookie) => cookie.name === "ciq_session"))
      .toBeUndefined();
    await page.goto("/cases/GOL001");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText("₹95,000", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Acute appendicitis", { exact: true })).toHaveCount(0);
  });

  test(`${profile} reads queue and the three case journeys`, async ({ page }) => {
    await signIn(page, profile);
    await expect(page.getByRole("heading", { name: "Case queue", exact: true })).toBeVisible();
    await expect(page.getByText("3 matching synthetic cases")).toBeVisible();
    await page.getByRole("link", { name: "Open GOL001" }).click();
    await expect(page.getByRole("heading", { name: "Deterministic calculation" })).toBeVisible();
    await expect(page.getByText("₹95,000", { exact: true })).toBeVisible();
    const clause = page.getByRole("link", { name: "NIA-9.5", exact: true }).first();
    await clause.click();
    await expect(page.locator("#NIA-9\\.5")).toBeVisible();
    if (profile === "medical_officer") {
      await expect(page.getByText("Acute appendicitis", { exact: true })).toBeVisible();
    } else {
      await expect(page.getByText("Clinical narrative is restricted", { exact: false })).toBeVisible();
      await expect(page.getByText("Acute appendicitis", { exact: true })).toHaveCount(0);
    }
    await expect(page.getByRole("button", { name: /approve|refer|query/i })).toHaveCount(0);
    await page.getByRole("link", { name: "Back to case queue" }).click();
    await page.getByRole("link", { name: "Open GOL027" }).click();
    await expect(page.getByRole("heading", { name: "Missing information" })).toBeVisible();
    await expect(page.getByText("Please provide cost breakup.", { exact: true })).toBeVisible();
    await expect(page.getByText("Not calculated", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "Back to case queue" }).click();
    await page.getByRole("link", { name: "Open GOL024" }).click();
    await expect(page.getByRole("heading", { name: "Referral reason" })).toBeVisible();
    await expect(page.getByText("Not calculated", { exact: true })).toBeVisible();
  });
}

test("queue filters and empty state", async ({ page }) => {
  await signIn(page, "processor");
  await page.getByRole("combobox", { name: "Recommendation", exact: true }).selectOption("QUERY");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByRole("link", { name: "Open GOL027" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open GOL001" })).toHaveCount(0);
  await page.getByLabel("Request or member reference").fill("SYN-GOL027");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await page.getByRole("link", { name: "Open GOL027" }).click();
  await page.getByRole("link", { name: "Back to case queue" }).click();
  await expect(page.getByLabel("Request or member reference")).toHaveValue("SYN-GOL027");
  await expect(page.getByRole("combobox", { name: "Recommendation", exact: true }))
    .toHaveValue("QUERY");
  await expect(page.getByText("1 matching synthetic case", { exact: true })).toBeVisible();
  await page.getByLabel("Request or member reference").fill("no-match");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByRole("heading", { name: "No matching cases" })).toBeVisible();
  await page.getByRole("link", { name: "Reset", exact: true }).click();
  await expect(page.getByText("3 matching synthetic cases")).toBeVisible();
});

test("anonymous case access redirects to sign-in", async ({ page }) => {
  await page.goto("/cases/GOL001");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("₹95,000", { exact: true })).toHaveCount(0);
});

test("unknown case is not found", async ({ page }) => {
  await signIn(page, "processor");
  await page.goto("/cases/UNKNOWN");
  await expect(page.getByRole("heading", { name: "Case not found" })).toBeVisible();
  await expect(page.getByText("₹95,000", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Back to case queue" }).click();
  await expect(page.getByRole("heading", { name: "Case queue", exact: true })).toBeVisible();
});

test("case queue and detail fit a mobile screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "medical_officer");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Open GOL001" }).click();
  await expect(page.getByRole("heading", { name: "Policy evidence" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
