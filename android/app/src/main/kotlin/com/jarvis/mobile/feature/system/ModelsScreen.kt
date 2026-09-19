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
 * Scaffolded from src/components/jarvis/screens/models-screen.tsx. Row-level
 * parity (download list, storage detail) follows in a later commit, see
 * android/PORTING_PLAN.md.
 */
@Composable
fun ModelsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Modelle",
        subtitle = "Lokale Modelldateien, LiteRT-Runtime, Download, Laden, Kompatibilität.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Runtime")
        JarvisListGroup {
            JarvisListRow(title = "Modell-Runtime", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.modelRuntime, dot = false) })
            JarvisListRow(title = "Geladenes Modell", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.localModel) })
        }
    }
}
