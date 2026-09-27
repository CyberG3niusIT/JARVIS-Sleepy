package com.jarvis.mobile.core.model

/**
 * Information architecture, ported 1:1 from src/lib/jarvis/ia.ts.
 * The hierarchy is fixed: four bottom navigation tabs (Start, Chat, System,
 * Mehr) and one ordered destination list per tab. Nothing here is runtime
 * data; every value is a documented design-state placeholder.
 */

enum class CapabilityDecision { KEEP, MODIFY, REPLACE, NEW }

/** Brand Spec Sec.12 - Status Language. German labels are fixed wording. */
enum class SystemState {
    READY,
    LOCAL,
    SLEEPY,
    WAITING_REMOTE,
    OFFLINE,
    UNAVAILABLE,
    PERMISSION_REQUIRED,
    PRIVACY_BLOCKED,
    ERROR,
    NOT_IMPLEMENTED,
    DEGRADED,
    DESIGN_STATE,
}

val stateLabel: Map<SystemState, String> = mapOf(
    SystemState.READY to "Bereit",
    SystemState.LOCAL to "Läuft lokal",
    SystemState.SLEEPY to "Auf Sleepy",
    SystemState.WAITING_REMOTE to "Wartet auf Sleepy",
    SystemState.OFFLINE to "Offline",
    SystemState.UNAVAILABLE to "Nicht verfügbar",
    SystemState.PERMISSION_REQUIRED to "Berechtigung erforderlich",
    SystemState.PRIVACY_BLOCKED to "Durch Privacy Mode blockiert",
    SystemState.ERROR to "Fehler",
    SystemState.NOT_IMPLEMENTED to "Derzeit nicht verfügbar",
    SystemState.DEGRADED to "Degradiert",
    SystemState.DESIGN_STATE to "Nicht eingerichtet",
)

/** Brand Spec Sec.16 - Execution Location. */
enum class ExecutionLocation { LOKAL, SLEEPY, CLOUD, EXTERN }

enum class PrivacyMode { NORMAL, PRIVACY, PRIVACY_LOCK }

/** Fixed bottom navigation. Not extendable in later phases. */
enum class NavTabId { START, CHAT, SYSTEM, MORE }

data class NavTab(
    val id: NavTabId,
    val label: String,
    /** What this tab is responsible for, and what explicitly is not. */
    val purpose: String,
    val order: Int,
)

val navTabs: List<NavTab> = listOf(
    NavTab(
        id = NavTabId.START,
        label = "Start",
        purpose = "Runtime-Überblick, Privacy-Zustand, Ausführungsort, blockierende Zustände, " +
            "kurze Entscheidungsreihenfolge. Keine Verwaltung von Funktionen.",
        order = 1,
    ),
    NavTab(
        id = NavTabId.CHAT,
        label = "Chat",
        purpose = "Konversation, sichtbarer Ausführungsort pro Ergebnis, lokale Aktionsanfragen, " +
            "später Sichtbarkeit von Übergaben. Keine Systemeinstellungen.",
        order = 2,
    ),
    NavTab(
        id = NavTabId.SYSTEM,
        label = "System",
        purpose = "Technisches Kontrollzentrum von J.A.R.V.I.S Mobile.",
        order = 3,
    ),
    NavTab(
        id = NavTabId.MORE,
        label = "Mehr",
        purpose = "Sekundäre Nutzerbereiche und Produkteinstellungen.",
        order = 4,
    ),
)

enum class AreaId {
    MODELS, AGENTS, TOOLS, PERMISSIONS, PRIVACY, RUNTIMES, DEVICE, DIAGNOSTICS,
    VOICE, MEMORY, AUTOMATIONS, SETTINGS, ABOUT,
}

/** Which tab owns the destination. A destination has exactly one parent. */
enum class AreaGroup { SYSTEM, MORE }

