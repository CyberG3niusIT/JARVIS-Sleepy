package com.jarvis.mobile.feature.chat

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisExecutionTag
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import com.jarvis.mobile.core.designsystem.component.JarvisTextField
import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.SystemState

/**
 * Ported 1:1 from src/components/jarvis/screens/chat-screen.tsx. Attachment
 * picking (paperclip, image/PDF preview) is deferred to a follow-up commit,
 * see android/PORTING_PLAN.md; every other structural element - header,
 * transcript, action rows, task states, composer - is ported.
 */
@Composable
fun ChatScreen(viewModel: ChatViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsState()

    Column(modifier = Modifier.fillMaxSize()) {
        ChatHeader(showReset = state.messages.isNotEmpty(), onReset = viewModel::onReset)

        Box(modifier = Modifier.weight(1f)) {
            if (state.messages.isEmpty()) {
                EmptyConversation(onPick = viewModel::onPickExample)
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.md),
                    verticalArrangement = Arrangement.spacedBy(JarvisSpacing.md),
                ) {
                    items(state.messages, key = { it.id }) { message ->
                        ChatMessageItem(message = message)
                    }
                }
            }
        }

        ChatComposer(
            value = state.draft,
            onChange = viewModel::onDraftChange,
            onSend = viewModel::onSend,
        )
    }
}

@Composable
private fun ChatHeader(showReset: Boolean, onReset: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
            .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.sm),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = if (showReset) "Prototypbeispiel" else "Neue Unterhaltung",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
        )
        if (showReset) {
            Text(
                text = "Neue Unterhaltung",
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 12.sp,
                modifier = Modifier
                    .clip(RoundedCornerShape(JarvisRadii.sm))
                    .clickable(role = Role.Button, onClick = onReset)
                    .defaultMinSize(minHeight = JarvisSpacing.xxl)
                    .padding(horizontal = JarvisSpacing.xs, vertical = JarvisSpacing.xs),
            )
        }
    }
}

@Composable
private fun EmptyConversation(onPick: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = JarvisSpacing.lg, vertical = JarvisSpacing.xxl),
    ) {
        Text(text = "Was soll ich erledigen?", color = JarvisSemanticColor.foreground, fontSize = 15.sp, lineHeight = 20.sp)
        Text(
            text = "Lokale Aktionen, Fragen oder Abläufe. Standardausführung: LOKAL.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 12.sp,
            lineHeight = 18.sp,
            modifier = Modifier.padding(top = JarvisSpacing.xs),
        )
        Column(
            modifier = Modifier
                .padding(top = JarvisSpacing.lg)
                .border(BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft)),
        ) {
            examplePrompts.forEach { prompt ->
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .defaultMinSize(minHeight = 48.dp)
                        .clickable(role = Role.Button) { onPick(prompt) }
                        .padding(vertical = JarvisSpacing.sm),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    Text(text = prompt, color = JarvisSemanticColor.subtleForeground, fontSize = 13.sp)
                }
            }
        }
        Text(
            text = "Beispiele übernehmen nur den Text in die Eingabe. Benötigt eine Aktion eine " +
                "Berechtigung, wird das als Zustand angezeigt.",
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(top = JarvisSpacing.sm),
        )
    }
}

@Composable
private fun ChatMessageItem(message: ChatMessage) {
    when (message.role) {
        ChatRole.USER -> Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
            Box(
                modifier = Modifier
                    .widthIn(max = 280.dp)
                    .clip(RoundedCornerShape(JarvisRadii.sm))
                    .background(JarvisSemanticColor.surfaceSelected)
                    .padding(horizontal = JarvisSpacing.md, vertical = JarvisSpacing.sm),
            ) {
                Text(text = message.text, color = JarvisSemanticColor.foreground, fontSize = 13.sp, lineHeight = 20.sp)
            }
        }

        ChatRole.SYSTEM -> Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, JarvisSemanticColor.border, RoundedCornerShape(JarvisRadii.sm))
                .padding(horizontal = JarvisSpacing.md, vertical = JarvisSpacing.sm),
        ) {
            JarvisStatusTag(state = SystemState.DESIGN_STATE)
            Text(
                text = message.text,
                color = JarvisSemanticColor.mutedForeground,
                fontSize = 12.sp,
                lineHeight = 18.sp,
                modifier = Modifier.padding(top = JarvisSpacing.xs),
            )
        }

        ChatRole.JARVIS -> Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(BorderStroke(2.dp, JarvisSemanticColor.border))
                .padding(start = JarvisSpacing.md),
        ) {
            if (message.execution != null) {
                JarvisExecutionTag(where = message.execution, modifier = Modifier.padding(bottom = JarvisSpacing.xs))
            }
            Text(text = message.text, color = JarvisSemanticColor.subtleForeground, fontSize = 13.sp, lineHeight = 20.sp)
            if (message.actions.isNotEmpty()) {
                Column(
                    modifier = Modifier
                        .padding(top = JarvisSpacing.sm)
                        .border(1.dp, JarvisSemanticColor.borderSoft, RoundedCornerShape(JarvisRadii.sm)),
                ) {
                    message.actions.forEach { action ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = JarvisSpacing.sm, vertical = JarvisSpacing.sm),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(text = action.label, color = JarvisSemanticColor.foreground, fontSize = 12.sp)
                            Text(text = action.requirement, color = JarvisSemanticColor.warning, fontSize = 11.sp)
                        }
                    }
                }
            }
            if (message.task != null) {
                ChatTaskStateView(state = message.task)
            }
        }
    }
}

