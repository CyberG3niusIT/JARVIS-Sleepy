package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.PrivacyMode
import org.junit.Assert.assertEquals
import org.junit.Test

/** Round-trip tests for the string codec backing [PrivacyScreen]'s `rememberSaveable` overlay state. */
class PrivacyOverlayCodecTest {

    @Test
    fun `round trips None`() {
        assertEquals(PrivacyOverlay.None, decodePrivacyOverlay(encodePrivacyOverlay(PrivacyOverlay.None)))
    }

    @Test
    fun `round trips every overlay kind for every privacy mode`() {
        PrivacyMode.entries.forEach { mode ->
            listOf(
                PrivacyOverlay.Explain(mode),
                PrivacyOverlay.ConfirmLock(mode),
                PrivacyOverlay.ConfirmRelax(mode),
            ).forEach { overlay ->
                assertEquals(overlay, decodePrivacyOverlay(encodePrivacyOverlay(overlay)))
            }
        }
    }
}
