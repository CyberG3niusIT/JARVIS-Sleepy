# Komponenten

Status bezeichnet Implementierungs-/Abnahmestand, nicht Marketing-Reife.

| Komponente | Status | Aktuelle Grenze |
|---|---|---|
| Runtime Supervisor | implemented / live | READY-Snapshot nach Reboot belegt |
| Continuous Voice | partial / live | läuft, aber erster Voice-Acceptance-Test nicht bestanden |
| Gemma Primary | partial / live | Service READY; Dialogantwort live; Direct-Audio-End-to-End noch nicht sauber abgenommen |
| Qwen Expert | partial | Service on-demand; Handover aktuell deaktiviert |
| Qwen3-ASR | live | reale Transkriptionen im Voice-Test |
| Chatterbox TTS | live / partial | reale Ausgabe; Watchdog/TTS-State-Race offen |
| TurnAssembler / Speculative Audio | partial | Code/Test vorhanden; reale Pause/Wake-Cases noch fehlerhaft |
| ConversationRouter | implemented | deterministische Route vor generativem Pfad |
| SkillManager / Skills | implemented | externe Abhängigkeiten pro Skill separat |
| ToolRegistry / ToolExecutor | implemented | Tool-Gates und Runtime-Abhängigkeiten beachten |
| MCPBridge | partial | Client vorhanden; konkrete Runtime-Server configabhängig |
| MemoryManager / ContextWindow | implemented / runtimeabhängig | persistente Daten extern; Livewerte nicht allgemeingültig dokumentieren |
| PrivacyGate | implemented / partial coverage | konkrete Gates vorhanden; prozessübergreifende Coverage weiter auditieren |
| ObservationCollector | implemented | `auto_consult` aktuell false; kein automatischer Cloudversand |
| VVS | live service / partial feature | Supervisor READY; School/Mobility-Fachabnahme separat |
| NPU Presence | partial | Sensorpfad vorhanden, Runtime nicht initialisiert |
| FLUX | optional / on-demand | Supervisor STOPPED, erwartungsgemäß |
| Web API | partial | Code vorhanden; im Runtime-Supervisor noch NOT_IMPLEMENTED |
| Desktop UI | redesign | bisherige visuelle Implementierung wird ersetzt |
| Android | separates Projekt | außerhalb des Desktop-Redesign-Scopes |

`implemented` bedeutet Codepfad vorhanden. `live` bedeutet in der dokumentierten Umgebung tatsächlich beobachtet. `partial` bedeutet, dass Integrations-, Hardware- oder Acceptance-Grenzen offen sind.
