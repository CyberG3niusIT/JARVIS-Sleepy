package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.SystemState

/** Ported 1:1 from src/components/jarvis/screens/agents-screen.tsx. */

/** Local, demo-only task lifecycle state. Never bound to a real scheduler. */
enum class AgentTaskState { RUNNING, WAITING_REMOTE, COMPLETED, FAILED, CANCELLED }

val agentTaskStateLabel: Map<AgentTaskState, String> = mapOf(
    AgentTaskState.RUNNING to "Läuft",
    AgentTaskState.WAITING_REMOTE to "Wartet auf Sleepy",
    AgentTaskState.COMPLETED to "Abgeschlossen",
    AgentTaskState.FAILED to "Fehlgeschlagen",
    AgentTaskState.CANCELLED to "Abgebrochen",
)

val agentTaskStateTone: Map<AgentTaskState, SystemState> = mapOf(
    AgentTaskState.RUNNING to SystemState.LOCAL,
    AgentTaskState.WAITING_REMOTE to SystemState.WAITING_REMOTE,
    AgentTaskState.COMPLETED to SystemState.READY,
    AgentTaskState.FAILED to SystemState.ERROR,
    AgentTaskState.CANCELLED to SystemState.OFFLINE,
)

/** Compact record of a single tool call, for the tool-activity summary only. */
data class ToolActivityEntry(val tool: String, val summary: String)

/** Reusable entry for future real agents. */
data class AgentEntry(
    val id: String,
    val name: String,
    val purpose: String,
    /** Concrete goal of the current task, distinct from the general purpose. */
    val goal: String,
    val state: SystemState,
    /** Tools the agent may call, never wider than the calling context. */
    val allowedTools: List<String>,
    val runtime: ExecutionLocation,
    val privacyContext: PrivacyMode,
    val currentTask: String? = null,
    val taskState: AgentTaskState,
    val maxSteps: Int? = null,
    val currentStep: Int? = null,
    val timeoutSeconds: Int? = null,
    /** Context explicitly approved for the task, never widened by the agent. */
    val approvedContext: List<String> = emptyList(),
    val expectedResult: String? = null,
    val lastResult: String? = null,
    val errorReason: String? = null,
    val toolActivity: List<ToolActivityEntry> = emptyList(),
    val startedAt: String? = null,
    val updatedAt: String? = null,
)

val agentModel: List<Pair<String, String>> = listOf(
    "Begrenztes Ziel" to "Eine klar umrissene Aufgabe je Agent.",
    "Erlaubte Tools" to "Nur ausdrücklich freigegebene Werkzeuge.",
    "Privacy-Kontext" to "Der Modus des Aufrufkontexts gilt weiter.",
    "Schrittlimit" to "Maximale Anzahl an Planungs- und Ausführungsschritten.",
    "Zeitlimit" to "Harte Obergrenze für die Laufzeit einer Aufgabe.",
    "Ausführungsruntime" to "Lokal, sofern keine Übergabe freigegeben ist.",
)

val agentSafetyBounds: List<String> = listOf(
    "Keine Rechteausweitung über den Aufrufkontext hinaus.",
    "Keine automatische Cloud-Freigabe.",
    "Keine Tool-Nutzung außerhalb des erlaubten Kontexts.",
    "Abbruch bei Grenzverletzung oder erreichtem Limit.",
)

/** Example task shown only inside the Zustandsdemonstration section. */
val demoAgent = AgentEntry(
    id = "demo-agent-1",
    name = "Beispiel-Agent",
    purpose = "Terminvorschlag aus einer Chat-Anfrage ableiten.",
    goal = "Drei passende Terminvorschläge für ein Treffen nächste Woche finden.",
    state = SystemState.LOCAL,
    allowedTools = listOf("Kalenderlesezugriff", "Textantwort verfassen"),
    runtime = ExecutionLocation.LOKAL,
    privacyContext = PrivacyMode.NORMAL,
    currentTask = "Terminvorschlag erstellen",
    taskState = AgentTaskState.RUNNING,
    maxSteps = 6,
    currentStep = 3,
    timeoutSeconds = 90,
    approvedContext = listOf("Aktueller Chat-Verlauf", "Kalendereinträge der laufenden Woche"),
    expectedResult = "Liste mit drei Terminvorschlägen inklusive Begründung.",
    toolActivity = listOf(
        ToolActivityEntry("Kalenderlesezugriff", "Verfügbare Zeitfenster der Woche gelesen."),
        ToolActivityEntry("Textantwort verfassen", "Entwurf für Terminvorschlag erstellt."),
    ),
    startedAt = "vor 2 Minuten",
    updatedAt = "vor 12 Sekunden",
)
