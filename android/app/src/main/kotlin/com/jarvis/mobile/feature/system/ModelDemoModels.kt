package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.util.StringFieldCodec
import com.jarvis.mobile.core.util.StringFieldReader
import com.jarvis.mobile.core.util.StringFieldWriter

/** Ported 1:1 from src/components/jarvis/screens/models-screen.tsx + models-demo.tsx. */

/**
 * Reusable load and download states for future real entries. Exactly one of
 * them describes a model at a time; the current baseline is NOT_LOADED.
 */
enum class ModelLoadState { NOT_LOADED, READY, DOWNLOADING, PAUSED, LOADING, INCOMPATIBLE, ERROR }

val modelLoadStateLabel: Map<ModelLoadState, String> = mapOf(
    ModelLoadState.NOT_LOADED to "Nicht geladen",
    ModelLoadState.READY to "Bereit",
    ModelLoadState.DOWNLOADING to "Wird heruntergeladen",
    ModelLoadState.PAUSED to "Pausiert",
    ModelLoadState.LOADING to "Wird geladen",
    ModelLoadState.INCOMPATIBLE to "Inkompatibel",
    ModelLoadState.ERROR to "Fehler",
)

/** Tone mapping onto the locked status language. */
val modelLoadStateTone: Map<ModelLoadState, SystemState> = mapOf(
    ModelLoadState.NOT_LOADED to SystemState.DESIGN_STATE,
    ModelLoadState.READY to SystemState.READY,
    ModelLoadState.DOWNLOADING to SystemState.LOCAL,
    ModelLoadState.PAUSED to SystemState.OFFLINE,
    ModelLoadState.LOADING to SystemState.LOCAL,
    ModelLoadState.INCOMPATIBLE to SystemState.DEGRADED,
    ModelLoadState.ERROR to SystemState.ERROR,
)

enum class ModelSource { IMPORT, KATALOG }
enum class ModelIntegrity { BESTANDEN, FEHLGESCHLAGEN }
enum class ModelErrorKind { LADEN, DOWNLOAD }

/** Zustandsdemonstration entry. UI example, never device data. */
data class DemoModelEntry(
    val id: String,
    val name: String,
    val loadState: ModelLoadState,
    val compatible: Boolean? = null,
    val integrity: ModelIntegrity? = null,
    val size: String? = null,
    val note: String? = null,
    val source: ModelSource,
    val downloadProgress: Int? = null,
    val errorKind: ModelErrorKind? = null,
)

val initialDemoModels: List<DemoModelEntry> = listOf(
    DemoModelEntry(
        id = "demo-ready", name = "Beispielmodell A (bereit)", loadState = ModelLoadState.READY,
        compatible = true, integrity = ModelIntegrity.BESTANDEN, size = "412 MB", note = "Beispieleintrag", source = ModelSource.IMPORT,
    ),
    DemoModelEntry(
        id = "demo-downloading", name = "Beispielmodell B (Download läuft)", loadState = ModelLoadState.DOWNLOADING,
        compatible = true, size = "1,1 GB", note = "Beispieleintrag", source = ModelSource.KATALOG, downloadProgress = 35,
    ),
    DemoModelEntry(
        id = "demo-error", name = "Beispielmodell C (Fehler)", loadState = ModelLoadState.ERROR,
        compatible = true, integrity = ModelIntegrity.BESTANDEN, size = "780 MB", note = "Beispieleintrag", source = ModelSource.KATALOG, errorKind = ModelErrorKind.LADEN,
    ),
    DemoModelEntry(
        id = "demo-incompatible", name = "Beispielmodell D (inkompatibel)", loadState = ModelLoadState.INCOMPATIBLE,
        compatible = false, size = "2,3 GB", note = "Beispieleintrag", source = ModelSource.KATALOG,
    ),
)

