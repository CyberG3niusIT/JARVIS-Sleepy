package com.jarvis.mobile.feature.more

import com.jarvis.mobile.core.model.ExecutionLocation
import com.jarvis.mobile.core.model.PrivacyMode
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Round-trip tests for the string codec that backs every `rememberSaveable`
 * in the Automationen feature (draft, list, editor session). A codec bug
 * here would silently corrupt or drop local automation state across
 * activity recreation - exactly the class of bug this codec exists to fix.
 */
class AutomationDraftCodecTest {

    @Test
    fun `round trip preserves an empty macro draft`() {
        val draft = createEmptyDraft(AutomationType.MACRO)

        val restored = decodeAutomationDraft(encodeAutomationDraft(draft))

        assertEquals(draft, restored)
    }

    @Test
    fun `round trip preserves steps, permissions and enabled flag`() {
        val draft = createEmptyDraft(AutomationType.MACRO).copy(
            name = "Nachtmodus",
            purpose = "Handy nachts stumm schalten",
            enabled = true,
            runtime = ExecutionLocation.SLEEPY,
            privacy = PrivacyMode.PRIVACY_LOCK,
            permissions = listOf("Standort", "Kalender"),
            steps = listOf(
                AutomationStep("step-1", "Lautlos aktivieren"),
                AutomationStep("step-2", "Bildschirm dimmen"),
            ),
        )

        val restored = decodeAutomationDraft(encodeAutomationDraft(draft))

        assertEquals(draft, restored)
    }

    @Test
    fun `round trip preserves routine conditions and logic`() {
        val draft = createEmptyDraft(AutomationType.ROUTINE).copy(
            conditionLogic = ConditionLogic.ODER,
            conditions = listOf(
                AutomationCondition("cond-1", "WLAN verbunden"),
                AutomationCondition("cond-2", "Nach 22 Uhr"),
            ),
        )

        val restored = decodeAutomationDraft(encodeAutomationDraft(draft))

        assertEquals(draft, restored)
    }

    @Test
    fun `round trip preserves schedule fields`() {
        val draft = createEmptyDraft(AutomationType.SCHEDULE).copy(
            scheduleMode = ScheduleMode.INTERVAL,
            scheduleInterval = "2 Stunden",
            scheduleDateTime = "2026-01-01 08:00",
        )

        val restored = decodeAutomationDraft(encodeAutomationDraft(draft))

        assertEquals(draft, restored)
    }

    @Test
    fun `automations list round trips through the shared list separator`() {
        val drafts = listOf(
            createEmptyDraft(AutomationType.MACRO).copy(name = "Erste"),
            createEmptyDraft(AutomationType.SCHEDULE).copy(name = "Zweite", scheduleInterval = "1 Tag"),
        )

        val encoded = drafts.joinToString(AUTOMATION_DRAFT_LIST_SEP) { encodeAutomationDraft(it) }
        val restored = encoded.split(AUTOMATION_DRAFT_LIST_SEP).map { decodeAutomationDraft(it) }

        assertEquals(drafts, restored)
    }

    @Test
    fun `empty automations list encodes to an empty string`() {
        val drafts = emptyList<AutomationDraft>()

        val encoded = drafts.joinToString(AUTOMATION_DRAFT_LIST_SEP) { encodeAutomationDraft(it) }

        assertEquals("", encoded)
    }
}
