package com.jarvis.mobile.feature.chat

import androidx.lifecycle.ViewModel
import com.jarvis.mobile.core.model.comparisonBaseline
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

data class ChatUiState(
    val messages: List<ChatMessage> = demoConversation,
    /** Static part of the transcript, matching the web reference's baseCount. */
    val baseCount: Int = demoConversation.size,
    val draft: String = "",
)

/**
 * Local, in-memory only, ported 1:1 from the web ChatScreen state. No model,
 * no runtime, no backend is touched: sending only appends a truthful system
 * note about the current design state (Sec.9 - no fake telemetry, no
 * fabricated results).
 */
@HiltViewModel
class ChatViewModel @Inject constructor() : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    fun onDraftChange(next: String) {
        _uiState.value = _uiState.value.copy(draft = next)
    }

    fun onPickExample(prompt: String) {
        _uiState.value = _uiState.value.copy(draft = prompt)
    }

    fun onReset() {
        _uiState.value = ChatUiState(messages = emptyList(), baseCount = 0, draft = "")
    }

    fun onSend() {
        val state = _uiState.value
        val text = state.draft.trim()
        if (text.isEmpty()) return
        val stamp = System.currentTimeMillis()
        val note = "Keine Antwort erzeugt. ${comparisonBaseline.labels.runtime}, " +
            "${comparisonBaseline.labels.localModel}. Der Prototyp übernimmt die Eingabe " +
            "nur als Entwurfszustand."
        _uiState.value = state.copy(
            messages = state.messages +
                ChatMessage(id = "u-$stamp", role = ChatRole.USER, text = text) +
                ChatMessage(id = "s-$stamp", role = ChatRole.SYSTEM, text = note),
            draft = "",
        )
    }
}
