package com.jarvis.mobile.core.designsystem.component

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.performTextReplacement
import com.jarvis.mobile.core.designsystem.JarvisTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class JarvisTextFieldTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun emptyFieldStaysCompactInsideWeightedChatLayout() {
        composeRule.setContent {
            JarvisTheme {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("screen"),
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                    )
                    Row(modifier = Modifier.fillMaxWidth()) {
                        JarvisTextField(
                            value = "",
                            onValueChange = {},
                            modifier = Modifier.weight(1f),
                            minLines = 1,
                            maxLines = 5,
                            accessibilityLabel = "Nachricht",
                        )
                    }
                }
            }
        }

        val screenHeight = composeRule.onNodeWithTag("screen").fetchSemanticsNode().boundsInRoot.height
        val fieldHeight = composeRule.onNodeWithContentDescription("Nachricht").fetchSemanticsNode().boundsInRoot.height

        assertTrue("Leeres Chatfeld darf nicht den verfügbaren Screen füllen", fieldHeight < screenHeight / 4f)
    }

    @Test
    fun multilineFieldGrowsUntilFiveLinesThenKeepsItsHeight() {
        composeRule.setContent {
            JarvisTheme {
                var text by remember { mutableStateOf("") }
                JarvisTextField(
                    value = text,
                    onValueChange = { text = it },
                    minLines = 1,
                    maxLines = 5,
                    accessibilityLabel = "Nachricht",
                )
            }
        }

        val field = composeRule.onNodeWithContentDescription("Nachricht")
        val oneLineHeight = field.fetchSemanticsNode().boundsInRoot.height

        field.performTextReplacement("1\n2\n3\n4\n5")
        composeRule.waitForIdle()
        val fiveLineHeight = field.fetchSemanticsNode().boundsInRoot.height

        field.performTextReplacement("1\n2\n3\n4\n5\n6")
        composeRule.waitForIdle()
        val sixLineHeight = field.fetchSemanticsNode().boundsInRoot.height

        assertTrue(fiveLineHeight > oneLineHeight)
        assertEquals(fiveLineHeight, sixLineHeight, 1f)
    }
}
