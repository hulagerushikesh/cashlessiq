import "server-only";
import { notFound } from "next/navigation";

/** Test harness only until the live-source security gate is approved. */
export function requireSourceContractMode() {
  if (
    process.env.CIQ_ENVIRONMENT !== "local" ||
    process.env.CIQ_AUTH_MODE !== "local" ||
    process.env.CIQ_SOURCE_UI_MODE !== "contract_test"
  )
    notFound();
}
