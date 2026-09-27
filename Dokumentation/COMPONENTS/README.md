# Komponentenregister

Stand 27.09.2026. `implemented` bedeutet Codepfad, `live` bedeutet beobachtete Runtime, `partial` bedeutet offene Integration/Abnahme.

| Bereich | Status | Evidenz / Grenze |
|---|---|---|
| Runtime Supervisor | implemented / live | READY-Snapshot nach Reboot |
| Continuous Voice | partial / live | läuft; Acceptance-Fehler offen |
| Gemma Primary | partial / live | Service READY, Dialogantwort live |
| Qwen Expert | partial | on-demand, Handover disabled |
| Qwen3-ASR | live | reale STT-Ausgabe |
| Chatterbox | live / partial | Ausgabe live; Watchdog/TTS-State offen |
| ConversationRouter | implemented | deterministische Routen |
| TaskPlanner | implemented | Mehrschrittpfad |
| MemoryManager / ContextWindow | implemented | Daten extern |
| SkillManager / Tools | implemented | Einzelabhängigkeiten separat |
| MCPBridge | partial | Runtime-Server configabhängig |
| ObservationCollector | implemented | Auto-Consult false |
| VVS | live | Dienst READY |
| School/Mobility | partial | Fach-E2E offen |
| NPU | partial | Runtime nicht initialisiert |
| Web API | partial | Supervisor NOT_IMPLEMENTED |
| Desktop UI | redesign | Neuaufbau |
| Android | separates Projekt | nicht Desktop-Scope |

Siehe [Entrypoints](ENTRYPOINTS.md), [Storage](STORAGE.md), [Observation/Privacy](OBSERVATION_AND_PRIVACY.md).
