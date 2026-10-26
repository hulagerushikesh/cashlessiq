import Link from "next/link";
import { currentIdentity } from "@/lib/server-api";
import { mvpApi, type Policy } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";
import { PolicyList } from "@/components/workflow-lists";

export default async function Policies() {
  const [policies, session] = await Promise.all([
    mvpApi<{ items: Policy[] }>("policies"),
    currentIdentity(),
  ]);
  if (!policies || session.state !== "ready") return <CaseServiceError />;
  return (
    <>
      <h1 className="text-3xl font-semibold">Policy library</h1>
      <p className="mt-3 text-sm text-slate-600">
        A policy analyst proposes a version. A different policy approver reviews it, approves it,
        then activates it. Only active policies are available for new requests.
      </p>
      {session.identity.role === "policy_analyst" && (
        <Link
          href="/workflows/policies/new"
          className="mt-5 inline-block rounded-lg bg-teal-800 px-4 py-3 text-sm text-white"
        >
          Propose a policy version
        </Link>
      )}
      <PolicyList items={policies.items} />
    </>
  );
}
