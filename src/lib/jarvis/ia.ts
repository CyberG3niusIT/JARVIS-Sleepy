/**
 * JARVIS Mobile - Information Architecture (Phase 4, locked)
 *
 * Derived from:
 *   JARVIS_MOBILE_PRODUCT_BRIEF.md   (product areas, runtime model, states)
 *   JARVIS_MOBILE_CAPABILITIES.md    (KEEP / MODIFY / REPLACE / NEW)
 *
 * The hierarchy is fixed: four bottom navigation tabs (Start, Chat, System,
 * Mehr) and one ordered destination list per tab. Every later screen has
 * exactly one place here, so no duplicate routes can appear.
 *
 * Nothing here is runtime data. Every operational value shown in the
 * prototypes is a documented design-state placeholder, never a live value.
 * Maps 1:1 onto a Compose navigation graph + sealed capability model.
 */

export type CapabilityDecision = "KEEP" | "MODIFY" | "REPLACE" | "NEW";

/** Brand Spec §12 - Status Language. German labels are fixed wording. */
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
  design_state: "Entwurfszustand",
};

/** Brand Spec §16 - Execution Location. */
export type ExecutionLocation = "LOKAL" | "SLEEPY" | "CLOUD" | "EXTERN";

export type PrivacyMode = "NORMAL" | "PRIVACY" | "PRIVACY_LOCK";

/** Fixed bottom navigation. Not extendable in later phases. */
export type NavTabId = "start" | "chat" | "system" | "more";

export interface NavTab {
  id: NavTabId;
  label: string;
  /** What this tab is responsible for, and what explicitly is not. */
  purpose: string;
  order: number;
}

export const navTabs: NavTab[] = [
  {
    id: "start",
    label: "Start",
    purpose:
      "Runtime-Überblick, Privacy-Zustand, Ausführungsort, blockierende Zustände, kurze Entscheidungsreihenfolge. Keine Verwaltung von Funktionen.",
    order: 1,
  },
  {
    id: "chat",
    label: "Chat",
    purpose:
      "Konversation, sichtbarer Ausführungsort pro Ergebnis, lokale Aktionsanfragen, später Sichtbarkeit von Übergaben. Keine Systemeinstellungen.",
    order: 2,
  },
  {
    id: "system",
    label: "System",
    purpose: "Technisches Kontrollzentrum von J.A.R.V.I.S Mobile.",
    order: 3,
  },
  {
    id: "more",
    label: "Mehr",
    purpose: "Sekundäre Nutzerbereiche und Produkteinstellungen.",
    order: 4,
  },
];

export type AreaId =
  | "models"
  | "agents"
  | "tools"
  | "permissions"
  | "privacy"
  | "runtimes"
  | "device"
  | "diagnostics"
  | "voice"
  | "memory"
  | "automations"
  | "settings"
  | "about";

/** Which tab owns the destination. A destination has exactly one parent. */
export type AreaGroup = Extract<NavTabId, "system" | "more">;

export interface ProductArea {
  id: AreaId;
  label: string;
  /** One line of what the area actually controls, no marketing copy. */
  purpose: string;
  /** Parent tab in the locked hierarchy. */
  group: AreaGroup;
  /** Position inside the parent tab, 1-based and fixed. */
  order: number;
  decision: CapabilityDecision;
  /** Design-state only: how the area would report itself once bound. */
  state: SystemState;
}

/**
 * Locked destination list. Removed OpenDroid subsystems (Finance, Food and
 * Shopping, Social suite, Gemini Nano mock, simulated screen recording,
 * browser incognito as privacy) stay deliberately absent.
 */
export const productAreas: ProductArea[] = [
  {
    id: "models",
    label: "Modelle",
    purpose: "Lokale Modelldateien, LiteRT-Runtime, Download, Laden, Kompatibilität.",
    group: "system",
    order: 1,
    decision: "KEEP",
    state: "design_state",
  },
  {
    id: "agents",
    label: "Agenten",
    purpose: "Begrenzte Agenten, erlaubte Tools, Limits, Aufgabenzustand.",
    group: "system",
    order: 2,
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "tools",
    label: "Tools",
    purpose: "Android-Aktionen, Bedienungshilfen-Aktionen, Skills und Tools mit Zustand.",
    group: "system",
    order: 3,
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "permissions",
    label: "Berechtigungen",
    purpose: "Echter Android-Berechtigungsstatus und Auswirkung auf Fähigkeiten.",
    group: "system",
    order: 4,
    decision: "MODIFY",
    state: "permission_required",
  },
  {
    id: "privacy",
    label: "Privacy",
    purpose: "NORMAL / PRIVACY / PRIVACY_LOCK und Regeln für geschützte Fähigkeiten.",
    group: "system",
    order: 5,
    decision: "NEW",
    state: "design_state",
  },
  {
    id: "runtimes",
    label: "Runtimes",
    purpose: "Dieses Telefon, später Sleepy: Vertrauen, Kopplung, Übergabezustand.",
    group: "system",
    order: 6,
    decision: "NEW",
    state: "not_implemented",
  },
  {
    id: "device",
    label: "Gerät",
    purpose: "Lokale Android- und Geräteinformationen sowie Zustand des JARVIS-Dienstes.",
    group: "system",
    order: 7,
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "diagnostics",
    label: "Logs & Diagnose",
    purpose: "Ausführungshistorie, Crash-Logs, redigierte Diagnose.",
    group: "system",
    order: 8,
    decision: "KEEP",
    state: "design_state",
  },
  {
    id: "voice",
    label: "Voice",
    purpose: "Wake Word, Spracherkennung, Sprachausgabe, Mikrofonzustand.",
    group: "more",
    order: 1,
    decision: "REPLACE",
    state: "not_implemented",
  },
  {
    id: "memory",
    label: "Memory",
    purpose: "Arbeitskontext, kürzlich, Kandidaten, bestätigte Einträge, Herkunft.",
    group: "more",
    order: 2,
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "automations",
    label: "Automationen",
    purpose: "Makros, Zeitpläne, Routinen.",
    group: "more",
    order: 3,
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "settings",
    label: "Einstellungen",
    purpose: "Sprache, Darstellung, Speicher, Hintergrunddienst, allgemeine Konfiguration.",
    group: "more",
    order: 4,
    decision: "MODIFY",
    state: "design_state",
  },
  {
    id: "about",
    label: "Über J.A.R.V.I.S",
    purpose: "Version, Lizenzen, Produktinformationen.",
    group: "more",
    order: 5,
    decision: "KEEP",
    state: "design_state",
  },
];

export const areaById = Object.fromEntries(
  productAreas.map((a) => [a.id, a]),
) as Record<AreaId, ProductArea>;

/** Destinations of one tab in their fixed order. */
export function areasInGroup(group: AreaGroup): ProductArea[] {
  return productAreas
    .filter((a) => a.group === group)
    .sort((a, b) => a.order - b.order);
}

export const systemDestinations = areasInGroup("system");
export const moreDestinations = areasInGroup("more");

/**
 * Underlying capability data. Content for the Tools destination, not a
 * top-level product area of its own.
 */
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
    state: "permission_required",
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

/**
 * Condensed form of the ladder for Start. Same meaning, fewer rows; the full
 * eight-step ladder stays in System.
 */
export const routingLadderShort = [
  "Android-Aktion",
  "Lokaler Skill oder Tool",
  "Lokales Modell",
  "Vertrauenswürdige Runtime",
  "Freigegebener Cloud-Fallback",
];

/** Local-first routing ladder, Product Brief §7. Shown, not simulated. */
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
