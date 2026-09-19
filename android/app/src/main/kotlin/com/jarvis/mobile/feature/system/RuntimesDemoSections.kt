package com.jarvis.mobile.feature.system

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisActionResultText
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisDialog
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisNoticeTone
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.rememberJarvisActionResult
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/runtimes-demo.tsx
 * (SleepyPairingSection). Deliberately abstract phases only - see
 * android/OPEN_DECISIONS.md Sec.1 for why no real transport is bound.
 */
@Composable
fun SleepyPairingSection() {
    var pairing by remember { mutableStateOf(PairingState.NICHT_VERBUNDEN) }
    var sheetOpen by remember { mutableStateOf(false) }
    var disconnectOpen by remember { mutableStateOf(false) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()
    fun report(message: String) { scope.launch { actionResult.report("$message Entwurfszustand, keine Runtime-Aktion ausgeführt.") } }

    fun openPairing() { pairing = PairingState.KOPPLUNG_VORBEREITET; sheetOpen = true }
    fun advance() { nextPairingStage[pairing]?.let { next -> pairing = next; if (next == PairingState.VERBUNDEN) report("Demozustand: Sleepy als gekoppelt markiert.") } }
    fun failPairing() { pairing = PairingState.FEHLER }
    fun cancelPairing() { pairing = PairingState.NICHT_VERBUNDEN; sheetOpen = false; report("Kopplung im Demozustand abgebrochen.") }
    fun disconnect() { pairing = PairingState.NICHT_VERBUNDEN; disconnectOpen = false; report("Demozustand: Verbindung zu Sleepy getrennt.") }

    JarvisSectionHeader("Zustandsdemonstration: Sleepy-Kopplung")
    JarvisInlineNotice(
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.",
    )
    JarvisListGroup {
        JarvisListRow(
            title = "Kopplungszustand (Demo)",
            subtitle = pairingStepText.getValue(pairing),
            trailing = { JarvisStatusTag(state = pairingTone.getValue(pairing), label = pairingLabel.getValue(pairing), dot = false) },
        )
    }
    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
        if (pairing == PairingState.NICHT_VERBUNDEN || pairing == PairingState.FEHLER) {
            JarvisButton(text = "Sleepy koppeln", variant = JarvisButtonVariant.PRIMARY, onClick = ::openPairing)
        }
        if (pairing == PairingState.VERBUNDEN) {
            JarvisButton(text = "Verbindung trennen", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { disconnectOpen = true })
        }
    }
    JarvisActionResultText(message = actionResult.message)

    JarvisBottomSheet(open = sheetOpen, onClose = ::cancelPairing, title = "Sleepy koppeln (Demozustand)") {
        Column(modifier = Modifier.fillMaxWidth()) {
            JarvisInlineNotice(
                modifier = Modifier.padding(horizontal = 16.dp),
                tone = JarvisNoticeTone.WARNING,
                text = "Transport und Authentifizierung sind in diesem Projekt noch nicht festgelegt. " +
                    "Dieser Ablauf zeigt nur die Abfolge abstrakter Phasen, es wird kein Kopplungscode, " +
                    "kein QR-Code, keine IP-Adresse und kein Zertifikats-Fingerabdruck angezeigt oder erzeugt.",
            )
            JarvisListGroup(modifier = Modifier.padding(top = JarvisSpacing.sm)) {
                JarvisListRow(title = "Aktuelle Phase", trailing = { JarvisStatusTag(state = pairingTone.getValue(pairing), label = pairingLabel.getValue(pairing), dot = false) })
            }
            Text(
                text = pairingStepText.getValue(pairing),
                color = JarvisSemanticColor.subtleForeground,
                fontSize = 12.sp,
                lineHeight = 18.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
            )
            if (pairing == PairingState.VERBUNDEN) {
                JarvisInlineNotice(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    text = "Es wurde keine reale Verbindung erzeugt. Dieser Zustand dient nur der Darstellung der vorgesehenen Abfolge.",
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.md),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
            ) {
                if (pairing != PairingState.VERBUNDEN && pairing != PairingState.FEHLER) {
                    JarvisButton(text = "Nächste Phase (Demo)", variant = JarvisButtonVariant.PRIMARY, onClick = ::advance)
                    JarvisButton(text = "Fehlschlag simulieren", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = ::failPairing)
                }
                if (pairing == PairingState.VERBUNDEN) {
                    JarvisButton(text = "Schließen", variant = JarvisButtonVariant.PRIMARY, onClick = { sheetOpen = false })
                }
                if (pairing == PairingState.FEHLER) {
                    JarvisButton(text = "Erneut versuchen", onClick = { pairing = PairingState.KOPPLUNG_VORBEREITET })
                }
                JarvisButton(text = "Abbrechen", onClick = ::cancelPairing)
            }
        }
    }

    JarvisDialog(
        open = disconnectOpen,
        onClose = { disconnectOpen = false },
        title = "Verbindung trennen",
        description = "Die im Demozustand gekoppelte Sleepy-Verbindung wird getrennt. Es handelt sich um lokalen Zustand, keine reale Trennung.",
        actions = {
            JarvisButton(text = "Abbrechen", onClick = { disconnectOpen = false })
            JarvisButton(text = "Trennen", variant = JarvisButtonVariant.DESTRUCTIVE, modifier = Modifier.padding(start = JarvisSpacing.sm), onClick = ::disconnect)
        },
    )
}

