package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisEmptyState
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

private enum class AddModelChoice { IMPORT, KATALOG }

/**
 * Ported 1:1 from src/components/jarvis/screens/models-screen.tsx and
 * models-demo.tsx. The truthful baseline model registry stays empty on
 * purpose - it is not bound to a runtime yet, which is not a claim that the
 * real device carries no model file. [ModelsDemoSection] is the clearly
 * labelled Zustandsdemonstration with its own local state machine.
 */
@Composable
fun ModelsScreen(onBack: () -> Unit) {
    var sheetOpen by rememberSaveable { mutableStateOf(false) }
    var choice by rememberSaveable { mutableStateOf<AddModelChoice?>(null) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

    fun closeSheet() { sheetOpen = false; choice = null }
    fun report(message: String) { scope.launch { actionResult.report(message) } }

    DetailScaffold(
        title = "Modelle",
        subtitle = "Lokale Inferenz",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("Aktueller Zustand")
        JarvisListGroup {
            JarvisListRow(
                title = "Geladenes Modell",
                trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = comparisonBaseline.labels.localModel) },
            )
            JarvisListRow(
                title = "Lokale Runtime",
                subtitle = "Vorgesehene Inferenz-Runtime auf dem Gerät.",
                trailing = { MonoValue(comparisonBaseline.labels.modelRuntime) },
            )
            JarvisListRow(
                title = "Runtime-Bindung",
                trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, label = comparisonBaseline.labels.runtime) },
            )
        }

        JarvisSectionHeader("Lokale Modelle")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Modellverwaltung nicht verfügbar",
            body = "Eine lokale Modell-Runtime ist in dieser App-Version nicht verfügbar. Deshalb können Modelle derzeit weder geprüft noch importiert oder geladen werden.",
        )

        JarvisSectionHeader("Verwaltung")
        JarvisListGroup {
            managementCapabilities.forEach { (title, detail) ->
                JarvisListRow(title = title, subtitle = detail)
            }
        }
        Text(
            text = "Diese Funktionen benötigen zuerst eine unterstützte lokale Modell-Runtime und ein festgelegtes Modellformat.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
    }

}

private val managementCapabilities = listOf(
    "Import lokaler Modelle" to "Unterstützte Modelldateien aus dem Gerätespeicher übernehmen.",
    "Download im Hintergrund" to "Hintergrunddownload über WorkManager mit Netzwerkprüfung.",
    "Pause / Fortsetzen" to "Laufende Downloads anhalten und später fortsetzen.",
    "Integritätsprüfung" to "Prüfsumme nach SHA-256 nach dem Download.",
    "Kompatibilitätsprüfung" to "Prüfung gegen die LiteRT-Runtime vor dem Laden.",
)

@Composable
private fun MonoValue(text: String) {
    Text(text = text, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = JarvisSemanticColor.subtleForeground)
}
