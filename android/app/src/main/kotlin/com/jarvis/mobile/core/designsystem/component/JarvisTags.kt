package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.stateLabel
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color

/**
 * Ported 1:1 from src/components/jarvis/primitives.tsx (StatusTag, ExecutionTag,
 * PrivacyTag). Colour-only distinctions are always paired with text, never
 * colour alone (Sec.16 Accessibility).
 */

@Composable
private fun stateTone(state: SystemState): Color = when (state) {
    SystemState.READY -> JarvisSemanticColor.success
    SystemState.LOCAL, SystemState.SLEEPY -> JarvisSemanticColor.primary
    SystemState.WAITING_REMOTE, SystemState.PERMISSION_REQUIRED,
    SystemState.PRIVACY_BLOCKED, SystemState.DEGRADED -> JarvisSemanticColor.warning
    SystemState.OFFLINE, SystemState.UNAVAILABLE, SystemState.NOT_IMPLEMENTED,
    SystemState.DESIGN_STATE -> JarvisSemanticColor.mutedForeground
    SystemState.ERROR -> JarvisSemanticColor.destructive
}

@Composable
fun JarvisStatusTag(
    state: SystemState,
    modifier: Modifier = Modifier,
    label: String? = null,
    dot: Boolean = true,
) {
    val tone = stateTone(state)
    Row(modifier = modifier, verticalAlignment = Alignment.CenterVertically) {
        if (dot) {
            androidx.compose.foundation.layout.Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(tone),
            )
            Spacer(Modifier.width(6.dp))
        }
        Text(text = label ?: stateLabel.getValue(state), fontSize = 11.sp, lineHeight = 16.sp, color = tone)
    }
}

@Composable
fun JarvisExecutionTag(where: ExecutionLocation, modifier: Modifier = Modifier) {
    val tone = when (where) {
        ExecutionLocation.LOKAL -> JarvisSemanticColor.primary
        ExecutionLocation.SLEEPY -> JarvisSemanticColor.subtleForeground
        ExecutionLocation.CLOUD -> JarvisSemanticColor.warning
        ExecutionLocation.EXTERN -> JarvisSemanticColor.mutedForeground
    }
    Text(
        text = where.name,
        modifier = modifier
            .border(1.dp, tone.copy(alpha = 0.5f), RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 1.dp),
        color = tone,
        fontSize = 10.sp,
        lineHeight = 16.sp,
    )
}

@Composable
fun JarvisPrivacyTag(mode: PrivacyMode, modifier: Modifier = Modifier) {
    val tone = when (mode) {
        PrivacyMode.NORMAL -> JarvisSemanticColor.subtleForeground
        PrivacyMode.PRIVACY -> JarvisSemanticColor.primary
        PrivacyMode.PRIVACY_LOCK -> JarvisSemanticColor.warning
    }
    Row(modifier = modifier, verticalAlignment = Alignment.CenterVertically) {
        androidx.compose.foundation.layout.Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(tone),
        )
        Spacer(Modifier.width(6.dp))
        Text(text = mode.name, color = tone, fontSize = 10.sp)
    }
}
