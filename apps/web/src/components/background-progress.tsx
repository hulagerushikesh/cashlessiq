"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { pollProgress, type ProgressState } from "@/lib/progress-poller";
import {
  documentsPending,
  pendingJob,
  policyPending,
  requestPending,
  type Documents,
  type PolicyProgress,
  type RequestProgress,
} from "@/lib/workflow-progress";
import { rupees } from "@/lib/money";

type State = ProgressState | "error" | "session" | "stopped";
function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
  });
}

function useProgress<T>(initial: T, url: string, pending: (data: T) => boolean) {
  const [data, setData] = useState<T | null>(initial);
  const [state, setState] = useState<State>(pending(initial) ? "watching" : "current");
  const [attempt, setAttempt] = useState(0);
  const [enabled, setEnabled] = useState(true);
  const latest = useRef(initial);
  useEffect(() => {
    latest.current = initial;
    setData(initial);
  }, [initial]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setState(pending(latest.current) ? "watching" : "current");
    void pollProgress({
      initial: attempt === 0 ? initial : latest.current,
      pending,
      immediate: attempt > 0,
      signal: controller.signal,
      visible: () => document.visibilityState === "visible",
      online: () => navigator.onLine,
      wait,
      read: async (signal) => {
        const response = await fetch(url, {
          cache: "no-store",
          credentials: "same-origin",
          signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
        });
        if (response.status === 401 || response.status === 403) {
          setData(null);
          setState("session");
          throw new Error("Session unavailable");
        }
        if (!response.ok) throw new Error("Progress unavailable");
        return (await response.json()) as T;
      },
      onData: (next) => {
        latest.current = next;
        setData(next);
      },
      onState: setState,
    }).catch(() => {
      if (!controller.signal.aborted) setState((old) => (old === "session" ? old : "error"));
    });
    return () => controller.abort();
  }, [url, pending, attempt, enabled, initial]);
  return {
    data,
    state,
    check: () => {
      setEnabled(true);
      setAttempt((n) => n + 1);
    },
    stop: () => {
      setEnabled(false);
      setState("stopped");
    },
  };
}

function ProgressControls({
  state,
  check,
  stop,
}: {
  state: State;
  check: () => void;
  stop: () => void;
}) {
  const messages: Record<State, string> = {
    watching: "Checking progress every 5 seconds for up to 2 minutes. Your form entries stay here.",
    checking: "Checking for updated results…",
    paused: "Progress checks pause while this tab is hidden or your device is offline.",
    expired:
      "Automatic checks stopped after 2 minutes. Processing may continue; check again or open background jobs.",
    current: "Showing the latest loaded results.",
    stopped: "Automatic checks stopped. Background processing may continue.",
    error:
      "Progress could not be checked. Displayed results may be out of date. Check your connection and try again.",
    session: "Your session has ended or access changed. Sign in again to check progress.",
  };
  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
      <p role="status">{messages[state]}</p>
      <div className="mt-2 flex flex-wrap gap-4">
        {state === "session" ? (
          <Link href="/login" className="text-teal-800 underline">
            Sign in again
          </Link>
        ) : (
          <button
            type="button"
            disabled={state === "checking"}
            onClick={check}
            className="text-teal-800 underline disabled:opacity-50"
          >
            Check for updates
          </button>
        )}
        {["watching", "checking", "paused"].includes(state) && (
          <button type="button" onClick={stop} className="text-teal-800 underline">
            Stop checking
          </button>
        )}
        <Link href="/workflows/jobs" className="text-teal-800 underline">
          Open background jobs
        </Link>
      </div>
    </div>
  );
}

function JobLink({ id }: { id?: string | null }) {
  return id ? (
    <Link
      href={`/workflows/jobs/${encodeURIComponent(id)}`}
      className="mt-2 inline-block text-sm text-teal-800 underline"
    >
      Inspect this background job
    </Link>
  ) : null;
}

