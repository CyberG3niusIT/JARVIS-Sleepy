package com.jarvis.mobile.feature.chat

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.InputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Ported 1:1 from src/components/jarvis/chat-attachment.tsx. Only images and
 * PDF files are supported. Nothing here uploads, extracts or analyses
 * anything: an attachment is carried with the message and shown truthfully.
 */

enum class ChatAttachmentKind { IMAGE, PDF }

data class ChatAttachment(
    val id: String,
    val kind: ChatAttachmentKind,
    val name: String,
    /** Size in bytes of the selected file, used for the local draft budget. */
    val size: Long,
    /** Content URI for the local preview, valid for as long as the picker grants access. */
    val previewUri: Uri? = null,
)

val attachmentKindLabel: Map<ChatAttachmentKind, String> = mapOf(
    ChatAttachmentKind.IMAGE to "Bild",
    ChatAttachmentKind.PDF to "PDF",
)

const val MAX_ATTACHMENTS = 8
const val MAX_FILE_BYTES = 25L * 1024 * 1024
const val MAX_TOTAL_BYTES = 50L * 1024 * 1024

fun formatMiB(bytes: Long): String {
    val mib = Math.round((bytes / (1024.0 * 1024.0)) * 10) / 10.0
    return "$mib MiB"
}

/** Mirrors the web reference's `matches` signature checks against header bytes. */
private data class SignatureRule(
    val kind: ChatAttachmentKind,
    val extensions: List<String>,
    val mimeTypes: List<String>,
    val matches: (ByteArray) -> Boolean,
)

private fun startsWith(bytes: ByteArray, expected: IntArray, offset: Int = 0): Boolean =
    expected.withIndex().all { (i, b) -> offset + i < bytes.size && (bytes[offset + i].toInt() and 0xFF) == b }

private fun ascii(text: String): IntArray = text.map { it.code }.toIntArray()

