package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisNoticeTone
import com.jarvis.mobile.core.designsystem.component.JarvisPrivacyTag
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/agents-screen.tsx. There is
 * no verified agent inventory in this phase; the only populated agent lives
 * inside the clearly labelled Zustandsdemonstration section, and cancelling
 * or retrying it only changes that local demo state.
 */
private val AgentEntrySaver = Saver<AgentEntry, String>(
    save = { encodeAgentEntry(it) },
    restore = { decodeAgentEntry(it) },
)

@Composable
fun AgentsScreen(onBack: () -> Unit) {
    // Category A: cancel/retry/fail-demo edit this in place below.
    var demo by rememberSaveable(stateSaver = AgentEntrySaver) { mutableStateOf(demoAgent) }
    var sheetView by rememberSaveable { mutableStateOf(AgentSheetView.CLOSED) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

    fun report(message: String) {
        scope.launch { actionResult.report(message) }
    }

    fun cancelTask() {
        demo = demo.copy(taskState = AgentTaskState.CANCELLED, errorReason = null)
        report("Demo-Aufgabe abgebrochen. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun retryTask() {
        demo = demo.copy(taskState = AgentTaskState.RUNNING, currentStep = 1, errorReason = null, lastResult = null)
        report("Demo-Aufgabe erneut gestartet. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun failDemo() {
        demo = demo.copy(taskState = AgentTaskState.FAILED, errorReason = "Zeitlimit vor Abschluss des letzten Schritts erreicht (Demo).")
        report("Demo-Aufgabe als fehlgeschlagen markiert. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    DetailScaffold(
        title = "Agenten",
        subtitle = "Begrenzte Ausführung",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Agentenmodell")
        JarvisListGroup {
            agentModel.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
        FootNote("Architekturmerkmale des Aufgabenmodells, keine aktuellen Werte.")

        JarvisSectionHeader("Laufende Aufgaben")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Laufzeitdaten verfügbar",
            body = "Eine Agenten-Runtime ist noch nicht eingerichtet. Aufgaben, Schritte und Limits erscheinen hier erst, wenn sie aus einer realen Runtime gelesen werden können.",
        )

        JarvisSectionHeader("Sicherheitsgrenzen")
        JarvisListGroup {
            agentSafetyBounds.forEach { JarvisListRow(title = it) }
        }
    }

}

private enum class AgentSheetView { CLOSED, DETAIL, ERROR, ACTIVITY }

@Composable
private fun AgentDetailSheet(
    agent: AgentEntry,
    view: AgentSheetView,
    onShowDetail: () -> Unit,
    onShowError: () -> Unit,
    onShowActivity: () -> Unit,
    onClose: () -> Unit,
    onCancel: () -> Unit,
    onRetry: () -> Unit,
) {
    val title = when (view) {
        AgentSheetView.ERROR -> "Fehlerursache"
        AgentSheetView.ACTIVITY -> "Tool-Aktivität"
        else -> agent.name
    }

    JarvisBottomSheet(open = view != AgentSheetView.CLOSED, onClose = onClose, title = title) {
        when (view) {
            AgentSheetView.ERROR -> Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                JarvisInlineNotice(
                    tone = if (agent.errorReason != null) JarvisNoticeTone.ERROR else JarvisNoticeTone.INFO,
                    text = agent.errorReason ?: "Für diese Demo-Aufgabe liegt aktuell keine Fehlerursache vor.",
                )
                JarvisButton(text = "Zurück zur Aufgabe", fullWidth = true, modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = onShowDetail)
            }

            AgentSheetView.ACTIVITY -> Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                if (agent.toolActivity.isEmpty()) {
                    JarvisInlineNotice(text = "Für diese Demo-Aufgabe wurden noch keine Tool-Aufrufe erfasst.")
                } else {
                    JarvisListGroup {
                        agent.toolActivity.forEach { JarvisListRow(title = it.tool, subtitle = it.summary) }
                    }
                }
                Text(
                    text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.",
                    color = JarvisSemanticColor.mutedForeground,
                    fontSize = 11.sp,
                    lineHeight = 16.sp,
                    modifier = Modifier.padding(top = JarvisSpacing.sm),
                )
                JarvisButton(text = "Zurück zur Aufgabe", fullWidth = true, modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = onShowDetail)
            }

            else -> Column {
                JarvisDetailField(label = "Ziel", value = agent.goal)
                JarvisDetailField(label = "Zweck", value = agent.purpose)
                JarvisDetailField(label = "Erlaubte Tools", value = agent.allowedTools.joinToString("\n"))
                JarvisDetailField(
                    label = "Freigegebener Kontext",
                    value = agent.approvedContext.takeIf { it.isNotEmpty() }?.joinToString("\n") ?: "Nicht festgelegt",
                )
                JarvisDetailFieldTag(label = "Privacy-Kontext") { JarvisPrivacyTag(mode = agent.privacyContext) }
                JarvisDetailFieldTag(label = "Ausführungsruntime") { JarvisExecutionTag(where = agent.runtime) }
                JarvisDetailField(label = "Maximale Schritte", value = agent.maxSteps?.toString() ?: "Nicht festgelegt")
                JarvisDetailField(label = "Aktueller Schritt", value = agent.currentStep?.toString() ?: "Nicht bekannt")
                JarvisDetailField(
                    label = "Schrittzahl",
                    value = if (agent.maxSteps != null && agent.currentStep != null) "${agent.currentStep} von ${agent.maxSteps}" else "Nicht festgelegt",
                )
                JarvisDetailField(label = "Zeitlimit", value = agent.timeoutSeconds?.let { "$it s" } ?: "Nicht festgelegt")
                JarvisDetailField(label = "Erwartetes Ergebnis", value = agent.expectedResult ?: "Nicht festgelegt")
                JarvisDetailField(label = "Letztes Ergebnis", value = agent.lastResult ?: "Noch kein Ergebnis vorhanden")
                JarvisDetailFieldTag(label = "Aufgabenzustand") {
                    JarvisStatusTag(state = agentTaskStateTone.getValue(agent.taskState), label = agentTaskStateLabel.getValue(agent.taskState), dot = false)
                }
                JarvisDetailField(label = "Startzeit", value = agent.startedAt ?: "Nicht bekannt")
                JarvisDetailField(label = "Aktualisiert", value = agent.updatedAt ?: "Nicht bekannt")

                JarvisSectionHeader("Zustandsdemonstration")
                JarvisInlineNotice(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.",
                )

                Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.md)) {
                    JarvisButton(
                        text = "Aufgabe abbrechen (Demo)",
                        variant = JarvisButtonVariant.DESTRUCTIVE,
                        fullWidth = true,
                        enabled = agent.taskState != AgentTaskState.CANCELLED && agent.taskState != AgentTaskState.COMPLETED,
                        onClick = onCancel,
                    )
                    JarvisButton(
                        text = "Fehlgeschlagene Aufgabe erneut starten (Demo)",
                        fullWidth = true,
                        enabled = agent.taskState == AgentTaskState.FAILED,
                        modifier = Modifier.padding(top = JarvisSpacing.sm),
                        onClick = onRetry,
                    )
                    JarvisButton(text = "Fehlerursache ansehen", fullWidth = true, modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = onShowError)
                    JarvisButton(text = "Tool-Aktivität ansehen", fullWidth = true, modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = onShowActivity)
                }
            }
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
