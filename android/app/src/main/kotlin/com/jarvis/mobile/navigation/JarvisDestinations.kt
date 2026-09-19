package com.jarvis.mobile.navigation

import com.jarvis.mobile.core.model.NavTabId

/**
 * Flat route table for the whole app. One route per screen, no nested
 * NavGraphs: a tab switch always pops back to that tab's own start
 * destination (see [JarvisAppShell]), so a detail screen never survives a
 * tab change - matching the web reference, where the System/Mehr containers
 * unmount their detail state when the tab is left.
 *
 * Route prefixes double as the Back table from the goal spec: every
 * "system/..." and "more/..." detail route pops to its tab root, the four
 * tab roots pop to Start, and Start's back is the platform default (exit app).
 */
object JarvisRoute {
    const val START = "start"
    const val CHAT = "chat"

    const val SYSTEM = "system"
    const val SYSTEM_MODELS = "system/models"
    const val SYSTEM_AGENTS = "system/agents"
    const val SYSTEM_TOOLS = "system/tools"
    const val SYSTEM_PERMISSIONS = "system/permissions"
    const val SYSTEM_PRIVACY = "system/privacy"
    const val SYSTEM_RUNTIMES = "system/runtimes"
    const val SYSTEM_DEVICE = "system/device"
    const val SYSTEM_DIAGNOSTICS = "system/diagnostics"

    const val MORE = "more"
    const val MORE_VOICE = "more/voice"
    const val MORE_MEMORY = "more/memory"
    const val MORE_AUTOMATIONS = "more/automations"
    const val MORE_AUTOMATIONS_EDITOR = "more/automations/editor"
    const val MORE_SETTINGS = "more/settings"
    const val MORE_ABOUT = "more/about"

    /** The four bottom-navigation root routes, in locked order. */
    val tabRoots: List<String> = listOf(START, CHAT, SYSTEM, MORE)
}

/** Which bottom-navigation tab a given route belongs to, for tab highlighting. */
fun routeToTab(route: String?): NavTabId = when {
    route == null -> NavTabId.START
    route == JarvisRoute.CHAT -> NavTabId.CHAT
    route.startsWith("system") -> NavTabId.SYSTEM
    route.startsWith("more") -> NavTabId.MORE
    else -> NavTabId.START
}

fun NavTabId.rootRoute(): String = when (this) {
    NavTabId.START -> JarvisRoute.START
    NavTabId.CHAT -> JarvisRoute.CHAT
    NavTabId.SYSTEM -> JarvisRoute.SYSTEM
    NavTabId.MORE -> JarvisRoute.MORE
}
