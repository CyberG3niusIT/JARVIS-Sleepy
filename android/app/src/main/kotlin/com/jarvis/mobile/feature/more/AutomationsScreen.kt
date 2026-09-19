package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/** Ported 1:1 from src/components/jarvis/screens/automations-screen.tsx. */
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

/**
 * The local in-session automation list and its full step/condition/schedule
 * editor (automation-editor.tsx) are deferred, see android/PORTING_PLAN.md;
 * [AutomationEditorScreen] already implements the locked discard-confirmation
 * back behaviour for when that editor is built out. This screen ports the
 * static Typen/Ausführungsregeln content and the empty baseline state.
 */
@Composable
fun AutomationsScreen(onBack: () -> Unit, onCreateAutomation: () -> Unit) {
    DetailScaffold(
        title = "Automationen",
        subtitle = "Makros, Zeitpläne und Routinen",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Automationen")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Automationsdaten angebunden",
            body = "Die Automationsverwaltung ist im Entwurfszustand noch nicht an eine Runtime " +
                "gebunden. Der Editor unten legt Einträge nur lokal in dieser Sitzung an.",
        )
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.lg)) {
            JarvisButton(text = "Neue Automation", variant = JarvisButtonVariant.PRIMARY, fullWidth = true, onClick = onCreateAutomation)
        }

        JarvisSectionHeader("Typen")
        JarvisListGroup {
            automationTypeRows.forEach { (type, detail) -> JarvisListRow(title = automationTypeLabel.getValue(type), subtitle = detail) }
        }

        JarvisSectionHeader("Ausführungsregeln")
        JarvisListGroup {
            automationExecutionRules.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
    }
}
