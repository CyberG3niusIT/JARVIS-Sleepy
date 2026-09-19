package com.jarvis.mobile.feature.chat

import com.jarvis.mobile.core.model.ExecutionLocation

/** Ported 1:1 from src/components/jarvis/screens/chat-screen.tsx. */

enum class ChatRole { USER, JARVIS, SYSTEM }

/** Task lifecycle for a request. Reusable, only what is needed is rendered. */
enum class ChatTaskState { RUNNING, WAITING_FOR_REMOTE, BLOCKED_BY_PRIVACY, PERMISSION_REQUIRED, ERROR }

/** What the action does, in user language, and its confirmation requirement. */
data class ChatActionItem(val label: String, val requirement: String)

data class ChatMessage(
    val id: String,
    val role: ChatRole,
    val text: String,
    /** Where the answer was produced. Only set when it is actually known. */
    val execution: ExecutionLocation? = null,
    val actions: List<ChatActionItem> = emptyList(),
    val task: ChatTaskState? = null,
)

/**
 * Prototype fixture, not persisted user history. Demonstrates the two
 * required response patterns: deterministic local action and permission
 * required.
 */
val demoConversation: List<ChatMessage> = listOf(
    ChatMessage(
        id = "demo-1",
        role = ChatRole.USER,
        text = "Stell das Handy auf lautlos und wecke mich um 6:30.",
    ),
    ChatMessage(
        id = "demo-2",
        role = ChatRole.JARVIS,
        text = "Zwei Android-Aktionen vorbereitet. Ausführung deterministisch, ohne Modell.",
        execution = ExecutionLocation.LOKAL,
        actions = listOf(
            ChatActionItem("Lautlos aktivieren", "Bestätigung erforderlich"),
            ChatActionItem("Wecker 06:30 stellen", "Bestätigung erforderlich"),
        ),
    ),
    ChatMessage(
        id = "demo-3",
        role = ChatRole.USER,
        text = "Fasse den sichtbaren Inhalt zusammen.",
    ),
    ChatMessage(
        id = "demo-4",
        role = ChatRole.JARVIS,
        text = "Bildschirmanalyse benötigt die Android-Berechtigung für Bildschirmzugriff. " +
            "Ohne Freigabe passiert nichts, kein stiller Fallback und keine automatische Übergabe.",
        task = ChatTaskState.PERMISSION_REQUIRED,
    ),
)

val examplePrompts: List<String> = listOf(
    "Öffne Spotify",
    "Stell einen Wecker auf 6:30",
    "Fasse den sichtbaren Inhalt zusammen",
)
