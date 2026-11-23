import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

export interface AsyncState<T> { data: T | null; error: string | null; loading: boolean }

/** Run `load` whenever `deps` change; a newer call cancels the older one so answers never arrive out of order. */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    setState((s) => ({ ...s, error: null, loading: true }));
    load(ctl.signal).then(
      (data) => !ctl.signal.aborted && setState({ data, error: null, loading: false }),
      (err) => {
        if (ctl.signal.aborted || (err as Error).name === "AbortError") return;
        setState((s) => ({ data: s.data, error: err instanceof ApiError ? err.message : String(err), loading: false }));
      },
    );
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}
