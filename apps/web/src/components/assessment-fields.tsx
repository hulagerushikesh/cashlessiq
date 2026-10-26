"use client";

import { useState } from "react";

type Cost = { item: string; claimed_inr: number | null };
type Condition = {
  icd10_code: string;
  condition_name: string;
  first_diagnosed_on: string;
  declared_at_proposal: boolean;
};
export type Facts = {
  member_reference: string;
  inception_date: string;
  continuous_cover_since: string;
  admission_date: string | null;
  sum_insured_inr: number | null;
  si_remaining_inr: number | null;
  diagnosis?: string | null;
  icd10_code?: string | null;
  procedure?: string | null;
  is_emergency?: boolean | null;
  room_category?: string | null;
  room_rent_per_day_inr?: number | null;
  planned_los_days?: number | null;
  icu_days?: number | null;
  cost_breakup: Cost[];
  estimated_total_inr?: number | null;
  clinical_note?: string | null;
  declared_conditions?: Condition[];
};

export const defaultFacts: Facts = {
  member_reference: "SYN-TEST001",
  inception_date: "2023-01-01",
  continuous_cover_since: "2023-01-01",
  admission_date: "2026-10-02",
  sum_insured_inr: 500000,
  si_remaining_inr: 500000,
  diagnosis: "Acute appendicitis",
  procedure: "Laparoscopic appendicectomy",
  room_category: "Twin sharing",
  room_rent_per_day_inr: 4000,
  planned_los_days: 3,
  icu_days: 0,
  estimated_total_inr: 100000,
  cost_breakup: [
    { item: "Room and nursing", claimed_inr: 12000 },
    { item: "Procedure and professional fees", claimed_inr: 68000 },
    { item: "Medicines and diagnostics", claimed_inr: 20000 },
  ],
  declared_conditions: [],
};

const input = "mt-1 block w-full min-w-0 rounded border border-slate-300 bg-white p-2 text-sm";
const fields: {
  key: keyof Facts;
  label: string;
  type?: string;
  required?: boolean;
  max?: number;
  min?: number;
  length?: number;
}[] = [
  { key: "member_reference", label: "Synthetic member reference", required: true, length: 80 },
  { key: "inception_date", label: "Policy inception", type: "date", required: true },
  { key: "continuous_cover_since", label: "Continuous cover since", type: "date", required: true },
  { key: "admission_date", label: "Admission date", type: "date" },
  { key: "sum_insured_inr", label: "Sum insured in INR", type: "number", required: true, min: 1 },
  { key: "si_remaining_inr", label: "Remaining cover in INR", type: "number", required: true },
  { key: "diagnosis", label: "Diagnosis" },
  { key: "icd10_code", label: "ICD-10 code", length: 30 },
  { key: "procedure", label: "Procedure" },
  { key: "room_category", label: "Room category", length: 80 },
  { key: "room_rent_per_day_inr", label: "Room rent per day in INR", type: "number" },
  {
    key: "planned_los_days",
    label: "Planned length of stay in days",
    type: "number",
    min: 1,
    max: 365,
  },
  { key: "icu_days", label: "ICU days", type: "number", max: 365 },
  { key: "estimated_total_inr", label: "Estimated total in INR", type: "number" },
];