/** Ported 1:1 from runtimes-demo.tsx (TrustInspectionSection). Read-only. */
@Composable
fun TrustInspectionSection() {
    JarvisSectionHeader("Vertrauensprüfung (Nur-Lesen)")
    Column {
        JarvisDetailField(label = "Runtime-Name", value = "Sleepy")
        JarvisDetailField(label = "Vertrauenszustand", value = "Nicht gebunden")
        JarvisDetailField(label = "Ausführungsrolle", value = "Optionale vertraute Ausführungsumgebung")
        JarvisDetailField(label = "Identität", value = "Nicht gebunden")
        JarvisDetailField(label = "Fähigkeiten", value = "Noch nicht festgelegt")
        JarvisDetailField(label = "Erlaubter Übergabe-Umfang", value = "Noch nicht festgelegt")
    }
    Text(
        text = "Diese Felder zeigen die vorgesehene Struktur einer Vertrauensprüfung. Es sind keine " +
            "erfundenen Werte eingetragen, solange keine echte Kopplung besteht.",
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}

/** Ported 1:1 from runtimes-demo.tsx (HandoffReviewSection). No remote execution happens. */
@Composable
fun HandoffReviewSection() {
    var state by remember { mutableStateOf(HandoffReviewState.ENTWURF) }
    val actionResult = rememberJarvisActionResult()
    val scope = rememberCoroutineScope()
    fun report(message: String) { scope.launch { actionResult.report("$message Entwurfszustand, keine Runtime-Aktion ausgeführt.") } }

    JarvisSectionHeader("Übergabe-Ansicht (Nur lokale Demo, keine Ausführung)")
    JarvisInlineNotice(
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        text = "Diese Ansicht zeigt nur, wie eine Übergabe zur Prüfung dargestellt würde. Es findet keine entfernte Ausführung statt.",
    )
    Column {
        JarvisDetailField(label = "Aufgabe / Ziel", value = "Beispielziel einer Übergabe (Demo)")
        JarvisDetailField(label = "Freigegebener Kontext", value = "Nur ausdrücklich freigegebene Beispielinhalte")
        JarvisDetailField(label = "Privacy-Modus", value = "Wird aus dem aufrufenden Kontext übernommen")
        JarvisDetailField(label = "Limits", value = "Schritt-, Zeit- und Werkzeuggrenzen (Beispielstruktur)")
        JarvisDetailField(label = "Erwartetes Ergebnis", value = "Vereinbarte Form der Antwort (Beispielstruktur)")
        JarvisDetailField(label = "Ziel-Runtime", value = "Sleepy (Demozustand, nicht verbunden)")
    }

    if (state == HandoffReviewState.ENTWURF) {
        Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm)) {
            JarvisButton(text = "Bestätigen", variant = JarvisButtonVariant.PRIMARY, onClick = { state = HandoffReviewState.BESTAETIGT; report("Übergabe-Ansicht im Demozustand bestätigt, es fand keine Übergabe statt.") })
            JarvisButton(text = "Abbrechen", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { state = HandoffReviewState.ABGEBROCHEN; report("Übergabe-Ansicht im Demozustand abgebrochen.") })
        }
    } else {
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm)) {
            JarvisInlineNotice(
                tone = if (state == HandoffReviewState.BESTAETIGT) JarvisNoticeTone.INFO else JarvisNoticeTone.WARNING,
                text = if (state == HandoffReviewState.BESTAETIGT) {
                    "Demozustand bestätigt. Es wurde keine Übergabe ausgeführt und keine Runtime angesprochen."
                } else {
                    "Demozustand abgebrochen. Es wurde keine Übergabe ausgeführt."
                },
            )
            JarvisButton(text = "Zurücksetzen", modifier = Modifier.padding(top = JarvisSpacing.sm), onClick = { state = HandoffReviewState.ENTWURF })
        }
    }
    JarvisActionResultText(message = actionResult.message)
}
