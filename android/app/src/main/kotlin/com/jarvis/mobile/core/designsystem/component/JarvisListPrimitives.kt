package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing

/**
 * Ported 1:1 from src/components/jarvis/primitives.tsx (SectionHeader, ListRow,
 * ListGroup, Divider, DesignStateBlock).
 */

@Composable
fun JarvisSectionHeader(
    text: String,
    modifier: Modifier = Modifier,
    action: @Composable (RowScope.() -> Unit)? = null,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(
            text = text.uppercase(),
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            letterSpacing = 0.6.sp,
        )
        action?.invoke(this)
    }
}

/** Dense functional row - the core list unit. 48 dp minimum touch target. */
@Composable
fun JarvisListRow(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    leading: @Composable (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
    chevron: Boolean = false,
    selected: Boolean = false,
    onClick: (() -> Unit)? = null,
) {
    val rowModifier = modifier
        .fillMaxWidth()
        .defaultMinSize(minHeight = 48.dp)
        .background(if (selected) JarvisSemanticColor.surfaceSelected else androidx.compose.ui.graphics.Color.Transparent)
        .let { base ->
            if (onClick != null) base.clickable(role = Role.Button, onClick = onClick) else base
        }
        .padding(horizontal = 16.dp, vertical = 10.dp)

    Row(modifier = rowModifier, verticalAlignment = Alignment.CenterVertically) {
        if (leading != null) {
            leading()
            androidx.compose.foundation.layout.Spacer(Modifier.padding(end = JarvisSpacing.sm))
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                color = JarvisSemanticColor.foreground,
                fontSize = 13.sp,
                lineHeight = 20.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    color = JarvisSemanticColor.mutedForeground,
                    fontSize = 11.sp,
                    lineHeight = 16.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 2.dp),
                )
            }
        }
        trailing?.invoke()
        if (chevron) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = JarvisSemanticColor.mutedForeground,
                modifier = Modifier.padding(start = JarvisSpacing.xs),
            )
        }
    }
}

/**
 * Grouped list container, Android settings style. Rows provide their own
 * hairline separation via [JarvisDivider] where the web reference shows one.
 */
@Composable
fun JarvisListGroup(
    modifier: Modifier = Modifier,
    content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(JarvisSemanticColor.surface)
            .border(
                androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft),
            ),
        content = content,
    )
}

@Composable
fun JarvisDivider(modifier: Modifier = Modifier) {
    androidx.compose.foundation.layout.Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(0.dp)
            .background(JarvisSemanticColor.borderSoft)
            .defaultMinSize(minHeight = 1.dp),
    )
}

/**
 * Explicit design-state placeholder. Used wherever a runtime value would be -
 * never a fabricated number.
 */
@Composable
fun JarvisDesignStateBlock(
    state: com.jarvis.mobile.core.model.SystemState,
    modifier: Modifier = Modifier,
    note: String? = null,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(JarvisRadii.sm))
            .border(1.dp, JarvisSemanticColor.border, RoundedCornerShape(JarvisRadii.sm))
            .padding(JarvisSpacing.md),
    ) {
        JarvisStatusTag(state = state)
        if (note != null) {
            Text(
                text = note,
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 11.sp,
                lineHeight = 16.sp,
                modifier = Modifier.padding(top = JarvisSpacing.xs),
            )
        }
    }
}
