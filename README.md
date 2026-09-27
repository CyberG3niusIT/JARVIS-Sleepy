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

Dieser Branch enthält den vollständigen technischen Stand aus dem lokalen J.A.R.V.I.S-Sleepy-Workspace zum **27.09.2026**.

Der Snapshot vereint Runtime und Backend aus `Main/`, den Desktop Control Hub aus `UI/`, die native Android-App aus `Mobile-App/` sowie die technische Dokumentation aus `Dokumentation/`. Lokale Git-Worktree-Verwaltung, Zugangsdaten, Runtime-Daten und Build-Ausgaben gehören nicht zum Repository-Inhalt.

`main` bleibt davon unabhängig.

Dieser Branch ist der technische Referenzpunkt vor dem nächsten UI-Expert-Umbau mit Lovable. Die vorhandenen UI-Dateien dokumentieren den Implementierungsstand, sind aber keine visuelle Source of Truth.

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

Der nächste Entwicklungsschritt ist der UI-Expert-Umbau des J.A.R.V.I.S Desktop Control Centers mit Lovable.

Die vorhandenen Desktop-, Web- und Mobile-Clients liegen im Snapshot unter `UI/`, `web/` und `Mobile-App/`. Er dokumentiert den technischen Implementierungsstand, ist aber **keine visuelle Source of Truth**.

Technische Source of Truth bleiben Backend-Schnittstellen, echte Runtime-Zustände, Privacy-Gates und nachweisbare Fähigkeiten.

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
| Technischer Stand aus den Projektquellen | **IMPORTED** |
| Technische Dokumentation | **IMPORTED, geprüft am 24.09.2026** |
| Zentrales `INHALTSVERZEICHNIS.md` | **IM WORKSPACE NICHT VORHANDEN** |
| Lovable Handoff | **FOLGT** |
| UI-Expert-Umbau mit Lovable | **NOCH NICHT BEGONNEN** |

Diese Tabelle beschreibt den übernommenen Datei- und Planungsstand. Sie ist keine Runtime-Telemetrie und bestätigt keinen Live-Betrieb.

---

## 08 // REPOSITORY INDEX

Die technische Dokumentation und ihre Navigation liegen in [Dokumentation/README.md](Dokumentation/README.md). Das Quellen- und Dateiinventar steht in [Dokumentation/INVENTORY.md](Dokumentation/INVENTORY.md).

Ein separates `INHALTSVERZEICHNIS.md` ist in den übernommenen Projektdateien nicht vorhanden.

---

## 09 // SNAPSHOT RULE

Dieser Branch hält den vollständigen lokalen Projektstand zum **27.09.2026** als technischen Referenzpunkt fest.

Die vorhandenen Desktop-, Web- und Mobile-Clients sind als Implementierungsstand enthalten. Für den kommenden UI-Expert-Umbau mit Lovable sind sie keine visuelle Source of Truth.

Der Zweck dieses Branches ist reproduzierbare Vergleichbarkeit:

```text
CURRENT J.A.R.V.I.S SYSTEM
            │
            ▼
SLEEPY WORKSPACE SNAPSHOT
            │
            ▼
LOVABLE UI EXPERT REBUILD
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
