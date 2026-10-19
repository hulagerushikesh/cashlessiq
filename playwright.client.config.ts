import { defineConfig } from "@playwright/test";

// Pure HTTP-client tests use an injected fetch; no browser, server or credentials.
export default defineConfig({
  testDir: "tests/client",
  forbidOnly: Boolean(process.env.CI),
  reporter: "list",
});
