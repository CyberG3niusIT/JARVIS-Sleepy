package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import kotlinx.coroutines.delay

/**
 * Ported 1:1 from src/components/jarvis/prototype-state.tsx.
 *
 * Every newly interactive surface in this Phase 1 UI port may only change
 * local in-memory Compose state. Nothing is persisted, no Android permission
 * flow, no scheduler, no runtime and no backend is touched.
 */

/** Standard closing sentence after a completed prototype interaction. */
const val JARVIS_DESIGN_STATE_ACTION = "Entwurfszustand, keine Runtime-Aktion ausgeführt."

/** Used where a demo area shows example entries instead of device data. */
const val JARVIS_DEMO_AREA_NOTE =
    "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar."

/** Banner for a screen whose controls are frontend specification only. */
@Composable
fun JarvisPrototypeBanner(text: String, modifier: Modifier = Modifier) {
    JarvisInlineNotice(text = text, tone = JarvisNoticeTone.INFO, modifier = modifier.padding(horizontal = 16.dp))
}

class JarvisActionResultState {
    var message by mutableStateOf<String?>(null)
        private set

    suspend fun report(next: String, timeoutMs: Long = 6000) {
        message = next
        delay(timeoutMs)
        if (message == next) message = null
    }
}

@Composable
fun rememberJarvisActionResult(): JarvisActionResultState = remember { JarvisActionResultState() }

/**
 * Polite announcement of the result of a prototype action.
 * Renders nothing until an action ran, so no screen starts with a claim.
 */
@Composable
fun JarvisActionResultText(message: String?, modifier: Modifier = Modifier) {
    Text(
        text = message ?: "",
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}

/** Field label plus value row for compact detail sheets. */
@Composable
fun JarvisDetailField(label: String, value: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
    ) {
        Text(text = label.uppercase(), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
        Text(
            text = value,
            color = JarvisSemanticColor.subtleForeground,
            fontSize = 12.sp,
            lineHeight = 20.sp,
            textAlign = androidx.compose.ui.text.style.TextAlign.End,
        )
    }
}
