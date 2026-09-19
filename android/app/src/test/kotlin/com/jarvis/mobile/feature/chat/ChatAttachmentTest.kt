package com.jarvis.mobile.feature.chat

import org.junit.Assert.assertEquals
import org.junit.Test

class ChatAttachmentTest {

    @Test
    fun `formatMiB rounds to one decimal place`() {
        assertEquals("1.0 MiB", formatMiB(1024L * 1024))
        assertEquals("25.0 MiB", formatMiB(MAX_FILE_BYTES))
        assertEquals("50.0 MiB", formatMiB(MAX_TOTAL_BYTES))
    }

    @Test
    fun `limits match the web reference exactly`() {
        assertEquals(8, MAX_ATTACHMENTS)
        assertEquals(25L * 1024 * 1024, MAX_FILE_BYTES)
        assertEquals(50L * 1024 * 1024, MAX_TOTAL_BYTES)
    }
}
