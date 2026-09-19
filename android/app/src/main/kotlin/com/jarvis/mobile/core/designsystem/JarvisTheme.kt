package com.jarvis.mobile.core.designsystem

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider

/**
 * JARVIS is local-first, dark-only by product decision (Brand Spec):
 * professional system tool, not a themeable consumer app. Material 3 is used
 * only as the technical ripple/typography/shape host underneath - every
 * visible colour, spacing and radius value comes from [JarvisColors],
 * [JarvisSpacing] and [JarvisRadii], never from the M3 defaults.
 */
private val jarvisMaterialColorScheme = darkColorScheme(
    primary = JarvisColors().blue,
    onPrimary = JarvisColors().bg0,
    background = JarvisColors().bg0,
    onBackground = JarvisColors().text1,
    surface = JarvisColors().bg1,
    onSurface = JarvisColors().text1,
    error = JarvisColors().error,
)

@Composable
fun JarvisTheme(
    content: @Composable () -> Unit,
) {
    val colors = JarvisColors()
    val type = JarvisType()

    CompositionLocalProvider(
        LocalJarvisColors provides colors,
        LocalJarvisType provides type,
    ) {
        MaterialTheme(
            colorScheme = jarvisMaterialColorScheme,
            content = content,
        )
    }
}
