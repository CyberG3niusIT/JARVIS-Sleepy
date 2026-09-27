package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.model.ExecutionLocation
import kotlinx.coroutines.launch

private enum class SeverityFilter { ALLE, INFO, WARN, ERROR }
private enum class ExportStep { GESCHLOSSEN, PRUEFEN }

/**
 * Ported 1:1 from src/components/jarvis/screens/diagnostics-demo.tsx.
 * Explicitly separated from the truthful baseline: the two real lists
 * (Ausführungshistorie, Crash-Logs in [DiagnosticsScreen]) stay empty; only
 * example entries with already-redacted summaries are shown here.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DiagnosticsDemoSection() {
    // Category A: user-set filters and selections that should survive
    // activity recreation.
    var severity by rememberSaveable { mutableStateOf(SeverityFilter.ALLE) }
    var runtimeFilter by rememberSaveable { mutableStateOf<ExecutionLocation?>(null) }
    var openId by rememberSaveable { mutableStateOf<String?>(null) }
    var exportStep by rememberSaveable { mutableStateOf(ExportStep.GESCHLOSSEN) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()
    fun report(message: String) { scope.launch { actionResult.report("$message Entwurfszustand, keine Runtime-Aktion ausgeführt.") } }

    val runtimes = remember { diagnosticsDemoEntries.map { it.runtime }.distinct() }
    val filtered = diagnosticsDemoEntries.filter { e ->
        (severity == SeverityFilter.ALLE || logSeverityMatches(severity, e.severity)) &&
            (runtimeFilter == null || e.runtime == runtimeFilter)
    }
    val open = diagnosticsDemoEntries.find { it.id == openId }

    JarvisSectionHeader("Zustandsdemonstration")
    JarvisInlineNotice(
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.",
    )
    JarvisInlineNotice(
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        text = "Redaktion aktiv: sensible Werte wie Zugangsdaten, Nachrichteninhalte und geschützte " +
            "Parameter werden vor der Anzeige entfernt oder gekürzt. Die folgenden Beispieleinträge " +
            "zeigen ausschließlich bereits redigierte Zusammenfassungen.",
    )

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
        Text(text = "NACH SCHWEREGRAD FILTERN", color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
        FlowRow(modifier = Modifier.padding(top = JarvisSpacing.sm).selectableGroup(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
            SeverityFilter.entries.forEach { s ->
                JarvisButton(
                    text = if (s == SeverityFilter.ALLE) "Alle" else logSeverityLabel.getValue(LogSeverity.valueOf(s.name)),
                    variant = if (severity == s) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY,
                    selected = severity == s,
                    onClick = { severity = s },
                )
            }
        }
    }

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
        Text(text = "NACH RUNTIME FILTERN", color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
        FlowRow(modifier = Modifier.padding(top = JarvisSpacing.sm).selectableGroup(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
            JarvisButton(text = "Alle", variant = if (runtimeFilter == null) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY, selected = runtimeFilter == null, onClick = { runtimeFilter = null })
            runtimes.forEach { r ->
                JarvisButton(text = r.name, variant = if (runtimeFilter == r) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY, selected = runtimeFilter == r, onClick = { runtimeFilter = r })
            }
        }
    }

    if (filtered.isEmpty()) {
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Einträge für diese Filterkombination",
            body = "In dieser Beispielliste passt kein Eintrag zur gewählten Kombination aus Schweregrad und Runtime.",
        )
    } else {
        JarvisListGroup {
            filtered.forEach { e ->
                JarvisListRow(
                    title = e.redactedSummary,
                    subtitle = "${e.timestamp}, ${e.category}",
                    trailing = { JarvisStatusTag(state = logSeverityTone.getValue(e.severity), label = logSeverityLabel.getValue(e.severity), dot = false) },
                    chevron = true,
                    onClick = { openId = e.id },
                )
            }
        }
    }

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
        JarvisButton(text = "Diagnose exportieren", fullWidth = true, onClick = { exportStep = ExportStep.PRUEFEN })
    }
    JarvisActionResultText(message = actionResult.message)

    JarvisBottomSheet(open = open != null, onClose = { openId = null }, title = "Logeintrag (Beispiel)") {
        if (open != null) {
            Column {
                JarvisDetailField(label = "Zeitpunkt", value = open.timestamp)
                JarvisDetailField(label = "Kategorie", value = open.category)
                JarvisDetailFieldTag("Schweregrad") { JarvisStatusTag(state = logSeverityTone.getValue(open.severity), label = logSeverityLabel.getValue(open.severity), dot = false) }
                JarvisDetailField(label = "Runtime", value = open.runtime.name)
                JarvisInlineNotice(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp), text = "Redigiert: sensible Werte wurden vor der Anzeige entfernt oder gekürzt.")
                Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
                    Text(text = "REDIGIERTE ZUSAMMENFASSUNG", color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
                    Text(
                        text = open.redactedSummary,
                        color = JarvisSemanticColor.subtleForeground,
                        fontSize = 12.sp,
                        lineHeight = 18.sp,
                        modifier = Modifier
                            .padding(top = JarvisSpacing.xs)
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(JarvisRadii.sm))
                            .padding(JarvisSpacing.sm),
                    )
                }
                Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                    JarvisButton(text = "Redigierte Zusammenfassung kopieren", onClick = {
                        report("Redigierte Zusammenfassung von \"${open.redactedSummary}\" wurde im Demozustand als kopiert markiert.")
                    })
                    JarvisButton(text = "Schließen", onClick = { openId = null })
                }
            }
        }
    }

    JarvisBottomSheet(open = exportStep == ExportStep.PRUEFEN, onClose = { exportStep = ExportStep.GESCHLOSSEN }, title = "Diagnose exportieren") {
        Column {
            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                text = "Diese Übersicht zeigt, welche Datenkategorien in einem Diagnoseexport enthalten " +
                    "wären. Sensible Werte würden vor dem Export redigiert. Im Entwurfszustand wird keine " +
                    "Datei erstellt oder heruntergeladen.",
            )
            JarvisListGroup {
                JarvisListRow(title = "Ausführungshistorie", subtitle = "Zusammenfassungen, redigiert")
                JarvisListRow(title = "Crash-Logs", subtitle = "Stacktraces ohne sensible Parameter")
                JarvisListRow(title = "Redaktionsregeln", subtitle = "Angewandte Regeln zu diesem Export")
                JarvisListRow(title = "Geräte- und App-Version", subtitle = "Ohne persönliche Kennungen")
            }
            Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                JarvisButton(text = "Abbrechen", onClick = { exportStep = ExportStep.GESCHLOSSEN })
                JarvisButton(
                    text = "Export bestätigen",
                    variant = JarvisButtonVariant.PRIMARY,
                    onClick = {
                        exportStep = ExportStep.GESCHLOSSEN
                        report("Diagnoseexport wurde geprüft und bestätigt, es wurde keine Datei erstellt oder heruntergeladen.")
                    },
                )
            }
        }
    }
}

private fun logSeverityMatches(filter: SeverityFilter, severity: LogSeverity): Boolean = filter.name == severity.name

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
