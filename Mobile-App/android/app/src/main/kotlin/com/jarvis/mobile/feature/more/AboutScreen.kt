package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.BuildConfig
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Ported 1:1 from src/components/jarvis/screens/about-screen.tsx. No release
 * version exists in the prototype baseline, so none is invented here either.
 */
@Composable
fun AboutScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Über J.A.R.V.I.S",
        subtitle = "Produktinformationen",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Produkt")
        JarvisListGroup {
            JarvisListRow(title = "J.A.R.V.I.S Mobile", subtitle = "Local AI Assistant")
            JarvisListRow(title = "Plattform", trailing = { MonoValue("Android") })
            JarvisListRow(title = "Ausrichtung", trailing = { MonoValue("Local First") })
        }

        JarvisSectionHeader("Version")
        JarvisListGroup {
            JarvisListRow(title = "Version", trailing = { MonoValue(BuildConfig.VERSION_NAME) })
            JarvisListRow(title = "Build", trailing = { MonoValue(BuildConfig.VERSION_CODE.toString()) })
        }

        JarvisSectionHeader("Lizenzen")
        JarvisListGroup {
            JarvisListRow(title = "OpenDroid", trailing = { MonoValue("Apache License 2.0") })
        }
        Text(
            text = "Drittanbieter-Lizenzhinweis.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )

        JarvisSectionHeader("Prinzip")
        Text(
            text = "Local First. Deterministisch vor generativ. Keine stillen Cloud-Fallbacks.",
            color = JarvisSemanticColor.subtleForeground,
            fontSize = 13.sp,
            lineHeight = 20.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        )
    }
}

@Composable
private fun MonoValue(text: String) {
    Text(text = text, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = JarvisSemanticColor.subtleForeground)
}
