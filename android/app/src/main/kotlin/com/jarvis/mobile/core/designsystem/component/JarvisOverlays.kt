package com.jarvis.mobile.core.designsystem.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.FlowRowScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.jarvis.mobile.core.designsystem.JarvisDuration
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing

/**
 * Ported 1:1 from src/components/jarvis/controls.tsx (BottomSheet, Dialog).
 * Both use a platform Dialog window so Back and the scrim tap close them,
 * matching the locked Back table (Sheet: Back closes; Dialog: Back = Abbrechen).
 */

@Composable
fun JarvisBottomSheet(
    open: Boolean,
    onClose: () -> Unit,
    title: String,
    content: @Composable () -> Unit,
) {
    if (!open) return
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(modifier = Modifier.fillMaxSize()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(androidx.compose.ui.graphics.Color.Black.copy(alpha = 0.55f))
                    .clickable(onClick = onClose)
                    .clearAndSetSemantics {},
            )
            AnimatedVisibility(
                visible = true,
                enter = slideInVertically(animationSpec = tween(JarvisDuration.sheetMs)) { it } + fadeIn(),
                exit = slideOutVertically(animationSpec = tween(JarvisDuration.deliberateMs)) { it } + fadeOut(),
                modifier = Modifier.align(Alignment.BottomCenter),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(topStart = JarvisRadii.lg, topEnd = JarvisRadii.lg))
                        .background(JarvisSemanticColor.surfaceRaised),
                ) {
                    Box(modifier = Modifier.fillMaxWidth().padding(vertical = JarvisSpacing.sm), contentAlignment = Alignment.Center) {
                        Box(
                            modifier = Modifier
                                .size(width = 36.dp, height = 4.dp)
                                .clip(CircleShape)
                                .background(JarvisSemanticColor.border),
                        )
                    }
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
                        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = title,
                            color = JarvisSemanticColor.foreground,
                            fontSize = 13.sp,
                            modifier = Modifier.weight(1f),
                        )
                        IconButton(onClick = onClose) {
                            Icon(Icons.Filled.Close, contentDescription = "Schließen", tint = JarvisSemanticColor.mutedForeground)
                        }
                    }
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f, fill = false)
                            .verticalScroll(rememberScrollState())
                            .padding(bottom = JarvisSpacing.lg),
                    ) {
                        content()
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun JarvisDialog(
    open: Boolean,
    onClose: () -> Unit,
    title: String,
    description: String? = null,
    actions: @Composable FlowRowScope.() -> Unit = {},
    content: (@Composable () -> Unit)? = null,
) {
    if (!open) return
    Dialog(onDismissRequest = onClose) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(JarvisRadii.md))
                .background(JarvisSemanticColor.surfaceRaised)
                .verticalScroll(rememberScrollState())
                .padding(JarvisSpacing.lg),
        ) {
            Text(text = title, color = JarvisSemanticColor.foreground, fontSize = 14.sp)
            if (description != null) {
                Text(
                    text = description,
                    color = JarvisSemanticColor.mutedForeground,
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            content?.invoke()
            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = JarvisSpacing.lg),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.End,
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
                content = actions,
            )
        }
    }
}
