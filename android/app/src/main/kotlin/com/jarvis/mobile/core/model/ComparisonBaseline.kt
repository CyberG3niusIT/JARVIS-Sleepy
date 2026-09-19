package com.jarvis.mobile.core.model

/**
 * Ported 1:1 from src/lib/jarvis/comparison.ts.
 *
 * Single source of truth so the ported screens cannot drift from each other.
 * Nothing here is runtime data: every value is a documented design state.
 */

data class ComparisonLabels(
    val runtime: String = "Runtime nicht gebunden",
    val localModel: String = "Kein Modell geladen",
    val modelRuntime: String = "LiteRT-LM",
    val execution: String = "LOKAL",
    val sleepy: String = "Nicht verbunden",
    val sleepyHandoff: String = "Noch nicht implementiert",
    val cloud: String = "Nicht konfiguriert",
    val permissions: String = "Berechtigung erforderlich",
    val backgroundService: String = "Entwurfszustand",
)

data class ComparisonBaseline(
    val privacyMode: PrivacyMode = PrivacyMode.NORMAL,
    val execution: ExecutionLocation = ExecutionLocation.LOKAL,
    val runtimeBound: Boolean = false,
    val labels: ComparisonLabels = ComparisonLabels(),
)

val comparisonBaseline = ComparisonBaseline()
