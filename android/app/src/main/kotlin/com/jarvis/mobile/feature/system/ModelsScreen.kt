package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Column
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

/**
 * Ported 1:1 from src/components/jarvis/screens/models-screen.tsx. The local
 * model registry stays empty on purpose - it is not bound to a runtime yet,
 * which is not a claim that the real device carries no model file. The
 * catalog browser / local-file import flows inside the add-model sheet
 * (models-demo.tsx) are deferred, see android/PORTING_PLAN.md; the sheet's
 * two-choice entry point is ported.
 */
@Composable
fun ModelsScreen(onBack: () -> Unit) {
    var sheetOpen by remember { mutableStateOf(false) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()

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
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.localModel) },
            )
            JarvisListRow(
                title = "Lokale Runtime",
                subtitle = "Vorgesehene Inferenz-Runtime auf dem Gerät.",
                trailing = { MonoValue(comparisonBaseline.labels.modelRuntime) },
            )
            JarvisListRow(
                title = "Runtime-Bindung",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.runtime) },
            )
        }

        JarvisSectionHeader("Lokale Modelle")
        JarvisEmptyState(
            modifier = Modifier.padding(horizontal = 16.dp),
            title = "Keine Modelldaten verfügbar",
            body = "Die lokale Modellregistrierung ist im Prototyp noch nicht an eine Runtime " +
                "gebunden. Modelle können später lokal importiert oder über den Modellkatalog " +
                "verwaltet werden.",
        )
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
            JarvisButton(
                text = "Modell hinzufügen",
                variant = JarvisButtonVariant.PRIMARY,
                fullWidth = true,
                onClick = { sheetOpen = true },
            )
        }
        JarvisActionResultText(message = actionResult.message)

        JarvisSectionHeader("Verwaltung")
        JarvisListGroup {
            managementCapabilities.forEach { (title, detail) ->
                JarvisListRow(title = title, subtitle = detail)
            }
        }
        Text(
            text = "Fähigkeiten der Modellverwaltung. Es werden hier keine laufenden Runtime-Vorgänge simuliert.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
    }

    JarvisBottomSheet(open = sheetOpen, onClose = { sheetOpen = false }, title = "Modell hinzufügen") {
        JarvisListGroup {
            JarvisListRow(
                title = "Lokale Datei importieren",
                subtitle = "Unterstützte lokale Modelldatei auswählen.",
                chevron = true,
                onClick = {
                    sheetOpen = false
                    scope.launch { actionResult.report("Lokaler Import ist im Prototyp noch nicht angebunden.") }
                },
            )
            JarvisListRow(
                title = "Modellkatalog öffnen",
                subtitle = "Kompatibles Modell auswählen und lokal herunterladen.",
                chevron = true,
                onClick = {
                    sheetOpen = false
                    scope.launch { actionResult.report("Modellkatalog ist im Prototyp noch nicht angebunden.") }
                },
            )
        }
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
