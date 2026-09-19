package com.jarvis.mobile.feature.chat

import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
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

    @Test
    fun `signature header read fails closed when the stream throws`() {
        assertEquals(null, readAttachmentHeader { FailingInputStream() })
    }

    @Test
    fun `signature header read fails closed when no stream can be opened`() {
        assertEquals(null, readAttachmentHeader { null })
    }
}

private class FailingInputStream : InputStream() {
    override fun read(): Int = throw IOException("simulated read failure")
    override fun read(b: ByteArray, off: Int, len: Int): Int = throw IOException("simulated read failure")
}

/**
 * Tests for the actual size-resolution decision logic, not just the
 * constants it is checked against. Uses plain [InputStream] fakes so the
 * pure [resolveAttachmentSizeFromSources] function can be exercised without
 * Robolectric or any Android framework type.
 */
class ResolveAttachmentSizeFromSourcesTest {

    @Test
    fun `uses the cursor size when the provider reports one`() {
        val size = resolveAttachmentSizeFromSources(
            cursorSize = 1234L,
            descriptorLength = 9999L,
            openStream = { error("must not be called when cursor size is known") },
        )
        assertEquals(1234L, size)
    }

    @Test
    fun `falls back to the descriptor length when the cursor size is unknown`() {
        val size = resolveAttachmentSizeFromSources(
            cursorSize = null,
            descriptorLength = 5678L,
            openStream = { error("must not be called when descriptor length is known") },
        )
        assertEquals(5678L, size)
    }

    @Test
    fun `falls back to the descriptor length when the cursor reports zero`() {
        val size = resolveAttachmentSizeFromSources(
            cursorSize = 0L,
            descriptorLength = 42L,
            openStream = { error("must not be called when descriptor length is known") },
        )
        assertEquals(42L, size)
    }

    @Test
    fun `counts the stream exactly when both provider sizes are unknown and the file is small`() {
        val bytes = ByteArray(2048) { it.toByte() }
        val size = resolveAttachmentSizeFromSources(
            cursorSize = null,
            descriptorLength = null,
            openStream = { ByteArrayInputStream(bytes) },
        )
        assertEquals(2048L, size)
    }

    @Test
    fun `counts the stream exactly when the file is exactly at the per-file limit`() {
        val bytes = ByteArray(MAX_FILE_BYTES.toInt())
        val size = resolveAttachmentSizeFromSources(
            cursorSize = null,
            descriptorLength = null,
            openStream = { ByteArrayInputStream(bytes) },
        )
        assertEquals(MAX_FILE_BYTES, size)
    }

    @Test
    fun `caps the count at MAX_FILE_BYTES plus one when the stream exceeds the per-file limit`() {
        val bytes = ByteArray((MAX_FILE_BYTES + 1024).toInt())
        val size = resolveAttachmentSizeFromSources(
            cursorSize = null,
            descriptorLength = null,
            openStream = { ByteArrayInputStream(bytes) },
        )
        assertEquals(MAX_FILE_BYTES + 1, size)
    }

    @Test
    fun `resolves to the oversize sentinel when the stream throws while reading`() {
        val size = resolveAttachmentSizeFromSources(
            cursorSize = null,
            descriptorLength = null,
            openStream = { FailingInputStream() },
        )
        assertEquals(MAX_FILE_BYTES + 1, size)
    }

    @Test
    fun `never resolves an unknown size to zero when no stream can be opened`() {
        val size = resolveAttachmentSizeFromSources(
            cursorSize = null,
            descriptorLength = null,
            openStream = { null },
        )
        assertEquals(MAX_FILE_BYTES + 1, size)
        assert(size != 0L)
    }

    @Test
    fun `never resolves an unknown size to zero when both provider sizes are zero or negative`() {
        val bytes = ByteArray(10)
        val size = resolveAttachmentSizeFromSources(
            cursorSize = -1L,
            descriptorLength = 0L,
            openStream = { ByteArrayInputStream(bytes) },
        )
        assertEquals(10L, size)
        assert(size != 0L)
    }
}
