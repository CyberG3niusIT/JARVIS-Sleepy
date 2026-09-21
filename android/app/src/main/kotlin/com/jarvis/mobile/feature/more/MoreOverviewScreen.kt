package com.jarvis.mobile.feature.more

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
import com.jarvis.mobile.core.model.AreaId
import com.jarvis.mobile.core.model.moreDestinations
import com.jarvis.mobile.navigation.JarvisRoute

/** Ported 1:1 from src/components/jarvis/screens/more-screen.tsx (overview part). */
private val moreDetailRoutes: Map<AreaId, String> = mapOf(
    AreaId.VOICE to JarvisRoute.MORE_VOICE,
    AreaId.MEMORY to JarvisRoute.MORE_MEMORY,
    AreaId.AUTOMATIONS to JarvisRoute.MORE_AUTOMATIONS,
    AreaId.SETTINGS to JarvisRoute.MORE_SETTINGS,
    AreaId.ABOUT to JarvisRoute.MORE_ABOUT,
)

@Composable
fun MoreOverviewScreen(onOpenArea: (String) -> Unit) {
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
            Text(text = "Mehr", color = JarvisSemanticColor.foreground, fontSize = 15.sp, lineHeight = 20.sp)
            Text(
                text = "Nutzerbereiche und Produkteinstellungen",
                color = JarvisSemanticColor.subtleForeground,
                fontSize = 13.sp,
                lineHeight = 20.sp,
                modifier = Modifier.padding(top = JarvisSpacing.xs),
            )
        }

        JarvisSectionHeader("Bereiche")
        JarvisListGroup {
            moreDestinations.forEach { area ->
                val route = moreDetailRoutes.getValue(area.id)
                JarvisListRow(
                    title = area.label,
                    subtitle = area.purpose,
                    chevron = true,
                    onClick = { onOpenArea(route) },
                )
            }
        }

    }
}
