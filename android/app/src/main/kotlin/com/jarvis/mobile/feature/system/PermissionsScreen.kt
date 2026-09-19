package com.jarvis.mobile.feature.system

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
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
    var openId by remember { mutableStateOf<String?>(null) }
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
                subtitle = "Der tatsächliche Systemzustand ist im Entwurfszustand noch nicht angebunden.",
                trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED, label = comparisonBaseline.labels.permissions) },
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
            text = "Die Freigabe erfolgt später über den jeweils passenden Android-Berechtigungsablauf. " +
                "Ein Widerruf bleibt dort, wo Android das unterstützt, über die Systemeinstellungen " +
                "möglich. Im Entwurfszustand gibt es hier keine Schaltfläche, die eine Freigabe " +
                "auslösen könnte.",
        )
    }

    PermissionDetailSheet(group = openGroup, onClose = { openId = null })
}

@Composable
private fun PermissionDetailSheet(group: PermissionGroup?, onClose: () -> Unit) {
    var demoState by remember(group?.id) { mutableStateOf(PermissionGrantState.NOT_REQUESTED) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

    fun report(message: String) {
        scope.launch { actionResult.report(message) }
    }

    val canRequest = demoState == PermissionGrantState.NOT_REQUESTED ||
        demoState == PermissionGrantState.DENIED ||
        demoState == PermissionGrantState.REVOKED

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

            JarvisSectionHeader("Zustandsdemonstration")
            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp),
                text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.",
            )

            JarvisDetailField(label = "Demo-Zustand", value = permissionGrantLabel.getValue(demoState))

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = JarvisSpacing.sm)
                    .background(JarvisSemanticColor.surface)
                    .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft)),
            ) {
                demoStateOrder.forEach { state ->
                    val checked = state == demoState
                    JarvisListRow(
                        title = permissionGrantLabel.getValue(state),
                        selected = checked,
                        trailing = { JarvisStatusTag(state = permissionGrantTone.getValue(state), label = if (checked) "Ausgewählt" else "", dot = !checked) },
                        onClick = {
                            demoState = state
                            report("Demo-Zustand auf \"${permissionGrantLabel.getValue(state)}\" gesetzt. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
                        },
                    )
                }
            }

            if (demoState == PermissionGrantState.DENIED_PERMANENTLY) {
                JarvisInlineNotice(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    tone = JarvisNoticeTone.WARNING,
                    text = "Bei dauerhafter Ablehnung führt die spätere Route direkt in die " +
                        "Android-Systemeinstellungen. In diesem Entwurf wird nichts geöffnet.",
                )
            }
            if (demoState == PermissionGrantState.NOT_APPLICABLE) {
                JarvisInlineNotice(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    text = "Diese Berechtigung ist im Demo-Zustand nicht zutreffend, eine Anfrage ist hier nicht verfügbar.",
                )
            }

            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
                if (canRequest) {
                    JarvisButton(
                        text = "Berechtigung anfragen",
                        variant = JarvisButtonVariant.PRIMARY,
                        fullWidth = true,
                        onClick = {
                            demoState = PermissionGrantState.GRANTED
                            report("Berechtigung angefragt, Demo-Zustand auf \"Erteilt\" gesetzt. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
                        },
                    )
                }
                JarvisButton(
                    text = "Demo-Zustand zurücksetzen",
                    fullWidth = true,
                    modifier = Modifier.padding(top = JarvisSpacing.sm),
                    onClick = {
                        demoState = PermissionGrantState.NOT_REQUESTED
                        report("Demo-Zustand zurückgesetzt. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
                    },
                )
            }

            JarvisActionResultText(message = actionResult.message)
        }
    }
}