private data class TaskCopy(
    val tag: SystemState,
    val tagLabel: String,
    val note: String,
    val execution: ExecutionLocation? = null,
)

@Composable
private fun ChatTaskStateView(state: ChatTaskState) {
    val copy = when (state) {
        ChatTaskState.RUNNING -> TaskCopy(
            SystemState.LOCAL,
            "Läuft",
            "Aufgabe wird lokal ausgeführt. Kein Fortschrittswert verfügbar.",
            ExecutionLocation.LOKAL,
        )
        ChatTaskState.WAITING_FOR_REMOTE -> TaskCopy(
            SystemState.WAITING_REMOTE,
            "Wartet",
            "Übergabe an Sleepy: noch nicht implementiert. Aktuell: nicht verbunden.",
            ExecutionLocation.SLEEPY,
        )
        ChatTaskState.BLOCKED_BY_PRIVACY -> TaskCopy(
            SystemState.PRIVACY_BLOCKED,
            "Durch Privacy blockiert",
            "Der aktive Privacy Mode verbietet diese Ausführung. Es gibt keinen stillen Fallback.",
        )
        ChatTaskState.PERMISSION_REQUIRED -> TaskCopy(
            SystemState.PERMISSION_REQUIRED,
            "Berechtigung erforderlich",
            "Ohne Freigabe passiert nichts. Freigabe erfolgt unter System, Berechtigungen.",
        )
        ChatTaskState.ERROR -> TaskCopy(
            SystemState.ERROR,
            "Fehlgeschlagen",
            "Die Aufgabe konnte nicht abgeschlossen werden.",
        )
    }
    Column(
        modifier = Modifier
            .padding(top = JarvisSpacing.sm)
            .fillMaxWidth()
            .border(BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
            .padding(horizontal = JarvisSpacing.sm, vertical = JarvisSpacing.sm),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            JarvisStatusTag(state = copy.tag, label = copy.tagLabel)
            if (copy.execution != null) {
                Spacer(Modifier.padding(start = JarvisSpacing.sm))
                JarvisExecutionTag(where = copy.execution)
            }
        }
        Text(
            text = copy.note,
            color = JarvisSemanticColor.mutedForeground,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier.padding(top = JarvisSpacing.xs),
        )
    }
}

@Composable
private fun ChatComposer(value: String, onChange: (String) -> Unit, onSend: () -> Unit) {
    val canSend = value.isNotBlank()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft))
            .background(JarvisSemanticColor.surface)
            .padding(horizontal = JarvisSpacing.md, vertical = JarvisSpacing.sm),
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(JarvisSpacing.sm),
    ) {
        Box(modifier = Modifier.weight(1f)) {
            JarvisTextField(
                value = value,
                onValueChange = onChange,
                placeholder = "Lokal fragen oder Aktion nennen",
            )
        }
        IconButton(onClick = {}, enabled = false) {
            Icon(
                Icons.Filled.Mic,
                contentDescription = "Spracheingabe, noch nicht implementiert",
                tint = JarvisSemanticColor.disabled,
            )
        }
        IconButton(onClick = onSend, enabled = canSend) {
            Icon(
                Icons.AutoMirrored.Filled.Send,
                contentDescription = "Senden",
                tint = if (canSend) JarvisSemanticColor.primary else JarvisSemanticColor.disabled,
            )
        }
    }
}
