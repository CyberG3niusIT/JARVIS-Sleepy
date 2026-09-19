package com.jarvis.mobile.feature.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.jarvis.mobile.core.designsystem.JarvisRadii
import com.jarvis.mobile.core.designsystem.JarvisSemanticColor
import com.jarvis.mobile.core.designsystem.JarvisSpacing

/**
 * Ported 1:1 from src/components/jarvis/chat-attachment.tsx (AttachmentThumb,
 * AttachmentDraftList, MessageAttachmentList). Real image preview via Coil,
 * reading the same content:// URI the system picker granted access to -
 * nothing is uploaded, extracted or analysed.
 */
@Composable
private fun AttachmentThumb(attachment: ChatAttachment, modifier: Modifier = Modifier) {
    if (attachment.kind == ChatAttachmentKind.IMAGE && attachment.previewUri != null) {
        AsyncImage(
            model = attachment.previewUri,
            contentDescription = "Vorschau: ${attachment.name}",
            contentScale = ContentScale.Crop,
            modifier = modifier
                .size(36.dp)
                .clip(RoundedCornerShape(JarvisRadii.xs))
                .border(1.dp, JarvisSemanticColor.borderSoft, RoundedCornerShape(JarvisRadii.xs)),
        )
    } else {
        Box(
            modifier = modifier
                .size(36.dp)
                .clip(RoundedCornerShape(JarvisRadii.xs))
                .border(1.dp, JarvisSemanticColor.borderSoft, RoundedCornerShape(JarvisRadii.xs)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Filled.Description, contentDescription = null, tint = JarvisSemanticColor.mutedForeground, modifier = Modifier.size(16.dp))
        }
    }
}

@Composable
fun ChatAttachmentDraftList(attachments: List<ChatAttachment>, onRemove: (String) -> Unit) {
    if (attachments.isEmpty()) return
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(androidx.compose.foundation.BorderStroke(0.5.dp, JarvisSemanticColor.borderSoft)),
    ) {
        attachments.forEach { a ->
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = JarvisSpacing.md, vertical = JarvisSpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AttachmentThumb(a)
                Column(modifier = Modifier.weight(1f).padding(start = JarvisSpacing.sm)) {
                    Text(text = a.name, color = JarvisSemanticColor.foreground, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(
                        text = "${attachmentKindLabel.getValue(a.kind)}, angehängt",
                        color = JarvisSemanticColor.mutedForeground,
                        fontSize = 11.sp,
                        modifier = Modifier.padding(top = 2.dp),
                    )
                }
                IconButton(onClick = { onRemove(a.id) }) {
                    Icon(Icons.Filled.Close, contentDescription = "Anhang entfernen: ${a.name}", tint = JarvisSemanticColor.mutedForeground)
                }
            }
        }
    }
}

@Composable
fun ChatMessageAttachmentList(attachments: List<ChatAttachment>, modifier: Modifier = Modifier) {
    if (attachments.isEmpty()) return
    Column(modifier = modifier.padding(top = JarvisSpacing.sm)) {
        attachments.forEach { a ->
            Row(modifier = Modifier.padding(top = JarvisSpacing.xs), verticalAlignment = Alignment.CenterVertically) {
                AttachmentThumb(a)
                Column(modifier = Modifier.weight(1f).padding(start = JarvisSpacing.sm)) {
                    Text(text = a.name, color = JarvisSemanticColor.foreground, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(text = attachmentKindLabel.getValue(a.kind), color = JarvisSemanticColor.mutedForeground, fontSize = 11.sp)
                }
            }
        }
    }
}
