package com.jarvis.mobile.core.util

/**
 * Length-prefixed string field encoding, used everywhere a data class needs
 * to survive in a `rememberSaveable` `Saver<_, String>` (a plain `String` is
 * unconditionally Bundle-safe; a nested `List<List<Any>>` is not).
 *
 * Each field is written as `<code-unit-length>:<content>`. Decoding never
 * splits on a delimiter character search through the payload: it reads the
 * digit run up to the next literal `:` as a length, then blindly consumes
 * exactly that many UTF-16 code units as the field's content, whatever they
 * are. This makes the encoding provably collision-free - a field's content
 * can contain empty strings, unicode (including astral characters using
 * surrogate pairs; `String.length`/`substring` both operate on the same
 * UTF-16 code-unit index space, so they stay consistent), newlines, control
 * characters, digits or colons, without ever being misread as a boundary.
 *
 * [StringFieldWriter]/[StringFieldReader] additionally support nested,
 * variable-length lists (see [encodeStringList]/[decodeStringList]): a list
 * is itself encoded as one opaque field value (its size, then its items),
 * so it can be embedded as a single field in an outer record without any
 * risk of colliding with the outer record's own fields.
 */
object StringFieldCodec {

    fun writer(): StringFieldWriter = StringFieldWriter()

    fun reader(raw: String): StringFieldReader = StringFieldReader(raw)

    /** Encodes a variable-length list of strings as one opaque field value. */
    fun encodeStringList(items: List<String>): String {
        val writer = writer()
        writer.write(items.size.toString())
        items.forEach { writer.write(it) }
        return writer.build()
    }

    /** Decodes a field value previously produced by [encodeStringList]. */
    fun decodeStringList(raw: String): List<String> {
        val reader = reader(raw)
        val size = reader.read().toInt()
        return List(size) { reader.read() }
    }
}

class StringFieldWriter internal constructor() {
    private val builder = StringBuilder()

    fun write(value: String): StringFieldWriter {
        builder.append(value.length).append(':').append(value)
        return this
    }

    fun build(): String = builder.toString()
}

class StringFieldReader internal constructor(private val raw: String) {
    private var position = 0

    /**
     * Reads the next length-prefixed field. Throws [IllegalArgumentException]
     * if [raw] is truncated or malformed - this only happens for data this
     * codec did not itself produce, which never occurs for a `Saver` reading
     * back its own previously saved value.
     */
    fun read(): String {
        val colon = raw.indexOf(':', position)
        require(colon >= 0) { "Malformed field header at position $position in \"$raw\"." }
        val length = raw.substring(position, colon).toInt()
        val start = colon + 1
        val end = start + length
        require(end <= raw.length) { "Field length $length at position $position exceeds remaining input." }
        position = end
        return raw.substring(start, end)
    }
}
