import Link from "next/link";
import { currentIdentity } from "@/lib/server-api";
import { mvpApi, type RequestSummary } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";
import { RequestList } from "@/components/workflow-lists";
import { WorkflowFeedback } from "@/components/workflow-feedback";
import { roleLabels } from "@/lib/workflow-roles";

export default async function Workflows({
  searchParams,
}: {
  searchParams: Promise<{ result?: string; error?: string }>;
}) {
  const session = await currentIdentity();
  const requests = await mvpApi<{ items: RequestSummary[] }>("requests");
  if (session.state !== "ready" || !requests) return <CaseServiceError />;
  const feedback = await searchParams;
  const role = session.identity.role;
  const guidance = {
    processor:
      "Submit fictional requests, track their assessments and work with a medical officer on the final decision.",
    medical_officer:
      "Open a submitted request, review its calculation, assign it to yourself and record your decision or request more information.",
    policy_analyst:
      "Create a policy proposal and check its regression results. A policy approver must separately approve and activate it.",
    policy_approver:
      "Open the policy library, inspect a proposal and its regression results, approve it, then activate it. Approval and activation are separate steps.",
    auditor:
      "Inspect submitted requests, reviewer audit history and governance events. Your role cannot change decisions.",
    operations_lead:
      "Track background jobs, retry failed processing with a reason, and assign reviews.",
    tenant_admin: "Manage tenant access and inspect governance history and background processing.",
  };
  const cards = [
    ...(["processor", "medical_officer"].includes(role)
      ? [
          {
            href: "/workflows/new",
            title: "New request",
            text: "Submit fictional facts using an active policy.",
          },
        ]
      : []),
    ...(role === "policy_analyst"
      ? [
          {
            href: "/workflows/policies/new",
            title: "New policy",
            text: "Propose a version and run its regression checks.",
          },
        ]
      : []),
    {
      href: "/workflows/policies",
      title: "Policy library",
      text: "See proposals, review decisions and activation status.",
    },
    {
      href: "/workflows/requests",
      title: "Submitted requests",
      text: "Open an assessment, supporting documents and its reviewer workflow.",
    },
    {
      href: "/workflows/jobs",
      title: "Background jobs",
      text: "Follow assessments, policy checks and document extraction.",
    },
  ];
  return (
    <>
      <h1 className="text-3xl font-semibold">Testing workspace</h1>
      <p className="mt-3 text-sm text-slate-600">
        Signed in as {roleLabels[role]}. {guidance[role]}
      </p>
      <p className="mt-3 text-sm text-slate-500">
        To test another role, use Sign out and choose that role on the sign-in screen. Use fictional
        data only.
      </p>
      <WorkflowFeedback {...feedback} />
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="rounded-xl border border-slate-200 bg-white p-5 hover:border-teal-600"
          >
            <h2 className="font-semibold text-teal-800">{c.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{c.text}</p>
          </Link>
        ))}
      </div>
      <RequestList items={requests.items.slice(0, 5)} />
      <Link
        href="/workflows/requests"
        className="mt-4 inline-block text-sm text-teal-800 underline"
      >
        View submitted request queue
      </Link>
    </>
  );
}
