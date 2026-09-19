package com.jarvis.mobile.navigation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Tune
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.jarvis.mobile.core.designsystem.component.JarvisBottomNavigation
import com.jarvis.mobile.core.designsystem.component.JarvisNavItem
import com.jarvis.mobile.core.designsystem.component.JarvisRuntimeStrip
import com.jarvis.mobile.core.designsystem.component.JarvisTopBar
import com.jarvis.mobile.core.model.NavTabId
import com.jarvis.mobile.feature.chat.ChatScreen
import com.jarvis.mobile.feature.more.AboutScreen
import com.jarvis.mobile.feature.more.AutomationEditorScreen
import com.jarvis.mobile.feature.more.AutomationsScreen
import com.jarvis.mobile.feature.more.MemoryScreen
import com.jarvis.mobile.feature.more.MoreOverviewScreen
import com.jarvis.mobile.feature.more.SettingsScreen
import com.jarvis.mobile.feature.more.VoiceScreen
import com.jarvis.mobile.feature.start.StartScreen
import com.jarvis.mobile.feature.system.AgentsScreen
import com.jarvis.mobile.feature.system.DeviceScreen
import com.jarvis.mobile.feature.system.DiagnosticsScreen
import com.jarvis.mobile.feature.system.ModelsScreen
import com.jarvis.mobile.feature.system.PermissionsScreen
import com.jarvis.mobile.feature.system.PrivacyScreen
import com.jarvis.mobile.feature.system.RuntimesScreen
import com.jarvis.mobile.feature.system.SystemOverviewScreen
import com.jarvis.mobile.feature.system.ToolsScreen

private val bottomNavItems = listOf(
    JarvisNavItem(NavTabId.START, "Start", Icons.Filled.Home),
    JarvisNavItem(NavTabId.CHAT, "Chat", Icons.AutoMirrored.Filled.Chat),
    JarvisNavItem(NavTabId.SYSTEM, "System", Icons.Filled.Tune),
    JarvisNavItem(NavTabId.MORE, "Mehr", Icons.Filled.MoreHoriz),
)

/**
 * App shell: persistent [JarvisTopBar] + [JarvisRuntimeStrip] + content +
 * [JarvisBottomNavigation], ported 1:1 from src/App.tsx + shell.tsx. See
 * android/PORTING_PLAN.md for why tab switches pop to the tab's own start
 * destination instead of restoring saved state.
 */
@Composable
fun JarvisAppShell(navController: NavHostController = rememberNavController()) {
    val shellViewModel: AppShellViewModel = hiltViewModel()
    val shellState by shellViewModel.uiState.collectAsState()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentTab = routeToTab(backStackEntry?.destination?.route)

    Column(modifier = Modifier.fillMaxSize()) {
        JarvisTopBar(onSettings = {
            navController.navigateToTab(NavTabId.MORE)
            navController.navigate(JarvisRoute.MORE_SETTINGS)
        })
        JarvisRuntimeStrip(
            runtimeState = shellState.runtimeState,
            runtimeLabel = shellState.runtimeLabel,
            execution = shellState.execution,
            privacy = shellState.privacy,
        )

        NavHost(
            navController = navController,
            startDestination = JarvisRoute.START,
            modifier = Modifier.weight(1f),
        ) {
            composable(JarvisRoute.START) {
                StartScreen(
                    onOpenChat = { navController.navigateToTab(NavTabId.CHAT) },
                    onOpenSystem = { navController.navigateToTab(NavTabId.SYSTEM) },
                )
            }
            composable(JarvisRoute.CHAT) { ChatScreen() }

            composable(JarvisRoute.SYSTEM) {
                SystemOverviewScreen(onOpenArea = { route -> navController.navigate(route) })
            }
            composable(JarvisRoute.SYSTEM_MODELS) { ModelsScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_AGENTS) { AgentsScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_TOOLS) { ToolsScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_PERMISSIONS) { PermissionsScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_PRIVACY) { PrivacyScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_RUNTIMES) { RuntimesScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_DEVICE) { DeviceScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.SYSTEM_DIAGNOSTICS) { DiagnosticsScreen(onBack = navController::popBackStack) }

            composable(JarvisRoute.MORE) {
                MoreOverviewScreen(onOpenArea = { route -> navController.navigate(route) })
            }
            composable(JarvisRoute.MORE_VOICE) { VoiceScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.MORE_MEMORY) { MemoryScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.MORE_AUTOMATIONS) {
                AutomationsScreen(
                    onBack = navController::popBackStack,
                    onCreateAutomation = { navController.navigate(JarvisRoute.MORE_AUTOMATIONS_EDITOR) },
                )
            }
            composable(JarvisRoute.MORE_AUTOMATIONS_EDITOR) {
                AutomationEditorScreen(onBack = navController::popBackStack)
            }
            composable(JarvisRoute.MORE_SETTINGS) { SettingsScreen(onBack = navController::popBackStack) }
            composable(JarvisRoute.MORE_ABOUT) { AboutScreen(onBack = navController::popBackStack) }
        }

        JarvisBottomNavigation(
            items = bottomNavItems,
            current = currentTab,
            onSelect = { tab -> navController.navigateToTab(tab) },
        )
    }
}

/**
 * Tab switch: pops everything back to Start (the graph's single true root)
 * without saving state, then navigates to the target tab's own start
 * destination. A detail screen therefore never survives a tab change,
 * matching the web reference's per-tab container unmount behaviour.
 */
private fun NavHostController.navigateToTab(tab: NavTabId) {
    navigate(tab.rootRoute()) {
        popUpTo(graph.findStartDestination().id) { saveState = false }
        launchSingleTop = true
        restoreState = false
    }
}
