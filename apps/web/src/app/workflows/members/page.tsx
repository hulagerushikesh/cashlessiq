import { randomUUID } from "node:crypto";
import { mvpApi } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";

export default async function Members({
  searchParams,
}: {
  searchParams: Promise<{ result?: string }>;
}) {
  const members = await mvpApi<{
    items: { user_id: string; name: string; role: string; active: boolean }[];
    roles: string[];
  }>("admin/memberships");
  if (!members) return <CaseServiceError />;
  const { result } = await searchParams;
  return (
    <>
      <h1 className="text-3xl font-semibold">Tenant access</h1>
      <p className="mt-3 text-sm text-slate-600">
        Role changes apply to existing sessions immediately. Ask another administrator to change
        your own access.
      </p>
      {result && (
        <p role="status" className="mt-4 rounded bg-amber-50 p-4">
          {result === "saved"
            ? "Membership saved."
            : "Membership was not saved. Refresh and check the current access before retrying."}
        </p>
      )}
      {members.items.map((m) => (
        <form
          key={m.user_id}
          action="/workflows/commands"
          method="post"
          className="mt-6 grid gap-4 rounded-xl border bg-white p-6 sm:grid-cols-2"
        >
          <h2 className="font-semibold sm:col-span-2">{m.name}</h2>
          <input type="hidden" name="operation" value="member" />
          <input type="hidden" name="id" value={m.user_id} />
          <input type="hidden" name="command_id" value={randomUUID()} />
          <input type="hidden" name="expected_role" value={m.role} />
          <input type="hidden" name="expected_active" value={String(m.active)} />
          <label className="text-sm">
            Role
            <select
              name="role"
              defaultValue={m.role}
              className="mt-2 block w-full rounded border p-2"
            >
              {members.roles.map((role) => (
                <option key={role} value={role}>
                  {role.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Access
            <select
              name="active"
              defaultValue={String(m.active)}
              className="mt-2 block w-full rounded border p-2"
            >
              <option value="true">Active</option>
              <option value="false">Suspended</option>
            </select>
          </label>
          <label className="text-sm sm:col-span-2">
            Reason
            <input
              name="reason"
              required
              maxLength={2000}
              className="mt-2 block w-full rounded border p-2"
            />
          </label>
          <button type="submit" className="rounded bg-teal-800 p-3 text-white">
            Save access
          </button>
        </form>
      ))}
    </>
  );
}
