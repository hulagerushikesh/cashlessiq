import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { currentIdentity } from "@/lib/server-api";
import { CaseServiceError, CaseWorkspace } from "@/components/case-workspace";

export default async function CasesLayout({ children }: { children: ReactNode }) {
  const session = await currentIdentity();
  if (session.state === "anonymous") redirect("/login");
  if (session.state !== "ready")
    return (
      <main className="mx-auto max-w-3xl p-8">
        <CaseServiceError />
      </main>
    );
  return <CaseWorkspace identity={session.identity}>{children}</CaseWorkspace>;
}