const panel = "mt-6 rounded-xl border border-slate-200 bg-white p-6";
export function RequestResults({ id, initial }: { id: string; initial: RequestProgress }) {
  const progress = useProgress(
    initial,
    `/workflows/progress?kind=request&id=${encodeURIComponent(id)}`,
    requestPending,
  );
  const data = progress.data;
  const assessment = data && !pendingJob(data.assessment_job) ? data.assessment : null;
  return (
    <section aria-label="Request processing results">
      <ProgressControls {...progress} />
      {data && (
        <>
          {assessment && (
            <Link
              className="mt-4 inline-block rounded-lg bg-teal-800 px-4 py-2 text-sm text-white"
              href={`/reviews/${encodeURIComponent(id)}`}
            >
              Open reviewer workflow
            </Link>
          )}
          <section className={panel}>
            <h2 className="text-xl font-semibold">Assessment</h2>
            {assessment ? (
              <>
                <p className="mt-3">
                  {assessment.outcome.replaceAll("_", " ")} · {rupees(assessment.payable_inr)}
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  Policy {assessment.policy_version} · Deterministic calculation · Human review
                  required
                </p>
                <Link
                  href={`/workflows/policies/${assessment.policy_id}`}
                  className="mt-3 inline-block text-sm text-teal-800 underline"
                >
                  View pinned policy clauses and wording
                </Link>
                {assessment.queries?.map((q) => (
                  <p key={q} className="mt-3 text-sm text-amber-800">
                    {q}
                  </p>
                ))}
                {assessment.refer_reasons?.map((q) => (
                  <p key={q} className="mt-3 text-sm text-amber-800">
                    {q}
                  </p>
                ))}
                {assessment.payable?.lines.map((line) => (
                  <article key={line.item} className="mt-4 border-t pt-4 text-sm">
                    <h3 className="font-semibold">
                      {line.item} · {rupees(line.payable_inr)}
                    </h3>
                    <p className="mt-2">{line.reason}</p>
                    <p className="mt-2 font-mono text-xs">{line.calc}</p>
                    <p className="mt-2 text-xs text-teal-800">
                      {line.citations.map((c) => c.id).join(" · ")}
                    </p>
                  </article>
                ))}
              </>
            ) : (
              <p className="mt-3 text-sm text-slate-600">
                {data.assessment_job?.state === "dead"
                  ? "Assessment could not finish. Ask an operations reviewer to inspect and retry the background job."
                  : data.assessment_job && ["queued", "running"].includes(data.assessment_job.state)
                    ? "Assessment queued or processing. Results will appear here when ready."
                    : data.assessment_job?.state === "succeeded"
                      ? "Loading the completed assessment. Results will appear here shortly."
                      : "No current assessment is available. Check background jobs before reviewing this request."}
              </p>
            )}
            {!assessment && <JobLink id={data.assessment_job?.id} />}
            {data.clinical_restricted && (
              <p className="mt-3 text-sm text-slate-500">
                Clinical facts, detailed policy checks and document text are restricted to medical
                officers.
              </p>
            )}
          </section>
          <SupportingDocuments documents={data.documents} />
        </>
      )}
    </section>
  );
}

export function PolicyResults({ id, initial }: { id: string; initial: PolicyProgress }) {
  const progress = useProgress(
    initial,
    `/workflows/progress?kind=policy&id=${encodeURIComponent(id)}`,
    policyPending,
  );
  return (
    <section className={panel}>
      <h2 className="text-xl font-semibold">Regression results</h2>
      <ProgressControls {...progress} />
      {progress.data && (
        <>
          <p className="mt-3 text-sm">
            {progress.data.regression_state} ·{" "}
            {progress.data.regression
              ? `${progress.data.regression.passed ? "Passed" : "Failed"} · ${progress.data.regression.count} cases`
              : progress.data.regression_state === "dead"
                ? "Regression processing could not finish. Ask an operations reviewer to inspect and retry the background job."
                : "No completed regression results yet. Approval requires passing results for this proposal."}
          </p>
          {!progress.data.regression && <JobLink id={progress.data.regression_job_id} />}
          {progress.data.regression?.checks.map((c) => (
            <p key={c.name} className="mt-2 text-sm">
              {c.passed ? "Pass" : "Fail"} · {c.name} · {c.actual_outcome} ·{" "}
              {c.actual_payable_inr === null ? "Not calculated" : `INR ${c.actual_payable_inr}`}
            </p>
          ))}
        </>
      )}
    </section>
  );
}

