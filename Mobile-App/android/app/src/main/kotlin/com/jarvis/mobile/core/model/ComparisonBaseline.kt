package com.jarvis.mobile.core.model

/**
 * Ported 1:1 from src/lib/jarvis/comparison.ts.
 *
 * Single source of truth so the ported screens cannot drift from each other.
 * Nothing here is runtime data: every value is a documented design state.
 */

data class ComparisonLabels(
    val runtime: String = "Nicht verfügbar",
    val localModel: String = "Nicht verfügbar",
    val modelRuntime: String = "LiteRT-LM",
    val execution: String = "LOKAL",
    val sleepy: String = "Nicht verbunden",
    val sleepyHandoff: String = "Nicht verfügbar",
    val cloud: String = "Nicht konfiguriert",
    val permissions: String = "Berechtigung erforderlich",
    val backgroundService: String = "Nicht verfügbar",
)

data class ComparisonBaseline(
    val privacyMode: PrivacyMode = PrivacyMode.NORMAL,
    val execution: ExecutionLocation = ExecutionLocation.LOKAL,
    val runtimeBound: Boolean = false,
    val labels: ComparisonLabels = ComparisonLabels(),
)

val comparisonBaseline = ComparisonBaseline()
