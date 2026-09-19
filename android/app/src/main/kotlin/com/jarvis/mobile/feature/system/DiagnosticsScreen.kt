package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/** Scaffolded from src/components/jarvis/screens/diagnostics-screen.tsx. */
@Composable
fun DiagnosticsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Logs & Diagnose",
        subtitle = "Ausführungshistorie, Crash-Logs, redigierte Diagnose.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Ausführungshistorie")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Runtime-Daten",
            body = "Es liegen noch keine lokalen Ausführungs- oder Crash-Logs vor.",
        )
    }
}
