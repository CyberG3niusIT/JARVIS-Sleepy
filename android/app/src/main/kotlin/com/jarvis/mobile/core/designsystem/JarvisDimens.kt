package com.jarvis.mobile.core.designsystem

import androidx.compose.ui.unit.dp

/** Ported 1:1 from src/lib/jarvis/tokens.ts spacing / radii / borders / layout. */
object JarvisSpacing {
    val xxs = 2.dp
    val xs = 4.dp
    val sm = 8.dp
    val md = 12.dp
    val lg = 16.dp
    val xl = 20.dp
    val xxl = 24.dp
}

object JarvisRadii {
    val xs = 4.dp
    val sm = 6.dp
    val md = 8.dp
    val lg = 12.dp
}

object JarvisBorders {
    val hairline = 1.dp
}

object JarvisLayout {
    /** Android touch target floor. */
    val touchTargetMin = 48.dp
    val topBarHeight = 56.dp
    val runtimeStripHeight = 28.dp
    val bottomNavHeight = 56.dp
    val rowPaddingX = 16.dp
    val rowPaddingY = 10.dp
    val iconSm = 16.dp
    val iconMd = 18.dp
    val iconLg = 22.dp
}
