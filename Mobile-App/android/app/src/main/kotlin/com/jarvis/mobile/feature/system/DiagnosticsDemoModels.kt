package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.SystemState

/** Ported 1:1 from src/components/jarvis/screens/diagnostics-demo.tsx. */

enum class LogSeverity { INFO, WARN, ERROR }

val logSeverityLabel: Map<LogSeverity, String> = mapOf(
    LogSeverity.INFO to "Info",
    LogSeverity.WARN to "Warnung",
    LogSeverity.ERROR to "Fehler",
)

val logSeverityTone: Map<LogSeverity, SystemState> = mapOf(
    LogSeverity.INFO to SystemState.READY,
    LogSeverity.WARN to SystemState.WAITING_REMOTE,
    LogSeverity.ERROR to SystemState.ERROR,
)

/** Reusable entry for future real log rows. */
data class LogEntry(
    val id: String,
    val timestamp: String,
    val category: String,
    val severity: LogSeverity,
    val runtime: ExecutionLocation,
    /** Summary after redaction, never the raw payload. */
    val redactedSummary: String,
)

val diagnosticsDemoEntries: List<LogEntry> = listOf(
    LogEntry("demo-hist-1", "Heute, 09:14", "Ausführungshistorie", LogSeverity.INFO, ExecutionLocation.LOKAL, "Kapazität \"Termin anlegen\" lokal ausgeführt, Parameter redigiert"),
    LogEntry("demo-hist-2", "Heute, 09:02", "Ausführungshistorie", LogSeverity.WARN, ExecutionLocation.CLOUD, "Kapazität \"Zusammenfassung erstellen\" an Cloud delegiert, Inhalt minimiert"),
    LogEntry("demo-hist-3", "Gestern, 21:47", "Ausführungshistorie", LogSeverity.ERROR, ExecutionLocation.SLEEPY, "Kapazität \"Nachricht senden\" fehlgeschlagen, Zugangsdaten redigiert"),
    LogEntry("demo-crash-1", "Gestern, 18:30", "Absturzprotokoll", LogSeverity.ERROR, ExecutionLocation.LOKAL, "Absturz im Sprachmodul, Stacktrace ohne sensible Parameter"),
    LogEntry("demo-crash-2", "Vorgestern, 07:12", "Absturzprotokoll", LogSeverity.WARN, ExecutionLocation.EXTERN, "Externe Integration antwortete verzögert, Payload redigiert"),
)