private val signatureRules: List<SignatureRule> = listOf(
    SignatureRule(ChatAttachmentKind.PDF, listOf(".pdf"), listOf("application/pdf", "application/octet-stream", "")) { startsWith(it, ascii("%PDF-")) },
    SignatureRule(ChatAttachmentKind.IMAGE, listOf(".png"), listOf("image/png")) { startsWith(it, intArrayOf(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) },
    SignatureRule(ChatAttachmentKind.IMAGE, listOf(".jpg", ".jpeg"), listOf("image/jpeg")) { startsWith(it, intArrayOf(0xff, 0xd8, 0xff)) },
    SignatureRule(ChatAttachmentKind.IMAGE, listOf(".gif"), listOf("image/gif")) { startsWith(it, ascii("GIF87a")) || startsWith(it, ascii("GIF89a")) },
    SignatureRule(ChatAttachmentKind.IMAGE, listOf(".webp"), listOf("image/webp")) { startsWith(it, ascii("RIFF")) && startsWith(it, ascii("WEBP"), 8) },
)

sealed interface AttachmentCheck {
    data class Ok(val kind: ChatAttachmentKind, val name: String, val size: Long) : AttachmentCheck
    data class Failed(val reason: String) : AttachmentCheck
}

/**
 * Upper bound the counting fallback below ever reads: exactly one byte past
 * the largest size any attachment is ever allowed to have. Reading further
 * would only confirm "even larger", which the caller does not need to know.
 */
private const val SIZE_PROBE_LIMIT = MAX_FILE_BYTES + 1

/**
 * Pure decision logic behind [resolveAttachmentSize], taking a plain
 * [InputStream]-opening lambda instead of a [ContentResolver] so it is
 * unit-testable without Robolectric or any Android framework mock. Never
 * returns a guessed or defaulted value - in particular, an unknown size
 * (no cursor value, no descriptor length, an unreadable/failing stream, or
 * `openStream()` returning `null`) always resolves to [SIZE_PROBE_LIMIT]
 * (already over [MAX_FILE_BYTES]), never `0`, since `0` would let an
 * oversized file slip past the per-file and total budget checks in
 * [com.jarvis.mobile.feature.chat.ChatViewModel.onAddFiles].
 *
 * Resolution order:
 * 1. `cursorSize` when the provider reported a positive value.
 * 2. `descriptorLength` (a second, independent provider-reported value;
 *    some providers that omit the cursor column still fill this in).
 * 3. Counting bytes read from `openStream()`, capped at [SIZE_PROBE_LIMIT]
 *    so a multi-gigabyte file cannot be read in full just to be rejected.
 *    If the stream is exhausted before the cap, the count is the file's
 *    exact size. If the cap is reached, or the stream throws, or
 *    `openStream()` returns `null`, the result is [SIZE_PROBE_LIMIT],
 *    which the caller's per-file limit check rejects correctly without
 *    needing the file's true size.
 */
internal fun resolveAttachmentSizeFromSources(cursorSize: Long?, descriptorLength: Long?, openStream: () -> InputStream?): Long {
    if (cursorSize != null && cursorSize > 0) return cursorSize
    if (descriptorLength != null && descriptorLength > 0) return descriptorLength

    return runCatching {
        openStream()?.use { stream ->
            val buffer = ByteArray(8192)
            var counted = 0L
            while (counted < SIZE_PROBE_LIMIT) {
                val read = stream.read(buffer)
                if (read < 0) break
                counted += read
            }
            // A single read can return up to a full buffer past the cap
            // (the loop only checks the threshold before reading, not
            // after), so clamp here rather than letting an arbitrarily
            // large file overshoot SIZE_PROBE_LIMIT by an unbounded amount.
            minOf(counted, SIZE_PROBE_LIMIT)
        }
    }.getOrNull() ?: SIZE_PROBE_LIMIT
}

/**
 * Thin Android wrapper around [resolveAttachmentSizeFromSources]: resolves
 * the `AssetFileDescriptor.length` fallback value and supplies the content
 * stream, but holds none of the size-decision logic itself.
 */
private fun resolveAttachmentSize(resolver: ContentResolver, uri: Uri, cursorSize: Long?): Long {
    val descriptorLength = runCatching {
        resolver.openAssetFileDescriptor(uri, "r")?.use { it.length }
    }.getOrNull()
    return resolveAttachmentSizeFromSources(cursorSize, descriptorLength) { resolver.openInputStream(uri) }
}

/** Reads the signature header and converts missing or failing streams into a closed failure. */
internal fun readAttachmentHeader(openStream: () -> InputStream?): ByteArray? = runCatching {
    val header = ByteArray(16)
    val stream = openStream() ?: return@runCatching null
    val read = stream.use {
        var offset = 0
        while (offset < header.size) {
            val count = it.read(header, offset, header.size - offset)
            if (count < 0) break
            if (count == 0) {
                val single = it.read()
                if (single < 0) break
                header[offset] = single.toByte()
                offset += 1
            } else {
                offset += count
            }
        }
        offset
    }
    header.takeIf { read > 0 }
}.getOrNull()

/**
 * Reads display name, size and header bytes through the ContentResolver, the
 * Android equivalent of the web reference's File API access. Never a
 * security boundary by itself - a future backend must re-validate content
 * server-side, exactly as the web reference's own comment states.
 */
suspend fun validateAttachment(context: Context, uri: Uri): AttachmentCheck = withContext(Dispatchers.IO) {
    val resolver = context.contentResolver
    var displayName = uri.lastPathSegment ?: "Datei"
    var cursorSize: Long? = null
    resolver.query(uri, null, null, null, null)?.use { cursor ->
        val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
        if (cursor.moveToFirst()) {
            if (nameIdx >= 0) displayName = cursor.getString(nameIdx) ?: displayName
            if (sizeIdx >= 0 && !cursor.isNull(sizeIdx)) cursorSize = cursor.getLong(sizeIdx)
        }
    }

    val lowerName = displayName.lowercase()
    val rule = signatureRules.find { rule -> rule.extensions.any { lowerName.endsWith(it) } }
        ?: return@withContext AttachmentCheck.Failed("Dateityp wird nicht unterstützt. Erlaubt sind PNG, JPEG, GIF, WebP und PDF.")

    val mimeType = resolver.getType(uri) ?: ""
    if (mimeType !in rule.mimeTypes) {
        return@withContext AttachmentCheck.Failed("Dateityp und Inhaltstyp passen nicht zusammen.")
    }

    val header = readAttachmentHeader { resolver.openInputStream(uri) }
    if (header == null || !rule.matches(header)) {
        return@withContext AttachmentCheck.Failed("Dateiinhalt passt nicht zur Dateiendung.")
    }

    val size = resolveAttachmentSize(resolver, uri, cursorSize)
    AttachmentCheck.Ok(rule.kind, displayName, size)
}
