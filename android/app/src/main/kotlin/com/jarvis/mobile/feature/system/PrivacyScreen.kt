package com.jarvis.mobile.feature.system

import androidx.compose.runtime.Composable
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.PrivacyBlock
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Scaffolded from src/components/jarvis/screens/privacy-screen.tsx. The three
 * modes and the hard-boundary statement are ported verbatim; per-capability
 * enforcement rows follow with [com.jarvis.mobile.core.privacy.PrivacyGate]
 * in a later commit.
 */
@Composable
fun PrivacyScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Privacy",
        subtitle = "NORMAL / PRIVACY / PRIVACY_LOCK und Regeln für geschützte Fähigkeiten.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Privacy Mode")
        PrivacyBlock()
    }
}
