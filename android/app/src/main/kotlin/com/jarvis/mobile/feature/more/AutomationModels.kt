package com.jarvis.mobile.feature.more

import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import java.util.concurrent.atomic.AtomicInteger

/**
 * Ported 1:1 from src/components/jarvis/screens/automation-editor.tsx. Local,
 * in-memory prototype editor state only - nothing here reaches an Android
 * scheduler or runtime. Saving only changes the Compose state held by
 * [AutomationsScreen].
 */

data class AutomationStep(val id: String, val label: String)
data class AutomationCondition(val id: String, val text: String)

/** Extract<ExecutionLocation, "LOKAL" | "SLEEPY" | "CLOUD"> from the web type. */
val automationRuntimeOptions: List<ExecutionLocation> = listOf(ExecutionLocation.LOKAL, ExecutionLocation.SLEEPY, ExecutionLocation.CLOUD)

enum class ScheduleMode { DATETIME, INTERVAL }
enum class ConditionLogic { UND, ODER }

data class AutomationDraft(
    val id: String,
    val type: AutomationType,
    val name: String = "",
    val purpose: String = "",
    val enabled: Boolean = false,
    val runtime: ExecutionLocation = ExecutionLocation.LOKAL,
    val privacy: PrivacyMode = PrivacyMode.NORMAL,
    val permissions: List<String> = emptyList(),
    val steps: List<AutomationStep> = emptyList(),
    val scheduleMode: ScheduleMode = ScheduleMode.DATETIME,
    val scheduleDateTime: String = "",
    val scheduleInterval: String = "",
    val conditionLogic: ConditionLogic = ConditionLogic.UND,
    val conditions: List<AutomationCondition> = emptyList(),
)

private val localIdSeq = AtomicInteger(0)
fun nextLocalId(prefix: String): String = "$prefix-${localIdSeq.incrementAndGet()}"

fun createEmptyDraft(type: AutomationType): AutomationDraft = AutomationDraft(id = nextLocalId("automation"), type = type)

data class RuntimeOption(val value: ExecutionLocation, val detail: String)

val automationRuntimeDetails: List<RuntimeOption> = listOf(
    RuntimeOption(ExecutionLocation.LOKAL, "Läuft auf dem Gerät, ohne Netzwerkschritt."),
    RuntimeOption(ExecutionLocation.SLEEPY, "Optionale Übergabe an die vertraute Runtime Sleepy, nur wenn verbunden und ausdrücklich freigegeben."),
    RuntimeOption(ExecutionLocation.CLOUD, "Braucht einen Cloud-Weg mit vorheriger Freigabe."),
)

data class PrivacyOption(val value: PrivacyMode, val detail: String)

val automationPrivacyOptions: List<PrivacyOption> = listOf(
    PrivacyOption(PrivacyMode.NORMAL, "Normaler Betrieb."),
    PrivacyOption(PrivacyMode.PRIVACY, "Geschützte Wahrnehmungs- und Aufnahmepfade sind gesperrt."),
    PrivacyOption(PrivacyMode.PRIVACY_LOCK, "Zusätzlich können Netzwerk-, Cloud- und externe Werkzeugpfade hart gesperrt sein."),
)

val automationPermissionOptions: List<String> = listOf(
    "Standort", "Kalender", "Kontakte", "Benachrichtigungen", "Mikrofon", "Kamera", "Bedienungshilfen (Accessibility)",
)

data class StepListCopy(val heading: String, val addLabel: String, val empty: String)

fun stepListCopy(type: AutomationType): StepListCopy = if (type == AutomationType.MACRO) {
    StepListCopy("Aktionsreihenfolge", "Aktion hinzufügen", "Noch keine Aktion angelegt. Ein Makro braucht mindestens eine Aktion.")
} else {
    StepListCopy("Schritte", "Schritt hinzufügen", "Noch kein Schritt angelegt. Mindestens ein Schritt ist nötig.")
}

fun validateDraft(draft: AutomationDraft): List<String> {
    val errors = mutableListOf<String>()
    if (draft.name.isBlank()) errors += "Ein Name ist erforderlich."
    if (draft.steps.isEmpty()) {
        errors += if (draft.type == AutomationType.MACRO) "Mindestens eine Aktion ist erforderlich." else "Mindestens ein Schritt ist erforderlich."
    }
    if (draft.type == AutomationType.SCHEDULE) {
        if (draft.scheduleMode == ScheduleMode.DATETIME && draft.scheduleDateTime.isBlank()) {
            errors += "Ein Zeitpunkt ist erforderlich, wenn kein Intervall gewählt ist."
        }
        if (draft.scheduleMode == ScheduleMode.INTERVAL && draft.scheduleInterval.isBlank()) {
            errors += "Ein Intervall ist erforderlich, wenn kein Zeitpunkt gewählt ist."
        }
    }
    if (draft.type == AutomationType.ROUTINE && draft.conditions.isEmpty()) {
        errors += "Mindestens eine Bedingung ist erforderlich."
    }
    return errors
}

fun derivedNextRun(draft: AutomationDraft): String? {
    if (draft.type != AutomationType.SCHEDULE) return null
    if (draft.scheduleMode == ScheduleMode.DATETIME && draft.scheduleDateTime.isNotBlank()) {
        return "${draft.scheduleDateTime} (aus der Eingabe berechnet, keine geplante Ausführung)"
    }
    if (draft.scheduleMode == ScheduleMode.INTERVAL && draft.scheduleInterval.isNotBlank()) {
        return "Alle ${draft.scheduleInterval} (aus der Eingabe berechnet, keine geplante Ausführung)"
    }
    return null
}

fun draftSummary(draft: AutomationDraft): String = when (draft.type) {
    AutomationType.SCHEDULE -> if (draft.scheduleMode == ScheduleMode.DATETIME) {
        draft.scheduleDateTime.ifBlank { "Kein Zeitpunkt festgelegt" }
    } else {
        draft.scheduleInterval.takeIf { it.isNotBlank() }?.let { "Alle $it" } ?: "Kein Intervall festgelegt"
    }
    AutomationType.ROUTINE -> if (draft.conditions.isNotEmpty()) {
        "${draft.conditions.size} Bedingung(en), ${draft.conditionLogic}"
    } else {
        "Keine Bedingung festgelegt"
    }
    AutomationType.MACRO -> if (draft.steps.isNotEmpty()) "${draft.steps.size} Aktion(en)" else "Keine Aktion festgelegt"
}
