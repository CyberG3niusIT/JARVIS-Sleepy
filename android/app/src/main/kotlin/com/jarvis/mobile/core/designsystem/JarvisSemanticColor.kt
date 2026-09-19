package com.jarvis.mobile.core.designsystem

import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.Color

/**
 * Ported 1:1 from the `--color-*` semantic aliases in src/styles.css. Screens
 * and shared components read colour through these properties, never through
 * raw [JarvisColors] fields, so a palette change stays a one-file edit.
 */
object JarvisSemanticColor {
    val background: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.bg0
    val foreground: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.text1
    val surface: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.bg1
    val surfaceRaised: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.surface1
    val surfaceSelected: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.surface2

    val primary: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.blue
    val primaryForeground: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.bg0
    val primarySoft: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.blueSoft
    val primaryDim: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.blueDim

    val mutedForeground: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.text3
    val subtleForeground: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.text2

    val success: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.success
    val warning: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.warning
    val destructive: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.error
    val disabled: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.disabled

    val border: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.border
    val borderSoft: Color @Composable @ReadOnlyComposable get() = LocalJarvisColors.current.borderSoft
}
