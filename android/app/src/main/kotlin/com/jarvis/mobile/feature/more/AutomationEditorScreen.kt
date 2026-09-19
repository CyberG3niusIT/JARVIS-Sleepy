package com.jarvis.mobile.feature.more

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.core.designsystem.component.JARVIS_MORE_BACK_LABEL
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDialog
import com.jarvis.mobile.core.designsystem.component.JarvisTextField
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.feature.common.DetailScaffold

/**
 * Automation Editor, ported from src/components/jarvis/screens/automation-editor.tsx.
 *
 * Implements the goal spec's Sec.8 locked back behaviour: with unsaved
 * changes, both the system Back gesture and the screen's own back
 * affordance show a discard confirmation before leaving to Automationen;
 * without changes, back leaves immediately.
 */
@Composable
fun AutomationEditorScreen(onBack: () -> Unit) {
    var name by remember { mutableStateOf("") }
    var showDiscardConfirm by remember { mutableStateOf(false) }
    val isDirty = name.isNotBlank()

    fun requestBack() {
        if (isDirty) showDiscardConfirm = true else onBack()
    }

    BackHandler(onBack = ::requestBack)

    DetailScaffold(
        title = "Neue Automation",
        subtitle = "Makro, Zeitplan oder Routine anlegen.",
        onBack = ::requestBack,
        backLabel = JARVIS_MORE_BACK_LABEL,
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            JarvisTextField(
                value = name,
                onValueChange = { name = it },
                label = "Name",
                placeholder = "z. B. Nachtmodus",
            )
        }
    }

    JarvisDialog(
        open = showDiscardConfirm,
        onClose = { showDiscardConfirm = false },
        title = "Änderungen verwerfen?",
        description = "Die Automation wurde noch nicht gespeichert. Beim Verlassen gehen die " +
            "Eingaben verloren.",
        actions = {
            Button(onClick = { showDiscardConfirm = false }) { Text("Weiter bearbeiten") }
        },
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            JarvisButton(
                text = "Verwerfen",
                variant = JarvisButtonVariant.DESTRUCTIVE,
                fullWidth = true,
                onClick = {
                    showDiscardConfirm = false
                    onBack()
                },
            )
        }
    }
}
