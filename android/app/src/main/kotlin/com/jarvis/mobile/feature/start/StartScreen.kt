package com.jarvis.mobile.feature.start

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.PrivacyBlock
import com.jarvis.mobile.core.designsystem.component.RoutingLadderBlock
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.core.model.routingLadderShort
import com.jarvis.mobile.core.model.stateLabel

/**
 * Ported 1:1 from src/components/jarvis/screens/start-screen.tsx.
 *
 * Operational overview of JARVIS Mobile: is the local runtime usable, what
 * blocks it, where does work execute, what is the privacy state, is Sleepy
 * available, what is the local-first decision order. No feature management
 * here. Every value comes from [comparisonBaseline]; nothing is measured,
 * nothing is simulated.
 */
@Composable
fun StartScreen(onOpenChat: () -> Unit, onOpenSystem: (() -> Unit)? = null) {
    val overall = if (comparisonBaseline.runtimeBound) {
        "Lokale Runtime bereit"
    } else {
        "Lokale Runtime noch nicht vollständig eingerichtet"
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        StatusSummary(headline = overall)

        JarvisSectionHeader("Aktuelle Blocker")
        JarvisListGroup {
            JarvisListRow(
                title = "Lokales Modell",
                subtitle = "Modellgestützte lokale Antworten sind erst nach dem Laden eines Modells verfügbar.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.localModel) },
            )
            JarvisListRow(
                title = "Berechtigungen",
                subtitle = "Benötigte Android-Berechtigungen sind noch nicht vollständig freigegeben.",
                trailing = { JarvisStatusTag(state = SystemState.PERMISSION_REQUIRED, label = comparisonBaseline.labels.permissions) },
            )
        }
        FootNote("Beides betrifft die volle lokale Fähigkeit. Verwaltet wird es unter System.")

        JarvisSectionHeader("Optionale Runtimes")
        JarvisListGroup {
            JarvisListRow(
                title = "Sleepy",
                subtitle = "Optionale vertraute Runtime für begrenzte Übergaben.",
                trailing = { JarvisStatusTag(state = SystemState.UNAVAILABLE, label = comparisonBaseline.labels.sleepy) },
            )
            JarvisListRow(
                title = "Cloud",
                subtitle = "Optional und nur nach ausdrücklicher Freigabe.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.cloud) },
            )
        }
        FootNote("Sleepy und Cloud sind für den lokalen Betrieb nicht grundsätzlich erforderlich.")

        JarvisSectionHeader("Privacy")
        PrivacyBlock()

        JarvisSectionHeader("Entscheidungsreihenfolge")
        RoutingLadderBlock(steps = routingLadderShort, localSteps = 3)
        FootNote("Kurzform. Die vollständige Reihenfolge steht unter System.")

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.xl),
            verticalArrangement = Arrangement.spacedBy(JarvisSpacing.sm),
        ) {
            JarvisButton(text = "Chat öffnen", variant = JarvisButtonVariant.PRIMARY, fullWidth = true, onClick = onOpenChat)
            if (onOpenSystem != null) {
                Text(
                    text = "Zum Kontrollzentrum",
                    color = JarvisSemanticColor.mutedForeground,
                    fontSize = 12.sp,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(androidx.compose.foundation.shape.RoundedCornerShape(6.dp))
                        .clickable(role = Role.Button, onClick = onOpenSystem)
                        .padding(vertical = JarvisSpacing.sm),
                )
            }
        }
    }
}

@Composable
private fun StatusSummary(headline: String) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(JarvisSemanticColor.surface)
            .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
            .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.lg),
    ) {
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "J.A.R.V.I.S Mobile", color = JarvisSemanticColor.foreground, fontSize = 15.sp, lineHeight = 20.sp)
                Text(
                    text = headline,
                    color = JarvisSemanticColor.subtleForeground,
                    fontSize = 13.sp,
                    lineHeight = 20.sp,
                    modifier = Modifier.padding(top = JarvisSpacing.xs),
                )
            }
            JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.runtime)
        }
        Text(
            text = "${stateLabel.getValue(SystemState.DESIGN_STATE)}. Keine gemessenen Laufzeitwerte. " +
                "Standardausführung: ${comparisonBaseline.execution}.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(top = JarvisSpacing.sm),
        )
    }
}

@Composable
private fun FootNote(text: String) {
    Text(
        text = text,
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = Modifier.padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
    )
}
