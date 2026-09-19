package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor

/**
 * Ported 1:1 from src/components/jarvis/screens/detail-header.tsx.
 * Shared compact header for detail screens under System and under Mehr.
 * Back affordance, title and one technical secondary line. No hero treatment.
 */

const val JARVIS_MORE_BACK_LABEL = "Zurück zu Mehr"
private const val SYSTEM_BACK_LABEL = "Zurück zum Kontrollzentrum"

@Composable
fun JarvisDetailHeader(
    title: String,
    subtitle: String,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    backLabel: String = SYSTEM_BACK_LABEL,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(JarvisSemanticColor.surface)
            .padding(horizontal = 8.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack, modifier = Modifier.size(48.dp)) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = backLabel,
                tint = JarvisSemanticColor.subtleForeground,
            )
        }
        Column(modifier = Modifier.padding(start = 4.dp)) {
            Text(text = title, color = JarvisSemanticColor.foreground, fontSize = 15.sp, lineHeight = 20.sp)
            Text(
                text = subtitle,
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 12.sp,
                lineHeight = 16.sp,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
    }
}

/** Shared closing note: states come from the project base, not from telemetry. */
@Composable
fun JarvisDesignStateNote(modifier: Modifier = Modifier) {
    Text(
        text = "Entwurfszustand. Angezeigte Zustände stammen aus der aktuellen Projektbasis, " +
            "nicht aus gemessener Laufzeittelemetrie.",
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}
