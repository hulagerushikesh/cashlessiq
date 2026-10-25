import { mvpApi } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";

export default async function Events() {
  const [events, analytics] = await Promise.all([
    mvpApi<{
      items: {
        event_id: string;
        actor_id: string;
        actor_role: string;
        action: string;
        subject_id: string;
        occurred_at: string;
      }[];
    }>("events"),
    mvpApi<{ counts: Record<string, number> }>("analytics"),
  ]);
  if (!events) return <CaseServiceError />;
  return (
    <>
      <h1 className="text-3xl font-semibold">Governance and reporting</h1>
      <p className="mt-3 text-sm text-slate-600">
        Append-only policy, submission, retry and access history for this tenant.
      </p>
      {analytics && (
        <section className="mt-6 rounded-xl border bg-white p-6">
          <h2 className="text-xl font-semibold">Reviewer activity</h2>
          {Object.entries(analytics.counts).map(([action, count]) => (
            <p key={action} className="mt-3 text-sm">
              {action.replace("cashlessiq.review.", "").replaceAll("_", " ")} · {count}
            </p>
          ))}
          <p className="mt-3 text-xs text-slate-500">
            Local reporting. Snowflake publishing is disabled.
          </p>
        </section>
      )}
      {events.items.map((e) => (
        <article key={e.event_id} className="mt-4 rounded-xl border bg-white p-5 text-sm">
          <h2 className="font-semibold">{e.action.replaceAll("_", " ")}</h2>
          <p className="mt-2">
            {e.actor_role.replaceAll("_", " ")} · {new Date(e.occurred_at).toISOString()}
          </p>
          <p className="mt-2 break-all text-xs text-slate-500">
            Subject {e.subject_id} · Actor {e.actor_id} · Event {e.event_id}
          </p>
        </article>
      ))}
    </>
  );
}
