import { useCallback, useEffect, useRef, useState } from "react";
import { jarvisAdapter } from "./adapter";
import type { AdapterResult, Capability, JarvisSnapshot, RuntimeEnvelope } from "./types";

const initial: RuntimeEnvelope<JarvisSnapshot> = {
  phase: "loading",
  updatedAt: new Date(0).toISOString(),
};
/**
 * The backend has no push channel for runtime state (only /ws/dashboard, which pushes metric rows),
 * so the production adapter is refreshed by polling. The prototype adapter is static: no polling.
 */
const refreshIntervalMs = 15000;

export function useJarvis() {
  const [runtime, setRuntime] = useState(initial);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const mounted = useRef(true);
  const inFlight = useRef<Promise<void> | null>(null);

  const reload = useCallback((): Promise<void> => {
    if (inFlight.current) return inFlight.current;
    setIsRefreshing(true);
    const run = jarvisAdapter
      .getSnapshot()
      .then((next) => {
        if (mounted.current) setRuntime(next);
      })
      .catch(() => {
        if (mounted.current)
          setRuntime({
            phase: "error",
            message: "Runtime-Daten konnten nicht geladen werden.",
            updatedAt: new Date().toISOString(),
          });
      })
      .finally(() => {
        inFlight.current = null;
        if (mounted.current) setIsRefreshing(false);
      });
    inFlight.current = run;
    return run;
  }, []);

  /** Runs a backend action through the adapter, then re-reads state. Never assumes the outcome. */
  const execute = useCallback(
    async (capability: Capability, targetId?: string): Promise<AdapterResult> => {
      const result = await jarvisAdapter.execute(capability, targetId);
      // A refresh that started before the action would show pre-action state: wait for it,
      // then read again so the state shown always comes from after the action.
      if (inFlight.current) await inFlight.current;
      await reload();
      return result;
    },
    [reload],
  );

  useEffect(() => {
    mounted.current = true;
    void reload();
    const timer =
      jarvisAdapter.mode === "production"
        ? window.setInterval(() => {
            if (document.visibilityState === "visible") void reload();
          }, refreshIntervalMs)
        : undefined;
    const onVisible = () => {
      if (document.visibilityState === "visible") void reload();
    };
    if (timer !== undefined) document.addEventListener("visibilitychange", onVisible);
    return () => {
      mounted.current = false;
      if (timer !== undefined) window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [reload]);

  return { runtime, adapter: jarvisAdapter, isRefreshing, reload, execute };
}
