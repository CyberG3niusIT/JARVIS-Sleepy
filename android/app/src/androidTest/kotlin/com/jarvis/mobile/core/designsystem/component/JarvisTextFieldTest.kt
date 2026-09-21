package com.jarvis.mobile.core.designsystem.component

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createComposeRule
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
