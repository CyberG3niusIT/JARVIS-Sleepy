package com.jarvis.mobile.feature.chat

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
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
 * Reads display name, size and header bytes through the ContentResolver, the
 * Android equivalent of the web reference's File API access. Never a
 * security boundary by itself - a future backend must re-validate content
 * server-side, exactly as the web reference's own comment states.
 */
suspend fun validateAttachment(context: Context, uri: Uri): AttachmentCheck = withContext(Dispatchers.IO) {
    val resolver = context.contentResolver
    var displayName = uri.lastPathSegment ?: "Datei"
    var size = 0L
    resolver.query(uri, null, null, null, null)?.use { cursor ->
        val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
        if (cursor.moveToFirst()) {
            if (nameIdx >= 0) displayName = cursor.getString(nameIdx) ?: displayName
            if (sizeIdx >= 0) size = cursor.getLong(sizeIdx)
        }
    }

    val lowerName = displayName.lowercase()
    val rule = signatureRules.find { rule -> rule.extensions.any { lowerName.endsWith(it) } }
        ?: return@withContext AttachmentCheck.Failed("Dateityp wird nicht unterstützt. Erlaubt sind PNG, JPEG, GIF, WebP und PDF.")

    val mimeType = resolver.getType(uri) ?: ""
    if (mimeType !in rule.mimeTypes) {
        return@withContext AttachmentCheck.Failed("Dateityp und Inhaltstyp passen nicht zusammen.")
    }

    val header = ByteArray(16)
    val read = resolver.openInputStream(uri)?.use { it.read(header) } ?: -1
    if (read <= 0 || !rule.matches(header)) {
        return@withContext AttachmentCheck.Failed("Dateiinhalt passt nicht zur Dateiendung.")
    }

    AttachmentCheck.Ok(rule.kind, displayName, size)
}
