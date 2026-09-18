/**
 * JARVIS Mobile — Information Architecture (Phase 1)
 *
 * Derived from:
 *   JARVIS_MOBILE_PRODUCT_BRIEF.md   (product areas, runtime model, states)
 *   JARVIS_MOBILE_CAPABILITIES.md    (KEEP / MODIFY / REPLACE / REMOVE / NEW)
 *
 * Nothing here is runtime data. Every operational value shown in the
 * prototypes is a documented design-state placeholder, never a live value.
 * Maps 1:1 onto a Compose navigation graph + sealed capability model.
 */

export type CapabilityDecision = "KEEP" | "MODIFY" | "REPLACE" | "NEW";

/** Brand Spec §12 — Status Language. German labels are fixed wording. */
export type SystemState =
  | "ready"
  | "local"
  | "sleepy"
  | "waiting_remote"
  | "offline"
  | "unavailable"
  | "permission_required"
  | "privacy_blocked"
  | "error"
  | "not_implemented"
  | "degraded"
  | "design_state";

export const stateLabel: Record<SystemState, string> = {
  ready: "Bereit",
  local: "Läuft lokal",
  sleepy: "Auf Sleepy",
  waiting_remote: "Wartet auf Sleepy",
  offline: "Offline",
  unavailable: "Nicht verfügbar",
  permission_required: "Berechtigung erforderlich",
  privacy_blocked: "Durch Privacy Mode blockiert",
  error: "Fehler",
  not_implemented: "Noch nicht implementiert",
  degraded: "Degradiert",
  design_state: "Design state",
};

/** Brand Spec §16 — Execution Location. */
export type ExecutionLocation = "LOKAL" | "SLEEPY" | "CLOUD" | "EXTERN";

export type PrivacyMode = "NORMAL" | "PRIVACY" | "PRIVACY_LOCK";

export type AreaId =
  | "start"
  | "chat"
  | "voice"
  | "models"
  | "capabilities"
  | "agents"
  | "automations"
  | "memory"
  | "permissions"
  | "privacy"
  | "runtimes"
  | "diagnostics"
  | "settings";

export type AreaTier = "primary" | "secondary" | "settings";

export interface ProductArea {
  id: AreaId;
  label: string;
  /** One line of what the area actually controls — no marketing copy. */
  purpose: string;
  tier: AreaTier;
  decision: CapabilityDecision;
  /** Design-state only: how the area would report itself once bound. */
  state: SystemState;
}

/**
 * Top-level product areas. Only real capability groups from the audit.
 * Removed subsystems (Finance, Food/Shopping, Social suite, Gemini Nano mock,
 * simulated screen recording, browser incognito) are deliberately absent.
 */
export const productAreas: ProductArea[] = [
  {
    id: "start",
    label: "Start",
    purpose: "Runtime-Übersicht: was läuft, wo es läuft, was blockiert ist.",
    tier: "primary",
    decision: "NEW",
    state: "design_state",
  },
  {
    id: "chat",
    label: "Chat",
    purpose: "Lokale Konversation mit sichtbarem Ausführungsort pro Antwort.",
    tier: "primary",
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "capabilities",
    label: "Fähigkeiten",
    purpose: "Aktionen, Tools und Skills mit Berechtigung und Ausführungsort.",
    tier: "primary",
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "voice",
    label: "Voice",
    purpose: "Wake Word, Spracherkennung, Sprachausgabe, Mikrofonzustand.",
    tier: "secondary",
    decision: "REPLACE",
    state: "not_implemented",
  },
  {
    id: "models",
    label: "Modelle",
    purpose: "Lokale Modelldateien, Runtime, Ladezustand, Speicherbedarf.",
    tier: "secondary",
    decision: "KEEP",
    state: "design_state",
  },
  {
    id: "agents",
    label: "Agenten",
    purpose: "Begrenzte Ausführungseinheiten mit erlaubten Tools und Limits.",
    tier: "secondary",
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "automations",
    label: "Automationen",
    purpose: "Makros, Zeitpläne und erkannte Routinen.",
    tier: "secondary",
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "memory",
    label: "Memory",
    purpose: "Arbeitskontext, Kandidaten, bestätigte Einträge, Herkunft.",
    tier: "secondary",
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "permissions",
    label: "Berechtigungen",
    purpose: "Android-Berechtigungen als Fähigkeiten, mit echtem Systemstatus.",
    tier: "secondary",
    decision: "MODIFY",
    state: "permission_required",
  },
  {
    id: "privacy",
    label: "Privacy",
    purpose: "NORMAL / PRIVACY / PRIVACY_LOCK als harte Architekturgrenze.",
    tier: "secondary",
    decision: "NEW",
    state: "design_state",
  },
  {
    id: "runtimes",
    label: "Runtimes",
    purpose: "Vertrauenswürdige Laufzeiten und begrenzte Handoffs an Sleepy.",
    tier: "secondary",
    decision: "NEW",
    state: "not_implemented",
  },
  {
    id: "diagnostics",
    label: "Logs & Diagnose",
    purpose: "Ausführungshistorie, Crash-Logs, redigierte Protokolle.",
    tier: "settings",
    decision: "KEEP",
    state: "design_state",
  },
  {
    id: "settings",
    label: "Einstellungen",
    purpose: "Sprache, Darstellung, Speicher, Hintergrunddienst, Über JARVIS.",
    tier: "settings",
    decision: "MODIFY",
    state: "design_state",
  },
];

