import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { readSourceCase } from "@cashlessiq/api-client/source";
import { SourceCaseView, SourceUnavailable } from "@/components/source-case-detail";
import { currentIdentity, sessionApi } from "@/lib/server-api";
import { requireSourceContractMode } from "@/lib/source-workspace";

export default async function SourceCase({ params }: { params: Promise<{ requestId: string }> }) {
  requireSourceContractMode();
  const session = await currentIdentity();
  if (session.state === "anonymous") redirect("/login");
  if (session.state !== "ready") return <SourceUnavailable />;
  const api = await sessionApi();
  if (!api) redirect("/login");
  const { requestId } = await params;
  const result = await readSourceCase(api, session.identity, requestId);
  if (result.state === "anonymous") redirect("/login");
  if (result.state === "forbidden") return <p role="alert">Source case access is not permitted.</p>;
  if (result.state === "not_found") notFound();
  return (
    <div className="space-y-6">
      <Link href="/source-cases" className="text-sm text-teal-800 underline">
        Back to source queue
      </Link>
      {result.state === "ready" ? <SourceCaseView record={result.data} /> : <SourceUnavailable />}
    </div>
  );
}
