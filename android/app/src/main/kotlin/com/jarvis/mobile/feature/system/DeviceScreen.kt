package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.feature.common.DetailScaffold
import androidx.compose.material3.Text

private const val UNBOUND = "Nicht gebunden"

private val androidCapabilities = listOf(
    "Systemsteuerung" to "Systemnahe Einstellungen und Schalter.",
    "App-Steuerung" to "Starten, Wechseln und Bedienen von Apps.",
    "Bildschirm" to "Sichtbare Inhalte lesen und Aktionen ausführen.",
    "Medien" to "Wiedergabe und Lautstärke.",
    "Benachrichtigungen" to "Lesen und Beantworten.",
    "Dateien" to "Lokale Dateien lesen und ablegen.",
)

private val deviceInfoFields = listOf("Android-Version", "Gerätemodell", "Hardware-Beschleunigung", "Speicherstatus")

/**
 * Ported 1:1 from src/components/jarvis/screens/device-screen.tsx. The four
 * device-information fields deliberately stay "Nicht gebunden" - the web
 * reference reads them only through real Android APIs once bound, never
 * assumed, so this port does not pre-fill them from android.os.Build either.
 */
@Composable
fun DeviceScreen(onBack: () -> Unit) {
    DetailScaffold(
        title = "Gerät",
        subtitle = "Android und Dienste",
        onBack = onBack,
        backLabel = "Zurück zum Kontrollzentrum",
    ) {
        JarvisSectionHeader("J.A.R.V.I.S Dienst")
        JarvisListGroup {
            JarvisListRow(
                title = "Vordergrunddienst",
                subtitle = "Für dauerhafte lokale Verfügbarkeit vorgesehen, wird überarbeitet.",
                trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = comparisonBaseline.labels.backgroundService, dot = false) },
            )
        }
        FootNote("Der Dienstzustand wird erst aus dem System gelesen. Es wird hier weder ein laufender noch ein gestoppter Dienst behauptet.")

        JarvisSectionHeader("Android-Fähigkeiten")
        JarvisListGroup {
            androidCapabilities.forEach { (title, detail) -> JarvisListRow(title = title, subtitle = detail) }
        }
        FootNote("Fähigkeitskategorien, keine Aussage über die Unterstützung auf einem konkreten Gerät.")

        JarvisSectionHeader("Geräteinformationen")
        JarvisListGroup {
            deviceInfoFields.forEach { field ->
                JarvisListRow(title = field, trailing = { MonoValue(UNBOUND) })
            }
        }

        JarvisSectionHeader("Prüfprinzip")
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Geräte- und Hardwareeigenschaften werden ausschließlich über echte Android-APIs " +
                "ermittelt. Es wird nichts als unterstützt angenommen, und fehlende Werte bleiben " +
                "sichtbar ungebunden.",
        )
    }
}

@Composable
private fun MonoValue(text: String) {
    Text(text = text, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = JarvisSemanticColor.mutedForeground)
}

@Composable
private fun FootNote(text: String) {
    Text(
        text = text,
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}
