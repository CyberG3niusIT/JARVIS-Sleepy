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

/**
 * Flat string encoding for [AutomationDraft], used by every `rememberSaveable`
 * that needs to survive configuration changes AND process death (rotation,
 * activity recreation): a single [String] is unconditionally Bundle-safe,
 * unlike a nested `List<List<Any>>`. Shared by the editor's own draft state
 * ([AutomationEditorScreen]) and by the list/session state held in
 * [AutomationsScreen], so a draft is always encoded exactly once, the same
 * way, everywhere.
 *
 * Separator hierarchy (all non-printable control characters, never typable
 * via an IME, so they cannot collide with real user input in name/purpose/
 * step or condition text):
 * - [STEP_FIELD_SEP] between a step or condition's id and its label/text.
 * - [STEP_ITEM_SEP] between entries of the steps or conditions list.
 * - [DRAFT_FIELD_SEP] between a draft's top-level fields.
 * - [DRAFT_SEP] between drafts in an encoded automations list.
 * - [SESSION_SEP] between an editor session's mode and its encoded draft.
 */
private const val STEP_FIELD_SEP = "\u0001"
private const val STEP_ITEM_SEP = "\u0002"
private const val DRAFT_FIELD_SEP = "\u0003"
const val AUTOMATION_DRAFT_LIST_SEP = "\u0004"
const val AUTOMATION_SESSION_SEP = "\u0005"

private fun encodeSteps(steps: List<AutomationStep>) = steps.joinToString(STEP_ITEM_SEP) { "${it.id}$STEP_FIELD_SEP${it.label}" }
private fun decodeSteps(raw: String): List<AutomationStep> = if (raw.isEmpty()) emptyList() else raw.split(STEP_ITEM_SEP).map {
    val (id, label) = it.split(STEP_FIELD_SEP, limit = 2)
    AutomationStep(id, label)
}

private fun encodeConditions(conditions: List<AutomationCondition>) = conditions.joinToString(STEP_ITEM_SEP) { "${it.id}$STEP_FIELD_SEP${it.text}" }
private fun decodeConditions(raw: String): List<AutomationCondition> = if (raw.isEmpty()) emptyList() else raw.split(STEP_ITEM_SEP).map {
    val (id, text) = it.split(STEP_FIELD_SEP, limit = 2)
    AutomationCondition(id, text)
}

fun encodeAutomationDraft(d: AutomationDraft): String = listOf(
    d.id, d.type.name, d.name, d.purpose, d.enabled.toString(), d.runtime.name, d.privacy.name,
    d.permissions.joinToString(STEP_ITEM_SEP), encodeSteps(d.steps), d.scheduleMode.name,
    d.scheduleDateTime, d.scheduleInterval, d.conditionLogic.name, encodeConditions(d.conditions),
).joinToString(DRAFT_FIELD_SEP)

fun decodeAutomationDraft(raw: String): AutomationDraft {
    val f = raw.split(DRAFT_FIELD_SEP)
    return AutomationDraft(
        id = f[0],
        type = AutomationType.valueOf(f[1]),
        name = f[2],
        purpose = f[3],
        enabled = f[4].toBoolean(),
        runtime = ExecutionLocation.valueOf(f[5]),
        privacy = PrivacyMode.valueOf(f[6]),
        permissions = if (f[7].isEmpty()) emptyList() else f[7].split(STEP_ITEM_SEP),
        steps = decodeSteps(f[8]),
        scheduleMode = ScheduleMode.valueOf(f[9]),
        scheduleDateTime = f[10],
        scheduleInterval = f[11],
        conditionLogic = ConditionLogic.valueOf(f[12]),
        conditions = decodeConditions(f[13]),
    )
}
