import type { BackendRuntimeState, StatusTone } from "./types";

export const runtimeStatePresentation: Record<
  BackendRuntimeState,
  { label: string; tone: StatusTone }
> = {
  STARTING: { label: "Startet", tone: "info" },
  READY: { label: "Bereit", tone: "online" },
  DEGRADED: { label: "Eingeschränkt", tone: "warning" },
  ERROR: { label: "Fehler", tone: "error" },
  STOPPED: { label: "Gestoppt", tone: "idle" },
  OFFLINE: { label: "Offline", tone: "offline" },
  NOT_IMPLEMENTED: { label: "Nicht implementiert", tone: "warning" },
};

export function presentRuntimeState(state: BackendRuntimeState) {
  return runtimeStatePresentation[state];
}
