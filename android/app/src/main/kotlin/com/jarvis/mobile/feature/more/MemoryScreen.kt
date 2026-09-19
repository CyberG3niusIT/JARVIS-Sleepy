package com.jarvis.mobile.feature.more

import androidx.compose.runtime.Composable
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.feature.common.DetailScaffold

/** Scaffolded from src/components/jarvis/screens/memory-screen.tsx. */
@Composable
fun MemoryScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Memory",
        subtitle = "Arbeitskontext, kürzlich, Kandidaten, bestätigte Einträge, Herkunft.",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Arbeitskontext")
        JarvisListGroup {
            JarvisListRow(title = "Aktive Sitzung", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE) })
            JarvisListRow(title = "Bestätigte Einträge", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE) })
            JarvisListRow(title = "Kandidaten", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE) })
        }
    }
}
