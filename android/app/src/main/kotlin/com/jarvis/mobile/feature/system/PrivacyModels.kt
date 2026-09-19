package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.PrivacyMode

/** Ported 1:1 from src/components/jarvis/screens/privacy-screen.tsx. */

val privacyModeCopy: Map<PrivacyMode, String> = mapOf(
    PrivacyMode.NORMAL to "Normaler Betrieb.",
    PrivacyMode.PRIVACY to "JARVIS-Vorgänge laufen weiter, geschützte Wahrnehmungs- und " +
        "Aufnahmepfade sind jedoch gesperrt.",
    PrivacyMode.PRIVACY_LOCK to "Strengere Stufe. Zusätzlich können Netzwerk, Cloud und " +
        "externe Werkzeugpfade hart gesperrt werden.",
)

val privacyModes: List<PrivacyMode> = listOf(PrivacyMode.NORMAL, PrivacyMode.PRIVACY, PrivacyMode.PRIVACY_LOCK)

val privacyModeRank: Map<PrivacyMode, Int> = mapOf(
    PrivacyMode.NORMAL to 0,
    PrivacyMode.PRIVACY to 1,
    PrivacyMode.PRIVACY_LOCK to 2,
)

data class ProtectedGroup(val title: String, val detail: String)

val protectedGroups: List<ProtectedGroup> = listOf(
    ProtectedGroup("Aufnahme", "MIC_INGEST, STT, SCREEN_CAPTURE, CAMERA_CAPTURE, CLIPBOARD_READ"),
    ProtectedGroup("Beobachtung", "FILESYSTEM_OBSERVATION, PROACTIVE_OBSERVATION"),
    ProtectedGroup(
        "Verarbeitung und Gedächtnis",
        "MEMORY_EXTRACT, MEMORY_WRITE, EMBEDDING_GENERATE, SESSION_SUMMARY, AGENT_CONTEXT_INGEST",
    ),
    ProtectedGroup("Externe Ausführung", "CLOUD_LLM, REMOTE_TOOL"),
    ProtectedGroup("Protokollierung", "CONTENT_LOGGING"),
)

val privacyGuarantees: List<String> = listOf(
    "Kein stiller Cloud-Fallback.",
    "Keine nachträgliche Aufnahme geschützter Inhalte.",
    "Blockierte Daten gelangen nicht in Memory, Logs, Agenten oder eine entfernte Runtime.",
)

/** Affected capability groups shown per target mode in the explanation sheet. */
val affectedGroupsByMode: Map<PrivacyMode, List<String>> = mapOf(
    PrivacyMode.NORMAL to emptyList(),
    PrivacyMode.PRIVACY to listOf("Aufnahme", "Beobachtung"),
    PrivacyMode.PRIVACY_LOCK to listOf("Aufnahme", "Beobachtung", "Externe Ausführung"),
)

/** Compact "Was sich aendert" summary per target mode. */
val changeSummaryByMode: Map<PrivacyMode, String> = mapOf(
    PrivacyMode.NORMAL to "Alle geschützten Pfade werden wieder freigegeben. Aufnahme, " +
        "Beobachtung, externe Ausführung und Protokollierung laufen wieder wie im normalen Betrieb.",
    PrivacyMode.PRIVACY to "Aufnahme- und Beobachtungspfade (Mikrofon, STT, Bildschirm, Kamera, " +
        "Zwischenablage, Dateisystem-Beobachtung) werden gesperrt. JARVIS bleibt sonst nutzbar.",
    PrivacyMode.PRIVACY_LOCK to "Zusätzlich zu Aufnahme und Beobachtung werden externe " +
        "Ausführungspfade (Cloud-Modelle, entfernte Werkzeuge) hart gesperrt.",
)

sealed interface PrivacyOverlay {
    data object None : PrivacyOverlay
    data class Explain(val target: PrivacyMode) : PrivacyOverlay
    data class ConfirmLock(val target: PrivacyMode) : PrivacyOverlay
    data class ConfirmRelax(val target: PrivacyMode) : PrivacyOverlay
}

/**
 * String encoding for [PrivacyOverlay], since it is not itself Bundle-safe
 * (a sealed interface's `data object`/`data class` implementations are not
 * [java.io.Serializable] by default), so [PrivacyScreen]'s `overlay` state
 * needs a custom `Saver` to survive activity recreation.
 */
fun encodePrivacyOverlay(overlay: PrivacyOverlay): String = when (overlay) {
    is PrivacyOverlay.None -> "NONE"
    is PrivacyOverlay.Explain -> "EXPLAIN:${overlay.target.name}"
    is PrivacyOverlay.ConfirmLock -> "CONFIRM_LOCK:${overlay.target.name}"
    is PrivacyOverlay.ConfirmRelax -> "CONFIRM_RELAX:${overlay.target.name}"
}

fun decodePrivacyOverlay(raw: String): PrivacyOverlay {
    if (raw == "NONE") return PrivacyOverlay.None
    val (kind, target) = raw.split(":", limit = 2)
    val mode = PrivacyMode.valueOf(target)
    return when (kind) {
        "EXPLAIN" -> PrivacyOverlay.Explain(mode)
        "CONFIRM_LOCK" -> PrivacyOverlay.ConfirmLock(mode)
        "CONFIRM_RELAX" -> PrivacyOverlay.ConfirmRelax(mode)
        else -> throw IllegalArgumentException("Unknown PrivacyOverlay kind: $kind")
    }
}
