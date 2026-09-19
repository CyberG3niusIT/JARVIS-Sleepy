package com.jarvis.mobile.feature.system

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisPrivacyTag
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.PrivacyBlock
import com.jarvis.mobile.core.designsystem.component.RoutingLadderBlock
import com.jarvis.mobile.core.model.AreaId
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.core.model.stateLabel
import com.jarvis.mobile.core.model.systemDestinations
import com.jarvis.mobile.navigation.JarvisRoute

/**
 * Ported 1:1 from src/components/jarvis/screens/system-screen.tsx (overview
 * part; the container/detail routing itself lives in navigation, since
 * Compose Navigation already gives each detail its own back-stack entry).
 * Only destinations with a real detail route are tappable; every other row
 * stays informational without a chevron.
 */
private val systemDetailRoutes: Map<AreaId, String> = mapOf(
    AreaId.MODELS to JarvisRoute.SYSTEM_MODELS,
    AreaId.AGENTS to JarvisRoute.SYSTEM_AGENTS,
    AreaId.TOOLS to JarvisRoute.SYSTEM_TOOLS,
    AreaId.PERMISSIONS to JarvisRoute.SYSTEM_PERMISSIONS,
    AreaId.PRIVACY to JarvisRoute.SYSTEM_PRIVACY,
    AreaId.RUNTIMES to JarvisRoute.SYSTEM_RUNTIMES,
    AreaId.DEVICE to JarvisRoute.SYSTEM_DEVICE,
    AreaId.DIAGNOSTICS to JarvisRoute.SYSTEM_DIAGNOSTICS,
)

private val areaStatusLabel: Map<AreaId, String> = mapOf(
    AreaId.MODELS to comparisonBaseline.labels.localModel,
    AreaId.PERMISSIONS to comparisonBaseline.labels.permissions,
    AreaId.PRIVACY to comparisonBaseline.privacyMode.name,
    AreaId.RUNTIMES to comparisonBaseline.labels.runtime,
    AreaId.DIAGNOSTICS to "Keine Runtime-Daten",
)

private val areaDisplayState: Map<AreaId, SystemState> = mapOf(
    AreaId.RUNTIMES to SystemState.DESIGN_STATE,
)

@Composable
fun SystemOverviewScreen(onOpenArea: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(JarvisSemanticColor.surface)
                .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
                .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.lg),
        ) {
            Text(text = "System", color = JarvisSemanticColor.foreground, fontSize = 15.sp, lineHeight = 20.sp)
            Text(
                text = "Kontrollzentrum",
                color = JarvisSemanticColor.subtleForeground,
                fontSize = 13.sp,
                lineHeight = 20.sp,
                modifier = Modifier.padding(top = JarvisSpacing.xs),
            )
        }

        JarvisSectionHeader("Systemzustand")
        JarvisListGroup {
            JarvisListRow(title = "Lokale Runtime", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.runtime) })
            JarvisListRow(title = "Standardausführung", trailing = { JarvisExecutionTag(where = comparisonBaseline.execution) })
            JarvisListRow(title = "Privacy", trailing = { JarvisPrivacyTag(mode = comparisonBaseline.privacyMode) })
            JarvisListRow(title = "Berechtigungen", trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED, label = comparisonBaseline.labels.permissions) })
            JarvisListRow(title = "Lokales Modell", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.localModel) })
        }

        JarvisSectionHeader("Kontrollbereiche")
        JarvisListGroup {
            systemDestinations.forEach { area ->
                val display = areaDisplayState[area.id] ?: area.state
                val route = systemDetailRoutes[area.id]
                JarvisListRow(
                    title = area.label,
                    subtitle = area.purpose,
                    trailing = { JarvisStatusTag(state = display, label = areaStatusLabel[area.id] ?: stateLabel.getValue(display), dot = false) },
                    chevron = route != null,
                    onClick = route?.let { { onOpenArea(it) } },
                )
            }
        }
        Text(
            text = "Teile der Tools und Android-Aktionen hängen von freigegebenen Berechtigungen ab.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
        )

        JarvisSectionHeader("Benötigt Aufmerksamkeit")
        JarvisListGroup {
            JarvisListRow(
                title = "Lokales Modell",
                subtitle = "Modellgestützte lokale Antworten sind erst nach dem Laden eines Modells verfügbar.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.localModel) },
            )
            JarvisListRow(
                title = "Berechtigungen",
                subtitle = "Benötigte Android-Berechtigungen sind noch nicht vollständig freigegeben.",
                trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED, label = comparisonBaseline.labels.permissions) },
            )
        }
        Text(
            text = "Sleepy und Cloud sind optional und zählen deshalb nicht als Blocker.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
        )

        JarvisSectionHeader("Privacy")
        PrivacyBlock()

        JarvisSectionHeader("Vollständige Entscheidungsreihenfolge")
        RoutingLadderBlock()
        Text(
            text = "Deterministische Android-Aktionen zuerst, lokale Skills und Tools vor generativer " +
                "Antwort, lokales Modell vor vertrauenswürdiger Runtime. Sleepy bleibt optional, ein " +
                "Cloud-Fallback nur nach Freigabe. Kein stiller Fallback.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
        )

        Text(
            text = "${stateLabel.getValue(SystemState.DESIGN_STATE)}. Angezeigte Zustände stammen aus der " +
                "aktuellen Projektbasis, nicht aus gemessener Laufzeittelemetrie.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.xl),
        )
    }
}
