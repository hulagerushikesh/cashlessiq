"use client";

import { useEffect, useRef, useState, type ComponentProps, type FormEvent } from "react";
import { WorkflowFeedback } from "./workflow-feedback";

// Keep drafts only in the mounted form: no clinical values in URLs or browser storage.
export function WorkflowForm({ children, ...props }: ComponentProps<"form">) {
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  const [feedback, setFeedback] = useState<{ result: string; error?: string }>();
  const lock = useRef(false);
  const alert = useRef<HTMLDivElement>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    const form = event.currentTarget;
    const body = new FormData(form);
    lock.current = true;
    setBusy(true);
    setFeedback(undefined);
    try {
      const response = await fetch(String(props.action), {
        method: "POST",
        headers: { Accept: "application/json" },
        body,
        signal: AbortSignal.timeout(35000),
      });
      const data = await response.json();
      if (data.result === "saved") {
        const location = new URL(data.location, window.location.origin);
        if (location.origin !== window.location.origin) throw new Error("Invalid destination");
        window.location.assign(location.href);
        return;
      }
      setFeedback({
        result: data.result === "conflict" ? "conflict" : "failed",
        error: data.error,
      });
    } catch {
      // A lost response may have committed. Reuse the command ID for a safe identical retry.
      setFeedback({ result: "failed", error: "connection" });
    }
    lock.current = false;
    setBusy(false);
    requestAnimationFrame(() => alert.current?.focus());
  }
  return (
    <form
      {...props}
      onSubmit={submit}
      aria-busy={busy}
      onInvalidCapture={(event) => {
        // Bring required controls inside disclosures into view before native validation focuses them.
        let parent = (event.target as HTMLElement).parentElement;
        while (parent) {
          if (parent instanceof HTMLDetailsElement) parent.open = true;
          parent = parent.parentElement;
        }
      }}
    >
      {!ready && <p role="status">Enable JavaScript to edit and submit this form safely.</p>}
      <div ref={alert} tabIndex={-1} className="col-span-full outline-none">
        {feedback && <WorkflowFeedback {...feedback} />}
        {feedback && (
          <>
            <p className="mt-2 text-sm text-slate-600">
              Your entries are still here. Review them before retrying. They are not saved as a
              draft and will be lost if you leave or reload this page.
            </p>
            <button
              type="button"
              onClick={() => window.open(window.location.pathname, "_blank", "noopener")}
              className="mt-2 inline-block text-sm text-teal-800 underline"
            >
              Open this page in another tab
            </button>
          </>
        )}
        {busy && (
          <p role="status" className="text-sm text-slate-600">
            Saving…
          </p>
        )}
      </div>
      <fieldset disabled={!ready || busy} className="contents">
        {children}
      </fieldset>
    </form>
  );
}
