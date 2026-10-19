"use client";

import { useState } from "react";
import { ExternalLink, FileText, Search } from "lucide-react";
import type { SourceCaseDetail } from "@cashlessiq/api-client";

/** Filters supplied reference metadata only. Does not retrieve or rank evidence. */
export function SourceClauseRegister({
  productName,
  clauses,
}: {
  productName: string;
  clauses: SourceCaseDetail["evidence"];
}) {
  const [search, setSearch] = useState("");
  const query = search.trim().toLowerCase();
  const visible = clauses.filter((clause) =>
    `${clause.clause_id} ${clause.title}`.toLowerCase().includes(query),
  );
  return (
    <section
      aria-labelledby="clause-register-title"
      className="rounded-xl border border-slate-200 bg-white p-6"
    >
      <h2 id="clause-register-title" className="flex items-center gap-2 text-lg font-semibold">
        <FileText size={19} aria-hidden="true" /> Product clause register
      </h2>
      <p className="mt-3 text-sm text-slate-600">{productName}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        Reference metadata, not retrieved quotations or proof that every clause supports this
        recommendation. Verify page references against the policy PDF. Filtering is text matching,
        not relevance ranking.
      </p>
      {clauses.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">No clause references returned.</p>
      ) : (
        <>
          <label htmlFor="clause-search" className="mt-5 block text-sm font-medium">
            Find a clause by ID or title
          </label>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <div className="relative min-w-0 flex-1 basis-56">
              <Search
                size={16}
                aria-hidden="true"
                className="absolute left-3 top-3 text-slate-500"
              />
              <input
                id="clause-search"
                type="search"
                maxLength={80}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus-visible:outline-2 focus-visible:outline-teal-700"
                placeholder="e.g. co-pay"
              />
            </div>
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="rounded-lg px-3 py-2 text-sm text-teal-800 underline focus-visible:outline-2"
              >
                Clear filter
              </button>
            )}
          </div>
          <p role="status" className="mt-3 text-xs text-slate-500">
            Showing {visible.length} of {clauses.length} clause references
          </p>
          {visible.length === 0 && (
            <p className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              No matching references. Clear the filter to see the register; this does not mean a
              policy clause is absent or a benefit is covered.
            </p>
          )}
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {visible.map((clause) => (
              <article
                key={clause.clause_id}
                className="min-w-0 rounded-lg border border-slate-200 p-4"
              >
                <h3 className="break-words text-sm font-medium">
                  {clause.clause_id} · {clause.title}
                </h3>
                <a
                  href={`${clause.source_url.split("#")[0]}#page=${clause.page}`}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`${clause.clause_id}: source PDF, page ${clause.page} (opens in new tab)`}
                  className="mt-3 inline-flex items-center gap-2 text-xs text-teal-800 underline"
                >
                  Source PDF · page {clause.page} <ExternalLink size={12} aria-hidden="true" />
                </a>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
