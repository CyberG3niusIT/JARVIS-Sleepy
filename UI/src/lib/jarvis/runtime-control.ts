import { invoke as tauriInvoke, isTauri } from "@tauri-apps/api/core";
import type { BackendRuntimeState, RuntimeComponent } from "./types";

/**
 * Runtime control contract (transport-neutral).
 *
 * Runtime state and lifecycle are NOT part of the backend data API (`jarvis_web.py` cannot report
 * STOPPED reliably nor restart itself). The planned owner is a native supervisor:
 *
 *   JARVIS.exe / Tauri (Rust) -> Runtime Supervisor / Native Control Plane -> WSL2 -> JARVIS backend
 *
 * The React UI only *reads* what the supervisor reports and *asks* it to start/stop/restart. It
 * never decides a state itself and there is deliberately no generic "run command" method in this
 * contract. In the native app, a closed Rust host bridge invokes the fixed PowerShell entry point.
 *
 * A native bridge implements `RuntimeControlTransport` and is installed once at startup with
 * `setRuntimeControlTransport()`. Until then the default below reports NOT_IMPLEMENTED with all
 * lifecycle capabilities off. Nothing else in the UI changes when the bridge arrives.
 */

export const runtimeControlStates: readonly BackendRuntimeState[] = [
  "STARTING",
  "READY",
  "DEGRADED",
  "ERROR",
  "STOPPED",
  "OFFLINE",
  "NOT_IMPLEMENTED",
];

export type RuntimeAction = "start" | "stop" | "restart";

/** What the supervisor currently allows (e.g. `start` only while STOPPED). Decided by the supervisor. */
export interface RuntimeControlCapabilities {
  start: boolean;
  stop: boolean;
  restart: boolean;
}

/** One reading of the runtime, produced by the supervisor. */
export interface RuntimeControlSnapshot {
  state: BackendRuntimeState;
  /** Human-readable reasons, meaningful for DEGRADED (may be empty otherwise). */
  degradedReasons: string[];
  /** ISO 8601 time of the supervisor's own observation. */
  updatedAt: string;
  components: RuntimeComponent[];
  capabilities: RuntimeControlCapabilities;
  detail?: string;
}

/** Acknowledgement of a lifecycle request. It is NOT a state: the state comes from the next reading. */
export interface RuntimeActionResult {
  accepted: boolean;
  message: string;
}

export interface RuntimeControlTransport {
  getRuntime(): Promise<RuntimeControlSnapshot>;
  start(): Promise<RuntimeActionResult>;
  stop(): Promise<RuntimeActionResult>;
  restart(): Promise<RuntimeActionResult>;
}

const noCapabilities: RuntimeControlCapabilities = { start: false, stop: false, restart: false };

export function notImplementedRuntime(detail: string): RuntimeControlSnapshot {
  return {
    state: "NOT_IMPLEMENTED",
    degradedReasons: [],
    // Only the local time of this reading; there is no supervisor observation to report.
    updatedAt: new Date().toISOString(),
    components: [],
    capabilities: { ...noCapabilities },
    detail,
  };
}

const unavailableAction = async (): Promise<RuntimeActionResult> => ({
  accepted: false,
  message: "Runtime-Supervisor im Browsermodus nicht verfügbar.",
});

/** Browser-only default; the Tauri executable installs the native bridge automatically. */
export const unavailableRuntimeControl: RuntimeControlTransport = {
  async getRuntime() {
    return notImplementedRuntime("Runtime-Supervisor nur in der Desktop-App verfügbar");
  },
  start: unavailableAction,
  stop: unavailableAction,
  restart: unavailableAction,
};

let activeControl: RuntimeControlTransport = unavailableRuntimeControl;

