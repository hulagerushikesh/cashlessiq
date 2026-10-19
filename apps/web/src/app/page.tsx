import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CircleDot,
  ClipboardCheck,
  FileCheck2,
  Fingerprint,
  Layers3,
  LayoutDashboard,
  LockKeyhole,
  PanelLeft,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { currentIdentity } from "@/lib/server-api";

const roles = { processor: "Processor", medical_officer: "Medical officer", auditor: "Auditor" };

export default async function Workspace() {
  const session = await currentIdentity();
  const identity = session.state === "ready" ? session.identity : null;
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[236px_1fr]">
      <a
        href="#workspace"
        className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-white focus:p-4"
      >
        Skip to workspace
      </a>
      <aside className="flex flex-col border-r border-slate-200 bg-white p-5 lg:min-h-screen">
        <Link
          href="/"
          className="flex items-center gap-2.5 px-2 py-3 text-xl font-semibold tracking-tight"
          aria-label="CashlessIQ home"
        >
          <span className="grid size-9 place-items-center rounded-xl bg-teal-800 text-white">
            <Layers3 size={20} />
          </span>
          Cashless<span className="-ml-2 text-teal-700">IQ</span>
        </Link>
        <div className="mt-8 hidden rounded-xl border border-slate-200 p-3 lg:block">
          <p className="text-[10px] font-bold tracking-[.15em] text-slate-400">YOUR ORGANISATION</p>
          <p className="mt-2 text-sm font-semibold">
            {identity ? identity.tenant.name.split(" · ")[0] : "Review workspace"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {identity ? "Synthetic sandbox" : "Sign in to your workspace"}
          </p>
        </div>
        <nav aria-label="Main navigation" className="mt-7 hidden space-y-2 text-sm lg:block">
          <Link
            href="/"
            aria-current="page"
            className="flex items-center gap-3 rounded-lg bg-teal-50 px-3 py-3 font-medium text-teal-900"
          >
            <LayoutDashboard size={18} /> Overview
          </Link>
          {[
            { title: "Case queue", icon: ClipboardCheck },
            { title: "Policy library", icon: BookOpen },
            { title: "Audit history", icon: ShieldCheck },
          ].map(({ title, icon: Icon }) => (
            <div
              key={title}
              className="flex items-center gap-3 px-3 py-3 text-slate-400"
              aria-disabled="true"
            >
              <Icon size={18} />
              <span>{title}</span>
              <LockKeyhole className="ml-auto" size={12} />
            </div>
          ))}
        </nav>
        <div className="mt-8 hidden border-t border-slate-100 px-2 pt-5 lg:mt-auto lg:block">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-800">
            <CircleDot size={11} /> Development workspace
          </span>
          <p className="mt-3 text-xs leading-5 text-slate-500">
            Synthetic identities. Human review at every final decision.
          </p>
        </div>
      </aside>
      <div>
        <header className="flex min-h-20 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 lg:px-10">
          <div className="flex items-center gap-3 text-sm">
            <PanelLeft size={17} className="text-slate-400" />
            <span className="text-slate-400">Workspace</span>
            <span className="text-slate-300">/</span>
            <span className="font-medium">Overview</span>
          </div>
          <div className="flex items-center gap-3">
            {identity ? (
              <>
                <span className="grid size-9 place-items-center rounded-full bg-teal-50 text-xs font-bold text-teal-800">
                  {identity.user.display_name
                    .split(" ")
                    .map((part) => part[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <div>
                  <p className="text-sm font-semibold" data-testid="signed-in-name">
                    {identity.user.display_name}
                  </p>
                  <p className="text-xs text-slate-500">{roles[identity.role]}</p>
                </div>
                <form action="/auth/logout" method="post">
                  <Button variant="ghost" size="sm">
                    Sign out
                  </Button>
                </form>
              </>
            ) : (
              <Button asChild variant="outline" size="sm">
                <Link href="/login">
                  Sign in <ArrowUpRight size={14} />
                </Link>
              </Button>
            )}
          </div>
        </header>
        <main id="workspace" className="mx-auto max-w-[1320px] px-6 py-10 lg:px-10 lg:py-12">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[.17em] text-teal-700">
                The review workspace
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight lg:text-4xl">
                Clarity before every decision.
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
                One place for the request, the policy and the evidence behind your recommendation.
              </p>
            </div>
            <span className="mt-2 flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
              <span className="size-1.5 rounded-full bg-teal-600" /> Product foundation
            </span>
          </div>
          {session.state === "unavailable" && (
            <div
              role="alert"
              className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
            >
              Your session could not be checked. The workspace service may be unavailable. Please
              refresh to try again.
            </div>
          )}
          <section
            className="mt-9 overflow-hidden rounded-2xl border border-slate-200 bg-white lg:grid lg:grid-cols-[1.45fr_1fr]"
            aria-labelledby="welcome-title"
          >
            <div className="p-7 lg:p-9">
              <div className="mb-6 flex size-11 items-center justify-center rounded-xl bg-teal-50 text-teal-800">
                <Fingerprint size={23} />
              </div>
              <h2 id="welcome-title" className="text-2xl font-semibold tracking-tight">
                {identity
                  ? `Welcome, ${identity.user.display_name.split(" ")[0]}.`
                  : "Your workspace starts with you."}
              </h2>
              <p className="mt-3 max-w-md text-sm leading-7 text-slate-500">
                {identity
                  ? "Your organisation and role are verified. This foundation connects your workspace to a governed identity before case review is introduced."
                  : "Enter the synthetic sandbox to explore the workspace as a processor, medical officer or auditor."}
              </p>
              <div className="mt-7">
                {identity ? (
                  <div
                    className="inline-flex items-center gap-2 rounded-lg bg-teal-50 px-4 py-3 text-sm font-medium text-teal-900"
                    data-testid="identity-verified"
                  >
                    <Check size={17} /> Identity and organisation verified
                  </div>
                ) : (
                  <Button asChild>
                    <Link href="/login">
                      Enter the workspace <ArrowRight size={16} />
                    </Link>
                  </Button>
                )}
              </div>
            </div>
            <div className="border-t border-slate-100 bg-slate-50/70 p-7 lg:border-l lg:border-t-0 lg:p-9">
              <p className="text-[10px] font-semibold tracking-[.16em] text-slate-400">
                WORKSPACE ACCESS
              </p>
              <dl className="mt-6 space-y-5 text-sm">
                <div>
                  <dt className="text-xs text-slate-500">Organisation</dt>
                  <dd className="mt-1.5 font-medium" data-testid="tenant-name">
                    {identity?.tenant.name ?? "Available after sign-in"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Your role</dt>
                  <dd className="mt-1.5 font-medium" data-testid="identity-role">
                    {identity ? roles[identity.role] : "Not signed in"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Data environment</dt>
                  <dd className="mt-1.5 font-medium">Synthetic sandbox</dd>
                </div>
              </dl>
            </div>
          </section>
          <section className="mt-7 grid gap-4 md:grid-cols-3" aria-label="Review principles">
            {[
              {
                icon: FileCheck2,
                title: "Evidence in context",
                text: "Connect every recommendation to the policy wording and source record.",
              },
              {
                icon: ShieldCheck,
                title: "A traceable calculation",
                text: "Follow every deduction and payable amount through a deterministic rule.",
              },
              {
                icon: ClipboardCheck,
                title: "The reviewer decides",
                text: "Keep the final action with an authorised human, with a clear audit trail.",
              },
            ].map(({ icon: Icon, title, text }) => (
              <article key={title} className="rounded-xl border border-slate-200 bg-white p-6">
                <Icon className="text-teal-700" size={21} />
                <h2 className="mt-4 text-sm font-semibold">{title}</h2>
                <p className="mt-2 text-xs leading-6 text-slate-500">{text}</p>
              </article>
            ))}
          </section>
          <section
            className="mt-9 flex flex-wrap items-start justify-between gap-4 rounded-xl border border-dashed border-slate-300 p-5"
            aria-labelledby="next-title"
          >
            <div className="flex gap-3">
              <Sparkles size={18} className="mt-0.5 text-slate-400" />
              <div>
                <h2 id="next-title" className="text-sm font-medium">
                  Case review is the next milestone
                </h2>
                <p className="mt-1.5 text-xs leading-6 text-slate-500">
                  The queue, member context and evidence workspace will be connected after this
                  foundation passes validation.
                </p>
              </div>
            </div>
            <a
              className="text-xs font-medium text-teal-800 underline-offset-4 hover:underline"
              href="https://cashlessiq.hulage.in"
              target="_blank"
              rel="noreferrer"
            >
              Explore the public demo ↗
            </a>
          </section>
          <footer className="mt-9 flex flex-wrap justify-between gap-2 text-[11px] text-slate-400">
            <p>CashlessIQ · Thoughtful decisions. Clear evidence.</p>
            <p>Sandbox · Synthetic data only</p>
          </footer>
        </main>
      </div>
    </div>
  );
}
