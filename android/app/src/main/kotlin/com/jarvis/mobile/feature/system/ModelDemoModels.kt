package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.SystemState

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
