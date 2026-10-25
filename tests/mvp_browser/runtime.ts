import { readFileSync } from "node:fs";

export function mvpBrowserOptions() {
  const baseURL = process.env.MVP_BASE_URL ?? "http://localhost:3000";
  const url = new URL(baseURL);
  if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
    throw new Error("MVP smoke tests require an explicitly local synthetic workspace");
  }
  const passwordFile = process.env.MVP_OWNER_PASSWORD_FILE;
  if (!passwordFile) return { baseURL };
  const password = readFileSync(passwordFile, "utf8").split("Password: ")[1]?.trim();
  if (!password) throw new Error("Disposable owner credentials are unavailable");
  return { baseURL, httpCredentials: { username: "owner", password } };
}
