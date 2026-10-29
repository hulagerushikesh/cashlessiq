import { expect, test } from "@playwright/test";
import {
  pollProgress,
  PROGRESS_WINDOW_MS,
  type ProgressState,
} from "../../apps/web/src/lib/progress-poller";
import {
  requestPending,
  policyPending,
  type RequestProgress,
} from "../../apps/web/src/lib/workflow-progress";

function world() {
  let time = 0;
  let reads = 0;
  const controller = new AbortController();
  const states: ProgressState[] = [];
  const data: boolean[] = [];
  return {
    controller,
    states,
    data,
    reads: () => reads,
    options: {
      initial: true,
      pending: (value: boolean) => value,
      read: async () => {
        reads++;
        return false;
      },
      onData: (value: boolean) => {
        data.push(value);
      },
      onState: (state: ProgressState) => {
        states.push(state);
      },
      signal: controller.signal,
      visible: () => true,
      online: () => true,
      wait: async (ms: number) => {
        time += ms;
      },
      now: () => time,
    },
  };
}

test("completed records issue no automatic reads; manual checks can start a new observation", async () => {
  const w = world();
  await pollProgress({ ...w.options, initial: false });
  expect(w.reads()).toBe(0);
  await pollProgress({ ...w.options, initial: false, immediate: true });
  expect(w.reads()).toBe(1);
  expect(w.states).toEqual(["checking", "current"]);
});

test("pending work updates once and stops on a terminal result", async () => {
  const w = world();
  await pollProgress(w.options);
  expect(w.reads()).toBe(1);
  expect(w.data).toEqual([false]);
  expect(w.states).toEqual(["checking", "current"]);
});

for (const mode of ["hidden", "offline"]) {
  test(`${mode} tabs make no reads and expire without an endless watcher`, async () => {
    const w = world();
    await pollProgress({
      ...w.options,
      visible: () => mode !== "hidden",
      online: () => mode !== "offline",
    });
    expect(w.reads()).toBe(0);
    expect(w.states).toContain("paused");
    expect(w.states.at(-1)).toBe("expired");
  });
}

test("a pending job is bounded to the two-minute window", async () => {
  const w = world();
  await pollProgress({
    ...w.options,
    read: async () => {
      return true;
    },
  });
  expect(w.data.length).toBeLessThanOrEqual(24);
  expect(w.data.length).toBeGreaterThan(0);
  expect(w.states.at(-1)).toBe("expired");
});

test("clock jump beyond the deadline sends no late read", async () => {
  const w = world();
  let time = 0;
  await pollProgress({
    ...w.options,
    now: () => time,
    wait: async () => {
      time += PROGRESS_WINDOW_MS + 1;
    },
  });
  expect(w.reads()).toBe(0);
  expect(w.states).toEqual(["expired"]);
});

test("aborting during a read discards its result", async () => {
  const w = world();
  await pollProgress({
    ...w.options,
    read: async () => {
      w.controller.abort();
      return false;
    },
  });
  expect(w.data).toEqual([]);
});

test("failed reads stop rather than silently retrying or claiming completion", async () => {
  const w = world();
  await expect(
    pollProgress({
      ...w.options,
      read: async () => {
        throw new Error("offline");
      },
    }),
  ).rejects.toThrow("offline");
  expect(w.data).toEqual([]);
  expect(w.states).toEqual(["checking"]);
});

test("only live processing states trigger observations, including pending PDFs", () => {
  const request: RequestProgress = {
    assessment: null,
    assessment_job: { id: "test", state: "queued", attempts: 0 },
    clinical_restricted: true,
    documents: { clinical_restricted: true, items: [] },
  };
  expect(requestPending(request)).toBe(true);
  for (const state of ["dead", "missing"]) {
    expect(
      requestPending({
        ...request,
        assessment_job: { id: "test", state, attempts: 3 },
      }),
    ).toBe(false);
    expect(
      policyPending({
        regression_job_id: null,
        regression_state: state,
        regression: null,
      }),
    ).toBe(false);
  }
  expect(
    requestPending({
      ...request,
      assessment_job: null,
      documents: {
        clinical_restricted: true,
        items: [
          {
            id: "pdf",
            digest: "hash",
            text: null,
            state: "quarantined",
            processing_job: { id: "job", state: "running", attempts: 1 },
          },
        ],
      },
    }),
  ).toBe(true);
});

test("completion races keep observing until the assessment or released document is visible", () => {
  const request: RequestProgress = {
    assessment: null,
    assessment_job: { id: "job", state: "succeeded", attempts: 1 },
    clinical_restricted: true,
    documents: { clinical_restricted: true, items: [] },
  };
  expect(requestPending(request)).toBe(true);
  expect(
    requestPending({
      ...request,
      assessment_job: null,
      documents: {
        clinical_restricted: true,
        items: [
          {
            id: "pdf",
            digest: "hash",
            text: null,
            state: "quarantined",
            processing_job: { id: "job", state: "succeeded", attempts: 1 },
          },
        ],
      },
    }),
  ).toBe(true);
  expect(
    policyPending({
      regression_job_id: null,
      regression_state: "succeeded",
      regression: null,
    }),
  ).toBe(false);
});
