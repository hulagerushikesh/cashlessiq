import Link from "next/link";
import { redirect } from "next/navigation";
import { readSourceQueue } from "@cashlessiq/api-client/source";
import { rupees } from "@/components/case-workspace";
import { SourceUnavailable } from "@/components/source-case-detail";
import { currentIdentity, sessionApi } from "@/lib/server-api";
import { requireSourceContractMode } from "@/lib/source-workspace";

export default async function SourceQueue({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  requireSourceContractMode();
  const session = await currentIdentity();
  if (session.state === "anonymous") redirect("/login");
  if (session.state !== "ready") return <SourceUnavailable />;
  const api = await sessionApi();
  if (!api) redirect("/login");
  const params = await searchParams;
  const search = typeof params.search === "string" ? params.search.slice(0, 80) : "";
  const parsed = Number(params.page ?? 1);
  const page = Number.isInteger(parsed) && parsed > 0 && parsed <= 10000 ? parsed : 1;
  const result = await readSourceQueue(api, session.identity, { search, page, page_size: 20 });
  if (result.state === "anonymous") redirect("/login");
  if (result.state === "forbidden") return <p role="alert">Source case access is not permitted.</p>;
  if (result.state !== "ready") return <SourceUnavailable />;
  const data = result.data;
  const pageUrl = (next: number) =>
    `/source-cases?${new URLSearchParams({ search, page: String(next) })}`;
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Source case queue</h1>
      <p className="text-sm leading-6 text-slate-600">
        Metadata only · Recommendations are not loaded in this queue. Open a case to check its saved
        recommendation. A listed request does not imply an assessment exists.
      </p>
      <form
        action="/source-cases"
        className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-5"
      >
        <label className="min-w-0 flex-1 text-sm font-medium">
          Request reference
          <input
            name="search"
            defaultValue={search}
            maxLength={80}
            className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
        <button type="submit" className="rounded-lg bg-teal-800 px-4 py-2 text-sm text-white">
          Apply filter
        </button>
        <Link href="/source-cases" className="py-2 text-sm text-teal-800 underline">
          Reset
        </Link>
      </form>
      <section
        aria-label="Source case results"
        className="rounded-xl border border-slate-200 bg-white"
      >
        <p className="border-b border-slate-200 p-5 text-sm text-slate-600">
          {data.total} matching requests
        </p>
        {data.items.length === 0 ? (
          <div className="p-6">
            <h2 className="font-semibold">No matching source requests</h2>
            <p className="mt-2 text-sm text-slate-500">
              This scoped read succeeded. Reset the filter to check available requests.
            </p>
          </div>
        ) : (
          data.items.map((item) => (
            <Link
              key={item.request_id}
              href={`/source-cases/${encodeURIComponent(item.request_id)}`}
              aria-label={`Inspect ${item.request_id}`}
              className="grid gap-3 border-b border-slate-100 p-5 hover:bg-teal-50/40 sm:grid-cols-3"
            >
              <div className="min-w-0">
                <p className="break-words font-semibold">{item.request_id}</p>
                <p className="mt-2 break-words text-xs text-slate-500">
                  {item.policy_id} · {item.policy_version}
                </p>
              </div>
              <p className="text-sm text-slate-600">Admission {item.admission_date}</p>
              <dl className="text-sm">
                <dt className="text-xs text-slate-500">Supplied estimate · Not draft payable</dt>
                <dd className="mt-2 font-medium">{rupees(item.estimated_total_inr)}</dd>
              </dl>
            </Link>
          ))
        )}
        <footer className="flex flex-wrap justify-between gap-4 p-5 text-sm text-slate-600">
          <span>Page {data.page}</span>
          <div className="flex gap-4">
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
    </div>
  );
}
