package com.jarvis.mobile.feature.more

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisPrototypeBanner
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.JarvisTextField
import com.jarvis.mobile.core.designsystem.component.JarvisToggle
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.feature.common.DetailScaffold
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/voice-screen.tsx. Voice is
 * REPLACE in the mobile IA: no microphone permission state, wake word
 * engine, STT/TTS engine or latency is real here. The labelled
 * Zustandsdemonstration and the three configuration sheets only ever change
 * local, in-memory Compose state.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun VoiceScreen(onBack: () -> Unit) {
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()
    fun report(message: String) {
        scope.launch { actionResult.report("$message Entwurfszustand, keine Runtime-Aktion ausgeführt.") }
    }

    // Category A: all of this is user-set config/demo state (selected state,
    // sheet toggles, configured values) that should survive activity
    // recreation rather than silently resetting.
    var voiceState by rememberSaveable { mutableStateOf(VoiceState.IDLE) }
    fun goTo(next: VoiceState, note: String) {
        voiceState = next
        report(note)
    }

    var wakeWordSheetOpen by rememberSaveable { mutableStateOf(false) }
    var wakeWordEnabled by rememberSaveable { mutableStateOf(false) }
    var keyword by rememberSaveable { mutableStateOf("Jarvis") }
    var sensitivity by rememberSaveable { mutableStateOf("Mittel") }

    var sttSheetOpen by rememberSaveable { mutableStateOf(false) }
    var sttLanguage by rememberSaveable { mutableStateOf("Deutsch") }
    var sttLocalOnly by rememberSaveable { mutableStateOf(true) }
    var sttPunctuation by rememberSaveable { mutableStateOf(true) }

    var ttsSheetOpen by rememberSaveable { mutableStateOf(false) }
    var ttsVoice by rememberSaveable { mutableStateOf(ttsVoiceOptions[0]) }
    var tempo by rememberSaveable { mutableStateOf("Normal") }
    var volume by rememberSaveable { mutableStateOf("Normal") }

    val currentConfig = voiceStateConfig.getValue(voiceState)

    DetailScaffold(
        title = "Voice",
        subtitle = "Spracheingabe und Sprachausgabe",
        onBack = onBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        JarvisSectionHeader("Gesamtzustand")
        JarvisListGroup {
            JarvisListRow(
                title = "Voice",
                subtitle = "Die mobile Sprachschicht wird neu aufgebaut und ist noch nicht angebunden.",
                trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED) },
            )
            JarvisListRow(title = "Mikrofonstatus", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = VOICE_UNBOUND_STATUS, dot = false) })
        }

        JarvisSectionHeader("Zustandsdemonstration")
        JarvisPrototypeBanner(
            text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein " +
                "Inventar. Kein Mikrofon, keine STT und keine TTS werden verwendet.",
        )
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = "Aktueller Beispielzustand", color = JarvisSemanticColor.foreground, fontSize = 13.sp)
            JarvisStatusTag(state = currentConfig.tag, label = currentConfig.label)
        }
        FootNote(currentConfig.desc)

        FlowRow(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
        ) {
            JarvisButton(text = "Sprachinteraktion starten", variant = JarvisButtonVariant.PRIMARY, onClick = {
                if (voiceState == VoiceState.PERMISSION_REQUIRED || voiceState == VoiceState.PRIVACY_BLOCKED || voiceState == VoiceState.UNAVAILABLE) {
                    report("Sprachinteraktion kann in diesem Beispielzustand nicht gestartet werden.")
                } else {
                    goTo(VoiceState.LISTENING, "Sprachinteraktion gestartet (simuliert).")
                }
            })
            JarvisButton(text = "Zuhören beenden", enabled = voiceState == VoiceState.LISTENING, onClick = {
                if (voiceState != VoiceState.LISTENING) report("Kein aktives Zuhören zum Beenden.") else goTo(VoiceState.PROCESSING, "Zuhören beendet, Verarbeitung simuliert.")
            })
            JarvisButton(text = "Verarbeitung abbrechen", enabled = voiceState == VoiceState.PROCESSING || voiceState == VoiceState.LISTENING, onClick = {
                if (voiceState != VoiceState.PROCESSING && voiceState != VoiceState.LISTENING) report("Keine laufende Verarbeitung zum Abbrechen.") else goTo(VoiceState.CANCELLED, "Verarbeitung abgebrochen.")
            })
            JarvisButton(text = "Sprachausgabe stoppen", enabled = voiceState == VoiceState.SPEAKING, onClick = {
                if (voiceState != VoiceState.SPEAKING) report("Keine laufende Sprachausgabe zum Stoppen.") else goTo(VoiceState.IDLE, "Sprachausgabe gestoppt.")
            })
        }
        JarvisActionResultText(message = actionResult.message)

        JarvisSectionHeader("Zustand wählen")
        JarvisListGroup {
            voiceStateOrder.forEach { id ->
                val cfg = voiceStateConfig.getValue(id)
                JarvisListRow(
                    title = cfg.label,
                    subtitle = cfg.desc,
                    selected = id == voiceState,
                    trailing = { JarvisStatusTag(state = cfg.tag, label = cfg.label, dot = false) },
                    onClick = { goTo(id, "Beispielzustand \"${cfg.label}\" ausgewählt.") },
                )
            }
        }
        FootNote("Die Auswahl dient allein der Ansicht jedes möglichen Zustands und verändert nur den lokalen Vorschauzustand dieser Ansicht.")

        JarvisSectionHeader("Wake Word") { JarvisButton(text = "Konfigurieren", onClick = { wakeWordSheetOpen = true }) }
        JarvisListGroup {
            JarvisListRow(title = "Aktivierung", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = if (wakeWordEnabled) "Aktiviert (Entwurf)" else "Deaktiviert", dot = false) })
            JarvisListRow(title = "Engine", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = VOICE_UNBOUND, dot = false) })
            JarvisListRow(title = "Schlüsselwort", trailing = { MonoValue(keyword.ifBlank { VOICE_UNBOUND }) })
        }
        FootNote("Die Erkennung des Schlüsselworts soll lokal auf dem Gerät laufen. Engine wird erst festgelegt, wenn die mobile Sprachschicht steht. Die Werte hier sind reine Oberflächen-Beispiele.")

        JarvisSectionHeader("Spracherkennung") { JarvisButton(text = "Konfigurieren", onClick = { sttSheetOpen = true }) }
        JarvisListGroup {
            JarvisListRow(title = "STT", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, dot = false) })
            JarvisListRow(title = "Sprache", subtitle = "Produktsprache der Anwendung, kein erkannter Laufzeitwert.", trailing = { MonoValue(sttLanguage) })
        }
        FootNote("Ziel ist eine lokale Transkription auf dem Gerät. Modell, Laufzeit und Güte werden erst angezeigt, wenn sie wirklich gemessen werden.")

        JarvisSectionHeader("Sprachausgabe") { JarvisButton(text = "Konfigurieren", onClick = { ttsSheetOpen = true }) }
        JarvisListGroup {
            JarvisListRow(title = "TTS", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, dot = false) })
            JarvisListRow(title = "Stimme", subtitle = "Oberflächen-Beispiel, kein echtes Stimmprofil.", trailing = { MonoValue(ttsVoice) })
        }

        JarvisSectionHeader("Privacy")
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Sprachaufnahme muss dem zentralen PrivacyGate folgen. In PRIVACY sind " +
                "geschützte Mikrofon- und STT-Pfade gesperrt, PRIVACY_LOCK kann strengere Grenzen " +
                "erzwingen. Das Gate ist im Entwurfszustand noch nicht verdrahtet.",
        )
    }

    JarvisBottomSheet(open = wakeWordSheetOpen, onClose = { wakeWordSheetOpen = false }, title = "Wake-Word-Konfiguration") {
        Column(modifier = Modifier.fillMaxWidth()) {
            FootNote("Reine Oberflächen-Werte. Es ist noch keine Wake-Word-Engine ausgewählt, dieser Dialog legt keine fest.")
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "Aktivierung", color = JarvisSemanticColor.foreground, fontSize = 13.sp)
                JarvisToggle(checked = wakeWordEnabled, onCheckedChange = { wakeWordEnabled = it }, label = "Wake Word aktivieren")
            }
            JarvisTextField(value = keyword, onValueChange = { keyword = it }, label = "Schlüsselwort", placeholder = "z. B. Jarvis")
            SegmentedOptions("Empfindlichkeit", sensitivityOptions, sensitivity) { sensitivity = it }
            Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                JarvisButton(
                    text = "Übernehmen",
                    variant = JarvisButtonVariant.PRIMARY,
                    fullWidth = true,
                    onClick = { wakeWordSheetOpen = false; report("Wake-Word-Konfiguration gespeichert (lokal).") },
                )
            }
        }
    }

    JarvisBottomSheet(open = sttSheetOpen, onClose = { sttSheetOpen = false }, title = "STT-Konfiguration") {
        Column(modifier = Modifier.fillMaxWidth()) {
            FootNote("Reine Oberflächen-Werte. Es ist noch kein Erkennungsmodell ausgewählt.")
            SegmentedOptions("Sprache", sttLanguageOptions, sttLanguage) { sttLanguage = it }
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "Lokale Ausführung", color = JarvisSemanticColor.foreground, fontSize = 13.sp)
                JarvisToggle(checked = sttLocalOnly, onCheckedChange = { sttLocalOnly = it }, label = "Lokale Ausführung")
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "Interpunktion", color = JarvisSemanticColor.foreground, fontSize = 13.sp)
                JarvisToggle(checked = sttPunctuation, onCheckedChange = { sttPunctuation = it }, label = "Interpunktion")
            }
            Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                JarvisButton(
                    text = "Übernehmen",
                    variant = JarvisButtonVariant.PRIMARY,
                    fullWidth = true,
                    onClick = { sttSheetOpen = false; report("STT-Konfiguration gespeichert (lokal).") },
                )
            }
        }
    }

    JarvisBottomSheet(open = ttsSheetOpen, onClose = { ttsSheetOpen = false }, title = "TTS-Stimmenauswahl") {
        Column(modifier = Modifier.fillMaxWidth()) {
            FootNote("Neutrale Platzhalter, reine Oberflächen-Beispiele. Es ist noch kein Sprachausgabe-Anbieter ausgewählt.")
            JarvisListGroup {
                ttsVoiceOptions.forEach { option ->
                    JarvisListRow(title = option, selected = option == ttsVoice, onClick = { ttsVoice = option })
                }
            }
            SegmentedOptions("Tempo", tempoOptions, tempo) { tempo = it }
            SegmentedOptions("Lautstärke", volumeOptions, volume) { volume = it }
            Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                JarvisButton(
                    text = "Übernehmen",
                    variant = JarvisButtonVariant.PRIMARY,
                    fullWidth = true,
                    onClick = { ttsSheetOpen = false; report("TTS-Stimmenauswahl gespeichert (lokal).") },
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SegmentedOptions(label: String, options: List<String>, selected: String, onSelect: (String) -> Unit) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
        Text(text = label.uppercase(), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp, modifier = Modifier.padding(bottom = 6.dp))
        FlowRow(modifier = Modifier.selectableGroup(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
            options.forEach { option ->
                JarvisButton(
                    text = option,
                    variant = if (option == selected) JarvisButtonVariant.PRIMARY else JarvisButtonVariant.SECONDARY,
                    selected = option == selected,
                    onClick = { onSelect(option) },
                )
            }
        }
    }
}

@Composable
private fun MonoValue(text: String) {
    Text(text = text, fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace, fontSize = 11.sp, color = JarvisSemanticColor.subtleForeground)
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
