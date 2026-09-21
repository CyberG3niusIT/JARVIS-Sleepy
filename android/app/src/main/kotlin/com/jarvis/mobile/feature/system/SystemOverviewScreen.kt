package com.jarvis.mobile.feature.system

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
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
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.AreaId
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
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

private val setupAreas = setOf(AreaId.MODELS, AreaId.PERMISSIONS, AreaId.RUNTIMES)
private val operationAreas = setOf(AreaId.DEVICE, AreaId.PRIVACY, AreaId.DIAGNOSTICS)
private val capabilityAreas = setOf(AreaId.TOOLS, AreaId.AGENTS)

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

        JarvisSectionHeader("Einrichtung")
        JarvisListGroup {
            JarvisListRow(title = "Lokale Runtime", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = "Nicht verfügbar") })
            JarvisListRow(title = "Lokales Modell", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = comparisonBaseline.labels.localModel) })
            JarvisListRow(title = "Berechtigungen", trailing = { JarvisStatusTag(state = SystemState.UNAVAILABLE, label = "Status nicht verfügbar") })
            JarvisListRow(title = "Sleepy", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = "Nicht verfügbar") })
        }

        JarvisSectionHeader("Modelle & Verbindungen")
        JarvisListGroup {
            systemDestinations.filter { it.id in setupAreas }.forEach { area ->
                val route = systemDetailRoutes[area.id]
                JarvisListRow(
                    title = area.label,
                    subtitle = area.purpose,
                    chevron = route != null,
                    onClick = route?.let { { onOpenArea(it) } },
                )
            }
        }
        JarvisSectionHeader("Gerät & Betrieb")
        JarvisListGroup {
            systemDestinations.filter { it.id in operationAreas }.forEach { area ->
                val route = systemDetailRoutes[area.id]
                JarvisListRow(title = area.label, subtitle = area.purpose, chevron = route != null, onClick = route?.let { { onOpenArea(it) } })
            }
        }
        JarvisSectionHeader("Funktionen")
        JarvisListGroup {
            systemDestinations.filter { it.id in capabilityAreas }.forEach { area ->
                val route = systemDetailRoutes[area.id]
                JarvisListRow(title = area.label, subtitle = area.purpose, chevron = route != null, onClick = route?.let { { onOpenArea(it) } })
            }
        }
    }
}
