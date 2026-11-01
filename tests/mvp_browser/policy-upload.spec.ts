import { expect, test, type Browser } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { mvpBrowserOptions } from "./runtime";

const endpoint = "/workflows/progress?kind=policy-documents&id=POLICY-WORDING";
const pdf = path.join(process.cwd(), "tests/fixtures/mvp/synthetic.pdf");

async function author(browser: Browser) {
  const context = await browser.newContext(mvpBrowserOptions());
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByLabel("Review role").selectOption("policy_analyst");
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await page
    .getByRole("navigation", { name: "Workflow navigation" })
    .getByRole("link", { name: "New policy", exact: true })
    .click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel("Policy product ID").fill(`UPLOAD_${Date.now()}`);
  await page
    .getByLabel("Policy name", { exact: true })
    .fill("Fictional proposal kept during upload");
  await page
    .getByLabel("Proposal reason")
    .fill("Preserve these unsaved fictional authoring entries");
  await page.getByText("Policy clauses", { exact: true }).click();
  await page
    .getByLabel("Clause title", { exact: true })
    .fill("Fictional edited clause title");
  await page
    .getByText("Optional: upload fictional policy wording PDF", { exact: true })
    .click();
  await page.evaluate(() => {
    document.documentElement.dataset.uploadMarker = "same-document";
  });
  const proposal = page
    .locator("form")
    .filter({ has: page.getByLabel("Policy product ID") });
  const upload = page
    .locator("form")
    .filter({ has: page.getByLabel("Policy PDF", { exact: true }) });
  const source = page.getByLabel("Source wording");
  return { context, page, proposal, upload, source };
}

