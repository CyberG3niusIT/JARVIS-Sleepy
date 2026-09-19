package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JarvisNotImplementedState
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/** Scaffolded from src/components/jarvis/screens/agents-screen.tsx. */
@Composable
fun AgentsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Agenten",
        subtitle = "Begrenzte Agenten, erlaubte Tools, Limits, Aufgabenzustand.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Agenten")
        JarvisNotImplementedState(
            modifier = Modifier.padding(horizontal = 16.dp),
            body = "Begrenzte Agenten mit erlaubten Tools und Limits sind geplant, aber im Prototyp nicht angebunden.",
        )
    }
}
