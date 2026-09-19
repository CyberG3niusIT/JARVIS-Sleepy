package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.model.SystemState

/**
 * Ported 1:1 from src/components/jarvis/controls.tsx (InlineNotice,
 * LoadingState, EmptyState, ErrorState, PermissionRequiredState,
 * NotImplementedState).
 */

enum class JarvisNoticeTone { INFO, WARNING, ERROR }

@Composable
fun JarvisInlineNotice(
    text: String,
    modifier: Modifier = Modifier,
    tone: JarvisNoticeTone = JarvisNoticeTone.INFO,
) {
    val (ring, contentColor, icon) = when (tone) {
        JarvisNoticeTone.INFO -> Triple(JarvisSemanticColor.border, JarvisSemanticColor.subtleForeground, Icons.Filled.Info)
        JarvisNoticeTone.WARNING -> Triple(JarvisSemanticColor.warning.copy(alpha = 0.5f), JarvisSemanticColor.warning, Icons.Filled.Warning)
        JarvisNoticeTone.ERROR -> Triple(JarvisSemanticColor.destructive.copy(alpha = 0.5f), JarvisSemanticColor.destructive, Icons.Filled.Warning)
    }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(JarvisRadii.sm))
            .border(1.dp, ring, RoundedCornerShape(JarvisRadii.sm))
            .padding(horizontal = JarvisSpacing.md, vertical = JarvisSpacing.sm),
    ) {
        Icon(icon, contentDescription = null, tint = contentColor, modifier = Modifier.padding(top = 1.dp))
        Text(
            text = text,
            color = JarvisSemanticColor.subtleForeground,
            fontSize = 12.sp,
            lineHeight = 18.sp,
            modifier = Modifier.padding(start = JarvisSpacing.sm),
        )
    }
}

/** Honest waiting indicator. Never shown for a state that is already known. */
@Composable
fun JarvisLoadingState(modifier: Modifier = Modifier, label: String = "Wird geladen") {
    Column(modifier = modifier.fillMaxWidth().padding(JarvisSpacing.lg)) {
        Text(text = label, color = JarvisSemanticColor.mutedForeground, fontSize = 12.sp)
        LinearProgressIndicator(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = JarvisSpacing.sm)
                .clip(RoundedCornerShape(JarvisRadii.xs)),
            color = JarvisSemanticColor.primary,
            trackColor = JarvisSemanticColor.borderSoft,
        )
    }
}

@Composable
private fun JarvisStatePanel(
    icon: ImageVector,
    title: String,
    body: String,
    modifier: Modifier = Modifier,
    state: SystemState? = null,
    iconTint: androidx.compose.ui.graphics.Color = JarvisSemanticColor.mutedForeground,
    action: @Composable (() -> Unit)? = null,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(JarvisRadii.sm))
            .border(1.dp, JarvisSemanticColor.border, RoundedCornerShape(JarvisRadii.sm))
            .padding(JarvisSpacing.lg),
    ) {
        Icon(icon, contentDescription = null, tint = iconTint)
        Text(
            text = title,
            color = JarvisSemanticColor.foreground,
            fontSize = 13.sp,
            modifier = Modifier.padding(top = JarvisSpacing.sm),
        )
        Text(
            text = body,
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 12.sp,
            lineHeight = 18.sp,
            modifier = Modifier.padding(top = JarvisSpacing.xs),
        )
        if (state != null) {
            JarvisStatusTag(state = state, modifier = Modifier.padding(top = JarvisSpacing.sm))
        }
        action?.invoke()
    }
}

@Composable
fun JarvisEmptyState(
    modifier: Modifier = Modifier,
    title: String = "Noch nichts vorhanden",
    body: String = "Sobald Einträge entstehen, erscheinen sie hier.",
) {
    JarvisStatePanel(icon = Icons.Filled.Inbox, title = title, body = body, modifier = modifier)
}

@Composable
fun JarvisErrorState(
    modifier: Modifier = Modifier,
    title: String = "Vorgang fehlgeschlagen",
    body: String = "Der Vorgang konnte nicht abgeschlossen werden. Bitte erneut versuchen.",
    onRetry: (() -> Unit)? = null,
) {
    JarvisStatePanel(
        icon = Icons.Filled.Warning,
        title = title,
        body = body,
        state = SystemState.ERROR,
        iconTint = JarvisSemanticColor.destructive,
        modifier = modifier,
        action = onRetry?.let { retry ->
            { JarvisButton(text = "Erneut versuchen", onClick = retry, modifier = Modifier.padding(top = JarvisSpacing.sm)) }
        },
    )
}

@Composable
fun JarvisPermissionRequiredState(
    modifier: Modifier = Modifier,
    title: String = "Berechtigung erforderlich",
    body: String = "Diese Fähigkeit braucht eine Android-Berechtigung. Ohne Freigabe passiert nichts, kein stiller Fallback.",
    onGrant: (() -> Unit)? = null,
) {
    JarvisStatePanel(
        icon = Icons.Filled.Lock,
        title = title,
        body = body,
        state = SystemState.PERMISSION_REQUIRED,
        iconTint = JarvisSemanticColor.warning,
        modifier = modifier,
        action = onGrant?.let { grant ->
            { JarvisButton(text = "Berechtigung öffnen", onClick = grant, modifier = Modifier.padding(top = JarvisSpacing.sm)) }
        },
    )
}

@Composable
fun JarvisNotImplementedState(
    modifier: Modifier = Modifier,
    title: String = "Noch nicht implementiert",
    body: String = "Diese Fähigkeit ist geplant, aber im Prototyp nicht angebunden.",
) {
    JarvisStatePanel(
        icon = Icons.Filled.Info,
        title = title,
        body = body,
        state = SystemState.NOT_IMPLEMENTED,
        modifier = modifier,
    )
}
