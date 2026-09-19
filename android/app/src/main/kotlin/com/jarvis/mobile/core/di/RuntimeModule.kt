package com.jarvis.mobile.core.di

import com.jarvis.mobile.core.privacy.PrivacyGate
import com.jarvis.mobile.core.privacy.StaticPrivacyGate
import com.jarvis.mobile.core.runtime.DesignStateLocalRuntimeGateway
import com.jarvis.mobile.core.runtime.DesignStatePermissionGateway
import com.jarvis.mobile.core.runtime.DesignStateSleepyRuntimeGateway
import com.jarvis.mobile.core.runtime.LocalRuntimeGateway
import com.jarvis.mobile.core.runtime.PermissionGateway
import com.jarvis.mobile.core.runtime.SleepyRuntimeGateway
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Binds the Phase 1 design-state-only implementations. Swapping in the real
 * local runtime, permission and Sleepy gateways later only touches this
 * module, never the feature ViewModels that depend on the interfaces.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class RuntimeModule {

    @Binds
    @Singleton
    abstract fun bindPrivacyGate(impl: StaticPrivacyGate): PrivacyGate

    @Binds
    @Singleton
    abstract fun bindLocalRuntimeGateway(impl: DesignStateLocalRuntimeGateway): LocalRuntimeGateway

    @Binds
    @Singleton
    abstract fun bindPermissionGateway(impl: DesignStatePermissionGateway): PermissionGateway

    @Binds
    @Singleton
    abstract fun bindSleepyRuntimeGateway(impl: DesignStateSleepyRuntimeGateway): SleepyRuntimeGateway
}
