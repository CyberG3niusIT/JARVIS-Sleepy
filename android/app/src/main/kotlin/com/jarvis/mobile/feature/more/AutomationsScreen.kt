package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

enum class AutomationType { MACRO, SCHEDULE, ROUTINE }

val automationTypeLabel: Map<AutomationType, String> = mapOf(
    AutomationType.MACRO to "Makro",
    AutomationType.SCHEDULE to "Zeitplan",
    AutomationType.ROUTINE to "Routine",
)

val automationTypeRows: List<Pair<AutomationType, String>> = listOf(
    AutomationType.MACRO to "Mehrere definierte Aktionen in fester Reihenfolge.",
    AutomationType.SCHEDULE to "Ausführung zu einem festgelegten Zeitpunkt oder Intervall.",
    AutomationType.ROUTINE to "Wiederkehrende Abläufe mit klaren Bedingungen und Grenzen.",
)

val automationExecutionRules: List<Pair<String, String>> = listOf(
    "Deterministisch vor generativ" to "Feste Aktionen laufen vor modellgestütztem Verhalten.",
    "Berechtigungen bleiben nötig" to "Eine Automation umgeht keine Android-Berechtigung.",
    "Privacy kann blockieren" to "Geschützte Schritte werden im jeweiligen Modus gesperrt.",
    "Keine automatische Cloud-Eskalation" to "Ein Cloud-Weg entsteht nur nach ausdrücklicher Freigabe.",
    "Keine Rechteausweitung" to "Eine Automation kann ihre eigenen Grenzen nicht erweitern.",
)

private data class EditorSession(val mode: AutomationEditorMode, val draft: AutomationDraft)

/**
 * String-encoded so both the automation list and the open editor session
 * survive not just rotation but full activity recreation (process death):
 * a plain [String] is unconditionally Bundle-safe, matching the approach
 * [AutomationEditorScreen] already uses for its own draft state. Without
 * this, an in-progress "neue Automation" or a locally saved automation
 * would silently vanish on recreation - the same class of bug the Codex
 * review already flagged for the editor's draft field.
 */
private val AutomationsListSaver = androidx.compose.runtime.saveable.Saver<List<AutomationDraft>, String>(
    save = { list -> list.joinToString(AUTOMATION_DRAFT_LIST_SEP) { encodeAutomationDraft(it) } },
    restore = { raw -> if (raw.isEmpty()) emptyList() else raw.split(AUTOMATION_DRAFT_LIST_SEP).map { decodeAutomationDraft(it) } },
)

private const val NO_SESSION = "\u0000none"
private val EditorSessionSaver = androidx.compose.runtime.saveable.Saver<EditorSession?, String>(
    save = { session -> session?.let { "${it.mode.name}$AUTOMATION_SESSION_SEP${encodeAutomationDraft(it.draft)}" } ?: NO_SESSION },
    restore = { raw ->
        if (raw == NO_SESSION) {
            null
        } else {
            val separatorIndex = raw.indexOf(AUTOMATION_SESSION_SEP)
            EditorSession(
                mode = AutomationEditorMode.valueOf(raw.substring(0, separatorIndex)),
                draft = decodeAutomationDraft(raw.substring(separatorIndex + AUTOMATION_SESSION_SEP.length)),
            )
        }
    },
)

/**
 * Ported 1:1 from src/components/jarvis/screens/automations-screen.tsx,
 * including the full [AutomationEditorScreen]. Mirrors the web reference's
 * own architecture: the editor is not a separate navigation route but a
 * local state swap inside this screen (`editorSession`), so the in-progress
 * draft never needs to cross a navigation boundary. The automation list
 * itself is local, in-memory prototype state; nothing is created, scheduled
 * or stored on the device by this screen.
 */
