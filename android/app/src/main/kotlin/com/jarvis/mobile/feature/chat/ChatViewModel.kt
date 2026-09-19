package com.jarvis.mobile.feature.chat

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jarvis.mobile.core.model.comparisonBaseline
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatUiState(
    val messages: List<ChatMessage> = demoConversation,
    /** Static part of the transcript, matching the web reference's baseCount. */
    val baseCount: Int = demoConversation.size,
    val draft: String = "",
    val attachments: List<ChatAttachment> = emptyList(),
    val attachmentError: String? = null,
)

/**
 * Local, in-memory only, ported 1:1 from the web ChatScreen state. No model,
 * no runtime, no backend is touched: sending only appends a truthful system
 * note about the current design state (Sec.9 - no fake telemetry, no
 * fabricated results). Attachment validation reads real file metadata
 * through the ContentResolver (see [validateAttachment]), but the picked
 * file is never uploaded, parsed or analysed.
 */
@HiltViewModel
class ChatViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
) : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()
    private var attachmentIdSeq = 0

    fun onDraftChange(next: String) {
        _uiState.value = _uiState.value.copy(draft = next)
    }

    fun onPickExample(prompt: String) {
        _uiState.value = _uiState.value.copy(draft = prompt)
    }

    fun onReset() {
        _uiState.value = ChatUiState(messages = emptyList(), baseCount = 0, draft = "")
    }

    fun onRemoveAttachment(id: String) {
        _uiState.value = _uiState.value.copy(
            attachments = _uiState.value.attachments.filterNot { it.id == id },
            attachmentError = null,
        )
    }

    /**
     * Count, single-file size and total draft size are checked first, then
     * the content signature. An over-sized or unsupported file is rejected
     * completely, never truncated - matching the web reference's addFiles.
     */
    fun onAddFiles(uris: List<Uri>) {
        viewModelScope.launch {
            val current = _uiState.value.attachments
            val accepted = mutableListOf<ChatAttachment>()
            val errors = mutableListOf<String>()
            var count = current.size
            var total = current.sumOf { it.size }

            for (uri in uris) {
                val label = uri.lastPathSegment ?: "Datei"
                if (count >= MAX_ATTACHMENTS) {
                    errors += "$label: maximal $MAX_ATTACHMENTS Anhänge pro Nachricht."
                    continue
                }
                when (val check = validateAttachment(context, uri)) {
                    is AttachmentCheck.Failed -> errors += "$label: ${check.reason}"
                    is AttachmentCheck.Ok -> {
                        if (check.size > MAX_FILE_BYTES) {
                            errors += "${check.name}: ${formatMiB(check.size)} überschreitet das Limit von ${formatMiB(MAX_FILE_BYTES)} pro Datei."
                            continue
                        }
                        if (total + check.size > MAX_TOTAL_BYTES) {
                            errors += "${check.name}: Gesamtgröße überschreitet das Limit von ${formatMiB(MAX_TOTAL_BYTES)}."
                            continue
                        }
                        attachmentIdSeq += 1
                        accepted += ChatAttachment(
                            id = "a-${System.currentTimeMillis()}-$attachmentIdSeq",
                            kind = check.kind,
                            name = check.name,
                            size = check.size,
                            previewUri = if (check.kind == ChatAttachmentKind.IMAGE) uri else null,
                        )
                        count += 1
                        total += check.size
                    }
                }
            }

            _uiState.value = _uiState.value.copy(
                attachments = _uiState.value.attachments + accepted,
                attachmentError = errors.takeIf { it.isNotEmpty() }?.joinToString(" "),
            )
        }
    }

    fun onSend() {
        val state = _uiState.value
        val text = state.draft.trim()
        val sent = state.attachments
        if (text.isEmpty() && sent.isEmpty()) return
        val stamp = System.currentTimeMillis()
        val note = if (sent.isNotEmpty()) {
            val countLabel = if (sent.size == 1) "1 Datei angehängt" else "${sent.size} Dateien angehängt"
            "$countLabel. Analyse ist erst nach Runtime-Anbindung verfügbar. " +
                "${comparisonBaseline.labels.runtime}, ${comparisonBaseline.labels.localModel}."
        } else {
            "Keine Antwort erzeugt. ${comparisonBaseline.labels.runtime}, " +
                "${comparisonBaseline.labels.localModel}. Der Prototyp übernimmt die Eingabe " +
                "nur als Entwurfszustand."
        }
        _uiState.value = state.copy(
            messages = state.messages +
                ChatMessage(id = "u-$stamp", role = ChatRole.USER, text = text, attachments = sent) +
                ChatMessage(id = "s-$stamp", role = ChatRole.SYSTEM, text = note),
            draft = "",
            attachments = emptyList(),
            attachmentError = null,
        )
    }
}