fun modelCompatibilityLabel(compatible: Boolean?): String = when (compatible) {
    null -> "Nicht geprüft"
    true -> "Kompatibilitätsprüfung bestanden"
    false -> "Kompatibilitätsprüfung nicht bestanden"
}

fun modelIntegrityLabel(integrity: ModelIntegrity?): String = when (integrity) {
    null -> "Nicht geprüft"
    ModelIntegrity.BESTANDEN -> "Integritätsprüfung bestanden"
    ModelIntegrity.FEHLGESCHLAGEN -> "Integritätsprüfung fehlgeschlagen"
}

enum class ModelImportStep { AUSWAHL, KOMPATIBILITAET, INTEGRITAET, REGISTRIERUNG, FERTIG }

val modelImportStepLabel: Map<ModelImportStep, String> = mapOf(
    ModelImportStep.AUSWAHL to "1 von 4: Datei auswählen",
    ModelImportStep.KOMPATIBILITAET to "2 von 4: Kompatibilitätsprüfung",
    ModelImportStep.INTEGRITAET to "3 von 4: Integritätsprüfung",
    ModelImportStep.REGISTRIERUNG to "4 von 4: Registrierung",
    ModelImportStep.FERTIG to "Abgeschlossen",
)

data class ModelCatalogEntry(val id: String, val name: String, val size: String, val note: String)

val modelCatalogEntries: List<ModelCatalogEntry> = listOf(
    ModelCatalogEntry("cat-1", "Katalogbeispiel Klein", "350 MB", "Katalogbeispiel"),
    ModelCatalogEntry("cat-2", "Katalogbeispiel Mittel", "900 MB", "Katalogbeispiel"),
    ModelCatalogEntry("cat-3", "Katalogbeispiel Groß", "2,1 GB", "Katalogbeispiel"),
)

/**
 * String encoding for [DemoModelEntry], since [ModelsDemoSection]'s `models`
 * state is edited in place (load/unload/download start-pause-resume-cancel/
 * retry/delete), so it must survive activity recreation like any other
 * edited demo state. Built on [StringFieldCodec]; nullable fields use an
 * explicit presence flag, never an empty-string sentinel.
 */
private fun StringFieldWriter.writeNullable(value: String?): StringFieldWriter {
    write((value != null).toString())
    if (value != null) write(value)
    return this
}

private fun StringFieldReader.readNullable(): String? = if (read().toBoolean()) read() else null

private fun encodeDemoModelEntry(m: DemoModelEntry): String {
    val writer = StringFieldCodec.writer()
    writer.write(m.id)
    writer.write(m.name)
    writer.write(m.loadState.name)
    writer.writeNullable(m.compatible?.toString())
    writer.writeNullable(m.integrity?.name)
    writer.writeNullable(m.size)
    writer.writeNullable(m.note)
    writer.write(m.source.name)
    writer.writeNullable(m.downloadProgress?.toString())
    writer.writeNullable(m.errorKind?.name)
    return writer.build()
}

private fun decodeDemoModelEntry(raw: String): DemoModelEntry {
    val reader = StringFieldCodec.reader(raw)
    return DemoModelEntry(
        id = reader.read(),
        name = reader.read(),
        loadState = ModelLoadState.valueOf(reader.read()),
        compatible = reader.readNullable()?.toBoolean(),
        integrity = reader.readNullable()?.let { ModelIntegrity.valueOf(it) },
        size = reader.readNullable(),
        note = reader.readNullable(),
        source = ModelSource.valueOf(reader.read()),
        downloadProgress = reader.readNullable()?.toInt(),
        errorKind = reader.readNullable()?.let { ModelErrorKind.valueOf(it) },
    )
}

fun encodeDemoModelEntries(entries: List<DemoModelEntry>): String =
    StringFieldCodec.encodeStringList(entries.map { encodeDemoModelEntry(it) })

fun decodeDemoModelEntries(raw: String): List<DemoModelEntry> =
    StringFieldCodec.decodeStringList(raw).map { decodeDemoModelEntry(it) }
