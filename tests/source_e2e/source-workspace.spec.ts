import { createHmac } from "node:crypto";
import { expect, test, type BrowserContext } from "@playwright/test";

const key = "source-e2e-test-key-not-for-any-deployment-0000";
const tenants = {
  TPA001: "00000000-0000-4000-8000-000000000101",
  TPA003: "00000000-0000-4000-8000-000000000103",
};
type Role = "processor" | "medical_officer" | "auditor";
function token(tenant: keyof typeof tenants, role: Role, expired = false) {
  const now = Math.floor(Date.now() / 1000);
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const body = `${encode({ alg: "HS256", typ: "JWT" })}.${encode({ iss: "urn:cashlessiq:local", aud: "cashlessiq-api", sub: `source-alpha:${tenant}:${role}`, ciq_tenant_id: tenants[tenant], iat: now - 10, exp: expired ? now - 1 : now + 300 })}`;
  return `${body}.${createHmac("sha256", key).update(body).digest("base64url")}`;
}
async function login(context: BrowserContext, tenant: keyof typeof tenants, role: Role) {
  await context.addCookies([
    {
      name: "ciq_session",
      value: token(tenant, role),
      url: "http://localhost:3003",
      httpOnly: true,
      sameSite: "Strict",
    },
  ]);
}

test("anonymous and expired source sessions redirect without case data", async ({
  page,
  context,
}) => {
  await page.goto("/source-cases/GOL001");
  await expect(page).toHaveURL(/\/login$/);
  await context.addCookies([
    {
      name: "ciq_session",
      value: token("TPA001", "processor", true),
      url: "http://localhost:3003",
    },
  ]);
  await page.goto("/source-cases");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Source case queue" })).toHaveCount(0);
});

for (const role of ["processor", "medical_officer", "auditor"] as const) {
  test(`${role}: TPA001 queue and saved detail traverse real HTTP`, async ({
    page,
    context,
  }, testInfo) => {
    await login(context, "TPA001", role);
    await page.goto("/source-cases");
    await expect(page.getByText("Offline source contract test · Fake gateways")).toBeVisible();
    await expect(page.getByRole("link", { name: "Inspect GOL001", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Inspect GOL024" })).toHaveCount(0);
    await expect(
      page.getByText("Metadata only · Recommendations are not loaded", { exact: false }),
    ).toBeVisible();
    await expect(page.getByText("Deductions draft", { exact: true })).toHaveCount(0);
    await page.getByRole("link", { name: "Inspect GOL001", exact: true }).click();
    await expect(page.getByRole("heading", { name: "GOL001", exact: true })).toBeVisible();
    await expect(page.getByText("₹95,000", { exact: true })).toBeVisible();
    if (role === "medical_officer") {
      await expect(
        page.getByRole("listitem").filter({ hasText: "I10 · Synthetic condition" }),
      ).toBeVisible();
    } else {
      await expect(page.getByText("Conditions are restricted for this role.")).toBeVisible();
      expect(await page.content()).not.toContain("Synthetic condition");
    }
    expect(await page.content()).not.toContain("Restricted synthetic narrative");
    expect(await page.content()).not.toContain("Sensitive synthetic prose");
    await expect(page.getByRole("button", { name: /approve|refer|query|generate/i })).toHaveCount(
      0,
    );
    const register = page.getByRole("region", { name: "Product clause register" });
    await register.getByRole("searchbox").fill("copay");
    await expect(register.getByRole("status")).toHaveText("Showing 1 of 1 clause references");
    await expect(register.getByRole("link")).toHaveAttribute(
      "href",
      "https://example.com/policy.pdf#page=5",
    );
    if (role === "medical_officer")
      await page.screenshot({ path: testInfo.outputPath("source-desktop.png"), fullPage: true });
  });
}

for (const role of ["processor", "medical_officer", "auditor"] as const) {
  test(`${role}: TPA003 missing decisions never inherit the offline demo outcomes`, async ({
    page,
    context,
  }) => {
    await login(context, "TPA003", role);
    await page.goto("/source-cases");
    await expect(page.getByRole("link", { name: "Inspect GOL001" })).toHaveCount(0);
    for (const request of ["GOL024", "GOL027"]) {
      await page.getByRole("link", { name: `Inspect ${request}`, exact: true }).click();
      await expect(page.getByRole("heading", { name: "No saved recommendation" })).toBeVisible();
      await expect(page.getByText("Draft payable", { exact: true })).toHaveCount(0);
      await expect(page.getByText("Medical referral", { exact: true })).toHaveCount(0);
      await expect(page.getByText("Information needed", { exact: true })).toHaveCount(0);
      await page.getByRole("link", { name: "Back to source queue" }).click();
    }
  });
}

for (const [tenant, foreign] of [
  ["TPA001", "GOL024"],
  ["TPA003", "GOL001"],
] as const) {
  for (const role of ["processor", "medical_officer", "auditor"] as const) {
    test(`${tenant}/${role}: foreign known ID is 404 even with spoofed tenant header`, async ({
      page,
      context,
    }) => {
      await login(context, tenant, role);
      await page.setExtraHTTPHeaders({
        "X-Tenant-Id": tenant === "TPA001" ? tenants.TPA003 : tenants.TPA001,
      });
      await page.goto(`/source-cases/${foreign}`);
      await expect(page.getByRole("heading", { name: "404" })).toBeVisible();
      await expect(page.getByRole("heading", { name: foreign, exact: true })).toHaveCount(0);
      await expect(page.getByText("₹95,000", { exact: true })).toHaveCount(0);
    });
  }
}

test("queue filters have a truthful empty state and mobile fits", async ({ page, context }) => {
  await login(context, "TPA003", "auditor");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/source-cases");
  await page.getByRole("textbox", { name: "Request reference" }).fill("unknown");
  await page.getByRole("button", { name: "Apply filter" }).click();
  await expect(page.getByRole("heading", { name: "No matching source requests" })).toBeVisible();
  await expect(page.getByRole("alert", { name: "Source unavailable" })).toHaveCount(0);
  await page.getByRole("link", { name: "Reset", exact: true }).click();
  await page.getByRole("link", { name: "Inspect GOL027", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("HTTP source outage is unknown, never missing or demo fallback", async ({ page, context }) => {
  await login(context, "TPA003", "processor");
  await page.goto("/source-cases?search=TEST_SOURCE_OUTAGE");
  await expect(page.getByRole("alert", { name: "Source unavailable" })).toContainText(
    "Recommendation status is unknown, not missing",
  );
  await expect(page.getByRole("heading", { name: "No matching source requests" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "No saved recommendation" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Inspect GOL/ })).toHaveCount(0);
  await expect(page.getByText("Medical referral", { exact: true })).toHaveCount(0);
});
