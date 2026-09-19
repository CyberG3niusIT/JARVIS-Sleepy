package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisPrivacyTag
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold
import androidx.compose.material3.Text

private const val FIXED = "Festgelegt"
private const val UNBOUND_STATUS = "Status nicht gebunden"
private const val MANAGED_MODELS = "Verwaltung in Modelle"
private const val MANAGED_PRIVACY = "Verwaltung in Privacy"
private const val MANAGED_RUNTIMES = "Verwaltung in Runtimes"
private const val MANAGED_PERMISSIONS = "Verwaltung in Berechtigungen"

/**
 * Ported 1:1 from src/components/jarvis/screens/settings-screen.tsx. Owns
 * language, appearance, storage policy, background service and general
 * defaults. Nothing here writes a setting; every row carries exactly one
 * explicit marker for what kind of non-editable state it shows: a fixed
 * product decision (FESTGELEGT), an unbound prototype status (STATUS NICHT
 * GEBUNDEN), or a pointer to the destination that actually manages the value.
 */
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Einstellungen",
        subtitle = "Allgemeine Konfiguration",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Sprache")
        JarvisListGroup {
            JarvisListRow(
                title = "Anwendungssprache",
                subtitle = "Deutsch ist die festgelegte Produktsprache der Oberfläche, kein erkannter Gerätewert.",
                trailing = { MarkerRow("Deutsch", FIXED) },
            )
        }

        JarvisSectionHeader("Darstellung")
        JarvisListGroup {
            JarvisListRow(title = "Design", subtitle = "Festgelegtes Designsystem des Prototyps.", trailing = { MarkerRow("Dunkel", FIXED) })
            JarvisListRow(title = "Dichte", subtitle = "Kompakte Systemdichte des festgelegten Designsystems.", trailing = { MarkerRow("Kompakt", FIXED) })
        }
        FootNote("Festgelegte Darstellung des Prototyps. Es gibt hier keinen Schalter, der eine Einstellung dauerhaft speichern würde.")

        JarvisSectionHeader("Speicher")
        JarvisListGroup {
            JarvisListRow(
                title = "Modellspeicher",
                subtitle = "Modelldateien werden unter Modelle verwaltet und hier nicht doppelt geführt.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = MANAGED_MODELS, dot = false) },
            )
        }

        JarvisSectionHeader("Hintergrunddienst")
        JarvisListGroup {
            JarvisListRow(
                title = "Hintergrunddienst des Assistenten",
                subtitle = "Der Assistenzdienst ist technisch vorgesehen, sein Laufzeitzustand ist hier nicht gebunden.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = UNBOUND_STATUS, dot = false) },
            )
        }

        JarvisSectionHeader("Allgemein")
        JarvisListGroup {
            JarvisListRow(
                title = "Lokale Standardausführung",
                subtitle = "Anzeige des aktuellen Ausführungsorts der Vergleichsgrundlage.",
                trailing = { JarvisExecutionTag(where = comparisonBaseline.execution) },
            )
            JarvisListRow(
                title = "Privacy-Modus",
                subtitle = "Wird vollständig in Privacy verwaltet, hier nur zur Einordnung angezeigt.",
                trailing = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        JarvisPrivacyTag(mode = comparisonBaseline.privacyMode)
                        androidx.compose.foundation.layout.Spacer(Modifier.padding(start = JarvisSpacing.sm))
                        JarvisStatusTag(state = SystemState.DESIGN_STATE, label = MANAGED_PRIVACY, dot = false)
                    }
                },
            )
            JarvisListRow(
                title = "Cloud- und Runtime-Auswahl",
                subtitle = "Wird vollständig in Runtimes verwaltet.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = MANAGED_RUNTIMES, dot = false) },
            )
            JarvisListRow(
                title = "Berechtigungen",
                subtitle = "Wird vollständig in Berechtigungen verwaltet.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = MANAGED_PERMISSIONS, dot = false) },
            )
        }
    }
}

@Composable
private fun MarkerRow(value: String, marker: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(text = value, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = JarvisSemanticColor.subtleForeground)
        androidx.compose.foundation.layout.Spacer(Modifier.padding(start = JarvisSpacing.sm))
        JarvisStatusTag(state = SystemState.DESIGN_STATE, label = marker, dot = false)
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
