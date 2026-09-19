package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing

/** Ported 1:1 from src/components/jarvis/controls.tsx (Button, Toggle, TextInput). */

enum class JarvisButtonVariant { PRIMARY, SECONDARY, DESTRUCTIVE }

@Composable
fun JarvisButton(
    text: String,
    modifier: Modifier = Modifier,
    variant: JarvisButtonVariant = JarvisButtonVariant.SECONDARY,
    fullWidth: Boolean = false,
    enabled: Boolean = true,
    onClick: () -> Unit = {},
) {
    val (background, border, contentColor) = when {
        !enabled -> Triple(Color.Transparent, JarvisSemanticColor.borderSoft, JarvisSemanticColor.disabled)
        variant == JarvisButtonVariant.PRIMARY -> Triple(
            JarvisSemanticColor.primary,
            JarvisSemanticColor.primary,
            JarvisSemanticColor.primaryForeground,
        )
        variant == JarvisButtonVariant.SECONDARY -> Triple(
            Color.Transparent,
            JarvisSemanticColor.border,
            JarvisSemanticColor.subtleForeground,
        )
        else -> Triple(
            Color.Transparent,
            JarvisSemanticColor.destructive.copy(alpha = 0.6f),
            JarvisSemanticColor.destructive,
        )
    }

    Box(
        modifier = modifier
            .let { if (fullWidth) it.fillMaxWidth() else it.wrapContentWidth() }
            .defaultMinSize(minHeight = 48.dp)
            .clip(RoundedCornerShape(JarvisRadii.sm))
            .background(background)
            .border(1.dp, border, RoundedCornerShape(JarvisRadii.sm))
            .let { if (enabled) it.clickable(role = Role.Button, onClick = onClick) else it }
            .padding(horizontal = JarvisSpacing.lg),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = text, color = contentColor, fontSize = 13.sp, lineHeight = 20.sp)
    }
}

@Composable
fun JarvisToggle(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
) {
    val trackColor = if (checked) JarvisSemanticColor.primary.copy(alpha = 0.25f) else JarvisSemanticColor.surfaceRaised
    val trackBorder = if (checked) JarvisSemanticColor.primary.copy(alpha = 0.6f) else JarvisSemanticColor.border
    val thumbColor = if (checked) JarvisSemanticColor.primary else JarvisSemanticColor.disabled

    Box(
        modifier = modifier
            .defaultMinSize(minWidth = 48.dp, minHeight = 48.dp)
            .clickable(role = Role.Switch) { onCheckedChange(!checked) }
            .semantics { contentDescription = label; role = Role.Switch },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .width(36.dp)
                .height(20.dp)
                .clip(CircleShape)
                .background(trackColor)
                .border(1.dp, trackBorder, CircleShape),
        ) {
            Box(
                modifier = Modifier
                    .padding(start = if (checked) 18.dp else 3.dp, top = 3.dp)
                    .width(14.dp)
                    .height(14.dp)
                    .clip(CircleShape)
                    .background(thumbColor),
            )
        }
    }
}

@Composable
fun JarvisTextField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    label: String? = null,
    placeholder: String? = null,
) {
    androidx.compose.foundation.layout.Column(modifier = modifier.fillMaxWidth()) {
        if (label != null) {
            Text(
                text = label.uppercase(),
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 11.sp,
                modifier = Modifier.padding(bottom = 6.dp),
            )
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 48.dp)
                .clip(RoundedCornerShape(JarvisRadii.sm))
                .background(JarvisSemanticColor.surface)
                .border(1.dp, JarvisSemanticColor.border, RoundedCornerShape(JarvisRadii.sm))
                .padding(horizontal = JarvisSpacing.md),
            contentAlignment = Alignment.CenterStart,
        ) {
            if (value.isEmpty() && placeholder != null) {
                Text(text = placeholder, color = JarvisSemanticColor.mutedForeground, fontSize = 13.sp)
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                textStyle = TextStyle(color = JarvisSemanticColor.foreground, fontSize = 13.sp),
                cursorBrush = androidx.compose.ui.graphics.SolidColor(JarvisSemanticColor.primary),
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