export function AssessmentFields({
  value,
  onChange,
}: {
  value: Facts;
  onChange: (facts: Facts) => void;
}) {
  const costs = value.cost_breakup;
  const [costIds, setCostIds] = useState(() => value.cost_breakup.map((_, i) => `cost-${i}`));
  const [conditionIds, setConditionIds] = useState(() =>
    (value.declared_conditions ?? []).map((_, i) => `condition-${i}`),
  );
  const conditions = value.declared_conditions ?? [];
  const total = costs.reduce((sum, line) => sum + (line.claimed_inr ?? 0), 0);
  return (
    <div className="grid min-w-0 gap-5 sm:grid-cols-2">
      {fields.map(({ key, label, type = "text", required, max, min, length }) => (
        <label key={key} className="min-w-0 text-sm">
          {label}
          <input
            type={type}
            required={required}
            value={String(value[key] ?? "")}
            className={input}
            min={type === "number" ? (min ?? 0) : undefined}
            max={type === "number" ? (max ?? 100000000) : undefined}
            step={type === "number" ? 1 : undefined}
            maxLength={length ?? 500}
            pattern={key === "member_reference" ? "SYN-[A-Za-z0-9-]+" : undefined}
            onChange={(e) =>
              onChange({
                ...value,
                [key]:
                  type === "number"
                    ? e.target.value === ""
                      ? null
                      : Number(e.target.value)
                    : e.target.value || (required ? "" : null),
              })
            }
          />
        </label>
      ))}
      <label className="text-sm">
        Emergency admission
        <select
          className={input}
          value={
            value.is_emergency === true ? "yes" : value.is_emergency === false ? "no" : "unknown"
          }
          onChange={(e) =>
            onChange({
              ...value,
              is_emergency: e.target.value === "unknown" ? null : e.target.value === "yes",
            })
          }
        >
          <option value="unknown">Not provided</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      </label>
      <fieldset className="min-w-0 sm:col-span-2">
        <legend className="text-sm font-medium">Cost lines in whole INR</legend>
        {costs.map((line, index) => (
          <div key={costIds[index]} className="mt-3 flex flex-wrap gap-2">
            <label className="min-w-0 grow text-xs">
              Expense {index + 1}
              <input
                className={input}
                required
                maxLength={120}
                value={line.item}
                onChange={(e) =>
                  onChange({
                    ...value,
                    cost_breakup: costs.map((c, i) =>
                      i === index ? { ...c, item: e.target.value } : c,
                    ),
                  })
                }
              />
            </label>
            <label className="text-xs">
              Claimed INR
              <input
                className={`${input} w-36`}
                type="number"
                required
                min={0}
                max={100000000}
                step={1}
                value={line.claimed_inr ?? ""}
                onChange={(e) =>
                  onChange({
                    ...value,
                    cost_breakup: costs.map((c, i) =>
                      i === index
                        ? {
                            ...c,
                            claimed_inr: e.target.value === "" ? null : Number(e.target.value),
                          }
                        : c,
                    ),
                  })
                }
              />
            </label>
            <button
              type="button"
              className="self-end rounded border p-2 text-sm"
              onClick={() => {
                setCostIds(costIds.filter((_, i) => i !== index));
                onChange({ ...value, cost_breakup: costs.filter((_, i) => i !== index) });
              }}
            >
              Remove expense {index + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          className="mt-3 rounded border p-2 text-sm"
          disabled={costs.length >= 50}
          onClick={() => {
            setCostIds([...costIds, crypto.randomUUID()]);
            onChange({ ...value, cost_breakup: [...costs, { item: "", claimed_inr: 0 }] });
          }}
        >
          Add expense
        </button>
        <p className="mt-2 text-sm">
          Line total: INR {total}. This must match the estimated total.
        </p>
        {costs.length > 0 && total !== value.estimated_total_inr && (
          <p role="status" className="mt-2 text-sm text-amber-800">
            The cost lines and estimated total do not match.
          </p>
        )}
      </fieldset>
      <label className="text-sm sm:col-span-2">
        Clinical note
        <textarea
          aria-label="Clinical note"
          className={input}
          maxLength={2000}
          rows={3}
          value={value.clinical_note ?? ""}
          onChange={(e) => onChange({ ...value, clinical_note: e.target.value || null })}
        />
      </label>
      <fieldset className="min-w-0 sm:col-span-2">
        <legend className="text-sm font-medium">Declared conditions</legend>
        {conditions.map((condition, index) => (
          <div
            key={conditionIds[index]}
            className="mt-3 grid gap-3 rounded border p-3 sm:grid-cols-2"
          >
            {(
              [
                ["icd10_code", "Condition ICD-10 code", "text"],
                ["condition_name", "Condition name", "text"],
                ["first_diagnosed_on", "First diagnosed on", "date"],
              ] as const
            ).map(([key, label, type]) => (
              <label key={key} className="text-sm">
                {label} {index + 1}
                <input
                  type={type}
                  className={input}
                  value={condition[key]}
                  required={key === "first_diagnosed_on"}
                  maxLength={key === "icd10_code" ? 30 : 120}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      declared_conditions: conditions.map((c, i) =>
                        i === index ? { ...c, [key]: e.target.value } : c,
                      ),
                    })
                  }
                />
              </label>
            ))}
            <label className="self-center text-sm">
              <input
                type="checkbox"
                checked={condition.declared_at_proposal}
                onChange={(e) =>
                  onChange({
                    ...value,
                    declared_conditions: conditions.map((c, i) =>
                      i === index ? { ...c, declared_at_proposal: e.target.checked } : c,
                    ),
                  })
                }
              />{" "}
              Declared at proposal {index + 1}
            </label>
            <button
              type="button"
              className="justify-self-start rounded border p-2 text-sm"
              onClick={() => {
                setConditionIds(conditionIds.filter((_, i) => i !== index));
                onChange({
                  ...value,
                  declared_conditions: conditions.filter((_, i) => i !== index),
                });
              }}
            >
              Remove condition {index + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          className="mt-3 rounded border p-2 text-sm"
          disabled={conditions.length >= 20}
          onClick={() => {
            setConditionIds([...conditionIds, crypto.randomUUID()]);
            onChange({
              ...value,
              declared_conditions: [
                ...conditions,
                {
                  icd10_code: "",
                  condition_name: "",
                  first_diagnosed_on: "",
                  declared_at_proposal: false,
                },
              ],
            });
          }}
        >
          Add declared condition
        </button>
      </fieldset>
    </div>
  );
}

export function FactsEditor({ initial = defaultFacts }: { initial?: Facts }) {
  const [facts, setFacts] = useState(initial);
  return (
    <>
      <input type="hidden" name="facts" value={JSON.stringify(facts)} />
      <AssessmentFields value={facts} onChange={setFacts} />
    </>
  );
}
