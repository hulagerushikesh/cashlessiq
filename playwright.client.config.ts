import { defineConfig } from "@playwright/test";

// Pure client and test-scope checks; no browser, server or real credentials.
export default defineConfig({
  testDir: "tests/client",
  outputDir: "test-results/client",
  forbidOnly: Boolean(process.env.CI),
  reporter: "list",
});
