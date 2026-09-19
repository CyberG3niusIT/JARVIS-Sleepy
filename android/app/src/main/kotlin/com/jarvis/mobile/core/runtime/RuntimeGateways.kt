package com.jarvis.mobile.core.runtime

import com.jarvis.mobile.core.model.SystemState
import kotlinx.coroutines.flow.Flow

/**
 * Seam where the real local LiteRT-LM runtime will be bound later (goal spec
 * Sec.13). Phase 1 ViewModels depend on this interface via Hilt; the only
 * implementation provided is [DesignStateLocalRuntimeGateway], which returns
 * the same fixed design-state values as the web baseline, never a fabricated
 * model name or measurement.
 */
interface LocalRuntimeGateway {
    val state: Flow<SystemState>
    val boundModelName: Flow<String?>
}

/**
 * Seam for real Android runtime permission checks (Accessibility, screen
 * capture, notification listener, microphone, and so on). Phase 1 ships the
 * interface only; no permission is requested or checked by the fake
 * implementation.
 */
interface PermissionGateway {
    suspend fun isGranted(permission: String): Boolean
}

/**
 * Seam for the optional Sleepy handoff runtime (goal spec Sec.15). No
 * transport, pairing or certificate scheme is defined here - that remains an
 * open decision, see android/OPEN_DECISIONS.md. This interface only describes
 * the connection state the UI needs to render.
 */
interface SleepyRuntimeGateway {
    val state: Flow<SystemState>
    val isPaired: Flow<Boolean>
}
