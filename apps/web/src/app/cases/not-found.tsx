import Link from "next/link";

export default function CaseNotFound() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-8">
      <h1 className="text-2xl font-semibold">Case not found</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        This request is not available in your workspace. Check the reference or return to the case
        queue.
      </p>
      <Link href="/cases" className="mt-5 inline-block text-sm text-teal-800 underline">
        Back to case queue
      </Link>
    </section>
  );
}
