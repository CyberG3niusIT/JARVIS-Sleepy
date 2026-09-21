package com.jarvis.mobile.feature.system

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisNoticeTone
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/permissions-screen.tsx. The
 * real Android permission state is intentionally not invented; each access
 * area opens a detail sheet explaining why it exists and what it unlocks.
 * The only interactive state lives in the sheet's clearly labelled demo area
 * ([com.jarvis.mobile.core.designsystem.component.JARVIS_DEMO_AREA_NOTE]),
 * never in the baseline list.
 */
@Composable
fun PermissionsScreen(onBack: () -> Unit) {
    var openId by rememberSaveable { mutableStateOf<String?>(null) }
    val openGroup = permissionGroups.find { it.id == openId }

    DetailScaffold(
        title = "Berechtigungen",
        subtitle = "Android-Zugriffe",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Gesamtzustand")
        JarvisListGroup {
            JarvisListRow(
                title = "Android-Berechtigungen",
                subtitle = "Die App liest den tatsächlichen Android-Berechtigungsstatus noch nicht aus.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = "Status nicht verfügbar") },
            )
        }

        JarvisSectionHeader("Zugriffsbereiche")
        JarvisListGroup {
            permissionGroups.forEach { group ->
                JarvisListRow(
                    title = group.title,
                    subtitle = group.purpose,
                    trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = PERMISSION_UNBOUND_STATUS, dot = false) },
                    chevron = true,
                    onClick = { openId = group.id },
                )
            }
        }

        JarvisSectionHeader("Freigabe")
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Berechtigungen können hier noch nicht angefragt oder geprüft werden. Bestehende Freigaben verwaltet Android in den Systemeinstellungen.",
        )
    }

    PermissionDetailSheet(group = openGroup, onClose = { openId = null })
}

@Composable
private fun PermissionDetailSheet(group: PermissionGroup?, onClose: () -> Unit) {
    JarvisBottomSheet(
        open = group != null,
        onClose = onClose,
        title = group?.title ?: "Berechtigung",
    ) {
        if (group == null) return@JarvisBottomSheet
        Column {
            JarvisDetailField(label = "Warum nötig", value = group.whyNeeded)
            JarvisDetailField(label = "Freigeschaltete Fähigkeiten", value = group.capabilities.joinToString("\n"))
            JarvisDetailField(label = "Erforderlichkeit", value = group.requirement)

            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp),
                text = "Der aktuelle Freigabestatus ist nicht verfügbar. Diese Ansicht erklärt nur, wofür der Zugriff benötigt wird.",
            )
        }
    }
}
