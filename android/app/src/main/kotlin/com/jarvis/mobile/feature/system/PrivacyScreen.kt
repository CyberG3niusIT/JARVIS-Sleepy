package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDialog
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisPrivacyTag
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/privacy-screen.tsx. The real
 * PrivacyGate is not wired here, see android/OPEN_DECISIONS.md Sec.2: this
 * selector only ever changes local Compose state to review the mode-change
 * flow (explain -> confirm for a stricter mode, confirm for relaxing), and
 * never touches [comparisonBaseline] or a real policy.
 */
@Composable
fun PrivacyScreen(onBack: () -> Unit) {
    val baseline = comparisonBaseline.privacyMode
    var selectedMode by remember { mutableStateOf(baseline) }
    var overlay by remember { mutableStateOf<PrivacyOverlay>(PrivacyOverlay.None) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

    fun closeOverlay() { overlay = PrivacyOverlay.None }

    fun applyMode(target: PrivacyMode) {
        selectedMode = target
        closeOverlay()
        scope.launch {
            actionResult.report("Modus auf $target gesetzt (nur lokale Auswahl). Entwurfszustand, keine Runtime-Aktion ausgeführt.")
        }
    }

    fun requestMode(target: PrivacyMode) {
        if (target == selectedMode) return
        overlay = if (privacyModeRank.getValue(target) > privacyModeRank.getValue(selectedMode)) {
            PrivacyOverlay.Explain(target)
        } else {
            PrivacyOverlay.ConfirmRelax(target)
        }
    }

    fun continueFromExplanation(target: PrivacyMode) {
        overlay = if (target == PrivacyMode.PRIVACY_LOCK) PrivacyOverlay.ConfirmLock(target) else {
            applyMode(target)
            PrivacyOverlay.None
        }
    }

    DetailScaffold(
        title = "Privacy",
        subtitle = "Schutzgrenzen",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Das echte PrivacyGate ist hier nicht gebunden. Diese Auswahl ist eine " +
                "lokale Vorschau der Moduswechsel-Abfolge und ändert keine Laufzeit-Policy.",
        )

        JarvisSectionHeader("Modus auswählen")
        JarvisListGroup {
            privacyModes.forEach { mode ->
                JarvisListRow(
                    title = mode.name,
                    subtitle = privacyModeCopy.getValue(mode),
                    selected = mode == selectedMode,
                    onClick = { requestMode(mode) },
                    trailing = {
                        if (mode == selectedMode) {
                            JarvisStatusTag(state = SystemState.DESIGN_STATE, label = "Ausgewählt (Entwurf)", dot = false)
                        } else {
                            JarvisPrivacyTag(mode = mode)
                        }
                    },
                )
            }
        }
        Text(
            text = "Ein Wechsel in einen strengeren Modus zeigt zuerst eine Erklärung der " +
                "betroffenen Fähigkeiten. PRIVACY_LOCK und die Rückkehr zu NORMAL verlangen " +
                "zusätzlich eine ausdrückliche Bestätigung.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
        JarvisActionResultText(message = actionResult.message)
        Text(
            text = "Referenzwert der Projektbasis: ${baseline.name} (unverändert, unabhängig von dieser Auswahl).",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        )

        JarvisSectionHeader("Geschützte Fähigkeiten")
        JarvisListGroup {
            protectedGroups.forEach { JarvisListRow(title = it.title, subtitle = it.detail) }
        }

        JarvisSectionHeader("Garantien")
        JarvisListGroup {
            privacyGuarantees.forEach { JarvisListRow(title = it) }
        }

        JarvisSectionHeader("Status")
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Das zentrale Privacy-Gate ist noch nicht implementiert. Beschrieben ist die " +
                "Zielarchitektur: eine einzige Prüfstelle, die geschützte Fähigkeiten vor der " +
                "Ausführung sperrt, statt sie nachträglich zu filtern.",
        )
    }

    val explainTarget = (overlay as? PrivacyOverlay.Explain)?.target
    JarvisBottomSheet(open = explainTarget != null, onClose = ::closeOverlay, title = "Was sich ändert") {
        if (explainTarget != null) {
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(
                    text = "Wechsel zu ${explainTarget.name}: ${changeSummaryByMode.getValue(explainTarget)}",
                    color = JarvisSemanticColor.subtleForeground,
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                )
            }
            JarvisSectionHeader("Betroffene Fähigkeitsgruppen")
            JarvisListGroup {
                affectedGroupsByMode.getValue(explainTarget).forEach { title ->
                    val group = protectedGroups.find { it.title == title }
                    JarvisListRow(title = title, subtitle = group?.detail)
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.lg),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
            ) {
                JarvisButton(text = "Abbrechen", onClick = ::closeOverlay, modifier = Modifier.weight(1f))
                JarvisButton(
                    text = "Fortfahren",
                    variant = JarvisButtonVariant.PRIMARY,
                    onClick = { continueFromExplanation(explainTarget) },
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }

    val lockTarget = (overlay as? PrivacyOverlay.ConfirmLock)?.target
    JarvisDialog(
        open = lockTarget != null,
        onClose = ::closeOverlay,
        title = "PRIVACY_LOCK aktivieren",
        description = "Diese Stufe sperrt zusätzlich externe Ausführungspfade. Das ist eine " +
            "lokale Entwurfsauswahl, keine Runtime-Aktion. Wirklich fortfahren?",
        actions = {
            JarvisButton(text = "Abbrechen", onClick = ::closeOverlay)
            JarvisButton(
                text = "PRIVACY_LOCK bestätigen",
                variant = JarvisButtonVariant.DESTRUCTIVE,
                onClick = { lockTarget?.let(::applyMode) },
                modifier = Modifier.padding(start = JarvisSpacing.sm),
            )
        },
    )

    val relaxTarget = (overlay as? PrivacyOverlay.ConfirmRelax)?.target
    JarvisDialog(
        open = relaxTarget != null,
        onClose = ::closeOverlay,
        title = "Weniger strengen Modus wählen",
        description = relaxTarget?.let {
            "Wechsel zu ${it.name}. Zuvor gesperrte Fähigkeiten würden wieder freigegeben. " +
                "Das ist eine lokale Entwurfsauswahl, keine Runtime-Aktion. Wirklich fortfahren?"
        },
        actions = {
            JarvisButton(text = "Abbrechen", onClick = ::closeOverlay)
            JarvisButton(
                text = "Bestätigen",
                variant = JarvisButtonVariant.PRIMARY,
                onClick = { relaxTarget?.let(::applyMode) },
                modifier = Modifier.padding(start = JarvisSpacing.sm),
            )
        },
    )
}
