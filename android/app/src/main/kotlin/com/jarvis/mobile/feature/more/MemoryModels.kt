package com.jarvis.mobile.feature.more

import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.util.StringFieldCodec
import com.jarvis.mobile.core.util.StringFieldReader
import com.jarvis.mobile.core.util.StringFieldWriter

/** Ported 1:1 from src/components/jarvis/screens/memory-screen.tsx. */

enum class MemoryLayer { WORKING, RECENT, CANDIDATE, CONFIRMED }
enum class MemoryProvenance { USER_STATEMENT, CONVERSATION, TOOL_RESULT, OBSERVATION, INFERENCE, IMPORT, PROFILE, SYSTEM }
enum class MemoryScope { SESSION, DEVICE, ACCOUNT, GLOBAL }
enum class MemorySensitivity { NORMAL, SENSITIVE, CONFIDENTIAL }
enum class MemoryConfirmationStatus { UNCONFIRMED, CONFIRMED, CORRECTED, DISCARDED }

data class MemorySupersedes(val id: String, val label: String)

data class MemoryEntry(
    val id: String,
    val layer: MemoryLayer,
    val subject: String? = null,
    val summary: String,
    val state: SystemState,
    val provenance: MemoryProvenance,
    val confidence: Float? = null,
    val createdAt: String? = null,
    val updatedAt: String? = null,
    val scope: MemoryScope? = null,
    val sensitivity: MemorySensitivity? = null,
    val confirmationStatus: MemoryConfirmationStatus? = null,
    val supersedes: MemorySupersedes? = null,
    val sourceReference: String? = null,
    val supersedeNote: String? = null,
)

val memoryProvenanceLabel: Map<MemoryProvenance, String> = mapOf(
    MemoryProvenance.USER_STATEMENT to "Explizite Nutzerangabe",
    MemoryProvenance.CONVERSATION to "Konversation",
    MemoryProvenance.TOOL_RESULT to "Tool-Ergebnis",
    MemoryProvenance.OBSERVATION to "Beobachtung",
    MemoryProvenance.INFERENCE to "Inferenz",
    MemoryProvenance.IMPORT to "Import",
    MemoryProvenance.PROFILE to "Profil",
    MemoryProvenance.SYSTEM to "System",
)

val memoryLayerLabel: Map<MemoryLayer, String> = mapOf(
    MemoryLayer.WORKING to "Arbeitskontext",
    MemoryLayer.RECENT to "Kürzlich",
    MemoryLayer.CANDIDATE to "Kandidat",
    MemoryLayer.CONFIRMED to "Bestätigt",
)

val memoryScopeLabel: Map<MemoryScope, String> = mapOf(
    MemoryScope.SESSION to "Nur diese Sitzung",
    MemoryScope.DEVICE to "Dieses Gerät",
    MemoryScope.ACCOUNT to "Konto",
    MemoryScope.GLOBAL to "Global",
)

val memorySensitivityLabel: Map<MemorySensitivity, String> = mapOf(
    MemorySensitivity.NORMAL to "Normal",
    MemorySensitivity.SENSITIVE to "Sensibel",
    MemorySensitivity.CONFIDENTIAL to "Vertraulich",
)

val memoryConfirmationStatusLabel: Map<MemoryConfirmationStatus, String> = mapOf(
    MemoryConfirmationStatus.UNCONFIRMED to "Unbestätigt",
    MemoryConfirmationStatus.CONFIRMED to "Bestätigt",
    MemoryConfirmationStatus.CORRECTED to "Korrigiert",
    MemoryConfirmationStatus.DISCARDED to "Verworfen",
)

val memoryLayers: List<Pair<String, String>> = listOf(
    "Arbeitskontext" to "Was für den laufenden Vorgang gerade gebraucht wird.",
    "Kürzlich" to "Kurzfristige Inhalte, die noch nicht bewertet sind.",
    "Kandidaten" to "Vorgemerkte Inhalte, noch keine bestätigten Fakten.",
    "Bestätigt" to "Bestätigte Fakten mit Herkunft und Korrekturweg.",
)

val memoryProvenanceRows: List<Pair<String, String>> = listOf(
    "Explizite Nutzerangabe" to "Direkt mitgeteilte Information.",
    "Konversation" to "Aus einem Gespräch abgeleitete Angabe.",
    "Tool-Ergebnis" to "Ergebnis eines ausgeführten Werkzeugs.",
    "Beobachtung" to "Aus zulässiger Beobachtung gewonnene Angabe.",
    "Inferenz" to "Abgeleitet, nicht direkt gesagt.",
    "Import" to "Aus einer übernommenen Quelle.",
    "Profil" to "Dauerhafte Angaben zur Person oder zum Gerät.",
    "System" to "Vom System gesetzte Angabe.",
)

val memoryRules: List<Pair<String, String>> = listOf(
    "Nicht jeder Satz wird Memory" to "Relevanz entscheidet, nicht Menge.",
    "Privacy-Inhalte erzeugen kein Memory" to "Geschützte Inhalte werden nicht extrahiert.",
    "Kandidaten sind keine Fakten" to "Erst nach Bestätigung zählt ein Eintrag als Faktum.",
    "Bestätigtes bleibt korrigierbar" to "Fakten können widerrufen oder ersetzt werden.",
    "Kein interner Gedankengang" to "Zwischenüberlegungen des Modells werden nicht gespeichert.",
)

