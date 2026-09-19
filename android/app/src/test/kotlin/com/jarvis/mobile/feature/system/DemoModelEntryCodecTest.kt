package com.jarvis.mobile.feature.system

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Round-trip tests for the string codec backing [ModelsDemoSection]'s
 * `rememberSaveable` demo model list, edited via load/unload/download
 * start-pause-resume-cancel/retry/delete.
 */
class DemoModelEntryCodecTest {

    @Test
    fun `round trips the seed entries unchanged`() {
        assertEquals(initialDemoModels, decodeDemoModelEntries(encodeDemoModelEntries(initialDemoModels)))
    }

    @Test
    fun `round trips an entry with every optional field null`() {
        val entry = DemoModelEntry(id = "bare", name = "Bare", loadState = ModelLoadState.NOT_LOADED, source = ModelSource.IMPORT)

        assertEquals(listOf(entry), decodeDemoModelEntries(encodeDemoModelEntries(listOf(entry))))
    }

    @Test
    fun `round trips fields containing separator-like and unicode content`() {
        val entry = DemoModelEntry(
            id = "id\u0001with\u0002control",
            name = "5:hello 😀",
            loadState = ModelLoadState.DOWNLOADING,
            compatible = true,
            size = "0: kein Header",
            note = "Zeile eins\nZeile zwei",
            source = ModelSource.KATALOG,
            downloadProgress = 42,
            errorKind = null,
        )

        assertEquals(listOf(entry), decodeDemoModelEntries(encodeDemoModelEntries(listOf(entry))))
    }

    @Test
    fun `zero download progress is not confused with a missing value`() {
        val entry = DemoModelEntry(id = "zero", name = "Zero", loadState = ModelLoadState.DOWNLOADING, source = ModelSource.KATALOG, downloadProgress = 0)

        val restored = decodeDemoModelEntries(encodeDemoModelEntries(listOf(entry))).single()
        assertEquals(0, restored.downloadProgress)
    }
}