export function SupportingDocuments({ documents }: { documents: RequestProgress["documents"] }) {
  return (
    <section className={panel}>
      <h2 className="text-xl font-semibold">Supporting documents</h2>
      {documents.items.length === 0 && (
        <p className="mt-3 text-sm text-slate-600">No supporting PDFs uploaded.</p>
      )}
      {documents.items.map((d) => (
        <article key={d.id} className="mt-4 border-t pt-4 text-sm">
          <p>{d.state.replaceAll("_", " ")}</p>
          {d.state === "quarantined" && (
            <p className="mt-2 text-amber-800">
              {d.processing_job?.state === "dead"
                ? "Extraction could not finish. An operations reviewer can inspect and retry the job."
                : "PDF is quarantined while extraction is pending. It is not available for download."}
            </p>
          )}
          {d.state === "needs_manual_extraction" && (
            <p className="mt-2 text-amber-800">
              This PDF needs manual transcription. A medical reviewer must verify and enter the
              facts.
            </p>
          )}
          {d.state === "rejected" && (
            <p className="mt-2 text-amber-800">
              PDF rejected by the safe extraction checks. Use a supported fictional PDF.
            </p>
          )}
          {d.state === "quarantined" && <JobLink id={d.processing_job?.id} />}
          <p className="mt-1 break-all text-xs text-slate-500">SHA-256 {d.digest}</p>
          {!documents.clinical_restricted && d.state === "extracted" && (
            <a
              href={`/workflows/documents/${d.id}`}
              className="mt-3 inline-block text-teal-800 underline"
            >
              Download PDF
            </a>
          )}
          {d.text && (
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 font-sans text-sm">
              {d.text}
            </pre>
          )}
        </article>
      ))}
    </section>
  );
}

export function PolicyWording({ initial }: { initial: Documents }) {
  const progress = useProgress(
    initial,
    "/workflows/progress?kind=policy-documents&id=POLICY-WORDING",
    documentsPending,
  );
  const [selected, setSelected] = useState("");
  return (
    <section aria-label="Policy wording extraction">
      <ProgressControls {...progress} />
      <label className="mt-4 block text-sm">
        Source wording
        <select
          name="wording_document_id"
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          className="mt-2 block w-full rounded border p-2"
        >
          <option value="">Synthetic baseline reference only</option>
          {progress.data?.items
            .filter((d) => d.state === "extracted")
            .map((d) => (
              <option key={d.id} value={d.id}>
                Extracted PDF · {d.digest.slice(0, 12)}
              </option>
            ))}
        </select>
      </label>
      {progress.data?.items.map((d) => (
        <article key={d.id} className="mt-4 rounded-xl border bg-white p-4 text-sm">
          <p>{d.state.replaceAll("_", " ")}</p>
          {d.state === "quarantined" && (
            <p className="mt-2 text-amber-800">
              {d.processing_job?.state === "dead"
                ? "Extraction could not finish. Ask an operations reviewer to inspect and retry the job."
                : "Extraction is pending. This PDF cannot be selected as source wording yet."}
            </p>
          )}
          {d.state === "needs_manual_extraction" && (
            <p className="mt-2 text-amber-800">
              This PDF needs manual transcription. Verify the wording before entering policy
              clauses.
            </p>
          )}
          {d.state === "rejected" && (
            <p className="mt-2 text-amber-800">
              PDF rejected by the safe extraction checks. Use a supported fictional PDF.
            </p>
          )}
          {d.state === "quarantined" && <JobLink id={d.processing_job?.id} />}
          <p className="mt-2 break-all text-xs text-slate-500">SHA-256 {d.digest}</p>
          {d.text && (
            <pre className="mt-3 max-h-60 overflow-auto whitespace-pre-wrap font-sans">
              {d.text}
            </pre>
          )}
        </article>
      ))}
    </section>
  );
}
