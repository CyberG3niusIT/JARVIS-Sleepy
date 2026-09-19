package com.jarvis.mobile.feature.more

import androidx.compose.runtime.Composable
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.feature.common.DetailScaffold

/** Ported from src/components/jarvis/screens/settings-screen.tsx + blocks.tsx SettingsList. */
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Einstellungen",
        subtitle = "Sprache, Darstellung, Speicher, Hintergrunddienst, allgemeine Konfiguration.",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Allgemein")
        JarvisListGroup {
            JarvisListRow(title = "Sprache & Ausgabe", subtitle = "Deutsch")
            JarvisListRow(title = "Darstellung", subtitle = "Dunkel, Systemdichte")
            JarvisListRow(title = "Speicher & Modelle", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE) })
            JarvisListRow(title = "Hintergrunddienst", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE) })
        }
    }
}
