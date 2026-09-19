package com.jarvis.mobile.feature.system

import androidx.compose.runtime.Composable
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Scaffolded from src/components/jarvis/screens/runtimes-screen.tsx. Sleepy's
 * transport, pairing and trust model are an open decision, see
 * android/OPEN_DECISIONS.md - this screen only renders the connection state.
 */
@Composable
fun RuntimesScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Runtimes",
        subtitle = "Dieses Telefon, später Sleepy: Vertrauen, Kopplung, Übergabezustand.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Dieses Telefon")
        JarvisListGroup {
            JarvisListRow(title = "Lokale Runtime", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.runtime) })
        }
        JarvisSectionHeader("Sleepy")
        JarvisListGroup {
            JarvisListRow(title = "Kopplung", subtitle = "Optionale vertraute Runtime für begrenzte Übergaben.", trailing = { JarvisStatusTag(state = SystemState.UNAVAILABLE, label = comparisonBaseline.labels.sleepy) })
            JarvisListRow(title = "Handoff", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = comparisonBaseline.labels.sleepyHandoff) })
        }
    }
}
