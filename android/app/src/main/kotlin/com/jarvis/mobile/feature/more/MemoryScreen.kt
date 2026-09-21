package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisDialog
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.JarvisTextField
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/memory-screen.tsx. No memory
 * source is bound in this phase - the empty baseline list describes the
 * missing binding, not a verified absence of entries. The demo entries and
 * their detail-sheet actions (confirm/correct/discard/supersede) only ever
 * change local Compose state, never a real memory store.
 */
private val MemoryEntriesSaver = Saver<List<MemoryEntry>, String>(
    save = { encodeMemoryEntries(it) },
    restore = { decodeMemoryEntries(it) },
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MemoryScreen(onBack: () -> Unit) {
    // Category A: demo entries are edited via confirm/correct/discard/
    // supersede below, so the edits must survive activity recreation.
    var demoEntries by rememberSaveable(stateSaver = MemoryEntriesSaver) { mutableStateOf(memoryDemoSeed) }
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()
    fun report(message: String) {
        scope.launch { actionResult.report("$message Entwurfszustand, keine Runtime-Aktion ausgeführt.") }
    }

    fun update(id: String, patch: (MemoryEntry) -> MemoryEntry) {
        demoEntries = demoEntries.map { if (it.id == id) patch(it) else it }
    }

    val selected = demoEntries.find { it.id == selectedId }

    DetailScaffold(
        title = "Memory",
        subtitle = "Gedächtnis und Herkunft",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Speicherbereiche")
        JarvisListGroup {
            memoryLayers.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }

        JarvisSectionHeader("Aktueller Zustand")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Memory derzeit nicht verfügbar",
            body = "Ein Memory-Speicher ist noch nicht eingerichtet. Es werden keine persönlichen Einträge gespeichert.",
        )

        JarvisSectionHeader("Herkunft")
        JarvisListGroup {
            memoryProvenanceRows.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
        FootNote("Beschreibt mögliche Quellen eines Eintrags, keine vorhandenen Einträge.")

        JarvisSectionHeader("Regeln")
        JarvisListGroup {
            memoryRules.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }

    }

}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MemoryDetailSheet(
    entry: MemoryEntry?,
    onClose: () -> Unit,
    onConfirm: (String) -> Unit,
    onCorrect: (String, String) -> Unit,
    onDiscard: (String) -> Unit,
    onSupersede: (String, String) -> Unit,
) {
    // Category A: mid-edit/mid-dialog state for the open sheet (draft text,
    // which sub-sheet/dialog is open) should survive activity recreation
    // while the sheet is open, keyed by entry id so switching entries resets it.
    var editing by rememberSaveable(entry?.id) { mutableStateOf(false) }
    var draft by rememberSaveable(entry?.id) { mutableStateOf(entry?.summary ?: "") }
    var confirmDiscard by rememberSaveable(entry?.id) { mutableStateOf(false) }
    var supersedeOpen by rememberSaveable(entry?.id) { mutableStateOf(false) }
    var supersedeNote by rememberSaveable(entry?.id) { mutableStateOf("") }
    var provenanceOpen by rememberSaveable(entry?.id) { mutableStateOf(false) }

    JarvisBottomSheet(open = entry != null, onClose = onClose, title = "Memory-Eintrag") {
        if (entry == null) return@JarvisBottomSheet
        Column {
            JarvisDetailField(label = "Subjekt", value = entry.subject ?: "Ohne Subjekt")
            if (editing) {
                Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                    JarvisTextField(value = draft, onValueChange = { draft = it }, label = "Korrigierter Wert")
                }
            } else {
                JarvisDetailField(label = "Wert / Zusammenfassung", value = entry.summary)
            }
            JarvisDetailField(label = "Ebene", value = memoryLayerLabel.getValue(entry.layer))
            JarvisDetailField(label = "Herkunft", value = memoryProvenanceLabel.getValue(entry.provenance))
            entry.confidence?.let { JarvisDetailField(label = "Konfidenz", value = "${(it * 100).toInt()} %") }
            entry.scope?.let { JarvisDetailField(label = "Geltungsbereich", value = memoryScopeLabel.getValue(it)) }
            entry.sensitivity?.let { JarvisDetailField(label = "Sensibilität", value = memorySensitivityLabel.getValue(it)) }
            entry.createdAt?.let { JarvisDetailField(label = "Erstellt", value = it) }
            entry.updatedAt?.let { JarvisDetailField(label = "Aktualisiert", value = it) }
            entry.confirmationStatus?.let { JarvisDetailField(label = "Bestätigungsstatus", value = memoryConfirmationStatusLabel.getValue(it)) }
            entry.supersedes?.let { JarvisDetailField(label = "Ersetzt", value = it.label) }
            entry.supersedeNote?.let { JarvisDetailField(label = "Ersetzungsnotiz", value = it) }
            entry.sourceReference?.let { JarvisDetailField(label = "Quellverweis", value = it) }

            FlowRow(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.md),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
            ) {
                if (editing) {
                    JarvisButton(text = "Korrektur speichern", variant = JarvisButtonVariant.PRIMARY, onClick = { onCorrect(entry.id, draft.ifBlank { entry.summary }); editing = false })
                    JarvisButton(text = "Abbrechen", onClick = { editing = false })
                } else {
                    JarvisButton(text = "Kandidat bestätigen", variant = JarvisButtonVariant.PRIMARY, onClick = { onConfirm(entry.id) })
                    JarvisButton(text = "Korrigieren", onClick = { draft = entry.summary; editing = true })
                    JarvisButton(text = "Ersetzen", onClick = { supersedeOpen = true })
                    JarvisButton(text = "Herkunft ansehen", onClick = { provenanceOpen = true })
                    JarvisButton(text = "Verwerfen", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { confirmDiscard = true })
                }
            }
        }
    }

    JarvisDialog(
        open = confirmDiscard,
        onClose = { confirmDiscard = false },
        title = "Eintrag verwerfen?",
        description = "Der Eintrag wird im Demonstrationszustand als verworfen markiert. Kein Memory-Speicher wird geschrieben.",
        actions = {
            JarvisButton(text = "Abbrechen", onClick = { confirmDiscard = false })
            JarvisButton(
                text = "Verwerfen",
                variant = JarvisButtonVariant.DESTRUCTIVE,
                modifier = Modifier.padding(start = JarvisSpacing.sm),
                onClick = {
                    entry?.let { onDiscard(it.id) }
                    confirmDiscard = false
                    onClose()
                },
            )
        },
    )

    JarvisBottomSheet(open = supersedeOpen, onClose = { supersedeOpen = false }, title = "Eintrag ersetzen") {
        Column(modifier = Modifier.fillMaxWidth()) {
            JarvisTextField(value = supersedeNote, onValueChange = { supersedeNote = it }, label = "Kurze Notiz zur Ersetzung", placeholder = "Zum Beispiel: durch aktuellere Angabe ersetzt")
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.md)) {
                JarvisButton(
                    text = "Ersetzung übernehmen",
                    variant = JarvisButtonVariant.PRIMARY,
                    fullWidth = true,
                    onClick = { entry?.let { onSupersede(it.id, supersedeNote) }; supersedeOpen = false; supersedeNote = "" },
                )
                JarvisButton(text = "Abbrechen", fullWidth = true, modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = { supersedeOpen = false })
            }
        }
    }

    JarvisBottomSheet(open = provenanceOpen, onClose = { provenanceOpen = false }, title = "Herkunft im Detail") {
        if (entry != null) {
            Column {
                JarvisDetailField(label = "Herkunftsart", value = memoryProvenanceLabel.getValue(entry.provenance))
                JarvisDetailField(label = "Erstellt", value = entry.createdAt ?: "Unbekannt")
                JarvisDetailField(label = "Quellverweis", value = entry.sourceReference ?: "Kein Quellverweis hinterlegt.")
                FootNote("Kompakte Herkunftsansicht ohne Gedankengang und ohne Rohinhalte der Quelle.")
            }
        }
    }
}

@Composable
private fun FootNote(text: String) {
    Text(
        text = text,
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}
