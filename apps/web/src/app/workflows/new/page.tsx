import { CostLines } from "@/components/cost-lines";
import { randomUUID } from "node:crypto";
import { mvpApi, type Policy } from "@/lib/mvp-api";
import { CaseServiceError } from "@/components/case-workspace";

export default async function NewRequest() {
  const policies = await mvpApi<{ items: Policy[] }>("policies");
  if (!policies) return <CaseServiceError />;
  const products = [
    ...new Set(policies.items.filter((p) => p.status === "approved").map((p) => p.product_id)),
  ];
  const input = "mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
  const fields = [
    ["member_reference", "Synthetic member reference", "text", "SYN-TEST001"],
    ["inception_date", "Policy inception", "date", "2023-01-01"],
    ["continuous_cover_since", "Continuous cover since", "date", "2023-01-01"],
    ["admission_date", "Admission date", "date", "2026-10-02"],
    ["sum_insured_inr", "Sum insured in INR", "number", "500000"],
    ["si_remaining_inr", "Remaining cover in INR", "number", "500000"],
    ["diagnosis", "Diagnosis", "text", "Acute appendicitis"],
    ["procedure", "Procedure", "text", "Laparoscopic appendicectomy"],
    ["room_category", "Room category", "text", "Twin sharing"],
    ["room_rent_per_day_inr", "Room rent per day in INR", "number", "4000"],
    ["planned_los_days", "Planned length of stay in days", "number", "3"],
    ["estimated_total_inr", "Estimated total in INR", "number", "100000"],
  ];
  return (
    <>
      <h1 className="text-3xl font-semibold">Submit a synthetic request</h1>
      <p className="mt-3 text-sm text-slate-600">
        These fictional defaults match the clean golden case. Clear missing clinical fields to test
        an information request. No real patient information.
      </p>
      <form
        action="/workflows/commands"
        method="post"
        className="mt-6 grid max-w-4xl gap-5 rounded-xl border bg-white p-6 sm:grid-cols-2"
      >
        <input type="hidden" name="operation" value="submit" />
        <input type="hidden" name="command_id" value={randomUUID()} />
        <label className="text-sm">
          Policy product
          <select name="product_id" required className={input}>
            {products.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Priority
          <select name="priority" className={input}>
            <option value="normal">Normal · one hour</option>
            <option value="urgent">Urgent · thirty minutes</option>
          </select>
        </label>
        {fields.map(([name, label, type, value]) => (
          <label key={name} className="text-sm">
            {label}
            <input
              name={name}
              type={type}
              defaultValue={value}
              min={type === "number" ? 0 : undefined}
              step={type === "number" ? 1 : undefined}
              maxLength={500}
              className={input}
            />
          </label>
        ))}
        <CostLines />
        <label className="text-sm sm:col-span-2">
          Clinical note
          <textarea name="clinical_note" maxLength={2000} className={input} />
        </label>
        <label className="text-sm sm:col-span-2">
          <input type="checkbox" name="synthetic_data" value="true" required /> I confirm that this
          request contains fictional test data only.
        </label>
        <button
          type="submit"
          disabled={products.length === 0}
          className="rounded-lg bg-teal-800 p-3 text-white disabled:opacity-50"
        >
          Queue assessment
        </button>
        {products.length === 0 && (
          <p className="text-sm text-amber-800">
            An analyst and a different approver must first approve and activate a policy.
          </p>
        )}
      </form>
    </>
  );
}
