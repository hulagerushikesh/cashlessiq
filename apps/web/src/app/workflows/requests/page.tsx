import { WorkflowPagination, listQuery, type PageResult } from "@/components/workflow-pagination";
import Link from "next/link";
import { currentIdentity } from "@/lib/server-api";
import { mvpApi, type RequestSummary } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";
import { RequestList } from "@/components/workflow-lists";

export default async function Requests({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; q?: string }>;
}) {
  const query = listQuery(await searchParams);
  const [requests, session] = await Promise.all([
    mvpApi<PageResult<RequestSummary>>(`requests?${query}`),
    currentIdentity(),
  ]);
  if (!requests || session.state !== "ready") return <CaseServiceError />;
  return (
    <>
      <h1 className="text-3xl font-semibold">Submitted request queue</h1>
      <p className="mt-3 text-sm text-slate-600">
        Open a request to inspect its assessment and use Open reviewer workflow for assignment,
        comments and decisions.
      </p>
      {["processor", "medical_officer"].includes(session.identity.role) && (
        <Link
          href="/workflows/new"
          className="mt-5 inline-block rounded-lg bg-teal-800 px-4 py-3 text-sm text-white"
        >
          Submit a request
        </Link>
      )}
      <WorkflowPagination
        result={requests}
        path="/workflows/requests"
        q={query.get("q") ?? ""}
        label="Search synthetic member reference or request ID"
      />
      <RequestList items={requests.items} />
    </>
  );
}
