package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.capabilityRows
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Ported from src/components/jarvis/screens/tools-screen.tsx +
 * blocks.tsx CapabilityList - the full capability audit list is real,
 * row-level actions (enable/disable) follow in a later commit.
 */
@Composable
fun ToolsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Tools",
        subtitle = "Android-Aktionen, Bedienungshilfen-Aktionen, Skills und Tools mit Zustand.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Fähigkeiten")
        JarvisListGroup {
            capabilityRows.forEach { row ->
                JarvisListRow(
                    title = row.name,
                    subtitle = row.detail,
                    trailing = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            JarvisStatusTag(state = row.state, label = row.statusLabel, dot = false)
                            Spacer(Modifier.padding(start = 8.dp))
                            JarvisExecutionTag(where = row.execution)
                        }
                    },
                )
            }
        }
    }
}
