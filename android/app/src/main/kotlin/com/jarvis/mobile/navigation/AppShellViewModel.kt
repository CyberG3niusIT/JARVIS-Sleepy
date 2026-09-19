package com.jarvis.mobile.navigation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.SystemState
import com.jarvis.mobile.core.model.comparisonBaseline
import com.jarvis.mobile.core.privacy.PrivacyGate
import com.jarvis.mobile.core.runtime.LocalRuntimeGateway
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

data class AppShellUiState(
    val runtimeState: SystemState = SystemState.DESIGN_STATE,
    val runtimeLabel: String = comparisonBaseline.labels.runtime,
    val execution: ExecutionLocation = comparisonBaseline.execution,
    val privacy: PrivacyMode = comparisonBaseline.privacyMode,
)

/**
 * Backs the persistent [com.jarvis.mobile.core.designsystem.component.JarvisRuntimeStrip],
 * which every tab shows regardless of navigation state. Reads through
 * [LocalRuntimeGateway] and [PrivacyGate] only - no tab-local state.
 */
@HiltViewModel
class AppShellViewModel @Inject constructor(
    localRuntimeGateway: LocalRuntimeGateway,
    privacyGate: PrivacyGate,
) : ViewModel() {

    val uiState: StateFlow<AppShellUiState> = combine(
        localRuntimeGateway.state,
        privacyGate.mode,
    ) { runtimeState, privacy ->
        AppShellUiState(
            runtimeState = runtimeState,
            runtimeLabel = comparisonBaseline.labels.runtime,
            execution = comparisonBaseline.execution,
            privacy = privacy,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AppShellUiState())
}
