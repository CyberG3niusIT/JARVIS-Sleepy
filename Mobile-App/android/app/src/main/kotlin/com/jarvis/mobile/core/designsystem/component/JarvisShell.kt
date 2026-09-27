package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.R
import com.jarvis.mobile.core.designsystem.JarvisLayout
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.NavTabId
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.SystemState

/**
 * Locked shell primitives, ported 1:1 from src/components/jarvis/shell.tsx:
 * top app bar, persistent runtime strip, bottom navigation.
 */

@Composable
fun JarvisTopBar(
    modifier: Modifier = Modifier,
    onSettings: (() -> Unit)? = null,
    settingsLabel: String = "Einstellungen",
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .windowInsetsPadding(WindowInsets.systemBars.only(androidx.compose.foundation.layout.WindowInsetsSides.Top))
            .height(JarvisLayout.topBarHeight)
            .background(JarvisSemanticColor.background)
            .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
            .padding(horizontal = JarvisSpacing.lg),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
    ) {
        androidx.compose.foundation.Image(
            painter = painterResource(R.drawable.jarvis_wordmark),
            contentDescription = "J.A.R.V.I.S",
            contentScale = ContentScale.FillHeight,
            modifier = Modifier.height(12.dp),
        )
        IconButton(onClick = { onSettings?.invoke() }, modifier = Modifier.size(48.dp)) {
            Icon(Icons.Filled.Settings, contentDescription = settingsLabel, tint = JarvisSemanticColor.mutedForeground)
        }
    }
}

@Composable
fun JarvisRuntimeStrip(
    runtimeState: SystemState,
    runtimeLabel: String,
    execution: ExecutionLocation?,
    privacy: PrivacyMode?,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(JarvisSemanticColor.surface)
            .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
            .padding(horizontal = JarvisSpacing.lg, vertical = 6.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        JarvisStatusTag(state = runtimeState, label = runtimeLabel)
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (execution != null) {
                JarvisExecutionTag(where = execution)
                androidx.compose.foundation.layout.Spacer(Modifier.padding(start = JarvisSpacing.sm))
            }
            if (privacy != null) {
                JarvisPrivacyTag(mode = privacy)
            }
        }
    }
}

data class JarvisNavItem(
    val id: NavTabId,
    val label: String,
    val icon: ImageVector,
)

@Composable
fun JarvisBottomNavigation(
    items: List<JarvisNavItem>,
    current: NavTabId,
    onSelect: (NavTabId) -> Unit,
    modifier: Modifier = Modifier,
) {
    val index = items.indexOfFirst { it.id == current }.coerceAtLeast(0)
    Column(modifier = modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(JarvisLayout.bottomNavHeight)
                .selectableGroup()
                .background(JarvisSemanticColor.surface)
                .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft)),
        ) {
            items.forEachIndexed { i, item ->
                val active = i == index
                val tint = if (active) JarvisSemanticColor.primary else JarvisSemanticColor.mutedForeground
                val labelColor = if (active) JarvisSemanticColor.foreground else JarvisSemanticColor.mutedForeground
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .selectable(selected = active, role = Role.Tab) { onSelect(item.id) },
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
                ) {
                    Box(
                        modifier = Modifier
                            .size(width = 56.dp, height = 28.dp)
                            .clip(CircleShape)
                            .background(if (active) JarvisSemanticColor.surfaceSelected else androidx.compose.ui.graphics.Color.Transparent),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(item.icon, contentDescription = null, tint = tint, modifier = Modifier.size(JarvisLayout.iconMd))
                    }
                    Text(text = item.label, color = labelColor, fontSize = 11.sp, lineHeight = 12.sp)
                }
            }
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.systemBars.only(androidx.compose.foundation.layout.WindowInsetsSides.Bottom))
                .background(JarvisSemanticColor.surface),
        )
    }
}
