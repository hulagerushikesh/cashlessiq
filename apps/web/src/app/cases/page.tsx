import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight, Search } from "lucide-react";
import type { Outcome } from "@cashlessiq/api-client";
import { sessionApi } from "@/lib/server-api";
import { CaseServiceError, OutcomeBadge, outcomeLabels, rupees } from "@/components/case-workspace";
import { Button } from "@/components/ui/button";

export default async function Cases({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const search = typeof params.search === "string" ? params.search.slice(0, 80) : "";
  const outcome =
    typeof params.outcome === "string" && Object.hasOwn(outcomeLabels, params.outcome)
      ? (params.outcome as Outcome)
      : undefined;
  const parsed = Number(params.page ?? 1);
  const page = Number.isInteger(parsed) && parsed > 0 && parsed <= 10000 ? parsed : 1;
  const api = await sessionApi();
  if (!api) redirect("/login");
  const result = await api
    .GET("/v1/cases", {
      params: { query: { search, outcome, page, page_size: 20 } },
      signal: AbortSignal.timeout(5000),
    })
    .catch(() => null);
  if (result?.response.status === 401 || result?.response.status === 403) redirect("/login");
  if (!result?.data) return <CaseServiceError />;
  const data = result.data;
  const pageUrl = (next: number) =>
    `/cases?${new URLSearchParams({ search, ...(outcome ? { outcome } : {}), page: String(next) })}`;
  return (
    <>
      <p className="text-xs font-semibold uppercase tracking-[.16em] text-teal-700">
        Review operations
      </p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Case queue</h1>
          <p className="mt-3 text-sm text-slate-500">
            Inspect a request, follow its calculation, and verify the evidence.
          </p>
        </div>
        <p className="text-sm text-slate-500">{data.total} matching synthetic cases</p>
      </div>
      <div className="mt-6 rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm leading-6 text-slate-600">
        Fixed golden snapshots, not a live operational queue. Assignment, SLA clocks, uploads and
        final actions are not active.
      </div>
      <form
        action="/cases"
        className="mt-7 flex flex-wrap items-end gap-4 rounded-t-xl border border-slate-200 bg-white p-5"
      >
        <label className="min-w-0 flex-1 text-xs font-medium text-slate-600">
          Request or member reference
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-slate-300 px-3">
            <Search size={16} />
            <input
              name="search"
              defaultValue={search}
              maxLength={80}
              placeholder="Search GOL001 or SYN-GOL001"
              className="min-w-0 w-full bg-transparent py-2.5 text-sm outline-offset-4"
            />
          </div>
        </label>
        <label className="text-xs font-medium text-slate-600">
          Recommendation
          <select
            name="outcome"
            defaultValue={outcome ?? ""}
            className="mt-2 block max-w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
          >
            <option value="">All recommendations</option>
            {Object.entries(outcomeLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit">Apply filters</Button>
        <Link href="/cases" className="py-2.5 text-sm text-slate-600 underline">
          Reset
        </Link>
      </form>
      <section
        aria-label="Case results"
        className="overflow-hidden rounded-b-xl border-x border-b border-slate-200 bg-white"
      >
        {data.items.length === 0 ? (
          <div className="p-10 text-center">
            <h2 className="font-semibold">No matching cases</h2>
            <p className="mt-2 text-sm text-slate-500">
              Change the reference or reset your filters.
            </p>
          </div>
        ) : (
          data.items.map((item) => (
            <Link
              key={item.request_id}
              href={`/cases/${item.request_id}`}
              className="grid gap-4 border-t border-slate-100 p-5 transition-colors hover:bg-teal-50/40 focus-visible:outline-2 focus-visible:outline-teal-700 md:grid-cols-[1.1fr_1fr_1fr_auto] md:items-center"
              aria-label={`Open ${item.request_id}`}
            >
              <div>
                <p className="font-semibold text-slate-900">{item.request_id}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {item.member_reference} · Admission {item.admission_date}
                </p>
              </div>
              <div>
                <OutcomeBadge outcome={item.outcome} />
                <p className="mt-2 text-xs text-slate-500">Draft ready · Not a final decision</p>
              </div>
              <dl className="grid grid-cols-2 gap-5 text-sm">
                <div>
                  <dt className="text-xs text-slate-500">Claimed / estimate</dt>
                  <dd className="mt-1 font-medium">{rupees(item.claimed_inr)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Draft payable</dt>
                  <dd className="mt-1 font-medium">{rupees(item.payable_inr)}</dd>
                </div>
              </dl>
              <ArrowRight size={18} className="text-teal-700" />
            </Link>
          ))
        )}
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-4 text-xs text-slate-500">
          <span>
            Page {data.page} · {data.page_size} per page
          </span>
          <div className="flex gap-5">
            {page > 1 && (
              <Link href={pageUrl(page - 1)} className="text-teal-800 underline">
                Previous
              </Link>
            )}
            {page * data.page_size < data.total && (
              <Link href={pageUrl(page + 1)} className="text-teal-800 underline">
                Next
              </Link>
            )}
          </div>
        </footer>
      </section>
    </>
  );
}