@Composable
fun AutomationsScreen(onBack: () -> Unit) {
    var automations by rememberSaveable(stateSaver = AutomationsListSaver) { mutableStateOf(emptyList()) }
    var editorSession by rememberSaveable(stateSaver = EditorSessionSaver) { mutableStateOf(null) }
    var sheetOpen by rememberSaveable { mutableStateOf(false) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

    val session = editorSession
    if (session != null) {
        AutomationEditorScreen(
            mode = session.mode,
            initial = session.draft,
            onSave = { saved ->
                automations = if (automations.any { it.id == saved.id }) {
                    automations.map { if (it.id == saved.id) saved else it }
                } else {
                    automations + saved
                }
                editorSession = EditorSession(AutomationEditorMode.EDIT, saved)
            },
            onDelete = if (session.mode == AutomationEditorMode.EDIT) {
                {
                    automations = automations.filterNot { it.id == session.draft.id }
                    editorSession = null
                    scope.launch { actionResult.report("Automation lokal entfernt. Entwurfszustand, keine Runtime-Aktion ausgeführt.") }
                }
            } else null,
            onClose = { editorSession = null },
        )
        return
    }

    DetailScaffold(
        title = "Automationen",
        subtitle = "Makros, Zeitpläne und Routinen",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Automationen")
        if (automations.isEmpty()) {
            JarvisEmptyState(
                modifier = Modifier.padding(horizontal = 16.dp),
                title = "Keine Automationsdaten angebunden",
                body = "Die Automationsverwaltung ist im Entwurfszustand noch nicht an eine Runtime " +
                    "gebunden. Der Editor unten legt Einträge nur lokal in dieser Sitzung an.",
            )
        } else {
            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und " +
                    "kein Inventar. Liste unten ist lokaler Editor-Zustand.",
            )
            JarvisListGroup {
                automations.forEach { a ->
                    JarvisListRow(
                        title = a.name.ifBlank { "Ohne Namen" },
                        subtitle = "${automationTypeLabel.getValue(a.type)}, ${draftSummary(a)}",
                        leading = { JarvisStatusTag(state = if (a.enabled) SystemState.READY else SystemState.OFFLINE, label = if (a.enabled) "Aktiviert" else "Deaktiviert") },
                        trailing = { JarvisExecutionTag(where = a.runtime) },
                        chevron = true,
                        onClick = { editorSession = EditorSession(AutomationEditorMode.EDIT, a) },
                    )
                }
            }
        }
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.lg)) {
            JarvisButton(text = "Neue Automation", variant = JarvisButtonVariant.PRIMARY, fullWidth = true, onClick = { sheetOpen = true })
        }
        JarvisActionResultText(message = actionResult.message)

        JarvisSectionHeader("Typen")
        JarvisListGroup {
            automationTypeRows.forEach { (type, detail) -> JarvisListRow(title = automationTypeLabel.getValue(type), subtitle = detail) }
        }

        JarvisSectionHeader("Ausführungsregeln")
        JarvisListGroup {
            automationExecutionRules.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
    }

    NewAutomationSheet(
        open = sheetOpen,
        onClose = { sheetOpen = false },
        onOpenEditor = { type ->
            sheetOpen = false
            editorSession = EditorSession(AutomationEditorMode.CREATE, createEmptyDraft(type))
        },
    )
}

@Composable
private fun NewAutomationSheet(open: Boolean, onClose: () -> Unit, onOpenEditor: (AutomationType) -> Unit) {
    var choice by rememberSaveable(open) { mutableStateOf<AutomationType?>(null) }

    JarvisBottomSheet(
        open = open,
        onClose = { choice = null; onClose() },
        title = choice?.let { automationTypeLabel.getValue(it) } ?: "Neue Automation",
    ) {
        val selected = choice
        if (selected != null) {
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                JarvisInlineNotice(
                    text = "Der Editor legt diese Automation nur lokal in dieser Sitzung an, ohne " +
                        "Android-Scheduler und ohne Runtime-Bindung.",
                )
                androidx.compose.foundation.layout.Row(
                    modifier = Modifier.fillMaxWidth().padding(top = JarvisSpacing.sm),
                    horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
                ) {
                    JarvisButton(text = "Zurück", modifier = Modifier.weight(1f), onClick = { choice = null })
                    JarvisButton(text = "Editor öffnen", variant = JarvisButtonVariant.PRIMARY, modifier = Modifier.weight(1f), onClick = { onOpenEditor(selected) })
                }
            }
        } else {
            JarvisListGroup {
                automationTypeRows.forEach { (type, detail) ->
                    JarvisListRow(title = automationTypeLabel.getValue(type), subtitle = detail, chevron = true, onClick = { choice = type })
                }
            }
        }
    }
}
