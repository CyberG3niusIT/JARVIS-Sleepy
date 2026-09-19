package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Ported 1:1 from src/components/jarvis/screens/runtimes-screen.tsx. Sleepy
 * pairing/trust/handoff demo sections (runtimes-demo.tsx) are deferred, see
 * android/PORTING_PLAN.md and android/OPEN_DECISIONS.md Sec.1; only the
 * documented handoff-package structure is ported, since it describes a
 * target shape, not a transport decision.
 */
@Composable
fun RuntimesScreen(onBack: () -> Unit) {
    val labels = comparisonBaseline.labels

    DetailScaffold(
        title = "Runtimes",
        subtitle = "Ausführungsorte",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Dieses Gerät")
        JarvisListGroup {
            JarvisListRow(
                title = "J.A.R.V.I.S Mobile",
                subtitle = "Vorgesehene lokale Runtime auf diesem Android-Gerät.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = labels.runtime, dot = false) },
            )
            JarvisListRow(title = "Standardausführung", trailing = { JarvisExecutionTag(where = comparisonBaseline.execution) })
            JarvisListRow(title = "Vorgesehene Inferenz", trailing = { MonoValue(labels.modelRuntime) })
        }

        JarvisSectionHeader("Vertraute Runtime")
        JarvisListGroup {
            JarvisListRow(
                title = "Sleepy",
                subtitle = "Optionale vertraute Ausführungsumgebung, nicht erforderlich für den lokalen Betrieb.",
                trailing = { JarvisStatusTag(state = SystemState.UNAVAILABLE, label = labels.sleepy, dot = false) },
            )
            JarvisListRow(title = "Übergabe", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = labels.sleepyHandoff, dot = false) })
        }

        JarvisSectionHeader("Cloud")
        JarvisListGroup {
            JarvisListRow(
                title = "Cloud-Ausführung",
                subtitle = "Nur nach ausdrücklicher Freigabe, niemals als Standardweg.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = labels.cloud, dot = false) },
            )
        }

        JarvisSectionHeader("Handoff-Prinzip")
        JarvisListGroup {
            handoffStructure.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
        Text(
            text = "Beschreibt die Zielstruktur einer Übergabe. Es findet keine Kopplung und keine Übergabe statt.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
    }
}

private val handoffStructure = listOf(
    "Aufgabe" to "Klar begrenztes Ziel der Übergabe.",
    "Freigegebener Kontext" to "Nur ausdrücklich freigegebene Inhalte.",
    "Privacy-Zustand" to "Der Modus des Aufrufkontexts wird mitgeführt.",
    "Limits" to "Schritt-, Zeit- und Werkzeuggrenzen.",
    "Erwartetes Ergebnis" to "Vereinbarte Form der Antwort.",
    "Rückkanal" to "Definierter Weg für Ergebnis, Abbruch und Fehler.",
)

@Composable
private fun MonoValue(text: String) {
    Text(text = text, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = JarvisSemanticColor.subtleForeground)
}
