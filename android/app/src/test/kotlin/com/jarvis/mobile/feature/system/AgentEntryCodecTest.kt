package com.jarvis.mobile.feature.system

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Round-trip tests for the string codec backing [AgentsScreen]'s
 * `rememberSaveable` demo agent, edited via cancel/retry/fail-demo.
 */
class AgentEntryCodecTest {

    @Test
    fun `round trips the seed demo agent unchanged`() {
        assertEquals(demoAgent, decodeAgentEntry(encodeAgentEntry(demoAgent)))
    }

    @Test
    fun `round trips every taskState the demo actions can reach`() {
        AgentTaskState.entries.forEach { taskState ->
            val entry = demoAgent.copy(taskState = taskState, errorReason = if (taskState == AgentTaskState.FAILED) "Zeitlimit erreicht" else null)
            assertEquals(entry, decodeAgentEntry(encodeAgentEntry(entry)))
        }
    }

    @Test
    fun `round trips an entry with every optional field null and empty lists`() {
        val entry = demoAgent.copy(
            currentTask = null,
            maxSteps = null,
            currentStep = null,
            timeoutSeconds = null,
            approvedContext = emptyList(),
            expectedResult = null,
            lastResult = null,
            errorReason = null,
            toolActivity = emptyList(),
            startedAt = null,
            updatedAt = null,
        )

        assertEquals(entry, decodeAgentEntry(encodeAgentEntry(entry)))
    }

    @Test
    fun `round trips fields containing separator-like and unicode content`() {
        val entry = demoAgent.copy(
            name = "5:hello \u0001 😀",
            purpose = "Zeile eins\nZeile zwei",
            allowedTools = listOf("Tool\u0001Eins", "0:Tool Zwei"),
            toolActivity = listOf(ToolActivityEntry("Tool:Eins", "Ergebnis\u0002mit Steuerzeichen")),
            lastResult = "",
        )

        assertEquals(entry, decodeAgentEntry(encodeAgentEntry(entry)))
    }
}
