import Link from "next/link";

export type PageResult<T> = { items: T[]; total: number; page: number; page_size: number };

export function listQuery(query: { page?: string; q?: string }) {
  const rawPage = Number(query.page);
  const page = Number.isSafeInteger(rawPage) && rawPage >= 1 && rawPage <= 10000 ? rawPage : 1;
  const q = (typeof query.q === "string" ? query.q : "").trim().slice(0, 120);
  return new URLSearchParams({ page: String(page), page_size: "20", ...(q ? { q } : {}) });
}

export function WorkflowPagination({
  result,
  path,
  q = "",
  label,
}: {
  result: Omit<PageResult<unknown>, "items">;
  path: string;
  q?: string;
  label: string;
}) {
  const pages = Math.max(1, Math.ceil(result.total / result.page_size));
  const link = (page: number) =>
    `${path}?${new URLSearchParams({ page: String(page), ...(q ? { q } : {}) })}`;
  return (
    <div className="mt-5 space-y-4">
      <form action={path} method="get" className="flex flex-wrap items-end gap-3">
        <label className="min-w-0 grow text-sm">
          {label}
          <input
            name="q"
            defaultValue={q}
            maxLength={120}
            className="mt-1 block w-full rounded border bg-white p-2"
          />
        </label>
        <button type="submit" className="rounded border bg-white px-4 py-2 text-sm">
          Search
        </button>
        {q && (
          <Link href={path} className="p-2 text-sm text-teal-800 underline">
            Clear search
          </Link>
        )}
      </form>
      <nav aria-label="List pagination" className="flex flex-wrap items-center gap-4 text-sm">
        <p>
          {result.total} results · Page {result.page} of {pages}
        </p>
        {result.page > 1 && (
          <Link href={link(result.page - 1)} className="text-teal-800 underline">
            Previous page
          </Link>
        )}
        {result.page < pages && (
          <Link href={link(result.page + 1)} className="text-teal-800 underline">
            Next page
          </Link>
        )}
        {result.page > pages && (
          <Link href={link(1)} className="text-teal-800 underline">
            Return to first page
          </Link>
        )}
      </nav>
    </div>
  );
}
