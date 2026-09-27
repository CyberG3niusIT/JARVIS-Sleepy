package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.SystemState

/**
 * Ported 1:1 from src/components/jarvis/screens/runtimes-demo.tsx. Pure
 * in-memory Compose state. No transport technology, QR code, pairing code,
 * IP address or certificate fingerprint is invented - the pairing phases
 * stay deliberately abstract because transport and authentication are not
 * yet decided for this project, see android/OPEN_DECISIONS.md Sec.1.
 */
enum class PairingState { NICHT_VERBUNDEN, KOPPLUNG_VORBEREITET, GEGENSTELLE_PRUEFEN, BESTAETIGUNG_ERFORDERLICH, VERBUNDEN, FEHLER }

val pairingLabel: Map<PairingState, String> = mapOf(
    PairingState.NICHT_VERBUNDEN to "Nicht verbunden",
    PairingState.KOPPLUNG_VORBEREITET to "Kopplung vorbereitet",
    PairingState.GEGENSTELLE_PRUEFEN to "Gegenstelle prüfen",
    PairingState.BESTAETIGUNG_ERFORDERLICH to "Bestätigung erforderlich",
    PairingState.VERBUNDEN to "Verbunden",
    PairingState.FEHLER to "Fehler",
)

val pairingTone: Map<PairingState, SystemState> = mapOf(
    PairingState.NICHT_VERBUNDEN to SystemState.UNAVAILABLE,
    PairingState.KOPPLUNG_VORBEREITET to SystemState.DESIGN_STATE,
    PairingState.GEGENSTELLE_PRUEFEN to SystemState.DESIGN_STATE,
    PairingState.BESTAETIGUNG_ERFORDERLICH to SystemState.DESIGN_STATE,
    PairingState.VERBUNDEN to SystemState.READY,
    PairingState.FEHLER to SystemState.ERROR,
)

val pairingStepText: Map<PairingState, String> = mapOf(
    PairingState.NICHT_VERBUNDEN to "Es besteht keine Kopplung zu Sleepy. Transport und Authentifizierung sind nicht festgelegt.",
    PairingState.KOPPLUNG_VORBEREITET to "Die Kopplung wird im Demozustand vorbereitet. Es wird noch kein Kanal geöffnet und keine Identität ausgetauscht.",
    PairingState.GEGENSTELLE_PRUEFEN to "Im Demozustand würde an dieser Stelle die Gegenstelle geprüft. Welche Prüfung das konkret ist (Verfahren, Kanal, Identitätsnachweis) ist in diesem Projekt noch nicht festgelegt.",
    PairingState.BESTAETIGUNG_ERFORDERLICH to "Im Demozustand würde hier eine ausdrückliche Bestätigung verlangt, bevor eine Kopplung als vertrauenswürdig gilt.",
    PairingState.VERBUNDEN to "Demozustand: Kopplung als abgeschlossen markiert. Es wurde keine reale Verbindung aufgebaut und keine Authentifizierung durchgeführt.",
    PairingState.FEHLER to "Demozustand: Die Kopplung ist im simulierten Ablauf fehlgeschlagen.",
)

val nextPairingStage: Map<PairingState, PairingState> = mapOf(
    PairingState.KOPPLUNG_VORBEREITET to PairingState.GEGENSTELLE_PRUEFEN,
    PairingState.GEGENSTELLE_PRUEFEN to PairingState.BESTAETIGUNG_ERFORDERLICH,
    PairingState.BESTAETIGUNG_ERFORDERLICH to PairingState.VERBUNDEN,
)

enum class HandoffReviewState { ENTWURF, BESTAETIGT, ABGEBROCHEN }
