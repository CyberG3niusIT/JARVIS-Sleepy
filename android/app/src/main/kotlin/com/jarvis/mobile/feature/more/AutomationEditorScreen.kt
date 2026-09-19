package com.jarvis.mobile.feature.more

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailHeader
import com.jarvis.mobile.core.designsystem.component.JarvisDialog
import com.jarvis.mobile.core.designsystem.component.JarvisDivider
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisNoticeTone
import com.jarvis.mobile.core.designsystem.component.JarvisPrivacyTag
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisTextField
import com.jarvis.mobile.core.designsystem.component.JarvisToggle
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.util.StringFieldCodec
import kotlinx.coroutines.launch

/**
 * Automation Editor, ported 1:1 from
 * src/components/jarvis/screens/automation-editor.tsx. Local, in-memory
 * prototype editor for Makro/Zeitplan/Routine entries; nothing here reaches
 * an Android scheduler or runtime. Saving only calls [onSave], which changes
 * the Compose state held by the parent [AutomationsScreen].
 *
 * Mirrors the web reference's own internal screen swap (no separate nav
 * route): back behaviour is a [BackHandler] that shows a discard
 * confirmation when [draft] differs from [initial], matching the goal
 * spec's locked Automation-Editor back table exactly.
 */
@Composable
fun AutomationEditorScreen(
    mode: AutomationEditorMode,
    initial: AutomationDraft,
    onSave: (AutomationDraft) -> Unit,
    onDelete: (() -> Unit)?,
    onClose: () -> Unit,
) {
    var draft by rememberSaveable(initial.id, stateSaver = AutomationDraftSaver) { mutableStateOf(initial) }
    var discardOpen by rememberSaveable { mutableStateOf(false) }
    var deleteOpen by rememberSaveable { mutableStateOf(false) }
    var stepSheet by rememberSaveable(stateSaver = StepSheetSaver) { mutableStateOf<StepSheetState?>(null) }
    var conditionSheet by rememberSaveable(stateSaver = ConditionSheetSaver) { mutableStateOf<ConditionSheetState?>(null) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

    val dirty by remember { derivedStateOf { draft != initial } }
    val errors by remember { derivedStateOf { validateDraft(draft) } }
    val nextRun by remember { derivedStateOf { derivedNextRun(draft) } }
    val stepLabels = stepListCopy(draft.type)

    fun requestClose() {
        if (dirty) discardOpen = true else onClose()
    }

    BackHandler(onBack = ::requestClose)

    fun report(message: String) {
        scope.launch { actionResult.report(message) }
    }

    fun handleSave() {
        val currentErrors = validateDraft(draft)
        if (currentErrors.isNotEmpty()) {
            report("Speichern nicht möglich: ${currentErrors.first()}")
            return
        }
        onSave(draft)
        report("Änderungen lokal übernommen. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun togglePermission(permission: String) {
        draft = draft.copy(
            permissions = if (draft.permissions.contains(permission)) draft.permissions - permission else draft.permissions + permission,
        )
    }

    fun moveStep(id: String, dir: Int) {
        val index = draft.steps.indexOfFirst { it.id == id }
        val target = index + dir
        if (index < 0 || target < 0 || target >= draft.steps.size) return
        val steps = draft.steps.toMutableList()
        val item = steps.removeAt(index)
        steps.add(target, item)
        draft = draft.copy(steps = steps)
    }

    fun removeStep(id: String) { draft = draft.copy(steps = draft.steps.filterNot { it.id == id }) }

    fun saveStep() {
        val sheet = stepSheet ?: return
        if (sheet.label.isBlank()) return
        draft = if (sheet.id != null) {
            draft.copy(steps = draft.steps.map { if (it.id == sheet.id) it.copy(label = sheet.label) else it })
        } else {
            draft.copy(steps = draft.steps + AutomationStep(nextLocalId("step"), sheet.label))
        }
        stepSheet = null
    }

    fun removeCondition(id: String) { draft = draft.copy(conditions = draft.conditions.filterNot { it.id == id }) }

    fun saveCondition() {
        val sheet = conditionSheet ?: return
        if (sheet.text.isBlank()) return
        draft = if (sheet.id != null) {
            draft.copy(conditions = draft.conditions.map { if (it.id == sheet.id) it.copy(text = sheet.text) else it })
        } else {
            draft.copy(conditions = draft.conditions + AutomationCondition(nextLocalId("condition"), sheet.text))
        }
        conditionSheet = null
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        JarvisDetailHeader(
            title = if (mode == AutomationEditorMode.CREATE) {
                "Neue Automation: ${automationTypeLabel.getValue(draft.type)}"
            } else {
                draft.name.ifBlank { "Automation bearbeiten" }
            },
            subtitle = "${automationTypeLabel.getValue(draft.type)}, lokaler Editor-Entwurf",
            onBack = ::requestClose,
            backLabel = "Zurück zu Automationen",
        )

        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            JarvisSectionHeader("Grunddaten")
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.md)) {
                JarvisTextField(value = draft.name, onValueChange = { draft = draft.copy(name = it) }, label = "Name", placeholder = "Name der Automation")
                JarvisTextField(value = draft.purpose, onValueChange = { draft = draft.copy(purpose = it) }, label = "Beschreibung / Zweck", placeholder = "Wofür ist diese Automation gedacht")
            }
            JarvisListGroup(modifier = Modifier.padding(top = JarvisSpacing.sm)) {
                JarvisListRow(
                    title = "Aktiviert",
                    subtitle = "Nur lokaler Schalter im Editor, keine Runtime-Wirkung.",
                    trailing = { JarvisToggle(checked = draft.enabled, onCheckedChange = { draft = draft.copy(enabled = it) }, label = "Automation aktiviert") },
                )
            }

            JarvisSectionHeader("Ausführungsruntime")
            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp),
                text = "CLOUD und SLEEPY sind hier nur auswählbare Entwurfsoptionen. Die Auswahl macht diese Runtimes nicht verfügbar oder autorisiert.",
            )
            JarvisListGroup {
                automationRuntimeDetails.forEach { opt ->
                    JarvisListRow(
                        title = opt.value.name,
                        subtitle = opt.detail,
                        selected = draft.runtime == opt.value,
                        onClick = { draft = draft.copy(runtime = opt.value) },
                        trailing = { JarvisExecutionTag(where = opt.value) },
                    )
                }
            }

            JarvisSectionHeader("Privacy-Kontext")
            JarvisListGroup {
                automationPrivacyOptions.forEach { opt ->
                    JarvisListRow(
                        title = opt.value.name,
                        subtitle = opt.detail,
                        selected = draft.privacy == opt.value,
                        onClick = { draft = draft.copy(privacy = opt.value) },
                        trailing = { JarvisPrivacyTag(mode = opt.value) },
                    )
                }
            }

            JarvisSectionHeader("Benötigte Berechtigungen")
            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp),
                text = "Auswahl beschreibt nur den Bedarf. Keine Berechtigung wird hier erteilt, das bleibt Sache des Android-Systemdialogs.",
            )
            JarvisListGroup(modifier = Modifier.padding(top = JarvisSpacing.sm)) {
                automationPermissionOptions.forEach { permission ->
                    JarvisListRow(
                        title = permission,
                        trailing = {
                            JarvisToggle(
                                checked = draft.permissions.contains(permission),
                                onCheckedChange = { togglePermission(permission) },
                                label = "Berechtigung $permission als benötigt markieren",
                            )
                        },
                    )
                }
            }

            if (draft.type == AutomationType.SCHEDULE) {
                JarvisSectionHeader("Zeitplan")
                Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                    JarvisButton(text = "Datum/Uhrzeit", variant = if (draft.scheduleMode == ScheduleMode.DATETIME) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY, onClick = { draft = draft.copy(scheduleMode = ScheduleMode.DATETIME) })
                    JarvisButton(text = "Intervall", variant = if (draft.scheduleMode == ScheduleMode.INTERVAL) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY, onClick = { draft = draft.copy(scheduleMode = ScheduleMode.INTERVAL) })
                }
                if (draft.scheduleMode == ScheduleMode.DATETIME) {
                    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                        JarvisTextField(
                            value = draft.scheduleDateTime,
                            onValueChange = { draft = draft.copy(scheduleDateTime = it) },
                            label = "Datum und Uhrzeit",
                            placeholder = "JJJJ-MM-TT HH:MM",
                        )
                    }
                } else {
                    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                        JarvisTextField(
                            value = draft.scheduleInterval,
                            onValueChange = { draft = draft.copy(scheduleInterval = it) },
                            label = "Intervall (z. B. 2 Stunden)",
                            placeholder = "Intervall eingeben",
                        )
                    }
                }
                JarvisInlineNotice(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
                    text = "Nächste Ausführung: ${nextRun ?: "noch keine gültige Eingabe vorhanden"}",
                )
            }

            if (draft.type == AutomationType.ROUTINE) {
                JarvisSectionHeader("Bedingungen") {
                    JarvisButton(text = "+ Bedingung", onClick = { conditionSheet = ConditionSheetState(null, "") })
                }
                Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                    JarvisButton(text = "UND", variant = if (draft.conditionLogic == ConditionLogic.UND) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY, onClick = { draft = draft.copy(conditionLogic = ConditionLogic.UND) })
                    JarvisButton(text = "ODER", variant = if (draft.conditionLogic == ConditionLogic.ODER) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY, onClick = { draft = draft.copy(conditionLogic = ConditionLogic.ODER) })
                }
                if (draft.conditions.isEmpty()) {
                    JarvisInlineNotice(modifier = Modifier.padding(horizontal = 16.dp), tone = JarvisNoticeTone.WARNING, text = "Noch keine Bedingung angelegt.")
                } else {
                    JarvisListGroup {
                        draft.conditions.forEachIndexed { i, c ->
                            JarvisListRow(
                                title = if (i > 0) "${draft.conditionLogic} ${c.text}" else c.text,
                                trailing = {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        IconButton(onClick = { conditionSheet = ConditionSheetState(c.id, c.text) }, modifier = Modifier.size(40.dp)) {
                                            Icon(Icons.Filled.Edit, contentDescription = "Bedingung ${c.text} bearbeiten", tint = JarvisSemanticColor.mutedForeground)
                                        }
                                        IconButton(onClick = { removeCondition(c.id) }, modifier = Modifier.size(40.dp)) {
                                            Icon(Icons.Filled.Delete, contentDescription = "Bedingung ${c.text} entfernen", tint = JarvisSemanticColor.mutedForeground)
                                        }
                                    }
                                },
                            )
                        }
                    }
                }
            }

            JarvisSectionHeader(stepLabels.heading) {
                JarvisButton(text = "+ ${stepLabels.addLabel}", onClick = { stepSheet = StepSheetState(null, "") })
            }
            if (draft.steps.isEmpty()) {
                JarvisInlineNotice(modifier = Modifier.padding(horizontal = 16.dp), tone = JarvisNoticeTone.WARNING, text = stepLabels.empty)
            } else {
                JarvisListGroup {
                    draft.steps.forEachIndexed { i, step ->
                        JarvisListRow(
                            title = step.label,
                            leading = {
                                Text(
                                    text = "${i + 1}",
                                    color = JarvisSemanticColor.mutedForeground,
                                    fontSize = 11.sp,
                                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                                )
                            },
                            trailing = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    IconButton(onClick = { moveStep(step.id, -1) }, enabled = i != 0, modifier = Modifier.size(40.dp)) {
                                        Icon(Icons.Filled.ArrowUpward, contentDescription = "Schritt ${step.label} nach oben verschieben", tint = JarvisSemanticColor.mutedForeground)
                                    }
                                    IconButton(onClick = { moveStep(step.id, 1) }, enabled = i != draft.steps.size - 1, modifier = Modifier.size(40.dp)) {
                                        Icon(Icons.Filled.ArrowDownward, contentDescription = "Schritt ${step.label} nach unten verschieben", tint = JarvisSemanticColor.mutedForeground)
                                    }
                                    IconButton(onClick = { stepSheet = StepSheetState(step.id, step.label) }, modifier = Modifier.size(40.dp)) {
                                        Icon(Icons.Filled.Edit, contentDescription = "Schritt ${step.label} bearbeiten", tint = JarvisSemanticColor.mutedForeground)
                                    }
                                    IconButton(onClick = { removeStep(step.id) }, modifier = Modifier.size(40.dp)) {
                                        Icon(Icons.Filled.Delete, contentDescription = "Schritt ${step.label} entfernen", tint = JarvisSemanticColor.mutedForeground)
                                    }
                                }
                            },
                        )
                    }
                }
            }

            JarvisSectionHeader("Validierung")
            if (errors.isEmpty()) {
                JarvisInlineNotice(modifier = Modifier.padding(horizontal = 16.dp), text = "Alle Pflichtangaben sind vollständig.")
            } else {
                JarvisInlineNotice(modifier = Modifier.padding(horizontal = 16.dp), tone = JarvisNoticeTone.ERROR, text = "Speichern noch nicht möglich: ${errors.joinToString(" ")}")
            }

            JarvisDivider(modifier = Modifier.padding(vertical = JarvisSpacing.lg))
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                JarvisButton(text = "Speichern", variant = JarvisButtonVariant.PRIMARY, fullWidth = true, enabled = errors.isEmpty(), onClick = ::handleSave)
                JarvisButton(text = "Verwerfen", fullWidth = true, onClick = ::requestClose)
                if (mode == AutomationEditorMode.EDIT && onDelete != null) {
                    JarvisButton(text = "Automation löschen", variant = JarvisButtonVariant.DESTRUCTIVE, fullWidth = true, onClick = { deleteOpen = true })
                }
            }
            JarvisActionResultText(message = actionResult.message)
            Text(
                text = "Entwurfszustand, keine Runtime-Aktion ausgeführt. Änderungen bleiben lokaler " +
                    "Editor-Zustand dieses Prototyps, es wird kein Android-Scheduler und keine Runtime angesprochen.",
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 11.sp,
                lineHeight = 16.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
            )
        }
    }

    JarvisBottomSheet(open = stepSheet != null, onClose = { stepSheet = null }, title = if (stepSheet?.id != null) "Schritt bearbeiten" else "Schritt hinzufügen") {
        Column(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            JarvisTextField(
                value = stepSheet?.label ?: "",
                onValueChange = { v -> stepSheet = stepSheet?.copy(label = v) },
                label = if (draft.type == AutomationType.MACRO) "Aktion" else "Schritt",
                placeholder = "Kurze, eindeutige Bezeichnung",
            )
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                JarvisButton(text = "Übernehmen", variant = JarvisButtonVariant.PRIMARY, modifier = Modifier.weight(1f), onClick = ::saveStep)
                JarvisButton(text = "Abbrechen", modifier = Modifier.weight(1f), onClick = { stepSheet = null })
            }
        }
    }

    JarvisBottomSheet(open = conditionSheet != null, onClose = { conditionSheet = null }, title = if (conditionSheet?.id != null) "Bedingung bearbeiten" else "Bedingung hinzufügen") {
        Column(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            JarvisTextField(
                value = conditionSheet?.text ?: "",
                onValueChange = { v -> conditionSheet = conditionSheet?.copy(text = v) },
                label = "Bedingung",
                placeholder = "z. B. WLAN verbunden",
            )
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                JarvisButton(text = "Übernehmen", variant = JarvisButtonVariant.PRIMARY, modifier = Modifier.weight(1f), onClick = ::saveCondition)
                JarvisButton(text = "Abbrechen", modifier = Modifier.weight(1f), onClick = { conditionSheet = null })
            }
        }
    }

    JarvisDialog(
        open = discardOpen,
        onClose = { discardOpen = false },
        title = "Änderungen verwerfen?",
        description = "Es gibt ungespeicherte Änderungen in diesem Editor. Sie gehen beim Verlassen verloren.",
        actions = {
            JarvisButton(text = "Zurück zum Editor", onClick = { discardOpen = false })
            JarvisButton(text = "Verwerfen", variant = JarvisButtonVariant.DESTRUCTIVE, modifier = Modifier.padding(start = JarvisSpacing.sm), onClick = { discardOpen = false; onClose() })
        },
    )

    JarvisDialog(
        open = deleteOpen,
        onClose = { deleteOpen = false },
        title = "Automation löschen?",
        description = "Der Eintrag wird nur aus dem lokalen Editor-Zustand dieses Prototyps entfernt, keine Android-Automation wird gelöscht.",
        actions = {
            JarvisButton(text = "Abbrechen", onClick = { deleteOpen = false })
            JarvisButton(text = "Löschen", variant = JarvisButtonVariant.DESTRUCTIVE, modifier = Modifier.padding(start = JarvisSpacing.sm), onClick = { deleteOpen = false; onDelete?.invoke() })
        },
    )
}

