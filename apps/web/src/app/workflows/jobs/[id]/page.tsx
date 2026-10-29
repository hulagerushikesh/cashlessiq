import Link from "next/link";
import { mvpApi, type Job } from "@/lib/mvp-api";
import { currentIdentity } from "@/lib/server-api";
import { CaseServiceError } from "@/components/case-workspace";
import { JobList } from "@/components/workflow-lists";
import { WorkflowFeedback } from "@/components/workflow-feedback";

export default async function JobPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ result?: string; error?: string }>;
}) {
  const { id } = await params;
  const [job, session] = await Promise.all([
    mvpApi<Job>(`jobs/${encodeURIComponent(id)}`),
    currentIdentity(),
  ]);
  if (!job || session.state !== "ready") return <CaseServiceError />;
  const related =
    job.kind === "assessment"
      ? `/workflows/requests/${encodeURIComponent(job.subject_id)}`
      : job.kind === "regression"
        ? `/workflows/policies/${encodeURIComponent(job.subject_id)}`
        : null;
  return (
    <>
      <Link href="/workflows/jobs" className="text-sm text-teal-800 underline">
        Back to background jobs
      </Link>
      <h1 className="mt-5 text-3xl font-semibold">Background job details</h1>
      <p className="mt-3 break-all text-sm text-slate-600">Job {job.id}</p>
      <WorkflowFeedback {...(await searchParams)} />
      {related && (
        <Link href={related} className="mt-3 inline-block text-sm text-teal-800 underline">
          Open related {job.kind === "assessment" ? "request" : "policy"}
        </Link>
      )}
      <JobList
        items={[job]}
        operations={["operations_lead", "tenant_admin"].includes(session.identity.role)}
      />
      <a
        href={`/workflows/jobs/${encodeURIComponent(id)}`}
        className="mt-4 inline-block text-sm text-teal-800 underline"
      >
        Refresh job status
      </a>
    </>
  );
}
