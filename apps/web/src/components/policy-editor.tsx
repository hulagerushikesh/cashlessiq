"use client";

import { useState } from "react";
import { AssessmentFields, type Facts } from "./assessment-fields";

type Clause = { clause_id: string; title: string; text: string; page: number | null };
type Param = string | number | boolean | string[] | null;
type Rule = {
  rule_id: string;
  rule_type: string;
  clause_id: string;
  params: Record<string, Param>;
};
type Example = {
  name: string;
  facts: Facts;
  expected_outcome: string;
  expected_payable_inr: number | null;
};
export type PolicyDefinition = {
  name: string;
  effective_from: string;
  effective_to: string | null;
  clauses: Clause[];
  rules: Rule[];
  examples: Example[];
};

const defaults: Record<string, Record<string, Param>> = {
  ROOM_RENT_CAP: { pct_of_si: 2, max_inr_per_day: 5000 },
  ICU_CAP: { pct_of_si: 5, max_inr_per_day: 10000 },
  PROPORTIONATE_DEDUCTION: {
    applies_to: ["procedure and professional fees"],
    exempt_items: ["medicines"],
  },
  PROCEDURE_SUBLIMIT: {
    procedure: "cataract",
    pct_of_si: 25,
    max_inr: 40000,
    basis: "per_eye_per_policy_year",
  },
  WAITING_PED: { months: 36 },
  WAITING_SPECIFIC: { months: 24, conditions: ["hernia"], accident_exempt: true },
  WAITING_INITIAL: { days: 30, accident_exempt: true },
  EXCLUSION: { condition: "refractive error" },
  COPAY: { pct: 5 },
};
const labels: Record<string, string> = {
  ROOM_RENT_CAP: "Room rent cap",
  ICU_CAP: "ICU cap",
  PROPORTIONATE_DEDUCTION: "Proportionate deduction",
  PROCEDURE_SUBLIMIT: "Procedure sublimit",
  WAITING_PED: "Pre-existing disease waiting period",
  WAITING_SPECIFIC: "Specific condition waiting period",
  WAITING_INITIAL: "Initial waiting period",
  EXCLUSION: "Exclusion",
  COPAY: "Co-payment",
  pct_of_si: "Percent of sum insured",
  max_inr_per_day: "Maximum INR per day",
  applies_to: "Applies to (one item per line)",
  exempt_items: "Exempt items (one item per line)",
  procedure: "Procedure",
  max_inr: "Maximum INR",
  basis: "Calculation basis",
  months: "Waiting period in months",
  conditions: "Conditions (one per line)",
  accident_exempt: "Accidents exempt",
  days: "Waiting period in days",
  condition: "Excluded condition",
  pct: "Co-payment percent",
};
const input = "mt-1 block w-full min-w-0 rounded border p-2 text-sm";
const button = "mt-3 rounded border px-3 py-2 text-sm disabled:opacity-50";

