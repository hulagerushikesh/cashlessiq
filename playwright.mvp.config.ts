import { defineConfig, devices } from "@playwright/test";
import { mvpBrowserOptions } from "./tests/mvp_browser/runtime";

export default defineConfig({
  testDir: "tests/mvp_browser",
  outputDir: "test-results/mvp",
  fullyParallel: false,
  workers: 1,
  timeout: 120000,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  use: {
    ...mvpBrowserOptions(),
    trace: "retain-on-failure",
    actionTimeout: 10000,
    navigationTimeout: 20000,
    ...devices["Desktop Chrome"],
  },
});
