import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "tests/source_e2e",
  outputDir: "test-results/source",
  forbidOnly: Boolean(process.env.CI),
  fullyParallel: true,
  workers: 3,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3003",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "uv run --project apps/api python tests/source_e2e/server.py",
      url: "http://127.0.0.1:8003/health/ready",
      reuseExistingServer: false,
      timeout: 60000,
      env: { CIQ_SOURCE_E2E: "1" },
      gracefulShutdown: { signal: "SIGTERM", timeout: 10000 },
    },
    {
      command:
        "node node_modules/next/dist/bin/next start apps/web --port 3003 --hostname 127.0.0.1",
      url: "http://127.0.0.1:3003/login",
      reuseExistingServer: false,
      timeout: 60000,
      env: {
        CIQ_ENVIRONMENT: "local",
        CIQ_AUTH_MODE: "local",
        CIQ_SOURCE_UI_MODE: "contract_test",
        CIQ_API_URL: "http://127.0.0.1:8003",
        CIQ_WEB_ORIGIN: "http://localhost:3003",
        CIQ_LOCAL_AUTH_SECRET: "source-e2e-test-key-not-for-any-deployment-0000",
      },
      gracefulShutdown: { signal: "SIGTERM", timeout: 10000 },
    },
  ],
});
