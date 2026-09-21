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
                subtitle = "Sprachfunktionen sind in dieser App-Version derzeit nicht verfügbar.",
                trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED) },
            )
            JarvisListRow(title = "Mikrofonstatus", trailing = { JarvisStatusTag(state = SystemState.DESIGN_STATE, label = VOICE_UNBOUND_STATUS, dot = false) })
        }

        JarvisSectionHeader("Wake Word")
        JarvisListGroup {
            JarvisListRow(title = "Wake Word", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, dot = false) })
        }
        FootNote("Eine lokale Wake-Word-Engine ist noch nicht eingerichtet.")

        JarvisSectionHeader("Spracherkennung")
        JarvisListGroup {
            JarvisListRow(title = "STT", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, dot = false) })
        }
        FootNote("Modell, Laufzeit und Qualität werden erst angezeigt, wenn eine reale Spracherkennung verfügbar ist.")

        JarvisSectionHeader("Sprachausgabe")
        JarvisListGroup {
            JarvisListRow(title = "TTS", trailing = { JarvisStatusTag(state = SystemState.NOT_IMPLEMENTED, dot = false) })
        }

        JarvisSectionHeader("Privacy")
        JarvisInlineNotice(
            modifier = Modifier.padding(horizontal = 16.dp),
            text = "Sprachfunktionen bleiben deaktiviert, bis Mikrofonzugriff und verbindliche Privacy-Regeln eingerichtet sind.",
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
            JarvisListGroup(modifier = Modifier.selectableGroup()) {
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
