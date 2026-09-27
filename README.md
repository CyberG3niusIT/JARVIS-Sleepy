<div align="center">

# J.A.R.V.I.S

### LOCAL AI SYSTEM

`SLEEPY`

<br>

**SYSTEM SNAPSHOT // 27.09.2026**

`PRE-UI EXPERT REBUILD · LOVABLE`

<br>

**Aktueller Stand vor UI-Expert-Umbau mit Lovable**

</div>

---

<table>
<tr>
<td><strong>BRANCH</strong></td>
<td><code>Sleepy-Aktuell-|-27.09</code></td>
</tr>
<tr>
<td><strong>ROLE</strong></td>
<td>Technischer Referenz-Snapshot</td>
</tr>
<tr>
<td><strong>BASELINE</strong></td>
<td>J.A.R.V.I.S Sleepy vor dem Desktop-UI-Neuaufbau</td>
</tr>
<tr>
<td><strong>ARCHITECTURE</strong></td>
<td>Local First</td>
</tr>
<tr>
<td><strong>SOURCE OF TRUTH</strong></td>
<td>Runtime → Repository → Tests → aktuelle Dokumentation</td>
</tr>
<tr>
<td><strong>UI STATUS</strong></td>
<td>Neuaufbau mit Lovable folgt nach vollständigem Snapshot</td>
</tr>
</table>

---

## 01 // SNAPSHOT

Dieser Branch ist der definierte technische Referenzpunkt für den **aktuellen J.A.R.V.I.S.-Stand unmittelbar vor dem UI-Expert-Umbau mit Lovable**.

Er soll den vollständigen realen Systemzustand dieses Zeitpunkts aufnehmen:

- Backend und Runtime
- Modelle und Inferenz
- Voice und Audio
- Memory und Kontext
- Tools, Skills und MCP
- Agenten und Orchestrierung
- Vision und Presence
- Privacy und Security
- Services und Recovery
- Tests und Dokumentation

`main` bleibt davon unabhängig.

Der Snapshot dient nicht als Experimentierfläche. Er ist die technische Baseline, gegen die der kommende Desktop-Neuaufbau geprüft werden kann.

---

## 02 // SYSTEM IDENTITY

> **J.A.R.V.I.S ist kein Chat-Frontend.**  
> J.A.R.V.I.S ist ein zusammenhängendes lokales Assistenzsystem mit Runtime, Modellen, Memory, Tools, Voice, Vision, Governance und eigener Desktop-Oberfläche.

Die Oberfläche darf das System sichtbar machen. Sie darf seinen Zustand nicht erfinden.

---

## 03 // CORE ARCHITECTURE

```text
                              J.A.R.V.I.S
                                  │
                         LOCAL FIRST RUNTIME
                                  │
             ┌────────────────────┴────────────────────┐
             │                                         │
          PRIMARY                                   EXPERT
       Gemma 4 12B                           Qwen3.5-35B-A3B
             │                                         │
      Conversation                               Escalation
      Direct Audio                               Deep Analysis
      Vision                                     Verification
             │                                         │
             └────────────────────┬────────────────────┘
                                  │
                              ORCHESTRATION
                                  │
        ┌───────────────┬─────────┼─────────┬───────────────┐
        │               │         │         │               │
      VOICE           MEMORY    TOOLS     VISION         SERVICES
        │               │         │         │               │
   Qwen3-ASR       Local Memory  Skills   Presence       Runtime
   Chatterbox      Retrieval     MCP      Camera          Recovery
```

### Model Roles

| Layer | Role |
|---|---|
| **Gemma 4 12B** | Primary |
| **Qwen3.5-35B-A3B** | Expert |
| **Qwen3-ASR** | Speech-to-Text |
| **Chatterbox** | Text-to-Speech |
| **Cloud** | Optionaler, explizit konfigurierter Fallback |

Cloud ist kein Ersatz für die lokale Kernarchitektur.

---

## 04 // OPERATING PRINCIPLES

### LOCAL FIRST

Kernfunktionen sollen lokal funktionieren. Externe Provider sind optionale Erweiterungen und keine Voraussetzung für den normalen Betrieb.

### BACKEND IS SOURCE OF TRUTH

Clients und Frontends dürfen keine Zustände, Telemetrie, Fähigkeiten oder Agentenaktivitäten erfinden.

Ein Zustand ist nur dann sichtbar, wenn das Backend ihn tatsächlich liefert.

### DETERMINISTIC BEFORE GENERATIVE

Eindeutige Aufgaben werden bevorzugt über Skills, Tools oder deterministische Runtime-Pfade gelöst.

LLM- und Agentenlogik kommt dort zum Einsatz, wo Flexibilität, Planung oder Mehrschrittlogik tatsächlich erforderlich ist.

