package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.CapabilityRow
import com.jarvis.mobile.core.model.capabilityRows
import com.jarvis.mobile.core.model.stateLabel
import com.jarvis.mobile.feature.common.DetailScaffold
import androidx.compose.material3.Text
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import androidx.compose.ui.unit.sp

private const val NOT_SET = "Nicht festgelegt"

private val executionRules = listOf(
    "Zugriff über Richtlinie" to "Tools werden durch die Ausführungsrichtlinie freigegeben, nicht einzeln erraten.",
    "Android-Berechtigungen" to "Ein Teil der Aktionen setzt freigegebene Android-Berechtigungen voraus.",
    "Privacy-Grenze" to "Geschützte Tools werden im Privacy Mode blockiert, ohne stillen Ersatzweg.",
    "Keine impliziten Rechte" to "Eine Modellanfrage erteilt keine Tool-Rechte.",
)

/**
 * Ported 1:1 from src/components/jarvis/screens/tools-screen.tsx. Rows come
 * from the audited [capabilityRows], so nothing is invented here. Tapping a
 * row opens a read-only detail sheet built only from audited fields.
 */
/**
 * [CapabilityRow] is a plain data class, not Bundle-safe by default, so this
 * saves the row's unique [CapabilityRow.name] and looks it up again in the
 * fixed, audited [capabilityRows] list on restore, rather than encoding the
 * whole row.
 */
private val SelectedCapabilityRowSaver = Saver<CapabilityRow?, String>(
    save = { it?.name ?: "" },
    restore = { name -> capabilityRows.find { it.name == name } },
)

@Composable
fun ToolsScreen(onBack: () -> Unit) {
    // Category A: the open detail sheet should survive activity recreation.
    var selected by rememberSaveable(stateSaver = SelectedCapabilityRowSaver) { mutableStateOf<CapabilityRow?>(null) }

    DetailScaffold(
        title = "Tools",
        subtitle = "Fähigkeiten und Ausführung",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Fähigkeiten")
        JarvisListGroup {
            capabilityRows.forEach { row ->
                JarvisListRow(
                    title = row.name,
                    subtitle = row.detail,
                    onClick = { selected = row },
                    trailing = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            JarvisExecutionTag(where = row.execution)
                            Spacer(Modifier.padding(start = 8.dp))
                            JarvisStatusTag(state = row.state, label = row.statusLabel, dot = false)
                        }
                    },
                )
            }
        }
        Text(
            text = "Zustände stammen aus der Fähigkeitsprüfung des Projekts, nicht aus einer laufenden " +
                "Runtime. Eine Fähigkeit antippen zeigt die geprüften Details.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )

        JarvisSectionHeader("Ausführungsregeln")
        JarvisListGroup {
            executionRules.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
    }

    JarvisBottomSheet(open = selected != null, onClose = { selected = null }, title = selected?.name ?: "Fähigkeit") {
        val row = selected
        if (row != null) {
            JarvisDetailField(label = "Beschreibung", value = row.detail)
            JarvisDetailFieldTag("Ausführungsort") { JarvisExecutionTag(where = row.execution) }
            JarvisDetailFieldTag("Prüfzustand") { JarvisStatusTag(state = row.state, label = row.statusLabel, dot = false) }
            JarvisDetailField(label = "Statusbezeichnung", value = row.statusLabel ?: stateLabel.getValue(row.state))
            JarvisDetailField(label = "Berechtigungsabhängigkeit", value = NOT_SET)
            JarvisDetailField(label = "Privacy-Sensibilität", value = NOT_SET)
            JarvisDetailField(label = "Audit-Entscheidung", value = row.decision.name)
            Text(
                text = "Diese Ansicht zeigt ausschließlich geprüfte Angaben aus der Fähigkeitsprüfung. " +
                    "Es gibt hier keinen Schalter und keine Ausführungsfunktion.",
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 11.sp,
                lineHeight = 16.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }
    }
}

@Composable
private fun JarvisDetailFieldTag(label: String, tag: @Composable () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
    ) {
        Text(text = label.uppercase(), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
        tag()
    }
}
