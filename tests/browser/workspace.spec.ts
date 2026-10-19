import { expect, test } from "@playwright/test";

for (const [profile, name, role] of [
  ["processor", "Asha Deshmukh", "Processor"],
  ["medical_officer", "Dr. Neel Shah", "Medical officer"],
  ["auditor", "Kavya Rao", "Auditor"],
]) {
  test(`sign in and out as ${profile}`, async ({ page, context }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Enter the workspace" }).click();
    await page.getByLabel("Review role").selectOption(profile);
    await page.getByRole("button", { name: "Enter workspace" }).click();
    await expect(page.getByTestId("signed-in-name")).toHaveText(name);
    await expect(page.getByTestId("identity-role")).toHaveText(role);
    await expect(page.getByTestId("identity-verified")).toBeVisible();
    await expect(page.getByTestId("tenant-name")).toContainText("Sahyadri Health TPA");
    const cookie = (await context.cookies()).find((item) => item.name === "ciq_session");
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("Strict");
    await page.getByRole("button", { name: "Sign out" }).click();
    await page.waitForURL("**/login");
    expect((await context.cookies()).find((item) => item.name === "ciq_session")).toBeUndefined();
    await page.goto("/");
    await expect(page.getByTestId("signed-in-name")).toHaveCount(0);
  });
}

test("mobile workspace has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Clarity before every decision." })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("login rejects a foreign origin", async ({ request }) => {
  const response = await request.post("/auth/login", {
    headers: { origin: "https://untrusted.example" },
    form: { profile: "medical_officer" },
  });
  expect(response.status()).toBe(403);
});
