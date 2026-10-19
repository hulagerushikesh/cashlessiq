import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { CaseServiceError, CaseWorkspace } from "@/components/case-workspace";
import { currentIdentity } from "@/lib/server-api";
import { requireSourceContractMode } from "@/lib/source-workspace";

export const dynamic = "force-dynamic";

export default async function SourceLayout({ children }: { children: ReactNode }) {
  requireSourceContractMode();
  const session = await currentIdentity();
  if (session.state === "anonymous") redirect("/login");
  if (session.state !== "ready") return <CaseServiceError />;
  return (
    <CaseWorkspace identity={session.identity}>
      <div className="mb-7 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <p className="font-semibold">Offline source contract test · Fake gateways</p>
        <p className="mt-2 text-sm leading-6">
          Real API and test-database memberships, but fictional source responses. No Snowflake
          connection, live-source parity, database tenant isolation or policy-grounding claim. No
          reviewer actions are enabled. PDF links are placeholders.
        </p>
      </div>
      {children}
    </CaseWorkspace>
  );
}
