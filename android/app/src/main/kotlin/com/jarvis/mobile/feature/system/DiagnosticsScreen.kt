package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Ported 1:1 from src/components/jarvis/screens/diagnostics-screen.tsx. Both
 * lists stay empty on purpose - no log source is bound in this phase, and an
 * empty list here is not a claim that a real device has no entries.
 */
@Composable
fun DiagnosticsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Logs & Diagnose",
        subtitle = "Lokale Diagnose",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Ausführungshistorie")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Historiendaten angebunden",
            body = "Spätere Einträge werden lokal gespeichert und dort redigiert, wo es " +
                "erforderlich ist. Im Entwurfszustand ist keine Historienquelle angebunden.",
        )

        JarvisSectionHeader("Crash-Logs")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Logdaten angebunden",
            body = "Die Absturzprotokollierung ist technisch vorgesehen, im Entwurfszustand " +
                "ist jedoch keine Logquelle angebunden.",
        )

        JarvisSectionHeader("Redaktion")
        JarvisListGroup {
            redactionRules.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }

        JarvisSectionHeader("Diagnose")
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Ein lokaler Export ist im Entwurfszustand nicht verfügbar. Sobald er " +
                "umgesetzt ist, verlässt eine Diagnosedatei das Gerät nur auf ausdrückliche Freigabe.",
        )

        DiagnosticsDemoSection()
    }
}

private val redactionRules = listOf(
    "Zugangsdaten redigieren" to "Schlüssel, Token und Passwörter werden entfernt.",
    "Sensible Parameter redigieren" to "Inhaltliche Argumente werden gekürzt.",
    "Kommunikationsinhalte minimieren" to "Nachrichteninhalte werden reduziert und redigiert.",
    "Privacy-Status berücksichtigen" to "Geschützte Inhalte werden nicht protokolliert.",
)
