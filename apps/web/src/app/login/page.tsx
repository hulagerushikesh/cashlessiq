import Link from "next/link";
import { ArrowLeft, ArrowRight, Layers3, ShieldCheck } from "lucide-react";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { currentIdentity } from "@/lib/server-api";

export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const session = await currentIdentity();
  if (session.state === "ready") redirect("/");
  const { error } = await searchParams;
  const local = process.env.CIQ_ENVIRONMENT === "local" && process.env.CIQ_AUTH_MODE === "local";
  return (
    <main className="grid min-h-screen place-items-center px-5 py-12">
      <div className="w-full max-w-lg">
        <Link href="/" className="mb-8 inline-flex items-center gap-2 text-sm text-slate-500">
          <ArrowLeft size={15} /> Back to workspace
        </Link>
        <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm sm:p-10">
          <div className="mb-7 flex items-center gap-3 text-xl font-semibold">
            <span className="grid size-10 place-items-center rounded-xl bg-teal-800 text-white">
              <Layers3 size={22} />
            </span>
            CashlessIQ
          </div>
          <p className="text-[11px] font-bold uppercase tracking-[.15em] text-teal-700">
            Synthetic sandbox
          </p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            Choose your review perspective.
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            Explore with a synthetic identity. Your role determines which clinical details you can
            see.
          </p>
          {error && (
            <p role="alert" className="mt-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
              Sign-in could not be completed. Please try again.
            </p>
          )}
          {local ? (
            <form action="/auth/login" method="post" className="mt-7 space-y-5">
              <div>
                <label htmlFor="profile" className="text-sm font-medium">
                  Review role
                </label>
                <select
                  id="profile"
                  name="profile"
                  className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm focus-visible:outline-2 focus-visible:outline-teal-700"
                >
                  <option value="processor">Processor · Asha Deshmukh</option>
                  <option value="medical_officer">Medical officer · Dr. Neel Shah</option>
                  <option value="auditor">Auditor · Kavya Rao</option>
                  {process.env.CIQ_SYNTHETIC_WORKFLOWS === "true" && (
                    <>
                      <option value="policy_analyst">Policy analyst · Mira Kulkarni</option>
                      <option value="policy_approver">Policy approver · Arjun Mehta</option>
                      <option value="operations_lead">Operations lead · Rohan Patil</option>
                      <option value="tenant_admin">Tenant administrator · Sana Khan</option>
                    </>
                  )}
                </select>
              </div>
              <Button className="w-full" type="submit">
                Enter workspace <ArrowRight size={16} />
              </Button>
            </form>
          ) : (
            <p className="mt-6 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              Organisation sign-in is not configured for this workspace yet.
            </p>
          )}
          <div className="mt-7 flex items-start gap-2 border-t border-slate-100 pt-5 text-xs leading-5 text-slate-500">
            <ShieldCheck size={16} className="mt-0.5 shrink-0 text-teal-700" />
            This local sandbox contains no patient records. Production workspaces will use
            organisation sign-in.
          </div>
        </section>
      </div>
    </main>
  );
}
