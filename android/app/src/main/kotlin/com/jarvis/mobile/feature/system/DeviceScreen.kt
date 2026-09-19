package com.jarvis.mobile.feature.system

import android.os.Build
import androidx.compose.runtime.Composable
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Scaffolded from src/components/jarvis/screens/device-screen.tsx. Uses real
 * [Build] fields (the same kind of static device metadata the web reference
 * describes), never a fabricated value; JARVIS-service status is design-state
 * until a real service binding exists.
 */
@Composable
fun DeviceScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Gerät",
        subtitle = "Lokale Android- und Geräteinformationen sowie Zustand des JARVIS-Dienstes.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Gerät")
        JarvisDetailField(label = "Modell", value = "${Build.MANUFACTURER} ${Build.MODEL}")
        JarvisDetailField(label = "Android-Version", value = "API ${Build.VERSION.SDK_INT}")
        JarvisDetailField(label = "Build", value = Build.DISPLAY)
    }
}
