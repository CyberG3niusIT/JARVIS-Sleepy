package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisNotImplementedState
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/** Scaffolded from src/components/jarvis/screens/voice-screen.tsx. */
@Composable
fun VoiceScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Voice",
        subtitle = "Wake Word, Spracherkennung, Sprachausgabe, Mikrofonzustand.",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Sprachsteuerung")
        JarvisNotImplementedState(
            modifier = Modifier.padding(horizontal = 16.dp),
            body = "Wake Word, Spracherkennung und Sprachausgabe ersetzen die bisherige Lösung " +
                "vollständig, sind aber im Prototyp noch nicht angebunden.",
        )
    }
}
