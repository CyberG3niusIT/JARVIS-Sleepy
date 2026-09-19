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
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MemoryScreen(onBack: () -> Unit) {
    var demoEntries by remember { mutableStateOf(memoryDemoSeed) }
    var selectedId by remember { mutableStateOf<String?>(null) }
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
            title = "Keine Memory-Daten angebunden",
            body = "Der Memory-Speicher ist im Entwurfszustand noch nicht an eine Runtime " +
                "gebunden. Einträge, Herkunft und Bestätigung werden später hier verwaltet.",
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

        JarvisSectionHeader("Zustandsdemonstration")
        FootNote("Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.")
        JarvisListGroup {
            demoEntries.forEach { entry ->
                JarvisListRow(
                    title = entry.subject?.let { "$it: ${entry.summary}" } ?: entry.summary,
                    subtitle = memoryProvenanceLabel.getValue(entry.provenance),
                    trailing = { JarvisStatusTag(state = entry.state, dot = false) },
                    chevron = true,
                    onClick = { selectedId = entry.id },
                )
            }
        }
        FootNote("Antippen öffnet das Detailmuster mit Aktionen zum Ausprobieren, ohne echten Memory-Zugriff.")
        JarvisActionResultText(message = actionResult.message)

        JarvisSectionHeader("Weiterentwicklung")
        JarvisListGroup {
            JarvisListRow(
                title = "Konsolidierung",
                subtitle = "Zusammenführen und Bereinigen bestätigter Inhalte.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = "Noch nicht vollständig implementiert", dot = false) },
            )
            JarvisListRow(title = "Decay", subtitle = "Alterung und Abwertung nicht mehr belegter Inhalte.", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, dot = false) })
            JarvisListRow(title = "Autonomie-Budget", subtitle = "Grenze dafür, wie viel JARVIS selbstständig merken darf.", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, dot = false) })
        }
        FootNote("Zielarchitektur, im Entwurfszustand noch keine bedienbaren Regler.")
    }

    MemoryDetailSheet(
        entry = selected,
        onClose = { selectedId = null },
        onConfirm = { id -> update(id) { it.copy(confirmationStatus = MemoryConfirmationStatus.CONFIRMED, layer = MemoryLayer.CONFIRMED) }; report("Kandidat als bestätigt markiert.") },
        onCorrect = { id, next -> update(id) { it.copy(summary = next, confirmationStatus = MemoryConfirmationStatus.CORRECTED) }; report("Wert lokal korrigiert.") },
        onDiscard = { id -> update(id) { it.copy(confirmationStatus = MemoryConfirmationStatus.DISCARDED) }; report("Eintrag als verworfen markiert.") },
        onSupersede = { id, note ->
            update(id) { it.copy(confirmationStatus = MemoryConfirmationStatus.CORRECTED, supersedeNote = note.ifBlank { "Ohne zusätzliche Notiz." }, updatedAt = "gerade eben") }
            report("Eintrag als ersetzt markiert.")
        },
    )
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
    var editing by remember(entry?.id) { mutableStateOf(false) }
    var draft by remember(entry?.id) { mutableStateOf(entry?.summary ?: "") }
    var confirmDiscard by remember(entry?.id) { mutableStateOf(false) }
    var supersedeOpen by remember(entry?.id) { mutableStateOf(false) }
    var supersedeNote by remember(entry?.id) { mutableStateOf("") }
    var provenanceOpen by remember(entry?.id) { mutableStateOf(false) }

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
