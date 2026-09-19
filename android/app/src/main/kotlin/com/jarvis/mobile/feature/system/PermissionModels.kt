package com.jarvis.mobile.feature.system

import com.jarvis.mobile.core.model.SystemState

/** Ported 1:1 from src/components/jarvis/screens/permissions-screen.tsx. */

enum class PermissionGrantState { NOT_REQUESTED, GRANTED, DENIED, DENIED_PERMANENTLY, REVOKED, NOT_APPLICABLE }

val permissionGrantLabel: Map<PermissionGrantState, String> = mapOf(
    PermissionGrantState.NOT_REQUESTED to "Nicht angefragt",
    PermissionGrantState.GRANTED to "Erteilt",
    PermissionGrantState.DENIED to "Abgelehnt",
    PermissionGrantState.DENIED_PERMANENTLY to "Dauerhaft abgelehnt",
    PermissionGrantState.REVOKED to "Widerrufen",
    PermissionGrantState.NOT_APPLICABLE to "Nicht zutreffend",
)

val permissionGrantTone: Map<PermissionGrantState, SystemState> = mapOf(
    PermissionGrantState.NOT_REQUESTED to SystemState.DESIGN_STATE,
    PermissionGrantState.GRANTED to SystemState.READY,
    PermissionGrantState.DENIED to SystemState.PERMISSION_REQUIRED,
    PermissionGrantState.DENIED_PERMANENTLY to SystemState.ERROR,
    PermissionGrantState.REVOKED to SystemState.OFFLINE,
    PermissionGrantState.NOT_APPLICABLE to SystemState.DESIGN_STATE,
)

val demoStateOrder: List<PermissionGrantState> = listOf(
    PermissionGrantState.NOT_REQUESTED,
    PermissionGrantState.GRANTED,
    PermissionGrantState.DENIED,
    PermissionGrantState.DENIED_PERMANENTLY,
    PermissionGrantState.REVOKED,
    PermissionGrantState.NOT_APPLICABLE,
)

data class PermissionGroup(
    val id: String,
    val title: String,
    val purpose: String,
    val whyNeeded: String,
    val capabilities: List<String>,
    val requirement: String = "Nicht festgelegt",
)

const val PERMISSION_UNBOUND_STATUS = "Status nicht gebunden"

val permissionGroups: List<PermissionGroup> = listOf(
    PermissionGroup(
        id = "accessibility",
        title = "Bedienungshilfen",
        purpose = "Generische App-Steuerung und Automation von Oberflächen.",
        whyNeeded = "Ermöglicht das Lesen und Bedienen sichtbarer Oberflächenelemente in anderen " +
            "Apps, damit Aktionen im Namen der Nutzerin oder des Nutzers ausgeführt werden können.",
        capabilities = listOf(
            "Oberflächenelemente in anderen Apps erkennen",
            "Tippen, Wischen und Texteingabe auslösen",
            "Automatisierte Bedienabläufe ausführen",
        ),
    ),
    PermissionGroup(
        id = "notifications",
        title = "Benachrichtigungen",
        purpose = "Mitlesen und Beantworten von Benachrichtigungen.",
        whyNeeded = "Erlaubt das Erfassen eingehender Benachrichtigungen und das Auslösen " +
            "passender Antworten oder Aktionen.",
        capabilities = listOf(
            "Benachrichtigungsinhalte lesen",
            "Schnellantworten aus Benachrichtigungen senden",
            "Benachrichtigungen wegwischen oder öffnen",
        ),
    ),
    PermissionGroup(
        id = "microphone",
        title = "Mikrofon",
        purpose = "Spracheingabe und lokale Spracherkennung.",
        whyNeeded = "Wird für gesprochene Anfragen und lokale Spracherkennung benötigt.",
        capabilities = listOf("Audio für Spracherkennung aufnehmen", "Sprachbefehle entgegennehmen"),
    ),
    PermissionGroup(
        id = "screen",
        title = "Bildschirmzugriff",
        purpose = "Analyse sichtbarer Inhalte auf dem Bildschirm.",
        whyNeeded = "Wird benötigt, um Anfragen zu beantworten, die sich auf den aktuell " +
            "sichtbaren Bildschirminhalt beziehen.",
        capabilities = listOf("Sichtbaren Bildschirminhalt auswerten", "Bildschirmkontext für Anfragen bereitstellen"),
    ),
    PermissionGroup(
        id = "camera",
        title = "Kamera",
        purpose = "Bildaufnahme für Anfragen, die ein Bild benötigen.",
        whyNeeded = "Wird für Anfragen benötigt, die ein aktuelles Kamerabild als Grundlage brauchen.",
        capabilities = listOf("Einzelbild aufnehmen", "Aufgenommenes Bild einer Anfrage zuordnen"),
    ),
    PermissionGroup(
        id = "files",
        title = "Dateien",
        purpose = "Lesen und Ablegen lokaler Dateien, etwa Modelldateien.",
        whyNeeded = "Wird benötigt, um lokale Dateien wie Modelldateien zu lesen und abzulegen.",
        capabilities = listOf("Lokale Dateien lesen", "Dateien im freigegebenen Bereich ablegen"),
    ),
    PermissionGroup(
        id = "contacts",
        title = "Kontakte / Kommunikation",
        purpose = "Aktionen rund um Kontakte und Nachrichten.",
        whyNeeded = "Wird für Aktionen benötigt, die einen Kontakt nachschlagen oder eine Nachricht auslösen.",
        capabilities = listOf("Kontakte nachschlagen", "Nachrichten über freigegebene Kanäle auslösen"),
    ),
    PermissionGroup(
        id = "location",
        title = "Standort",
        purpose = "Ortsbezogene Aktionen und Kontext.",
        whyNeeded = "Wird für Anfragen benötigt, die einen aktuellen oder ungefähren Standort als " +
            "Kontext brauchen.",
        capabilities = listOf("Aktuellen Standort als Kontext bereitstellen", "Ortsbezogene Aktionen ermöglichen"),
    ),
)
