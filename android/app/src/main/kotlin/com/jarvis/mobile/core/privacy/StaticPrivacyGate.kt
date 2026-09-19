package com.jarvis.mobile.core.privacy

import com.jarvis.mobile.core.model.PrivacyMode
import com.jarvis.mobile.core.model.comparisonBaseline
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Design-state-only [PrivacyGate]. Reports the same fixed
 * [comparisonBaseline] value the web prototype shows and allows every
 * capability, exactly like the web prototype does before a real privacy rule
 * set is bound. No runtime enforcement is fabricated here.
 */
@Singleton
class StaticPrivacyGate @Inject constructor() : PrivacyGate {
    private val current: MutableStateFlow<PrivacyMode> = MutableStateFlow(comparisonBaseline.privacyMode)
    override val mode: StateFlow<PrivacyMode> = current

    override suspend fun isAllowed(capability: String): Boolean = true
}
