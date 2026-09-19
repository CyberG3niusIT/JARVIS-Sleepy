package com.jarvis.mobile.core.util

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Collision tests for the length-prefixed codec every `rememberSaveable`
 * string-encoded state (Automationen, Memory) is built on. A control-
 * character-separator scheme would silently corrupt fields whose content
 * happens to contain that separator; this codec must not, for any content.
 */
class StringFieldCodecTest {

    private fun roundTrip(vararg fields: String): List<String> {
        val writer = StringFieldCodec.writer()
        fields.forEach { writer.write(it) }
        val reader = StringFieldCodec.reader(writer.build())
        return fields.map { reader.read() }
    }

    @Test
    fun `round trips empty strings`() {
        assertEquals(listOf("", "", ""), roundTrip("", "", ""))
    }

    @Test
    fun `round trips a mix of empty and non-empty fields`() {
        val fields = arrayOf("", "value", "", "another value", "")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `round trips unicode including astral characters using surrogate pairs`() {
        val fields = arrayOf("Ä ö ü ß", "😀 emoji", "日本語のテキスト", "👍🏻")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `round trips newlines and tabs`() {
        val fields = arrayOf("line one\nline two", "a\tb\tc", "\n\n\n", "trailing newline\n")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `round trips arbitrary control characters`() {
        val fields = arrayOf("\u0000\u0001\u0002", "\u001F control", "null\u0000inside")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `round trips content matching the codec's own header syntax`() {
        // A field whose entire content looks like a valid length header
        // ("5:hello") must not be misread as one; the codec only treats the
        // literal header it wrote as structural, never a coincidental match
        // inside a field's own content.
        val fields = arrayOf("5:hello", "0:", "12:not a field", ":::::")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `round trips previous ad hoc separator characters used before this codec`() {
        val fields = arrayOf("\u0001\u0002\u0003\u0004\u0005", "a\u0001b\u0002c", "id-1\u0001Some label\u0002more")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `does not shift fields when content contains colons and digits`() {
        val fields = arrayOf("12:34:56", "field:with:colons", "100", "0", "-1")
        assertEquals(fields.toList(), roundTrip(*fields))
    }

    @Test
    fun `encodeStringList and decodeStringList round trip empty and populated lists`() {
        assertEquals(emptyList<String>(), StringFieldCodec.decodeStringList(StringFieldCodec.encodeStringList(emptyList())))

        val items = listOf("Standort", "Kalender", "", "line\nbreak", "5:hello")
        assertEquals(items, StringFieldCodec.decodeStringList(StringFieldCodec.encodeStringList(items)))
    }

    @Test
    fun `a list field embedded in an outer record does not collide with sibling fields`() {
        val listBlob = StringFieldCodec.encodeStringList(listOf("a", "b:c", "5:not-a-header"))
        val writer = StringFieldCodec.writer()
        writer.write("before")
        writer.write(listBlob)
        writer.write("after")
        val reader = StringFieldCodec.reader(writer.build())

        assertEquals("before", reader.read())
        assertEquals(listOf("a", "b:c", "5:not-a-header"), StringFieldCodec.decodeStringList(reader.read()))
        assertEquals("after", reader.read())
    }

    @Test
    fun `multiple sequential lists round trip independently`() {
        val steps = StringFieldCodec.encodeStringList(listOf("step-1", "Lautlos aktivieren", "step-2", "Wecker stellen"))
        val conditions = StringFieldCodec.encodeStringList(listOf("cond-1", "WLAN verbunden"))
        val writer = StringFieldCodec.writer()
        writer.write(steps)
        writer.write(conditions)
        val reader = StringFieldCodec.reader(writer.build())

        assertEquals(listOf("step-1", "Lautlos aktivieren", "step-2", "Wecker stellen"), StringFieldCodec.decodeStringList(reader.read()))
        assertEquals(listOf("cond-1", "WLAN verbunden"), StringFieldCodec.decodeStringList(reader.read()))
    }
}
