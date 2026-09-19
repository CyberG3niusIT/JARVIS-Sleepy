package com.jarvis.mobile.core.designsystem

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * Ported 1:1 from src/lib/jarvis/tokens.ts colorTokens (and src/styles.css).
 * Single source of truth for JARVIS colour, dark only - the product does not
 * define a light theme.
 */
@Immutable
data class JarvisColors(
    val bg0: Color = Color(0xFF13191E),
    val bg1: Color = Color(0xFF171E24),
    val surface1: Color = Color(0xFF1B232A),
    val surface2: Color = Color(0xFF202A32),
    val border: Color = Color(0xFF33404A),
    val borderSoft: Color = Color(0xFF262F37),
    val text1: Color = Color(0xFFF7F8F8),
    val text2: Color = Color(0xFFC1C8CE),
    val text3: Color = Color(0xFF7E8993),
    val blue: Color = Color(0xFF34AAFB),
    val blueSoft: Color = Color(0xFF2196E8),
    val blueDim: Color = Color(0xFF17699D),
    val success: Color = Color(0xFF42C983),
    val warning: Color = Color(0xFFE7B34A),
    val error: Color = Color(0xFFE06464),
    val disabled: Color = Color(0xFF59636C),
)

val LocalJarvisColors = staticCompositionLocalOf { JarvisColors() }
