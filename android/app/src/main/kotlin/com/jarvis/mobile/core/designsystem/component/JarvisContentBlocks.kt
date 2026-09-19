package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.routingLadder

/**
 * Content blocks shared by Start and System overview, ported 1:1 from
 * src/components/jarvis/blocks.tsx (PrivacyBlock, RoutingLadderBlock). No
 * value here is runtime data.
 */

@Composable
fun PrivacyBlock(modifier: Modifier = Modifier, mode: PrivacyMode = com.jarvis.mobile.core.model.comparisonBaseline.privacyMode) {
    val modes = listOf(PrivacyMode.NORMAL, PrivacyMode.PRIVACY, PrivacyMode.PRIVACY_LOCK)
    Column(modifier = modifier.padding(horizontal = JarvisSpacing.lg)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(JarvisRadii.sm))
                .border(1.dp, JarvisSemanticColor.border, RoundedCornerShape(JarvisRadii.sm)),
        ) {
            modes.forEach { m ->
                val active = m == mode
                Text(
                    text = m.name,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    color = if (active) JarvisSemanticColor.primary else JarvisSemanticColor.mutedForeground,
                    modifier = Modifier
                        .weight(1f)
                        .background(if (active) JarvisSemanticColor.surfaceSelected else androidx.compose.ui.graphics.Color.Transparent)
                        .padding(vertical = JarvisSpacing.sm),
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
            }
        }
        Text(
            text = "Privacy Mode ist eine harte Grenze, keine Voreinstellung. PRIVACY blockiert " +
                "geschützte Wahrnehmungs- und Datenpfade. PRIVACY_LOCK kann zusätzlich " +
                "Netzwerk-, Cloud- und externe Tool-Pfade hart sperren.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(top = JarvisSpacing.sm),
        )
    }
}

@Composable
fun RoutingLadderBlock(
    modifier: Modifier = Modifier,
    steps: List<String> = routingLadder,
    localSteps: Int = 6,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(JarvisSemanticColor.surface)
            .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft)),
    ) {
        steps.forEachIndexed { i, step ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .defaultMinSize(minHeight = 40.dp)
                    .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "${i + 1}",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    color = JarvisSemanticColor.mutedForeground,
                    modifier = Modifier.padding(end = JarvisSpacing.sm),
                )
                Text(
                    text = step,
                    color = JarvisSemanticColor.subtleForeground,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    modifier = Modifier.weight(1f),
                )
                if (i < localSteps) {
                    JarvisExecutionTag(where = ExecutionLocation.LOKAL)
                }
            }
        }
    }
}
