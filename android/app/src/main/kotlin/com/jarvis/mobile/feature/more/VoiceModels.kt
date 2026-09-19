package com.jarvis.mobile.feature.more

import com.jarvis.mobile.core.model.SystemState

/** Ported 1:1 from src/components/jarvis/screens/voice-screen.tsx. */

const val VOICE_UNBOUND = "Nicht gebunden"
const val VOICE_UNBOUND_STATUS = "Status nicht gebunden"

enum class VoiceState { IDLE, LISTENING, PROCESSING, SPEAKING, CANCELLED, PERMISSION_REQUIRED, PRIVACY_BLOCKED, UNAVAILABLE, ERROR }

data class VoiceStateConfig(val label: String, val tag: SystemState, val desc: String)

val voiceStateOrder: List<VoiceState> = listOf(
    VoiceState.IDLE, VoiceState.LISTENING, VoiceState.PROCESSING, VoiceState.SPEAKING,
    VoiceState.CANCELLED, VoiceState.PERMISSION_REQUIRED, VoiceState.PRIVACY_BLOCKED,
    VoiceState.UNAVAILABLE, VoiceState.ERROR,
)

val voiceStateConfig: Map<VoiceState, VoiceStateConfig> = mapOf(
    VoiceState.IDLE to VoiceStateConfig("Idle", SystemState.DESIGN_STATE, "Keine aktive Sprachinteraktion. Ausgangszustand."),
    VoiceState.LISTENING to VoiceStateConfig("Hört zu", SystemState.LOCAL, "Beispielzustand einer Aufnahmephase. Es wird kein echtes Mikrofon verwendet."),
    VoiceState.PROCESSING to VoiceStateConfig("Verarbeitet", SystemState.DEGRADED, "Beispielzustand einer Verarbeitungsphase nach dem Ende der Aufnahme."),
    VoiceState.SPEAKING to VoiceStateConfig("Spricht", SystemState.LOCAL, "Beispielzustand einer Wiedergabephase. Es wird keine echte Sprachausgabe erzeugt."),
    VoiceState.CANCELLED to VoiceStateConfig("Abgebrochen", SystemState.DESIGN_STATE, "Die Interaktion wurde durch die Person abgebrochen."),
    VoiceState.PERMISSION_REQUIRED to VoiceStateConfig("Berechtigung erforderlich", SystemState.PERMISSION_REQUIRED, "Beispielzustand: Eine Mikrofonberechtigung fehlt. Ohne Freigabe passiert nichts."),
    VoiceState.PRIVACY_BLOCKED to VoiceStateConfig("Privacy blockiert", SystemState.PRIVACY_BLOCKED, "Beispielzustand: Der Privacy-Modus sperrt geschützte Aufnahmepfade."),
    VoiceState.UNAVAILABLE to VoiceStateConfig("Runtime nicht verfügbar", SystemState.UNAVAILABLE, "Beispielzustand: Die lokale Sprachlaufzeit ist nicht angebunden."),
    VoiceState.ERROR to VoiceStateConfig("Fehler", SystemState.ERROR, "Beispielzustand: Der Vorgang ist fehlgeschlagen."),
)

val sensitivityOptions = listOf("Niedrig", "Mittel", "Hoch")
val sttLanguageOptions = listOf("Deutsch", "Englisch")
val ttsVoiceOptions = listOf("Stimme A (UI-Beispiel)", "Stimme B (UI-Beispiel)", "Stimme C (UI-Beispiel)")
val tempoOptions = listOf("Langsam", "Normal", "Schnell")
val volumeOptions = listOf("Leise", "Normal", "Laut")
