package com.jarvis.mobile.feature.common

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.jarvis.mobile.core.designsystem.component.JarvisDesignStateNote
import com.jarvis.mobile.core.designsystem.component.JarvisDetailHeader

/**
 * Shared shell for every System/Mehr detail screen, mirroring the contract
 * every web detail screen takes: [com.jarvis.mobile.core.model.ProductArea]
 * title + purpose, a back affordance, scrollable body, closing design-state
 * note (src/components/jarvis/screens/detail-header.tsx).
 */
@Composable
fun DetailScaffold(
    title: String,
    subtitle: String,
    onBack: () -> Unit,
    backLabel: String,
    content: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        JarvisDetailHeader(title = title, subtitle = subtitle, onBack = onBack, backLabel = backLabel)
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            content()
            JarvisDesignStateNote()
        }
    }
}
