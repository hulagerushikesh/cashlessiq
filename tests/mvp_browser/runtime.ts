import { readFileSync } from "node:fs";

export function mvpBrowserOptions(environment = process.env) {
  const baseURL = environment.MVP_BASE_URL ?? "http://localhost:3000";
  const url = new URL(baseURL);
  const passwordFile = environment.MVP_OWNER_PASSWORD_FILE;
  const previewHost =
    url.hostname === "cashlessiq-test.hulage.in" ||
    /^[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com$/.test(url.hostname);
  if (
    !["localhost", "127.0.0.1"].includes(url.hostname) &&
    (environment.MVP_APPROVED_GCP_ORIGIN !== url.origin ||
      baseURL !== url.origin ||
      url.protocol !== "https:" ||
      url.port !== "" ||
      !previewHost ||
      !passwordFile)
  ) {
    throw new Error(
      "MVP smoke tests require localhost or an explicitly approved, password-protected GCP preview origin",
    );
  }
  if (!passwordFile) return { baseURL };
  const password = readFileSync(passwordFile, "utf8").split("Password: ")[1]?.trim();
  if (!password) throw new Error("Disposable owner credentials are unavailable");
  return { baseURL, httpCredentials: { username: "owner", password } };
}
