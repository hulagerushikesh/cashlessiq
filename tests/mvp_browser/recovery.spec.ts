import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { mvpBrowserOptions } from "./runtime";

// The normal browser suite creates a completed fictional journey. CI sets this
// only after restoring its database backup and restarting preview services. The
// same check is then run against a second preview restored onto a fresh volume.
if (process.env.MVP_RECOVERY_CHECKPOINT) {
  const checkpoint = JSON.parse(readFileSync(process.env.MVP_RECOVERY_CHECKPOINT, "utf8")) as {
    requestId: string;
    policyId: string;
    documentId: string;
  };

  test("saved workflow survives recovery and a fresh browser session", async ({ browser }) => {
    const context = await browser.newContext(mvpBrowserOptions());
    try {
      const page = await context.newPage();
      await page.goto("/login");
      await page.getByLabel("Review role").selectOption("medical_officer");
      await page.getByRole("button", { name: "Enter workspace" }).click();
      await expect(page).toHaveURL(/\/$/);

      await page
        .getByRole("navigation", { name: "Workflow navigation" })
        .getByRole("link", { name: "Submitted requests", exact: true })
        .click();
      await page
        .getByLabel("Search synthetic member reference or request ID")
        .fill(checkpoint.requestId);
      await page.getByRole("button", { name: "Search", exact: true }).click();
      await page.getByRole("link", { name: /SYN-MVP-E2E-/ }).click();
      await expect(page.getByText("APPROVE WITH DEDUCTIONS · ₹95,000")).toBeVisible();
      await expect(page.getByText("Fictional policy wording for synthetic testing.")).toBeVisible();
      const download = page.getByRole("link", { name: "Download PDF" });
      await expect(download).toHaveAttribute(
        "href",
        `/workflows/documents/${checkpoint.documentId}`,
      );
      expect(
        (await page.request.get(`/workflows/documents/${checkpoint.documentId}`)).status(),
      ).toBe(200);

      await page.getByRole("link", { name: "View pinned policy clauses and wording" }).click();
      await expect(page).toHaveURL(new RegExp(`/workflows/policies/${checkpoint.policyId}$`));
      await expect(page.getByText(/Currently active/)).toBeVisible();
      await page.goBack();
      await page.getByRole("link", { name: "Open reviewer workflow" }).click();
      await expect(page.getByText(/Synthetic testing · APPROVED WITH DEDUCTIONS/)).toBeVisible();
      await expect(
        page.getByText("Fictional clinical note restricted to medical officers"),
      ).toBeVisible();
    } finally {
      await context.close();
    }
  });
}
