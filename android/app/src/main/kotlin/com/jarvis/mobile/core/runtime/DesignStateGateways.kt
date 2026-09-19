package com.jarvis.mobile.core.runtime

import com.jarvis.mobile.core.model.SystemState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** Design-state-only fake, see [LocalRuntimeGateway]. */
@Singleton
class DesignStateLocalRuntimeGateway @Inject constructor() : LocalRuntimeGateway {
    override val state: StateFlow<SystemState> = MutableStateFlow(SystemState.DESIGN_STATE)
    override val boundModelName: StateFlow<String?> = MutableStateFlow(null)
}

/** Design-state-only fake, see [PermissionGateway]. Grants nothing. */
@Singleton
class DesignStatePermissionGateway @Inject constructor() : PermissionGateway {
    override suspend fun isGranted(permission: String): Boolean = false
}

/** Design-state-only fake, see [SleepyRuntimeGateway]. Sleepy is unavailable. */
@Singleton
class DesignStateSleepyRuntimeGateway @Inject constructor() : SleepyRuntimeGateway {
    override val state: StateFlow<SystemState> = MutableStateFlow(SystemState.UNAVAILABLE)
    override val isPaired: StateFlow<Boolean> = MutableStateFlow(false)
}