export const areaById = Object.fromEntries(
  productAreas.map((a) => [a.id, a]),
) as Record<AreaId, ProductArea>;

/** Capability rows used by the System/Fähigkeiten view in every variant. */
export interface CapabilityRow {
  name: string;
  detail: string;
  execution: ExecutionLocation;
  decision: CapabilityDecision;
  state: SystemState;
}

export const capabilityRows: CapabilityRow[] = [
  {
    name: "Android-Aktionen",
    detail: "Apps, Systemsteuerung, Medien, Navigation",
    execution: "LOKAL",
    decision: "MODIFY",
    state: "design_state",
  },
  {
    name: "Accessibility-Automation",
    detail: "Generische App-Steuerung über Bedienungshilfen",
    execution: "LOKAL",
    decision: "KEEP",
    state: "permission_required",
  },
  {
    name: "Lokales Modell",
    detail: "LiteRT-LM Runtime, Modellverwaltung",
    execution: "LOKAL",
    decision: "KEEP",
    state: "design_state",
  },
  {
    name: "Bildschirmanalyse",
    detail: "Screen Understanding, OCR",
    execution: "LOKAL",
    decision: "MODIFY",
    state: "privacy_blocked",
  },
  {
    name: "Benachrichtigungen",
    detail: "Listener, Auto-Reply-Regeln",
    execution: "LOKAL",
    decision: "MODIFY",
    state: "permission_required",
  },
  {
    name: "Spracherkennung",
    detail: "Wake Word, STT, TTS",
    execution: "LOKAL",
    decision: "REPLACE",
    state: "not_implemented",
  },
  {
    name: "Privilegierte Ausführung",
    detail: "Shizuku / Shell, begrenzt und protokolliert",
    execution: "LOKAL",
    decision: "MODIFY",
    state: "unavailable",
  },
  {
    name: "Handoff an Sleepy",
    detail: "Begrenztes Aufgabenpaket, freigegebener Kontext",
    execution: "SLEEPY",
    decision: "NEW",
    state: "not_implemented",
  },
  {
    name: "Cloud-Provider",
    detail: "Nur nach ausdrücklicher Freigabe",
    execution: "CLOUD",
    decision: "MODIFY",
    state: "unavailable",
  },
  {
    name: "MCP-Server",
    detail: "Externe Werkzeuge über MCP",
    execution: "EXTERN",
    decision: "MODIFY",
    state: "not_implemented",
  },
];

/** Local-first routing ladder — Product Brief §7. Shown, not simulated. */
export const routingLadder = [
  "Deterministische Android-Aktion",
  "Lokaler Skill",
  "Lokales Tool",
  "Kleines lokales Modell",
  "Großes lokales Modell",
  "Lokaler Planer / begrenzter Agent",
  "Handoff an vertraute Runtime",
  "Freigegebener Cloud-Fallback",
];
