// Bounded foreground observations, independent of page navigation or mutations.
export type ProgressState = "watching" | "checking" | "paused" | "expired" | "current";
export const PROGRESS_INTERVAL_MS = 5000;
export const PROGRESS_WINDOW_MS = 120000;

export async function pollProgress<T>(options: {
  initial: T;
  pending: (data: T) => boolean;
  read: (signal: AbortSignal) => Promise<T>;
  onData: (data: T) => void;
  onState: (state: ProgressState) => void;
  signal: AbortSignal;
  visible: () => boolean;
  online: () => boolean;
  wait: (ms: number, signal: AbortSignal) => Promise<void>;
  now?: () => number;
  immediate?: boolean;
}) {
  const now = options.now ?? (() => performance.now());
  const deadline = now() + PROGRESS_WINDOW_MS;
  let data = options.initial;
  let immediate = Boolean(options.immediate);
  while (!options.signal.aborted && (immediate || options.pending(data))) {
    if (now() >= deadline) {
      options.onState("expired");
      return;
    }
    if (!immediate) await options.wait(PROGRESS_INTERVAL_MS, options.signal);
    if (options.signal.aborted) return;
    if (now() >= deadline) {
      options.onState("expired");
      return;
    }
    if (!options.visible() || !options.online()) {
      options.onState("paused");
      // A manual check also waits without issuing hidden/offline reads.
      immediate = false;
      continue;
    }
    immediate = false;
    options.onState("checking");
    data = await options.read(options.signal);
    if (options.signal.aborted) return;
    options.onData(data);
    options.onState(options.pending(data) ? "watching" : "current");
  }
}
