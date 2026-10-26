import { currentIdentity } from "@/lib/server-api";
import { mvpApi, type Job } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";
import { JobList } from "@/components/workflow-lists";
import { WorkflowFeedback } from "@/components/workflow-feedback";

export default async function Jobs({
  searchParams,
}: {
  searchParams: Promise<{ result?: string; error?: string }>;
}) {
  const [jobs, session] = await Promise.all([mvpApi<{ items: Job[] }>("jobs"), currentIdentity()]);
  if (!jobs || session.state !== "ready") return <CaseServiceError />;
  return (
    <>
      <h1 className="text-3xl font-semibold">Background processing</h1>
      <WorkflowFeedback {...(await searchParams)} />
      <JobList
        items={jobs.items}
        operations={["operations_lead", "tenant_admin"].includes(session.identity.role)}
      />
    </>
  );
}
