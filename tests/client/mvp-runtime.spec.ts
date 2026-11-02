import { expect, test } from "@playwright/test";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { mvpBrowserOptions } from "../mvp_browser/runtime";

test("local smoke tests keep their existing default", () => {
  expect(mvpBrowserOptions({})).toEqual({ baseURL: "http://localhost:3000" });
});

test("remote smoke tests require an exact approved HTTPS quick-tunnel origin and credentials", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "ciq-browser-scope-"));
  const passwordFile = path.join(directory, "credentials.txt");
  writeFileSync(passwordFile, "Username: owner\nPassword: fictional-test-password\n", {
    mode: 0o600,
  });
  const origin = "https://fictional-ciq-preview.trycloudflare.com";
  const approved = {
    MVP_BASE_URL: origin,
    MVP_APPROVED_GCP_ORIGIN: origin,
    MVP_OWNER_PASSWORD_FILE: passwordFile,
  };
  try {
    expect(mvpBrowserOptions(approved)).toEqual({
      baseURL: origin,
      httpCredentials: { username: "owner", password: "fictional-test-password" },
    });
    for (const environment of [
      { ...approved, MVP_APPROVED_GCP_ORIGIN: undefined },
      { ...approved, MVP_OWNER_PASSWORD_FILE: undefined },
      { ...approved, MVP_APPROVED_GCP_ORIGIN: "https://another.trycloudflare.com" },
      { ...approved, MVP_BASE_URL: `${origin}/login` },
      { ...approved, MVP_BASE_URL: `https://owner:password@${new URL(origin).host}` },
      ...[
        "http://fictional-ciq-preview.trycloudflare.com",
        "https://production.example.com",
        "https://fictional-ciq-preview.trycloudflare.com.evil.invalid",
        "https://fictional-ciq-preview.trycloudflare.com:8443",
      ].map((target) => ({
        ...approved,
        MVP_BASE_URL: target,
        MVP_APPROVED_GCP_ORIGIN: target,
      })),
    ]) {
      expect(() => mvpBrowserOptions(environment)).toThrow(/explicitly approved/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