/** Closed Tauri command bridge to JARVIS-Runtime.ps1; never accepts a shell command string. */
export const tauriRuntimeControl: RuntimeControlTransport = {
  async getRuntime() {
    if (!isTauri()) throw new Error("Tauri-Bridge nicht verfügbar");
    return tauriInvoke<RuntimeControlSnapshot>("runtime_get");
  },
  async start() {
    if (!isTauri()) throw new Error("Tauri-Bridge nicht verfügbar");
    return tauriInvoke<RuntimeActionResult>("runtime_start");
  },
  async stop() {
    if (!isTauri()) throw new Error("Tauri-Bridge nicht verfügbar");
    return tauriInvoke<RuntimeActionResult>("runtime_stop");
  },
  async restart() {
    if (!isTauri()) throw new Error("Tauri-Bridge nicht verfügbar");
    return tauriInvoke<RuntimeActionResult>("runtime_restart");
  },
};

function installTauriRuntimeControl() {
  if (isTauri() && activeControl === unavailableRuntimeControl) activeControl = tauriRuntimeControl;
}

installTauriRuntimeControl();

export function setRuntimeControlTransport(transport: RuntimeControlTransport) {
  activeControl = transport;
}

export function getRuntimeControl() {
  installTauriRuntimeControl();
  return activeControl;
}

/** Opens the native folder picker and persists a validated full JARVIS checkout. */
export async function chooseRuntimeRepositoryRoot(): Promise<string | null> {
  if (!isTauri()) throw new Error("Repository-Konfiguration ist nur in der Desktop-App verfügbar");
  return tauriInvoke<string | null>("runtime_choose_repository_root");
}

export async function getRuntimeRepositoryRoot(): Promise<string | null> {
  if (!isTauri()) return null;
  return tauriInvoke<string | null>("runtime_repository_root");
}

const maxItems = 64;
const maxText = 500;
const isoDate = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
const okText = (value: unknown): value is string =>
  typeof value === "string" && value.length <= maxText;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/**
 * Validates a reading from an untrusted bridge. Anything that does not match the contract is not
 * interpreted or repaired: it becomes NOT_IMPLEMENTED with lifecycle capabilities off.
 */
export function parseRuntimeSnapshot(raw: unknown): RuntimeControlSnapshot {
  const invalid = (why: string) =>
    notImplementedRuntime(`ungültige Antwort des Supervisors (${why})`);
  if (!isRecord(raw)) return invalid("kein Objekt");
  const state = raw["state"];
  if (typeof state !== "string" || !runtimeControlStates.includes(state as BackendRuntimeState))
    return invalid("unbekannter state");
  const reasons = raw["degradedReasons"];
  if (!Array.isArray(reasons) || reasons.length > maxItems || !reasons.every(okText))
    return invalid("degradedReasons");
  const updatedAt = raw["updatedAt"];
  if (
    typeof updatedAt !== "string" ||
    !isoDate.test(updatedAt) ||
    Number.isNaN(Date.parse(updatedAt))
  )
    return invalid("updatedAt");
  const rawComponents = raw["components"];
  if (!Array.isArray(rawComponents) || rawComponents.length > maxItems)
    return invalid("components");
  const seenIds = new Set<string>();
  const components: RuntimeComponent[] = [];
  for (const item of rawComponents) {
    if (!isRecord(item)) return invalid("component");
    const id = item["id"];
    const name = item["name"];
    const componentState = item["state"];
    const detail = item["detail"];
    if (
      !okText(id) ||
      seenIds.has(id) ||
      !okText(name) ||
      typeof componentState !== "string" ||
      !runtimeControlStates.includes(componentState as BackendRuntimeState) ||
      (detail !== undefined && !okText(detail))
    )
      return invalid("component");
    seenIds.add(id);
    components.push({
      id,
      name,
      state: componentState as BackendRuntimeState,
      ...(detail !== undefined ? { detail } : {}),
    });
  }
  const caps = raw["capabilities"];
  if (
    !isRecord(caps) ||
    typeof caps["start"] !== "boolean" ||
    typeof caps["stop"] !== "boolean" ||
    typeof caps["restart"] !== "boolean"
  )
    return invalid("capabilities");
  const detail = raw["detail"];
  if (detail !== undefined && !okText(detail)) return invalid("detail");
  return {
    state: state as BackendRuntimeState,
    degradedReasons: reasons as string[],
    updatedAt,
    components,
    capabilities: { start: caps["start"], stop: caps["stop"], restart: caps["restart"] },
    ...(detail !== undefined ? { detail } : {}),
  };
}
