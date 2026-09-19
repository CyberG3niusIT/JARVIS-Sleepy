package com.jarvis.mobile.core.designsystem

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing

/**
 * Ported 1:1 from src/lib/jarvis/tokens.ts duration / easing.
 *
 * Motion rules (unchanged from the web specification):
 * - Bewegung erklärt Hierarchie und Richtung, sie dekoriert nicht.
 * - Keine Dauerschleifen, kein Pulsieren, keine Partikel, kein HUD.
 * - Keine Animation darf einen Erfolg zeigen, bevor der Zustand bestätigt ist.
 * - Bei "Reduzierte Bewegung" entfällt jede Verschiebung, Deckkraft bleibt.
 */
object JarvisDuration {
    /** Press feedback, tag colour changes. */
    const val instantMs = 80
    /** Small state and colour transitions. */
    const val fastMs = 120
    /** Default screen and layout movement. */
    const val standardMs = 180
    /** Emphasised state change, indicator travel. */
    const val deliberateMs = 240
    /** Sheets and dialogs, maximum allowed. */
    const val sheetMs = 280
}

object JarvisEasing {
    /** Movement within the screen. */
    val standard: Easing = CubicBezierEasing(0.2f, 0f, 0f, 1f)
    /** Entering elements, decelerate. */
    val enter: Easing = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)
    /** Leaving elements, accelerate. */
    val exit: Easing = CubicBezierEasing(0.3f, 0f, 0.8f, 0.15f)
    /** Emphasised state transition, used sparingly. */
    val emphasized: Easing = CubicBezierEasing(0.2f, 0f, 0f, 1f)
}
