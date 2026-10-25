"use client";

import { useState } from "react";

export function CostLines() {
  const [lines, setLines] = useState([
    { id: 1, item: "Room and nursing", claimed_inr: 12000 },
    { id: 2, item: "Procedure and professional fees", claimed_inr: 68000 },
    { id: 3, item: "Medicines and diagnostics", claimed_inr: 20000 },
  ]);
  const [nextId, setNextId] = useState(4);
  return (
    <fieldset className="sm:col-span-2">
      <legend className="text-sm font-medium">Cost lines in whole INR</legend>
      <input
        type="hidden"
        name="cost_breakup"
        value={JSON.stringify(lines.map(({ item, claimed_inr }) => ({ item, claimed_inr })))}
      />
      {lines.map((line, index) => (
        <div key={line.id} className="mt-3 flex flex-wrap gap-2">
          <label className="grow text-xs">
            Expense {index + 1}
            <input
              value={line.item}
              required
              maxLength={120}
              className="mt-1 block w-full rounded border p-2 text-sm"
              onChange={(e) =>
                setLines(lines.map((l) => (l.id === line.id ? { ...l, item: e.target.value } : l)))
              }
            />
          </label>
          <label className="text-xs">
            Claimed INR
            <input
              type="number"
              min={0}
              max={100000000}
              step={1}
              required
              value={line.claimed_inr}
              className="mt-1 block w-36 rounded border p-2 text-sm"
              onChange={(e) =>
                setLines(
                  lines.map((l) =>
                    l.id === line.id ? { ...l, claimed_inr: Number(e.target.value) } : l,
                  ),
                )
              }
            />
          </label>
          <button
            type="button"
            className="self-end rounded border p-2 text-sm"
            onClick={() => setLines(lines.filter((l) => l.id !== line.id))}
          >
            Remove expense {index + 1}
          </button>
        </div>
      ))}
      <button
        type="button"
        disabled={lines.length >= 50}
        className="mt-3 rounded border p-2 text-sm"
        onClick={() => {
          setLines([...lines, { id: nextId, item: "", claimed_inr: 0 }]);
          setNextId(nextId + 1);
        }}
      >
        Add expense
      </button>
      <p className="mt-2 text-xs text-slate-500">
        Line total: INR {lines.reduce((sum, line) => sum + line.claimed_inr, 0)}. This must match
        the estimated total above.
      </p>
    </fieldset>
  );
}
