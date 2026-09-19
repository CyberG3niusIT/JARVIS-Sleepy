package com.jarvis.mobile.feature.system

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing
import com.jarvis.mobile.core.designsystem.component.JarvisBottomSheet
import com.jarvis.mobile.core.designsystem.component.JarvisButton
import com.jarvis.mobile.core.designsystem.component.JarvisButtonVariant
import com.jarvis.mobile.core.designsystem.component.JarvisDetailField
import com.jarvis.mobile.core.designsystem.component.JarvisDialog
import com.jarvis.mobile.core.designsystem.component.JarvisInlineNotice
import com.jarvis.mobile.core.designsystem.component.JarvisListGroup
import com.jarvis.mobile.core.designsystem.component.JarvisListRow
import com.jarvis.mobile.core.designsystem.component.JarvisNoticeTone
import com.jarvis.mobile.core.designsystem.component.JarvisSectionHeader
import com.jarvis.mobile.core.designsystem.component.JarvisStatusTag
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Ported 1:1 from src/components/jarvis/screens/models-demo.tsx. Explicitly
 * separated from the truthful baseline in [ModelsScreen]: it shows example
 * entries with a local state machine (load, unload, download start/pause/
 * resume/cancel, delete). Pure in-memory Compose state, no runtime or device
 * data. The 700ms download ticker uses a per-model LaunchedEffect scoped by
 * `key(id)`, so it starts/stops exactly when that model enters/leaves the
 * DOWNLOADING state - the Compose equivalent of the web's setInterval scoped
 * per model id.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ModelsDemoSection() {
    var models by remember { mutableStateOf(initialDemoModels) }
    var openId by remember { mutableStateOf<String?>(null) }
    var deleteId by remember { mutableStateOf<String?>(null) }
    var confirmation by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun update(id: String, patch: (DemoModelEntry) -> DemoModelEntry) {
        models = models.map { if (it.id == id) patch(it) else it }
    }

    fun report(message: String) { confirmation = message }

    // Download ticker: one LaunchedEffect per currently-downloading model id.
    models.filter { it.loadState == ModelLoadState.DOWNLOADING }.forEach { m ->
        key(m.id) {
            LaunchedEffect(m.id) {
                while (isActive) {
                    delay(700)
                    val next = ((models.find { it.id == m.id }?.downloadProgress ?: 0) + 10).coerceAtMost(100)
                    if (next >= 100) {
                        update(m.id) { it.copy(loadState = ModelLoadState.NOT_LOADED, downloadProgress = null, integrity = ModelIntegrity.BESTANDEN) }
                        return@LaunchedEffect
                    }
                    update(m.id) { it.copy(downloadProgress = next) }
                }
            }
        }
    }

    fun load(m: DemoModelEntry) {
        update(m.id) { it.copy(loadState = ModelLoadState.LOADING) }
        scope.launch {
            delay(600)
            update(m.id) { it.copy(loadState = ModelLoadState.READY) }
            report("\"${m.name}\" wurde im Demozustand geladen. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
        }
    }

    fun unload(m: DemoModelEntry) {
        update(m.id) { it.copy(loadState = ModelLoadState.NOT_LOADED) }
        report("\"${m.name}\" wurde im Demozustand entladen. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun startDownload(m: DemoModelEntry) {
        update(m.id) { it.copy(loadState = ModelLoadState.DOWNLOADING, downloadProgress = 0, errorKind = null) }
        report("Download von \"${m.name}\" wurde im Demozustand gestartet. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun pauseDownload(m: DemoModelEntry) {
        update(m.id) { it.copy(loadState = ModelLoadState.PAUSED) }
        report("Download von \"${m.name}\" wurde im Demozustand pausiert. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun resumeDownload(m: DemoModelEntry) {
        update(m.id) { it.copy(loadState = ModelLoadState.DOWNLOADING) }
        report("Download von \"${m.name}\" wurde im Demozustand fortgesetzt. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun cancelDownload(m: DemoModelEntry) {
        update(m.id) { it.copy(loadState = ModelLoadState.NOT_LOADED, downloadProgress = null) }
        report("Download von \"${m.name}\" wurde im Demozustand abgebrochen. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    fun retry(m: DemoModelEntry) {
        if (m.errorKind == ModelErrorKind.DOWNLOAD) {
            update(m.id) { it.copy(loadState = ModelLoadState.DOWNLOADING, downloadProgress = 0, errorKind = null) }
        } else {
            update(m.id) { it.copy(loadState = ModelLoadState.LOADING, errorKind = null) }
            scope.launch {
                delay(600)
                update(m.id) { it.copy(loadState = ModelLoadState.READY) }
            }
        }
        report("Vorgang für \"${m.name}\" wurde im Demozustand erneut versucht. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    val open = models.find { it.id == openId }
    val deleteTarget = models.find { it.id == deleteId }

    fun deleteEntry() {
        val target = deleteTarget ?: return
        models = models.filterNot { it.id == target.id }
        deleteId = null
        openId = null
        report("\"${target.name}\" wurde im Demozustand gelöscht. Entwurfszustand, keine Runtime-Aktion ausgeführt.")
    }

    JarvisSectionHeader("Zustandsdemonstration")
    JarvisInlineNotice(
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        text = "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.",
    )
    JarvisListGroup {
        models.forEach { m ->
            val subtitle = listOfNotNull(
                modelCompatibilityLabel(m.compatible),
                if (m.loadState == ModelLoadState.DOWNLOADING || m.loadState == ModelLoadState.PAUSED) "${m.downloadProgress ?: 0}% geladen" else null,
                m.size,
            ).joinToString(", ")
            JarvisListRow(
                title = m.name,
                subtitle = subtitle,
                leading = { Icon(Icons.Filled.Storage, contentDescription = null, tint = JarvisSemanticColor.mutedForeground, modifier = Modifier.padding(end = 0.dp)) },
                trailing = { JarvisStatusTag(state = modelLoadStateTone.getValue(m.loadState), label = modelLoadStateLabel.getValue(m.loadState), dot = false) },
                chevron = true,
                onClick = { openId = m.id },
            )
        }
    }
    Text(
        text = confirmation ?: "",
        color = JarvisSemanticColor.mutedForeground,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )

    JarvisBottomSheet(open = open != null, onClose = { openId = null }, title = open?.name ?: "Modell") {
        if (open != null) {
            Column {
                JarvisDetailField(label = "Name", value = open.name)
                JarvisDetailField(label = "Quelle", value = if (open.source == ModelSource.IMPORT) "Lokaler Import" else "Modellkatalog")
                JarvisDetailFieldTag("Lokaler Zustand") { JarvisStatusTag(state = modelLoadStateTone.getValue(open.loadState), label = modelLoadStateLabel.getValue(open.loadState), dot = false) }
                JarvisDetailField(label = "Kompatibilität", value = modelCompatibilityLabel(open.compatible))
                JarvisDetailField(label = "Integrität", value = modelIntegrityLabel(open.integrity))
                open.size?.let { JarvisDetailField(label = "Größe", value = it) }
                JarvisDetailField(label = "Runtime-Zustand", value = "Nicht an eine Runtime gebunden")
                if (open.loadState == ModelLoadState.DOWNLOADING || open.loadState == ModelLoadState.PAUSED) {
                    JarvisDetailFieldTag("Fortschritt (Demo)") { DownloadProgressBar(open.downloadProgress ?: 0) }
                }

                if (open.loadState == ModelLoadState.INCOMPATIBLE) {
                    JarvisInlineNotice(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        tone = JarvisNoticeTone.WARNING,
                        text = "Dieses Beispielmodell ist als inkompatibel markiert und kann im Demozustand nicht geladen werden.",
                    )
                }
                if (open.loadState == ModelLoadState.ERROR) {
                    JarvisInlineNotice(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        tone = JarvisNoticeTone.ERROR,
                        text = if (open.errorKind == ModelErrorKind.DOWNLOAD) "Der Download ist im Demozustand fehlgeschlagen." else "Das Laden ist im Demozustand fehlgeschlagen.",
                    )
                }

                androidx.compose.foundation.layout.FlowRow(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = JarvisSpacing.sm),
                    horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(JarvisSpacing.sm),
                ) {
                    if (open.loadState == ModelLoadState.NOT_LOADED && open.compatible == true) {
                        JarvisButton(text = "Laden", variant = JarvisButtonVariant.PRIMARY, onClick = { load(open) })
                    }
                    if (open.loadState == ModelLoadState.NOT_LOADED && open.source == ModelSource.KATALOG && open.compatible == true) {
                        JarvisButton(text = "Download starten", onClick = { startDownload(open) })
                    }
                    if (open.loadState == ModelLoadState.READY) {
                        JarvisButton(text = "Entladen", onClick = { unload(open) })
                    }
                    if (open.loadState == ModelLoadState.DOWNLOADING) {
                        JarvisButton(text = "Download pausieren", onClick = { pauseDownload(open) })
                        JarvisButton(text = "Download abbrechen", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { cancelDownload(open) })
                    }
                    if (open.loadState == ModelLoadState.PAUSED) {
                        JarvisButton(text = "Download fortsetzen", onClick = { resumeDownload(open) })
                        JarvisButton(text = "Download abbrechen", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { cancelDownload(open) })
                    }
                    if (open.loadState == ModelLoadState.ERROR) {
                        JarvisButton(text = "Erneut versuchen", onClick = { retry(open) })
                    }
                    JarvisButton(text = "Löschen", variant = JarvisButtonVariant.DESTRUCTIVE, onClick = { deleteId = open.id })
                }
            }
        }
    }

    JarvisDialog(
        open = deleteTarget != null,
        onClose = { deleteId = null },
        title = "Modell löschen",
        description = deleteTarget?.let { "\"${it.name}\" wird im Demozustand aus dieser Beispielliste entfernt." },
        actions = {
            JarvisButton(text = "Abbrechen", onClick = { deleteId = null })
            JarvisButton(text = "Löschen", variant = JarvisButtonVariant.DESTRUCTIVE, modifier = Modifier.padding(start = JarvisSpacing.sm), onClick = ::deleteEntry)
        },
    )
}

@Composable
private fun JarvisDetailFieldTag(label: String, tag: @Composable () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
    ) {
        Text(text = label.uppercase(), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
        tag()
    }
}

@Composable
private fun DownloadProgressBar(progress: Int) {
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .width(96.dp)
                .height(6.dp)
                .clip(CircleShape)
                .background(JarvisSemanticColor.borderSoft),
        ) {
            Box(
                modifier = Modifier
                    .width((96 * (progress.coerceIn(0, 100) / 100f)).dp)
                    .height(6.dp)
                    .clip(CircleShape)
                    .background(JarvisSemanticColor.primary),
            )
        }
        Text(text = "$progress%", color = JarvisSemanticColor.subtleForeground, fontSize = 11.sp, modifier = Modifier.padding(start = JarvisSpacing.sm))
    }
}