enum class AutomationEditorMode { CREATE, EDIT }

private data class StepSheetState(val id: String?, val label: String)
private data class ConditionSheetState(val id: String?, val text: String)

/**
 * Encodes the draft as a single [String] via [encodeAutomationDraft], the
 * shared representation also used by [AutomationsScreen] for the automation
 * list and the editor session - so a draft survives both a configuration
 * change and full activity recreation (process death), not just rotation.
 */
private val AutomationDraftSaver = androidx.compose.runtime.saveable.Saver<AutomationDraft, String>(
    save = { encodeAutomationDraft(it) },
    restore = { decodeAutomationDraft(it) },
)

/**
 * `open` flag first, then id/label, all as [StringFieldCodec] fields -
 * `null` is encoded as its own explicit flag rather than an empty-string
 * sentinel, so an id or label that happens to be empty is never confused
 * with "no sheet open".
 */
private fun encodeStepSheet(s: StepSheetState?): String {
    val writer = StringFieldCodec.writer()
    writer.write((s != null).toString())
    if (s != null) {
        writer.write((s.id != null).toString())
        writer.write(s.id ?: "")
        writer.write(s.label)
    }
    return writer.build()
}
private fun decodeStepSheet(raw: String): StepSheetState? {
    val reader = StringFieldCodec.reader(raw)
    if (!reader.read().toBoolean()) return null
    val hasId = reader.read().toBoolean()
    val id = reader.read()
    val label = reader.read()
    return StepSheetState(if (hasId) id else null, label)
}
private val StepSheetSaver = androidx.compose.runtime.saveable.Saver<StepSheetState?, String>(
    save = { encodeStepSheet(it) },
    restore = { decodeStepSheet(it) },
)

private fun encodeConditionSheet(s: ConditionSheetState?): String {
    val writer = StringFieldCodec.writer()
    writer.write((s != null).toString())
    if (s != null) {
        writer.write((s.id != null).toString())
        writer.write(s.id ?: "")
        writer.write(s.text)
    }
    return writer.build()
}
private fun decodeConditionSheet(raw: String): ConditionSheetState? {
    val reader = StringFieldCodec.reader(raw)
    if (!reader.read().toBoolean()) return null
    val hasId = reader.read().toBoolean()
    val id = reader.read()
    val text = reader.read()
    return ConditionSheetState(if (hasId) id else null, text)
}
private val ConditionSheetSaver = androidx.compose.runtime.saveable.Saver<ConditionSheetState?, String>(
    save = { encodeConditionSheet(it) },
    restore = { decodeConditionSheet(it) },
)