test("real wording uploads keep the mounted proposal and selected source until proposal save", async ({
  browser,
}) => {
  const { context, page, proposal, upload, source } = await author(browser);
  try {
    const product = await page.getByLabel("Policy product ID").inputValue();
    const definition = await proposal
      .locator("input[name=proposal]")
      .inputValue();
    const proposalKey = await proposal
      .locator("input[name=command_id]")
      .inputValue();
    const existingIds = await source
      .locator("option")
      .evaluateAll((options) =>
        options.map((option) => (option as HTMLOptionElement).value),
      );
    let selected = "";
    for (let index = 0; index < 2; index++) {
      const uploadKey = await upload
        .locator("input[name=command_id]")
        .inputValue();
      await page.getByLabel("Policy PDF", { exact: true }).setInputFiles(pdf);
      await page.getByLabel("Fictional test data only").check();
      await page
        .getByRole("button", {
          name: "Upload wording for extraction",
          exact: true,
        })
        .click();
      await expect(upload.getByRole("status")).toContainText(
        "Your proposal entries are still here",
      );
      await expect(upload.locator("input[name=command_id]")).not.toHaveValue(
        uploadKey,
      );
      await expect(page.getByLabel("Policy PDF", { exact: true })).toHaveValue(
        "",
      );
      await expect(
        page.getByLabel("Fictional test data only"),
      ).not.toBeChecked();
      await expect(source.locator("option")).toHaveCount(
        existingIds.length + index + 1,
        { timeout: 30000 },
      );
      if (index === 0) {
        selected = await source
          .locator("option")
          .evaluateAll(
            (options, previous) =>
              (
                options.find(
                  (option) =>
                    !previous.includes((option as HTMLOptionElement).value),
                ) as HTMLOptionElement
              ).value,
            existingIds,
          );
        await source.selectOption(selected);
      }
      await expect(source).toHaveValue(selected);
      await expect(page.getByLabel("Policy product ID")).toHaveValue(product);
      await expect(page.getByLabel("Proposal reason")).toHaveValue(
        "Preserve these unsaved fictional authoring entries",
      );
      await expect(proposal.locator("input[name=proposal]")).toHaveValue(
        definition,
      );
      await expect(proposal.locator("input[name=command_id]")).toHaveValue(
        proposalKey,
      );
      expect(
        await page.evaluate(
          () => document.documentElement.dataset.uploadMarker,
        ),
      ).toBe("same-document");
      expect(
        await page.evaluate(() => [localStorage.length, sessionStorage.length]),
      ).toEqual([0, 0]);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole("button", {
        name: "Save proposal and run regressions",
        exact: true,
      })
      .click();
    await expect(page).toHaveURL(/\/workflows\/policies\/[a-f0-9-]+/);
    await expect(
      page.getByText("succeeded · Passed · 30 cases", { exact: true }),
    ).toBeVisible({ timeout: 30000 });
    await expect(
      page.getByRole("heading", {
        name: "Fictional proposal kept during upload",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Fictional edited clause title/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", {
        name: "Download source policy wording",
        exact: true,
      }),
    ).toHaveAttribute("href", `/workflows/documents/${selected}`);
  } finally {
    await context.close();
  }
});

test("lost upload receipts retain the file and command key; confirmed retry is idempotent", async ({
  browser,
}) => {
  const { context, page, upload, proposal } = await author(browser);
  try {
    const before = (await (await context.request.get(endpoint)).json()).items
      .length;
    const uploadKey = await upload
      .locator("input[name=command_id]")
      .inputValue();
    const proposalKey = await proposal
      .locator("input[name=command_id]")
      .inputValue();
    await page.getByLabel("Policy PDF", { exact: true }).setInputFiles(pdf);
    await page.getByLabel("Fictional test data only").check();
    await page.route(
      "**/workflows/commands",
      async (route) => {
        // Commit the same file/key through authenticated HTTP, then lose the
        // browser response. Supply explicit multipart bytes for this fault
        // injection instead of replaying an intercepted browser file body.
        const response = await context.request.post("/workflows/commands", {
          headers: { Origin: new URL(page.url()).origin, Accept: "application/json" },
          multipart: {
            operation: "policy-upload",
            command_id: uploadKey,
            synthetic_data: "true",
            document: {
              name: "synthetic.pdf",
              mimeType: "application/pdf",
              buffer: readFileSync(pdf),
            },
          },
        });
        expect((await response.json()).result).toBe("saved");
        await route.abort("failed");
      },
      { times: 1 },
    );
    await page
      .getByRole("button", {
        name: "Upload wording for extraction",
        exact: true,
      })
      .click();
    await expect(
      upload.getByRole("alert", { name: "Form error" }),
    ).toContainText("save could not be confirmed");
    await expect(upload.locator("input[name=command_id]")).toHaveValue(
      uploadKey,
    );
    await expect(
      page.getByLabel("Policy PDF", { exact: true }),
    ).not.toHaveValue("");
    await expect(page.getByLabel("Fictional test data only")).toBeChecked();
    await page.route("**/workflows/progress?kind=policy-documents&*", (route) =>
      route.fulfill({ status: 503 }),
    );
    await page
      .getByRole("button", {
        name: "Upload wording for extraction",
        exact: true,
      })
      .click();
    await expect(upload.getByRole("status")).toContainText("PDF uploaded");
    await expect(upload.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText(/Progress could not be checked/)).toBeVisible();
    await expect(proposal.locator("input[name=command_id]")).toHaveValue(
      proposalKey,
    );
    await expect(page.getByLabel("Proposal reason")).toHaveValue(
      "Preserve these unsaved fictional authoring entries",
    );
    const after = (await (await context.request.get(endpoint)).json()).items
      .length;
    expect(after).toBe(before + 1);
    await page.unroute("**/workflows/progress?kind=policy-documents&*");
    await page
      .getByRole("button", { name: "Check for updates", exact: true })
      .click();
    await expect(
      page.getByText("Showing the latest loaded results.", { exact: true }),
    ).toBeVisible({ timeout: 30000 });
    expect(
      await page.evaluate(() => document.documentElement.dataset.uploadMarker),
    ).toBe("same-document");
  } finally {
    await context.close();
  }
});
