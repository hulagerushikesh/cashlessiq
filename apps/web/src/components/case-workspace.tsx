import Link from "next/link";
import { ArrowLeft, Layers3, LockKeyhole } from "lucide-react";
import type { ReactNode } from "react";
import type { Identity, Outcome } from "@cashlessiq/api-client";
import { roleLabels } from "@/lib/workflow-roles";
import { WorkflowNavigation } from "@/components/workflow-navigation";
import { Button } from "@/components/ui/button";

export const outcomeLabels: Record<Outcome, string> = {
  APPROVE: "Approval draft",
  APPROVE_WITH_DEDUCTIONS: "Deductions draft",
  QUERY: "Information needed",
  REFER: "Medical referral",
};

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const colour =
    outcome === "QUERY"
      ? "bg-amber-50 text-amber-900 border-amber-200"
      : outcome === "REFER"
        ? "bg-indigo-50 text-indigo-900 border-indigo-200"
        : "bg-teal-50 text-teal-900 border-teal-200";
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${colour}`}>
      {outcomeLabels[outcome]}
    </span>
  );
}

export function rupees(amount: number | null) {
  return amount === null
    ? "Not calculated"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(amount);
}

export function CaseWorkspace({ identity, children }: { identity: Identity; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <a
        href="#case-workspace"
        className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-white focus:p-4"
      >
        Skip to cases
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-4 px-5 py-5 lg:px-9">
          <Link href="/" className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Layers3 className="text-teal-800" size={24} />
            CashlessIQ
          </Link>
          <nav
            aria-label="Workspace navigation"
            className="flex flex-wrap items-center gap-5 text-sm"
          >
            <Link href="/">Overview</Link>
            <Link href="/cases" className="font-semibold text-teal-800">
              Case queue
            </Link>
            {process.env.CIQ_ENVIRONMENT === "local" && process.env.CIQ_AUTH_MODE === "local" && (
              <Link href="/source-preview">UI preview</Link>
            )}
            {process.env.CIQ_ENVIRONMENT === "local" &&
              process.env.CIQ_AUTH_MODE === "local" &&
              process.env.CIQ_SOURCE_UI_MODE === "contract_test" && (
                <Link href="/source-cases">Source contract test</Link>
              )}
          </nav>
          <div className="flex items-center gap-4 text-sm">
            <span>
              {identity.user.display_name}
              <span className="block text-xs text-slate-500">{roleLabels[identity.role]}</span>
            </span>
            <form action="/auth/logout" method="post">
              <Button variant="outline" size="sm">
                Sign out
              </Button>
            </form>
          </div>
        </div>
        {process.env.CIQ_SYNTHETIC_WORKFLOWS === "true" && (
          <WorkflowNavigation role={identity.role} />
        )}
      </header>
      <main id="case-workspace" className="mx-auto max-w-[1480px] px-5 py-7 lg:px-9 lg:py-10">
        <div className="mb-7 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <span>{identity.tenant.name}</span>
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
            <LockKeyhole size={13} />
            {process.env.CIQ_SYNTHETIC_WORKFLOWS === "true"
              ? "Synthetic MVP · Human review required"
              : "Synthetic alpha · Read-only · No live assessment"}
          </span>
        </div>
        {children}
      </main>
    </div>
  );
}

export function CaseServiceError() {
  return (
    <section role="alert" className="rounded-xl border border-amber-200 bg-white p-8">
      <h1 className="text-xl font-semibold">Case service unavailable</h1>
      <p className="mt-3 text-sm text-slate-600">
        We could not load case data. No recommendation or action was saved. Refresh to try again.
      </p>
      <Link href="/" className="mt-5 inline-flex items-center gap-2 text-sm text-teal-800">
        <ArrowLeft size={15} />
        Back to overview
      </Link>
    </section>
  );
}