/** Example entries for the demonstration section. UI examples, no device data. */
val memoryDemoSeed: List<MemoryEntry> = listOf(
    MemoryEntry(
        id = "demo-1",
        layer = MemoryLayer.CANDIDATE,
        subject = "Bevorzugter Name",
        summary = "Möchte mit Vornamen angesprochen werden.",
        state = SystemState.DESIGN_STATE,
        provenance = MemoryProvenance.USER_STATEMENT,
        confidence = 0.72f,
        createdAt = "12.03.2024",
        scope = MemoryScope.ACCOUNT,
        sensitivity = MemorySensitivity.NORMAL,
        confirmationStatus = MemoryConfirmationStatus.UNCONFIRMED,
        sourceReference = "Gespräch vom 12.03.2024, Abschnitt Begrüßung",
    ),
    MemoryEntry(
        id = "demo-2",
        layer = MemoryLayer.CONFIRMED,
        subject = "Zeitzone",
        summary = "Europe/Berlin.",
        state = SystemState.DESIGN_STATE,
        provenance = MemoryProvenance.PROFILE,
        createdAt = "02.01.2024",
        updatedAt = "02.01.2024",
        scope = MemoryScope.DEVICE,
        sensitivity = MemorySensitivity.NORMAL,
        confirmationStatus = MemoryConfirmationStatus.CONFIRMED,
    ),
    MemoryEntry(
        id = "demo-3",
        layer = MemoryLayer.CONFIRMED,
        subject = "Kalenderzugriff",
        summary = "Erlaubt für Terminvorschläge, ersetzt frühere Einschränkung.",
        state = SystemState.DESIGN_STATE,
        provenance = MemoryProvenance.TOOL_RESULT,
        createdAt = "18.02.2024",
        updatedAt = "05.04.2024",
        scope = MemoryScope.DEVICE,
        sensitivity = MemorySensitivity.SENSITIVE,
        confirmationStatus = MemoryConfirmationStatus.CORRECTED,
        supersedes = MemorySupersedes("demo-3-alt", "Kalenderzugriff: nur lesend"),
        sourceReference = "Einstellungen, Verlaufseintrag Berechtigungen",
    ),
    MemoryEntry(
        id = "demo-4",
        layer = MemoryLayer.RECENT,
        subject = "Letzter Ort",
        summary = "Erwähnung eines Cafes im Gespräch, noch nicht bewertet.",
        state = SystemState.DESIGN_STATE,
        provenance = MemoryProvenance.CONVERSATION,
        createdAt = "heute",
        scope = MemoryScope.SESSION,
        sensitivity = MemorySensitivity.NORMAL,
        confirmationStatus = MemoryConfirmationStatus.UNCONFIRMED,
    ),
)

/**
 * String encoding for the user-edited demo entry list ([MemoryScreen]'s
 * `demoEntries`, changed by confirm/correct/discard/supersede), so it
 * survives activity recreation, not just rotation. Built on
 * [StringFieldCodec]; a nullable field is written as a presence flag
 * followed by its value (an empty flag skips the value read), never an
 * empty-string sentinel, so a genuinely empty string is never confused
 * with a missing value.
 */
private fun StringFieldWriter.writeNullable(value: String?): StringFieldWriter {
    write((value != null).toString())
    if (value != null) write(value)
    return this
}

private fun StringFieldReader.readNullable(): String? = if (read().toBoolean()) read() else null

private fun encodeMemoryEntry(e: MemoryEntry): String {
    val writer = StringFieldCodec.writer()
    writer.write(e.id)
    writer.write(e.layer.name)
    writer.writeNullable(e.subject)
    writer.write(e.summary)
    writer.write(e.state.name)
    writer.write(e.provenance.name)
    writer.writeNullable(e.confidence?.toString())
    writer.writeNullable(e.createdAt)
    writer.writeNullable(e.updatedAt)
    writer.writeNullable(e.scope?.name)
    writer.writeNullable(e.sensitivity?.name)
    writer.writeNullable(e.confirmationStatus?.name)
    writer.writeNullable(e.supersedes?.id)
    writer.writeNullable(e.supersedes?.label)
    writer.writeNullable(e.sourceReference)
    writer.writeNullable(e.supersedeNote)
    return writer.build()
}

private fun decodeMemoryEntry(raw: String): MemoryEntry {
    val reader = StringFieldCodec.reader(raw)
    val id = reader.read()
    val layer = MemoryLayer.valueOf(reader.read())
    val subject = reader.readNullable()
    val summary = reader.read()
    val state = SystemState.valueOf(reader.read())
    val provenance = MemoryProvenance.valueOf(reader.read())
    val confidence = reader.readNullable()?.toFloat()
    val createdAt = reader.readNullable()
    val updatedAt = reader.readNullable()
    val scope = reader.readNullable()?.let { MemoryScope.valueOf(it) }
    val sensitivity = reader.readNullable()?.let { MemorySensitivity.valueOf(it) }
    val confirmationStatus = reader.readNullable()?.let { MemoryConfirmationStatus.valueOf(it) }
    val supersedesId = reader.readNullable()
    val supersedesLabel = reader.readNullable()
    val sourceReference = reader.readNullable()
    val supersedeNote = reader.readNullable()
    return MemoryEntry(
        id = id,
        layer = layer,
        subject = subject,
        summary = summary,
        state = state,
        provenance = provenance,
        confidence = confidence,
        createdAt = createdAt,
        updatedAt = updatedAt,
        scope = scope,
        sensitivity = sensitivity,
        confirmationStatus = confirmationStatus,
        supersedes = supersedesId?.let { MemorySupersedes(it, supersedesLabel ?: "") },
        sourceReference = sourceReference,
        supersedeNote = supersedeNote,
    )
}

fun encodeMemoryEntries(entries: List<MemoryEntry>): String =
    StringFieldCodec.encodeStringList(entries.map { encodeMemoryEntry(it) })

fun decodeMemoryEntries(raw: String): List<MemoryEntry> =
    StringFieldCodec.decodeStringList(raw).map { decodeMemoryEntry(it) }