data class ProductArea(
    val id: AreaId,
    val label: String,
    /** One line of what the area actually controls, no marketing copy. */
    val purpose: String,
    val group: AreaGroup,
    /** Position inside the parent tab, 1-based and fixed. */
    val order: Int,
    val decision: CapabilityDecision,
    /** Design-state only: how the area would report itself once bound. */
    val state: SystemState,
)

/**
 * Locked destination list. Removed OpenDroid subsystems (Finance, Food and
 * Shopping, Social suite, Gemini Nano mock, simulated screen recording,
 * browser incognito as privacy) stay deliberately absent.
 */
val productAreas: List<ProductArea> = listOf(
    ProductArea(
        id = AreaId.MODELS,
        label = "Modelle",
        purpose = "Lokale Modelldateien, LiteRT-Runtime, Download, Laden, Kompatibilität.",
        group = AreaGroup.SYSTEM,
        order = 1,
        decision = CapabilityDecision.KEEP,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.AGENTS,
        label = "Agenten",
        purpose = "Begrenzte Agenten, erlaubte Tools, Limits, Aufgabenzustand.",
        group = AreaGroup.SYSTEM,
        order = 2,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.TOOLS,
        label = "Tools",
        purpose = "Android-Aktionen, Bedienungshilfen-Aktionen, Skills und Tools mit Zustand.",
        group = AreaGroup.SYSTEM,
        order = 3,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.PERMISSIONS,
        label = "Berechtigungen",
        purpose = "Echter Android-Berechtigungsstatus und Auswirkung auf Fähigkeiten.",
        group = AreaGroup.SYSTEM,
        order = 4,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.PERMISSION_REQUIRED,
    ),
    ProductArea(
        id = AreaId.PRIVACY,
        label = "Privacy",
        purpose = "NORMAL / PRIVACY / PRIVACY_LOCK und Regeln für geschützte Fähigkeiten.",
        group = AreaGroup.SYSTEM,
        order = 5,
        decision = CapabilityDecision.NEW,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.RUNTIMES,
        label = "Runtimes",
        purpose = "Dieses Telefon, später Sleepy: Vertrauen, Kopplung, Übergabezustand.",
        group = AreaGroup.SYSTEM,
        order = 6,
        decision = CapabilityDecision.NEW,
        state = SystemState.NOT_IMPLEMENTED,
    ),
    ProductArea(
        id = AreaId.DEVICE,
        label = "Gerät",
        purpose = "Lokale Android- und Geräteinformationen sowie Zustand des JARVIS-Dienstes.",
        group = AreaGroup.SYSTEM,
        order = 7,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.DIAGNOSTICS,
        label = "Logs & Diagnose",
        purpose = "Ausführungshistorie, Crash-Logs, redigierte Diagnose.",
        group = AreaGroup.SYSTEM,
        order = 8,
        decision = CapabilityDecision.KEEP,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.VOICE,
        label = "Voice",
        purpose = "Wake Word, Spracherkennung, Sprachausgabe, Mikrofonzustand.",
        group = AreaGroup.MORE,
        order = 1,
        decision = CapabilityDecision.REPLACE,
        state = SystemState.NOT_IMPLEMENTED,
    ),
    ProductArea(
        id = AreaId.MEMORY,
        label = "Memory",
        purpose = "Arbeitskontext, kürzlich, Kandidaten, bestätigte Einträge, Herkunft.",
        group = AreaGroup.MORE,
        order = 2,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.AUTOMATIONS,
        label = "Automationen",
        purpose = "Makros, Zeitpläne, Routinen.",
        group = AreaGroup.MORE,
        order = 3,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.SETTINGS,
        label = "Einstellungen",
        purpose = "Sprache, Darstellung, Speicher, Hintergrunddienst, allgemeine Konfiguration.",
        group = AreaGroup.MORE,
        order = 4,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    ProductArea(
        id = AreaId.ABOUT,
        label = "Über J.A.R.V.I.S",
        purpose = "Version, Lizenzen, Produktinformationen.",
        group = AreaGroup.MORE,
        order = 5,
        decision = CapabilityDecision.KEEP,
        state = SystemState.DESIGN_STATE,
    ),
)

val areaById: Map<AreaId, ProductArea> = productAreas.associateBy { it.id }

/** Destinations of one tab in their fixed order. */
fun areasInGroup(group: AreaGroup): List<ProductArea> =
    productAreas.filter { it.group == group }.sortedBy { it.order }

val systemDestinations: List<ProductArea> = areasInGroup(AreaGroup.SYSTEM)
val moreDestinations: List<ProductArea> = areasInGroup(AreaGroup.MORE)

/**
 * Underlying capability data. Content for the Tools destination, not a
 * top-level product area of its own.
 */
data class CapabilityRow(
    val name: String,
    val detail: String,
    val execution: ExecutionLocation,
    val decision: CapabilityDecision,
    val state: SystemState,
    /**
     * Truthful prototype label where the audited state alone would read as
     * absence. Set here so every capability view shows the same wording.
     */
    val statusLabel: String? = null,
)

val capabilityRows: List<CapabilityRow> = listOf(
    CapabilityRow(
        name = "Android-Aktionen",
        detail = "Apps, Systemsteuerung, Medien, Navigation",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
    CapabilityRow(
        name = "Accessibility-Automation",
        detail = "Generische App-Steuerung über Bedienungshilfen",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.KEEP,
        state = SystemState.PERMISSION_REQUIRED,
    ),
    CapabilityRow(
        name = "Lokales Modell",
        detail = "LiteRT-LM Runtime, Modellverwaltung",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.KEEP,
        state = SystemState.DESIGN_STATE,
    ),
    CapabilityRow(
        name = "Bildschirmanalyse",
        detail = "Screen Understanding, OCR",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.PERMISSION_REQUIRED,
    ),
    CapabilityRow(
        name = "Benachrichtigungen",
        detail = "Listener, Auto-Reply-Regeln",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.PERMISSION_REQUIRED,
    ),
    CapabilityRow(
        name = "Spracherkennung",
        detail = "Wake Word, STT, TTS",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.REPLACE,
        state = SystemState.NOT_IMPLEMENTED,
    ),
    CapabilityRow(
        name = "Privilegierte Ausführung",
        detail = "Shizuku / Shell, begrenzt und protokolliert",
        execution = ExecutionLocation.LOKAL,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
        statusLabel = "Status nicht verfügbar",
    ),
    CapabilityRow(
        name = "Handoff an Sleepy",
        detail = "Begrenztes Aufgabenpaket, freigegebener Kontext",
        execution = ExecutionLocation.SLEEPY,
        decision = CapabilityDecision.NEW,
        state = SystemState.NOT_IMPLEMENTED,
    ),
    CapabilityRow(
        name = "Cloud-Provider",
        detail = "Nur nach ausdrücklicher Freigabe",
        execution = ExecutionLocation.CLOUD,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
        statusLabel = "Nicht konfiguriert",
    ),
    CapabilityRow(
        name = "MCP-Server",
        detail = "Externe Werkzeuge über MCP",
        execution = ExecutionLocation.EXTERN,
        decision = CapabilityDecision.MODIFY,
        state = SystemState.DESIGN_STATE,
    ),
)

/**
 * Condensed form of the ladder for Start. Same meaning, fewer rows; the full
 * eight-step ladder stays in System.
 */
val routingLadderShort: List<String> = listOf(
    "Android-Aktion",
    "Lokaler Skill oder Tool",
    "Lokales Modell",
    "Vertrauenswürdige Runtime",
    "Freigegebener Cloud-Fallback",
)

/** Local-first routing ladder, Product Brief Sec.7. Shown, not simulated. */
val routingLadder: List<String> = listOf(
    "Deterministische Android-Aktion",
    "Lokaler Skill",
    "Lokales Tool",
    "Kleines lokales Modell",
    "Großes lokales Modell",
    "Lokaler Planer / begrenzter Agent",
    "Handoff an vertraute Runtime",
    "Freigegebener Cloud-Fallback",
)
