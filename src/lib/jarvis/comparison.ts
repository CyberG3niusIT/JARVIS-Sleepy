import type { ExecutionLocation, PrivacyMode } from "./ia";

/**
 * Phase 2 comparison baseline.
 *
 * Single source of truth so Variant A, B, C and D cannot drift apart again.
 * Nothing here is runtime data: every value is a documented design state.
 */
export const comparisonBaseline = {
  privacyMode: "NORMAL" as PrivacyMode,
  execution: "LOKAL" as ExecutionLocation,
  runtimeBound: false,
  labels: {
    runtime: "Runtime nicht gebunden",
    localModel: "Kein Modell geladen",
    modelRuntime: "LiteRT-LM",
    execution: "LOKAL",
    sleepy: "Nicht verbunden",
    sleepyHandoff: "Noch nicht implementiert",
    cloud: "Nicht konfiguriert",
    permissions: "Berechtigung erforderlich",
    backgroundService: "Design state",
  },
} as const;