export function PolicyEditor({ initial }: { initial: PolicyDefinition }) {
  const [value, setValue] = useState(initial);
  const [clauseIndex, selectClause] = useState(0);
  const [ruleIndex, selectRule] = useState(0);
  const [exampleIndex, selectExample] = useState(0);
  const clause = value.clauses[clauseIndex];
  const rule = value.rules[ruleIndex];
  const example = value.examples[exampleIndex];
  const updateClause = (patch: Partial<Clause>) =>
    setValue({
      ...value,
      clauses: value.clauses.map((c, i) => (i === clauseIndex ? { ...c, ...patch } : c)),
    });
  const updateRule = (patch: Partial<Rule>) =>
    setValue({
      ...value,
      rules: value.rules.map((r, i) => (i === ruleIndex ? { ...r, ...patch } : r)),
    });
  const updateExample = (patch: Partial<Example>) =>
    setValue({
      ...value,
      examples: value.examples.map((e, i) => (i === exampleIndex ? { ...e, ...patch } : e)),
    });
  return (
    <div className="space-y-5">
      <input type="hidden" name="proposal" value={JSON.stringify(value)} />
      <label className="block text-sm">
        Policy name
        <input
          className={input}
          required
          maxLength={200}
          value={value.name}
          onChange={(e) => setValue({ ...value, name: e.target.value })}
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm">
          Effective from
          <input
            type="date"
            className={input}
            required
            value={value.effective_from}
            onChange={(e) => setValue({ ...value, effective_from: e.target.value })}
          />
        </label>
        <label className="text-sm">
          Effective to (optional)
          <input
            type="date"
            className={input}
            min={value.effective_from}
            value={value.effective_to ?? ""}
            onChange={(e) => setValue({ ...value, effective_to: e.target.value || null })}
          />
        </label>
      </div>
      <p className="text-sm text-slate-600">
        The synthetic baseline includes {value.clauses.length} clauses, {value.rules.length} rules
        and {value.examples.length} regression examples. Edit below when needed. Changes must pass
        the examples and independent approval before activation.
      </p>
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">Policy clauses</summary>
        <label className="mt-4 block text-sm">
          Clause to edit
          <select
            className={input}
            value={clauseIndex}
            onChange={(e) => selectClause(Number(e.target.value))}
          >
            {value.clauses.map((c, i) => (
              <option key={c.clause_id} value={i}>
                {c.clause_id} · {c.title}
              </option>
            ))}
          </select>
        </label>
        {clause && (
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              Clause ID
              <input
                className={input}
                required
                maxLength={80}
                value={clause.clause_id}
                onChange={(e) => {
                  const id = e.target.value;
                  setValue({
                    ...value,
                    clauses: value.clauses.map((c, i) =>
                      i === clauseIndex ? { ...c, clause_id: id } : c,
                    ),
                    rules: value.rules.map((r) =>
                      r.clause_id === clause.clause_id ? { ...r, clause_id: id } : r,
                    ),
                  });
                }}
              />
            </label>
            <label className="block text-sm">
              Clause title
              <input
                className={input}
                required
                maxLength={200}
                value={clause.title}
                onChange={(e) => updateClause({ title: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Clause wording
              <textarea
                aria-label="Clause wording"
                className={input}
                required
                maxLength={10000}
                rows={4}
                value={clause.text}
                onChange={(e) => updateClause({ text: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Source page
              <input
                className={input}
                type="number"
                required
                min={1}
                max={2000}
                step={1}
                value={clause.page ?? ""}
                onChange={(e) =>
                  updateClause({ page: e.target.value === "" ? null : Number(e.target.value) })
                }
              />
            </label>
            <button
              type="button"
              className={button}
              disabled={
                value.clauses.length <= 1 ||
                value.rules.some((r) => r.clause_id === clause.clause_id)
              }
              onClick={() => {
                setValue({ ...value, clauses: value.clauses.filter((_, i) => i !== clauseIndex) });
                selectClause(0);
              }}
            >
              Remove selected clause
            </button>
            <p className="text-xs text-slate-500">
              A clause referenced by a rule cannot be removed. Choose another clause in that rule
              first.
            </p>
          </div>
        )}
        <button
          type="button"
          className={button}
          disabled={value.clauses.length >= 40}
          onClick={() => {
            selectClause(value.clauses.length);
            setValue({
              ...value,
              clauses: [
                ...value.clauses,
                {
                  clause_id: `CLAUSE-${crypto.randomUUID().slice(0, 8)}`,
                  title: "New clause",
                  text: "Synthetic wording to review",
                  page: 1,
                },
              ],
            });
          }}
        >
          Add clause
        </button>
      </details>
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">Policy rules</summary>
        <label className="mt-4 block text-sm">
          Rule to edit
          <select
            className={input}
            value={ruleIndex}
            onChange={(e) => selectRule(Number(e.target.value))}
          >
            {value.rules.map((r, i) => (
              <option key={r.rule_id} value={i}>
                {r.rule_id} · {labels[r.rule_type]}
              </option>
            ))}
          </select>
        </label>
        {rule && (
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              Rule ID
              <input
                className={input}
                required
                maxLength={80}
                value={rule.rule_id}
                onChange={(e) => updateRule({ rule_id: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Rule type
              <select
                className={input}
                value={rule.rule_type}
                onChange={(e) =>
                  updateRule({ rule_type: e.target.value, params: { ...defaults[e.target.value] } })
                }
              >
                {Object.keys(defaults).map((type) => (
                  <option key={type} value={type}>
                    {labels[type]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Supporting clause
              <select
                className={input}
                required
                value={rule.clause_id}
                onChange={(e) => updateRule({ clause_id: e.target.value })}
              >
                {value.clauses.map((c) => (
                  <option key={c.clause_id} value={c.clause_id}>
                    {c.clause_id} · {c.title}
                  </option>
                ))}
              </select>
            </label>
            {Object.entries(defaults[rule.rule_type]).map(([key, kind]) => {
              const current = rule.params[key];
              const update = (param: Param) =>
                updateRule({ params: { ...rule.params, [key]: param } });
              return (
                <label key={key} htmlFor={`policy-param-${key}`} className="block text-sm">
                  {labels[key]}
                  {Array.isArray(kind) ? (
                    <textarea
                      aria-label={labels[key]}
                      id={`policy-param-${key}`}
                      className={input}
                      rows={4}
                      required
                      value={(current as string[]).join("\n")}
                      onChange={(e) => update(e.target.value.split("\n"))}
                    />
                  ) : typeof kind === "boolean" ? (
                    <select
                      id={`policy-param-${key}`}
                      className={input}
                      value={String(current)}
                      onChange={(e) => update(e.target.value === "true")}
                    >
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  ) : key === "basis" ? (
                    <select
                      id={`policy-param-${key}`}
                      className={input}
                      value={String(current)}
                      onChange={(e) => update(e.target.value)}
                    >
                      <option value="per_eye_per_policy_year">Per eye per policy year</option>
                    </select>
                  ) : (
                    <input
                      id={`policy-param-${key}`}
                      className={input}
                      type={typeof kind === "number" ? "number" : "text"}
                      required
                      min={0}
                      max={
                        key.startsWith("pct")
                          ? 100
                          : ["days", "months"].includes(key)
                            ? 3650
                            : 100000000
                      }
                      step={1}
                      maxLength={120}
                      value={String(current ?? "")}
                      onChange={(e) =>
                        update(
                          typeof kind === "number"
                            ? e.target.value === ""
                              ? null
                              : Number(e.target.value)
                            : e.target.value,
                        )
                      }
                    />
                  )}
                </label>
              );
            })}
            <button
              type="button"
              className={button}
              disabled={value.rules.length <= 1}
              onClick={() => {
                setValue({ ...value, rules: value.rules.filter((_, i) => i !== ruleIndex) });
                selectRule(0);
              }}
            >
              Remove selected rule
            </button>
          </div>
        )}
        <button
          type="button"
          className={button}
          disabled={value.rules.length >= 30}
          onClick={() => {
            selectRule(value.rules.length);
            setValue({
              ...value,
              rules: [
                ...value.rules,
                {
                  rule_id: `RULE-${crypto.randomUUID().slice(0, 8)}`,
                  rule_type: "WAITING_SPECIFIC",
                  clause_id: value.clauses[0].clause_id,
                  params: { ...defaults.WAITING_SPECIFIC },
                },
              ],
            });
          }}
        >
          Add rule
        </button>
      </details>
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">Regression examples</summary>
        <p className="mt-3 text-sm text-slate-600">
          Keep at least one query, one referral and one calculated approval example. Select an
          example to edit its fictional facts and expected result.
        </p>
        <label className="mt-4 block text-sm">
          Example to edit
          <select
            className={input}
            value={exampleIndex}
            onChange={(e) => selectExample(Number(e.target.value))}
          >
            {value.examples.map((e, i) => (
              <option key={e.name} value={i}>
                {e.name}
              </option>
            ))}
          </select>
        </label>
        {example && (
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              Example name
              <input
                className={input}
                required
                maxLength={80}
                value={example.name}
                onChange={(e) => updateExample({ name: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Expected outcome
              <select
                className={input}
                value={example.expected_outcome}
                onChange={(e) =>
                  updateExample({
                    expected_outcome: e.target.value,
                    expected_payable_inr: ["QUERY", "REFER"].includes(e.target.value)
                      ? null
                      : example.expected_payable_inr,
                  })
                }
              >
                {["APPROVE", "APPROVE_WITH_DEDUCTIONS", "QUERY", "REFER"].map((outcome) => (
                  <option key={outcome} value={outcome}>
                    {outcome.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Expected payable in INR (optional)
              <input
                type="number"
                className={input}
                min={0}
                max={100000000}
                step={1}
                value={example.expected_payable_inr ?? ""}
                onChange={(e) =>
                  updateExample({
                    expected_payable_inr: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </label>
            <AssessmentFields
              key={exampleIndex}
              value={example.facts}
              onChange={(facts) => updateExample({ facts })}
            />
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className={button}
                disabled={value.examples.length >= 50}
                onClick={() => {
                  selectExample(value.examples.length);
                  setValue({
                    ...value,
                    examples: [
                      ...value.examples,
                      {
                        ...structuredClone(example),
                        name: `Synthetic example ${value.examples.length + 1}`,
                      },
                    ],
                  });
                }}
              >
                Duplicate selected example
              </button>
              <button
                type="button"
                className={button}
                disabled={value.examples.length <= 3}
                onClick={() => {
                  setValue({
                    ...value,
                    examples: value.examples.filter((_, i) => i !== exampleIndex),
                  });
                  selectExample(0);
                }}
              >
                Remove selected example
              </button>
            </div>
          </div>
        )}
      </details>
    </div>
  );
}