### PRIVACY BY ARCHITECTURE

Privacy ist eine technische Systemgrenze.

Mic, STT, Vision, Memory, Cloud, Tools und Logging müssen durch reale Datenflüsse, Gates und Zuständigkeiten abgesichert sein.

### OBSERVABLE AND RECOVERABLE

Runtime, Services und Modelle müssen ihren tatsächlichen Zustand nachvollziehbar melden.

`READY`, `DEGRADED`, `ERROR`, `OFFLINE`, `STOPPED`, `NOT IMPLEMENTED` und `UNAVAILABLE` dürfen nicht durch UI-Annahmen ersetzt werden.

---

## 05 // DESKTOP REBUILD

Der nächste große Entwicklungsschritt ist der **vollständige Neuaufbau des J.A.R.V.I.S Desktop Control Centers mit Lovable**.

Die bisherige Desktop- und Web-Oberfläche ist dabei **keine visuelle Source of Truth**.

Erhalten bleiben:

- reale Backend-Schnittstellen
- Runtime-Zustände
- Privacy-Gates
- Modellrollen
- Tool- und Skill-Zuständigkeiten
- Memory- und Voice-Pfade
- Recovery- und Fehlerzustände
- technische Dokumentation

Neu aufgebaut wird die visuelle und interaktive Ebene.

### Geplante Hauptbereiche

```text
HOME
CHAT
MEMORY
MODELS & RUNTIME
VOICE & AUDIO
TOOLS & INTEGRATIONS
AUTOMATIONS
VISION & PRESENCE
MOBILITY
OBSERVABILITY
SETTINGS
```

Ziel ist eine professionelle Desktop-Anwendung für Systemsteuerung, AI Runtime Management, Observability und lokale Assistenz.

Keine generische Chat-App.
Kein Sci-Fi-HUD.
Kein Marketing-Mockup.
Keine Fake-Telemetrie.

---

## 06 // MEMORY & THINKING

Die neue Oberfläche erhält eine zentrale **Memory & Thinking**-Visualisierung.

Das visuelle Motiv ist ein räumliches Gehirn mit aktiven Synapsen und neuronalen Signalwegen.

Es visualisiert ausschließlich technisch beobachtbare Systemvorgänge, zum Beispiel:

```text
MEMORY RETRIEVAL
CONTEXT ASSEMBLY
ROUTING
TOOL SELECTION
MODEL ACTIVITY
RESPONSE GENERATION
```

Nicht dargestellt werden:

- erfundene Chain-of-Thought-Inhalte
- simulierte Gedanken
- Fake-Agentenaktivität
- nicht vorhandene Telemetrie
- frei erfundene Modellzustände

Die Visualisierung erklärt Systemaktivität. Sie behauptet keine internen Gedankeninhalte.

---

## 07 // SNAPSHOT STATE

| Bereich | Status |
|---|---|
| README / Snapshot Identity | **PREPARED** |
| Vollständiger technischer Stand | **PENDING IMPORT** |
| Zentrales Repository-Inhaltsverzeichnis | **FOLGT MIT SNAPSHOT** |
| Dokumentationssatz | **FOLGT MIT SNAPSHOT** |
| Lovable Handoff | **AFTER SNAPSHOT** |
| Desktop UI Rebuild | **NOT STARTED IN THIS BRANCH** |

Diese Tabelle beschreibt ausschließlich den Stand dieses Snapshot-Branches. Sie ist keine Runtime-Telemetrie.

---

## 08 // REPOSITORY INDEX

Der vollständige Snapshot übernimmt zusätzlich das zentrale Repository-Inhaltsverzeichnis:

`INHALTSVERZEICHNIS.md`

Es wird als technischer Navigationspunkt für Quellcode, Runtime, Tests, Dokumentation und Betrieb verwendet.

Der Link wird erst gesetzt, sobald die Datei tatsächlich in diesem Branch vorhanden ist.

---

## 09 // SNAPSHOT RULE

Dieser Branch bleibt als **Referenzzustand vor dem Lovable-Umbau** erhalten.

Änderungen, die ausschließlich zum neuen Desktop-UI-Design gehören, werden nicht rückwirkend als Bestandteil dieser Baseline behandelt.

Der Zweck dieses Branches ist reproduzierbare Vergleichbarkeit:

```text
CURRENT J.A.R.V.I.S SYSTEM
            │
            ▼
PRE-LOVABLE SNAPSHOT
            │
            ▼
DESKTOP UI REBUILD
            │
            ▼
POST-REBUILD VERIFICATION
```

---

<div align="center">

### J.A.R.V.I.S

`LOCAL FIRST · BACKEND IS SOURCE OF TRUTH`

**SLEEPY**

</div>
