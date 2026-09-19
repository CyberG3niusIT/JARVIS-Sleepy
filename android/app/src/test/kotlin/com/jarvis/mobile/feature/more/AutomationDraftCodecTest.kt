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
    fun `automations list round trips through the shared codec`() {
        val drafts = listOf(
            createEmptyDraft(AutomationType.MACRO).copy(name = "Erste"),
            createEmptyDraft(AutomationType.SCHEDULE).copy(name = "Zweite", scheduleInterval = "1 Tag"),
        )

        val restored = decodeAutomationDraftList(encodeAutomationDraftList(drafts))

        assertEquals(drafts, restored)
    }

    @Test
    fun `empty automations list round trips`() {
        assertEquals(emptyList<AutomationDraft>(), decodeAutomationDraftList(encodeAutomationDraftList(emptyList())))
    }

    @Test
    fun `draft fields containing the previous ad hoc separator characters do not corrupt the round trip`() {
        val draft = createEmptyDraft(AutomationType.MACRO).copy(
            name = "a\u0001b\u0002c\u0003d",
            purpose = "\u0004\u0005 gemischt",
            steps = listOf(AutomationStep("step\u0001-1", "Label\u0002mit\u0003Steuerzeichen")),
        )

        assertEquals(draft, decodeAutomationDraft(encodeAutomationDraft(draft)))
    }

    @Test
    fun `draft fields containing unicode, newlines and colon-digit content do not shift fields`() {
        val draft = createEmptyDraft(AutomationType.ROUTINE).copy(
            name = "Nächte 😀 日本語",
            purpose = "Zeile eins\nZeile zwei\tmit Tab",
            scheduleDateTime = "12:34:56",
            conditions = listOf(AutomationCondition("cond-1", "5:hello 0: 12:not-a-header")),
        )

        assertEquals(draft, decodeAutomationDraft(encodeAutomationDraft(draft)))
    }

    @Test
    fun `empty string fields round trip without collapsing steps or conditions`() {
        val draft = createEmptyDraft(AutomationType.ROUTINE).copy(
            name = "",
            purpose = "",
            scheduleDateTime = "",
            scheduleInterval = "",
            permissions = listOf("", "Standort", ""),
            steps = listOf(AutomationStep("", ""), AutomationStep("step-2", "Zweiter Schritt")),
            conditions = listOf(AutomationCondition("", "")),
        )

        assertEquals(draft, decodeAutomationDraft(encodeAutomationDraft(draft)))
    }

    @Test
    fun `a list containing drafts whose fields embed encoded-list-like content does not collide with sibling drafts`() {
        val drafts = listOf(
            createEmptyDraft(AutomationType.MACRO).copy(name = "5:hello", purpose = "0:"),
            createEmptyDraft(AutomationType.SCHEDULE).copy(name = "Zweite", scheduleInterval = "1 Tag"),
        )

        assertEquals(drafts, decodeAutomationDraftList(encodeAutomationDraftList(drafts)))
    }

    @Test
    fun `closed step and condition sheets round trip as null`() {
        assertEquals(null, decodeStepSheet(encodeStepSheet(null)))
        assertEquals(null, decodeConditionSheet(encodeConditionSheet(null)))
    }

    @Test
    fun `new step and condition sheet inputs round trip arbitrary strings`() {
        val step = StepSheetState(null, "5:hello\n😀\u0001")
        val condition = ConditionSheetState(null, "12:not-a-header\t日本語\u0002")

        assertEquals(step, decodeStepSheet(encodeStepSheet(step)))
        assertEquals(condition, decodeConditionSheet(encodeConditionSheet(condition)))
    }

    @Test
    fun `sheet codecs distinguish a null id from an empty id`() {
        val newStep = StepSheetState(null, "")
        val existingStep = StepSheetState("", "")
        val newCondition = ConditionSheetState(null, "")
        val existingCondition = ConditionSheetState("", "")

        assertEquals(newStep, decodeStepSheet(encodeStepSheet(newStep)))
        assertEquals(existingStep, decodeStepSheet(encodeStepSheet(existingStep)))
        assertEquals(newCondition, decodeConditionSheet(encodeConditionSheet(newCondition)))
        assertEquals(existingCondition, decodeConditionSheet(encodeConditionSheet(existingCondition)))
    }
}
