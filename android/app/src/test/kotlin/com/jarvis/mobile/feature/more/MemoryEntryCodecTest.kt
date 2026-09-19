package com.jarvis.mobile.feature.more

import com.jarvis.mobile.core.model.SystemState
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Round-trip tests for the string codec backing [MemoryScreen]'s
 * `rememberSaveable` demo-entry list, edited via confirm/correct/discard/
 * supersede. Built on the same [com.jarvis.mobile.core.util.StringFieldCodec]
 * as the Automation codec, so it must not collide on entry content either.
 */
class MemoryEntryCodecTest {

    @Test
    fun `round trips the seed entries unchanged`() {
        assertEquals(memoryDemoSeed, decodeMemoryEntries(encodeMemoryEntries(memoryDemoSeed)))
    }

    @Test
    fun `round trips an entry with every optional field null`() {
        val entry = MemoryEntry(
            id = "bare",
            layer = MemoryLayer.WORKING,
            summary = "Nur Pflichtfelder",
            state = SystemState.DESIGN_STATE,
            provenance = MemoryProvenance.SYSTEM,
        )

        assertEquals(listOf(entry), decodeMemoryEntries(encodeMemoryEntries(listOf(entry))))
    }

    @Test
    fun `round trips fields containing separator-like and unicode content`() {
        val entry = MemoryEntry(
            id = "id\u0001with\u0002control",
            layer = MemoryLayer.CANDIDATE,
            subject = "5:hello",
            summary = "Zeile eins\nZeile zwei, 😀 日本語",
            state = SystemState.DESIGN_STATE,
            provenance = MemoryProvenance.INFERENCE,
            confirmationStatus = MemoryConfirmationStatus.CORRECTED,
            supersedes = MemorySupersedes("alt-id", "0: kein Header"),
            supersedeNote = "",
        )

        assertEquals(listOf(entry), decodeMemoryEntries(encodeMemoryEntries(listOf(entry))))
    }

    @Test
    fun `an empty summary is not confused with a missing optional field`() {
        val entry = MemoryEntry(
            id = "empty-summary",
            layer = MemoryLayer.RECENT,
            subject = "",
            summary = "",
            state = SystemState.DESIGN_STATE,
            provenance = MemoryProvenance.OBSERVATION,
            sourceReference = "",
        )

        val restored = decodeMemoryEntries(encodeMemoryEntries(listOf(entry))).single()
        assertEquals("", restored.subject)
        assertEquals("", restored.summary)
        assertEquals("", restored.sourceReference)
    }
}
