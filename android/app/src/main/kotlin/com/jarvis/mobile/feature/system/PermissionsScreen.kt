package com.jarvis.mobile.feature.system

import androidx.compose.runtime.Composable
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisPermissionRequiredState
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.feature.common.DetailScaffold
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * Scaffolded from src/components/jarvis/screens/permissions-screen.tsx. Real
 * Android permission-state reads follow via [com.jarvis.mobile.core.runtime.PermissionGateway]
 * in a later commit; this screen names the actual capabilities that need a
 * permission, per the web reference.
 */
@Composable
fun PermissionsScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Berechtigungen",
        subtitle = "Echter Android-Berechtigungsstatus und Auswirkung auf Fähigkeiten.",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Benötigte Berechtigungen")
        JarvisListGroup {
            JarvisListRow(title = "Bedienungshilfen", subtitle = "Generische App-Steuerung", trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED) })
            JarvisListRow(title = "Bildschirmzugriff", subtitle = "Screen Understanding, OCR", trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED) })
            JarvisListRow(title = "Benachrichtigungszugriff", subtitle = "Listener, Auto-Reply-Regeln", trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED) })
            JarvisListRow(title = "Mikrofon", subtitle = "Wake Word, Spracherkennung", trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED) })
        }
        JarvisPermissionRequiredState(modifier = Modifier.padding(horizontal = 16.dp, vertical = 16.dp))
    }
}
