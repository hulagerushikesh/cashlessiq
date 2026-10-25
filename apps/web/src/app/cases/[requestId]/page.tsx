import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, ExternalLink, FileText, LockKeyhole } from "lucide-react";
import { sessionApi } from "@/lib/server-api";
import { caseQueueState, caseQueueUrl } from "@/lib/case-navigation";
import { CaseServiceError, OutcomeBadge, rupees } from "@/components/case-workspace";

export default async function CasePage({
  params,
  searchParams,
}: {
  params: Promise<{ requestId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { requestId } = await params;
  const queueUrl = caseQueueUrl(caseQueueState(await searchParams));
  const api = await sessionApi();
  if (!api) redirect("/login");
  const result = await api
    .GET("/v1/cases/{request_id}", {
      params: { path: { request_id: requestId } },
      signal: AbortSignal.timeout(5000),
    })
    .catch(() => null);
  if (result?.response.status === 401 || result?.response.status === 403) redirect("/login");
  if (result?.response.status === 404) notFound();
  if (!result?.data) return <CaseServiceError />;
  const record = result.data;
  return (
    <>
      <Link href={queueUrl} className="inline-flex items-center gap-2 text-sm text-teal-800">
        <ArrowLeft size={15} />
        Back to case queue
      </Link>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[.15em] text-slate-500">
            Synthetic request
          </p>
          <h1 className="mt-2 text-3xl font-semibold">{record.request_id}</h1>
        </div>
        <OutcomeBadge outcome={record.outcome} />
      </div>
      <p className="mt-3 text-sm text-slate-500">
        Draft recommendation only. Human review is required.
      </p>
      {process.env.CIQ_SYNTHETIC_WORKFLOWS === "true" && (
        <Link
          className="mt-4 inline-block rounded-lg bg-teal-800 px-4 py-2 text-sm text-white"
          href={`/reviews/${encodeURIComponent(requestId)}`}
        >
          Open reviewer workflow
        </Link>
      )}
      <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          <section
            aria-labelledby="context-title"
            className="rounded-xl border border-slate-200 bg-white p-6"
          >
            <h2 id="context-title" className="text-lg font-semibold">
              Request & member context
            </h2>
            <dl className="mt-5 grid gap-5 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-slate-500">Member reference</dt>
                <dd className="mt-1.5 font-medium">{record.member_reference}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Admission date</dt>
                <dd className="mt-1.5">{record.admission_date}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Continuous cover since</dt>
                <dd className="mt-1.5">{record.continuous_cover_since}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Policy</dt>
                <dd className="mt-1.5">
                  {record.policy_id} · {record.policy_version}
                </dd>
              </div>
            </dl>
            <p className="mt-5 border-t border-slate-100 pt-4 text-xs leading-5 text-slate-500">
              No real patient identity or live member history is loaded. All dates and facts belong
              to a fixed synthetic scenario.
            </p>
          </section>
          <section
            aria-labelledby="clinical-title"
            className="rounded-xl border border-slate-200 bg-white p-6"
          >
            <h2 id="clinical-title" className="text-lg font-semibold">
              Clinical narrative
            </h2>
            {record.clinical_visible ? (
              <dl className="mt-4 space-y-4 text-sm">
                <div>
                  <dt className="text-xs text-slate-500">Diagnosis</dt>
                  <dd className="mt-1">{record.diagnosis}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Procedure</dt>
                  <dd className="mt-1">{record.procedure}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Submitted note · Synthetic</dt>
                  <dd className="mt-1 leading-6">{record.clinical_note}</dd>
                </div>
              </dl>
            ) : (
              <p className="mt-4 flex items-start gap-2 text-sm text-slate-500">
                <LockKeyhole size={16} className="shrink-0" />
                Clinical narrative is restricted to the medical-officer role. This restriction does
                not hide financial line-item labels.
              </p>
            )}
          </section>
          <section
            aria-labelledby="calculation-title"
            className="rounded-xl border border-slate-200 bg-white p-6"
          >
            <h2 id="calculation-title" className="text-lg font-semibold">
              Deterministic calculation
            </h2>
            <dl className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 p-4">
                <dt className="text-xs text-slate-500">Claimed / supplied estimate</dt>
                <dd className="mt-2 text-2xl font-semibold">{rupees(record.claimed_inr)}</dd>
              </div>
              <div className="rounded-lg bg-teal-50 p-4">
                <dt className="text-xs text-teal-800">Draft payable</dt>
                <dd className="mt-2 text-2xl font-semibold text-teal-900">
                  {rupees(record.payable_inr)}
                </dd>
              </div>
            </dl>
            {record.lines.length === 0 ? (
              <p className="mt-5 text-sm leading-6 text-slate-600">
                No payable calculation exists for this query or referral. “Not calculated” does not
                mean zero.
              </p>
            ) : (
              <div className="mt-5 space-y-4">
                {record.lines.map((line) => (
                  <article key={line.item} className="border-t border-slate-100 pt-4">
                    <h3 className="font-medium">{line.item}</h3>
                    <p className="mt-2 text-sm text-slate-600">
                      Claimed {rupees(line.claimed_inr)} · Deduction {rupees(line.deduction_inr)} ·
                      Payable {rupees(line.payable_inr)}
                    </p>
                    <p className="mt-2 break-words rounded-lg bg-slate-50 p-3 font-mono text-xs leading-6">
                      {line.calc}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{line.reason}</p>
                    <div className="mt-2 flex flex-wrap gap-3">
                      {line.citations.map((citation) => (
                        <a
                          key={citation.id}
                          href={`#${citation.id}`}
                          className="text-xs text-teal-800 underline"
                        >
                          {citation.id}
                        </a>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
          {(record.queries.length > 0 || record.refer_reasons.length > 0) && (
            <section className="rounded-xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-lg font-semibold">
                {record.queries.length > 0 ? "Missing information" : "Referral reason"}
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6">
                {[...record.queries, ...record.refer_reasons].map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </section>
          )}
          <section className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold">Policy checks</h2>
            {record.checks.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">
                Checks were not run because required information is missing.
              </p>
            ) : (
              <ul className="mt-4 divide-y divide-slate-100">
                {record.checks.map((check) => (
                  <li key={check.rule_id} className="py-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-medium">{check.rule_type.replaceAll("_", " ")}</span>
                      <a href={`#${check.clause_id}`} className="text-xs text-teal-800 underline">
                        {check.clause_id}
                      </a>
                    </div>
                    <p className="mt-2 leading-6 text-slate-500">{check.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <aside className="min-w-0 space-y-5" aria-label="Evidence and provenance">
          <section className="rounded-xl border border-slate-200 bg-white p-6">
            <div className="flex items-center gap-2">
              <FileText size={19} className="text-teal-700" />
              <h2 className="text-lg font-semibold">Policy evidence</h2>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              Source references, not retrieved clause quotations. Page numbers follow the existing
              policy register and should be verified against the PDF.
            </p>
            <p className="mt-4 text-sm font-medium leading-6">{record.product_name}</p>
            <div className="mt-4 space-y-4">
              {record.evidence.map((evidence) => (
                <article
                  id={evidence.clause_id}
                  key={evidence.clause_id}
                  className="scroll-mt-6 rounded-lg border border-slate-200 p-4"
                >
                  <p className="text-xs font-semibold text-teal-800">{evidence.clause_id}</p>
                  <h3 className="mt-2 text-sm font-medium">{evidence.title}</h3>
                  <a
                    href={`${evidence.source_url}#page=${evidence.page}`}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-2 text-xs text-teal-800 underline"
                  >
                    Source PDF · page {evidence.page}
                    <ExternalLink size={12} />
                  </a>
                </article>
              ))}
            </div>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="font-semibold">Snapshot provenance</h2>
            <dl className="mt-4 space-y-3 text-xs text-slate-500">
              <div>
                <dt>Data source</dt>
                <dd className="mt-1 text-slate-800">Frozen golden result · No live AI</dd>
              </div>
              <div>
                <dt>Baseline commit</dt>
                <dd className="mt-1 font-mono text-slate-800">{record.baseline_commit}</dd>
              </div>
              <div>
                <dt>Workflow</dt>
                <dd className="mt-1 text-slate-800">Draft ready · Read-only</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
    </>
  );
}
