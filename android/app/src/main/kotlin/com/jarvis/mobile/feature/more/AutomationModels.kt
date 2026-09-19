package com.jarvis.mobile.feature.more

import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.util.StringFieldCodec
import java.util.concurrent.atomic.AtomicInteger

/**
 * Ported 1:1 from src/components/jarvis/screens/automation-editor.tsx. Local,
 * in-memory prototype editor state only - nothing here reaches an Android
 * scheduler or runtime. Saving only changes the Compose state held by
 * [AutomationsScreen].
 */

data class AutomationStep(val id: String, val label: String)
data class AutomationCondition(val id: String, val text: String)

internal data class StepSheetState(val id: String?, val label: String)
internal data class ConditionSheetState(val id: String?, val text: String)

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
 * String encoding for [AutomationDraft], used by every `rememberSaveable`
 * that needs to survive configuration changes AND process death (rotation,
 * activity recreation): a single [String] is unconditionally Bundle-safe,
 * unlike a nested `List<List<Any>>`. Shared by the editor's own draft state
 * ([AutomationEditorScreen]) and by the list/session state held in
 * [AutomationsScreen], so a draft is always encoded exactly once, the same
 * way, everywhere.
 *
 * Built on [StringFieldCodec]'s length-prefixed fields, so no field - a
 * name, purpose, step label or condition text - can ever be misread as a
 * separator or a list boundary, whatever characters it contains.
 */
private fun encodeSteps(steps: List<AutomationStep>): String {
    val writer = StringFieldCodec.writer()
    writer.write(steps.size.toString())
    steps.forEach { writer.write(it.id); writer.write(it.label) }
    return writer.build()
}

private fun decodeSteps(raw: String): List<AutomationStep> {
    val reader = StringFieldCodec.reader(raw)
    val size = reader.read().toInt()
    return List(size) { AutomationStep(id = reader.read(), label = reader.read()) }
}

private fun encodeConditions(conditions: List<AutomationCondition>): String {
    val writer = StringFieldCodec.writer()
    writer.write(conditions.size.toString())
    conditions.forEach { writer.write(it.id); writer.write(it.text) }
    return writer.build()
}

private fun decodeConditions(raw: String): List<AutomationCondition> {
    val reader = StringFieldCodec.reader(raw)
    val size = reader.read().toInt()
    return List(size) { AutomationCondition(id = reader.read(), text = reader.read()) }
}

fun encodeAutomationDraft(d: AutomationDraft): String {
    val writer = StringFieldCodec.writer()
    writer.write(d.id)
    writer.write(d.type.name)
    writer.write(d.name)
    writer.write(d.purpose)
    writer.write(d.enabled.toString())
    writer.write(d.runtime.name)
    writer.write(d.privacy.name)
    writer.write(StringFieldCodec.encodeStringList(d.permissions))
    writer.write(encodeSteps(d.steps))
    writer.write(d.scheduleMode.name)
    writer.write(d.scheduleDateTime)
    writer.write(d.scheduleInterval)
    writer.write(d.conditionLogic.name)
    writer.write(encodeConditions(d.conditions))
    return writer.build()
}

fun decodeAutomationDraft(raw: String): AutomationDraft {
    val reader = StringFieldCodec.reader(raw)
    return AutomationDraft(
        id = reader.read(),
        type = AutomationType.valueOf(reader.read()),
        name = reader.read(),
        purpose = reader.read(),
        enabled = reader.read().toBoolean(),
        runtime = ExecutionLocation.valueOf(reader.read()),
        privacy = PrivacyMode.valueOf(reader.read()),
        permissions = StringFieldCodec.decodeStringList(reader.read()),
        steps = decodeSteps(reader.read()),
        scheduleMode = ScheduleMode.valueOf(reader.read()),
        scheduleDateTime = reader.read(),
        scheduleInterval = reader.read(),
        conditionLogic = ConditionLogic.valueOf(reader.read()),
        conditions = decodeConditions(reader.read()),
    )
}

/** Encodes a variable-length list of already-encoded [AutomationDraft] strings as one opaque field. */
fun encodeAutomationDraftList(drafts: List<AutomationDraft>): String =
    StringFieldCodec.encodeStringList(drafts.map { encodeAutomationDraft(it) })

/** Decodes a field value previously produced by [encodeAutomationDraftList]. */
fun decodeAutomationDraftList(raw: String): List<AutomationDraft> =
    StringFieldCodec.decodeStringList(raw).map { decodeAutomationDraft(it) }

internal fun encodeStepSheet(s: StepSheetState?): String {
    val writer = StringFieldCodec.writer()
    writer.write((s != null).toString())
    if (s != null) {
        writer.write((s.id != null).toString())
        writer.write(s.id ?: "")
        writer.write(s.label)
    }
    return writer.build()
}

internal fun decodeStepSheet(raw: String): StepSheetState? {
    val reader = StringFieldCodec.reader(raw)
    if (!reader.read().toBoolean()) return null
    val hasId = reader.read().toBoolean()
    val id = reader.read()
    val label = reader.read()
    return StepSheetState(if (hasId) id else null, label)
}

internal fun encodeConditionSheet(s: ConditionSheetState?): String {
    val writer = StringFieldCodec.writer()
    writer.write((s != null).toString())
    if (s != null) {
        writer.write((s.id != null).toString())
        writer.write(s.id ?: "")
        writer.write(s.text)
    }
    return writer.build()
}

internal fun decodeConditionSheet(raw: String): ConditionSheetState? {
    val reader = StringFieldCodec.reader(raw)
    if (!reader.read().toBoolean()) return null
    val hasId = reader.read().toBoolean()
    val id = reader.read()
    val text = reader.read()
    return ConditionSheetState(if (hasId) id else null, text)
}
