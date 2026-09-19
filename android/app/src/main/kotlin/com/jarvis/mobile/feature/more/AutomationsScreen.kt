package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Scaffolded from src/components/jarvis/screens/automations-screen.tsx. The
 * editor's dirty-state discard confirmation (goal spec Sec.8) is implemented
 * in [AutomationEditorScreen], since that is the architecturally locked part;
 * the list content itself follows row-level in a later commit.
 */
@Composable
fun AutomationsScreen(onBack: () -> Unit, onCreateAutomation: () -> Unit) {
    DetailScaffold(
        title = "Automationen",
        subtitle = "Makros, Zeitpläne, Routinen.",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Automationen")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Noch keine Automation angelegt",
            body = "Makros, Zeitpläne und Routinen erscheinen hier, sobald sie angelegt wurden.",
        )
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.lg)) {
            JarvisButton(text = "Automation anlegen", variant = JarvisButtonVariant.PRIMARY, fullWidth = true, onClick = onCreateAutomation)
        }
    }
}
