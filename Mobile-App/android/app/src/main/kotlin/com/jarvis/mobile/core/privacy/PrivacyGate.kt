package com.jarvis.mobile.core.privacy

import com.jarvis.mobile.core.model.PrivacyMode
import kotlinx.coroutines.flow.Flow

/**
 * Central architectural boundary every feature must go through before
 * performing an action that is sensitive under NORMAL / PRIVACY /
 * PRIVACY_LOCK (goal spec Sec.14). Not a UI toggle: the bottom navigation,
 * the runtime strip and every feature ViewModel read the current mode
 * through this interface, never through a local flag of their own.
 *
 * Phase 1 ships the interface and a design-state-only default implementation
 * ([StaticPrivacyGate]) that mirrors the web prototype's fixed
 * `comparisonBaseline.privacyMode`. It intentionally does not invent
 * enforcement rules beyond what the web specification states; which concrete
 * capabilities PRIVACY / PRIVACY_LOCK block is a product decision to be
 * ported from the web Privacy screen content, not assumed here.
 */
interface PrivacyGate {
    val mode: Flow<PrivacyMode>

    /**
     * Whether an action guarded by [capability] is currently allowed under
     * the active [PrivacyMode]. [capability] matches a name from
     * `core.model.capabilityRows` or a feature-defined identifier.
     */
    suspend fun isAllowed(capability: String): Boolean
}
