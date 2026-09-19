package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisNoticeTone

/**
 * Ported 1:1 from src/components/jarvis/screens/models-demo.tsx (ImportFlow,
 * CatalogBrowser). Both flows show the surface sequence only - no real
 * Android file picker or model catalog is bound; that binding stays open,
 * see android/OPEN_DECISIONS.md.
 */
@Composable
fun ModelImportFlow(onDone: (String) -> Unit) {
    var step by remember { mutableStateOf(ModelImportStep.AUSWAHL) }
    var failedAt by remember { mutableStateOf<ModelImportStep?>(null) }

    val failed = failedAt
    if (failed != null) {
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
            Text(text = modelImportStepLabel.getValue(failed).uppercase(), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
            JarvisInlineNotice(
                modifier = Modifier.padding(top = JarvisSpacing.sm),
                tone = JarvisNoticeTone.ERROR,
                text = if (failed == ModelImportStep.KOMPATIBILITAET) {
                    "Kompatibilitätsprüfung nicht bestanden (simuliert). Diese Beispieldatei gilt im Demozustand als nicht LiteRT-kompatibel."
                } else {
                    "Integritätsprüfung fehlgeschlagen (simuliert). Die Prüfsumme der Beispieldatei stimmt im Demozustand nicht überein."
                },
            )
            JarvisButton(text = "Erneut versuchen", modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = { failedAt = null })
        }
        return
    }

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
        Text(text = modelImportStepLabel.getValue(step).uppercase(), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)

        when (step) {
            ModelImportStep.AUSWAHL -> {
                JarvisInlineNotice(
                    modifier = Modifier.padding(top = JarvisSpacing.sm),
                    text = "Die Android-Dateiauswahl ist im Entwurfszustand nicht angebunden. Dieser " +
                        "Ablauf zeigt nur die Abfolge der Oberfläche, es wird keine reale Datei ausgewählt.",
                )
                JarvisButton(
                    text = "Beispieldatei auswählen (Demo)",
                    variant = JarvisButtonVariant.PRIMARY,
                    fullWidth = true,
                    modifier = Modifier.padding(top = JarvisSpacing.sm),
                    onClick = { step = ModelImportStep.KOMPATIBILITAET },
                )
            }
            ModelImportStep.KOMPATIBILITAET -> {
                JarvisInlineNotice(modifier = Modifier.padding(top = JarvisSpacing.sm), text = "Prüft die Beispieldatei im Demozustand gegen die LiteRT-Runtime.")
                Row(modifier = Modifier.padding(top = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                    JarvisButton(text = "Bestanden simulieren", variant = JarvisButtonVariant.PRIMARY, onClick = { step = ModelImportStep.INTEGRITAET })
                    JarvisButton(text = "Fehlschlag simulieren", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { failedAt = ModelImportStep.KOMPATIBILITAET })
                }
            }
            ModelImportStep.INTEGRITAET -> {
                JarvisInlineNotice(modifier = Modifier.padding(top = JarvisSpacing.sm), text = "Prüft die Prüfsumme der Beispieldatei im Demozustand nach SHA-256.")
                Row(modifier = Modifier.padding(top = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
                    JarvisButton(text = "Bestanden simulieren", variant = JarvisButtonVariant.PRIMARY, onClick = { step = ModelImportStep.REGISTRIERUNG })
                    JarvisButton(text = "Fehlschlag simulieren", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { failedAt = ModelImportStep.INTEGRITAET })
                }
            }
            ModelImportStep.REGISTRIERUNG -> {
                JarvisInlineNotice(modifier = Modifier.padding(top = JarvisSpacing.sm), text = "Registriert die Beispieldatei im Demozustand in der lokalen Modellliste.")
                JarvisButton(
                    text = "Registrierung abschließen",
                    variant = JarvisButtonVariant.PRIMARY,
                    fullWidth = true,
                    modifier = Modifier.padding(top = JarvisSpacing.sm),
                    onClick = {
                        step = ModelImportStep.FERTIG
                        onDone("Import der Beispieldatei abgeschlossen. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
                    },
                )
            }
            ModelImportStep.FERTIG -> {
                JarvisInlineNotice(modifier = Modifier.padding(top = JarvisSpacing.sm), text = "Import abgeschlossen (Demozustand). Es wurde keine reale Gerätedatei übernommen.")
            }
        }
    }
}

@Composable
fun ModelCatalogBrowser(onDone: (String) -> Unit) {
    var openId by remember { mutableStateOf<String?>(null) }
    val open = modelCatalogEntries.find { it.id == openId }

    Column {
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            text = "Katalogbeispiele, keine Empfehlung und kein Inventar. Der reale Modellkatalog ist im Entwurfszustand noch nicht angebunden.",
        )
        JarvisListGroup {
            modelCatalogEntries.forEach { c ->
                JarvisListRow(
                    title = c.name,
                    subtitle = "Katalogbeispiel, keine Empfehlung und kein Inventar, ${c.size}",
                    leading = { Icon(Icons.Filled.Storage, contentDescription = null, tint = JarvisSemanticColor.mutedForeground) },
                    chevron = true,
                    onClick = { openId = c.id },
                )
            }
        }
    }

    JarvisBottomSheet(open = open != null, onClose = { openId = null }, title = open?.name ?: "Katalogbeispiel") {
        if (open != null) {
            Column {
                JarvisDetailField(label = "Name", value = open.name)
                JarvisDetailField(label = "Quelle", value = "Modellkatalog (Beispiel)")
                JarvisDetailField(label = "Lokaler Zustand", value = "Nicht heruntergeladen")
                JarvisDetailField(label = "Kompatibilität", value = "Noch nicht geprüft")
                JarvisDetailField(label = "Integrität", value = "Noch nicht geprüft")
                JarvisDetailField(label = "Größe", value = open.size)
                JarvisDetailField(label = "Runtime-Zustand", value = "Nicht an eine Runtime gebunden")
                Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
                    JarvisButton(
                        text = "Download starten (Demo)",
                        variant = JarvisButtonVariant.PRIMARY,
                        fullWidth = true,
                        onClick = {
                            onDone("Download von \"${open.name}\" wurde im Entwurfszustand ausgelöst. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
                            openId = null
                        },
                    )
                }
            }
        }
    }
}
