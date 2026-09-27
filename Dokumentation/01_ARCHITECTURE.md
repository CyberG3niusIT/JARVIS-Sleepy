# Architektur

## Systemgrenzen

Der aktuelle Backend-Worktree befindet sich in `Main`. Relevante Einstiegspunkte sind `jarvis_continuous.py`, `jarvis_console.py`, `jarvis_web.py` sowie der Windows-Runtime-Supervisor `JARVIS-Runtime.ps1` / `JARVIS.Runtime.psm1`. Core-Funktionalität liegt in `core/`, Skills in `skills/`, Dienste und Hilfsprozesse in `services/`, `tools/` und `systemd/`.

Desktop-UI und Mobile-App sind eigene Frontend-/Clientflächen. Sie dürfen Backendzustände nicht erfinden. Der Desktop-Neuaufbau verwendet Backend und Runtime-Supervisor als Source of Truth.

## Aktueller Voice- und Modellfluss

```text
Mikrofon
  -> VAD / Segmentierung
  -> Wake-Erkennung Aura
  -> Turn-Assembler
  -> parallele Pfade
       A) Direct-Audio -> Gemma 4 12B PRIMARY
       B) Qwen3-ASR -> Text/Intent/Skill/Tool-Verdict
  -> bei deterministischer Aufgabe: Skill / Tool / Textpfad
  -> bei normalem Dialog: Gemma-Antwort
  -> bei expliziter/harte Eskalation: Qwen3.5 EXPERT über GPU-Handover
  -> Chatterbox TTS
  -> Windows-Audio-Brücke / Ausgabe
```

Direct-Audio bietet dem Primary derzeit bewusst keine Tool-Schemas (`llm.primary.audio_tools: none`). Tool-/Skill-Aufgaben werden über den parallelen STT-/Textpfad geroutet. Das ist eine pragmatische Trennung, weil Gemma Direct-Audio mit vielen Tool-Schemas im realen Testpfad nicht zuverlässig genug war.

## Modellrollen

- **PRIMARY: Gemma 4 12B**, Port 8080, Audio + Vision via mmproj, normaler Dialog und multimodaler Hauptpfad.
- **EXPERT: Qwen3.5-35B-A3B**, Port 8082, nur bei gezielter Eskalation, GPU-exklusiv und on-demand.
- **STT: Qwen3-ASR**, parallele Transkription und Text-/Routingpfad.
- **TTS: Chatterbox**, eigener Prozess/Endpoint.

Gemma und Expert-Qwen sollen nicht gleichzeitig resident sein.

## Runtime-Kontrollpfad

```text
JARVIS Desktop / Operator
  -> JARVIS-Runtime.ps1
  -> JARVIS.Runtime.psm1
  -> WSL Ubuntu-24.04
  -> scripts/runtime_status.py / systemd user services
  -> RuntimeSnapshot
```

Der RuntimeSnapshot ist autoritativ für `STARTING`, `READY`, `DEGRADED`, `ERROR`, `STOPPED`, `OFFLINE` und `NOT_IMPLEMENTED` sowie Komponentenstatus und Lifecycle-Capabilities. Einzelne HTTP-Health-Probes dürfen diesen Gesamtzustand nicht ersetzen.

## Zentrale Bausteine

- `core/pipeline.py`: Voice-/Antwortkoordination und Turn-Lifecycle.
- `core/continuous_listener.py`: Audio-Ingest, VAD und Segmentierung.
- `core/turn_assembler.py`: natürliche Segmentaggregation.
- `core/direct_audio.py`, `core/speculative_turn.py`, `core/audio_turn_routing.py`: Direct-/Speculative-Audio und Routing.
- `core/llm_router.py`: Rollenauflösung, lokaler Modellzugriff, optionaler Cloud-Provider, Streaming/Cancel.
- `core/model_handover.py`, `core/expert_policy.py`: Expert-Eskalation und GPU-Handover.
- `core/conversation_router.py`: Skills, Tools und deterministische Routen.
- `core/memory_manager.py`, `core/context_window.py`: Langzeit-/Arbeitskontext.
- `core/privacy_gate.py`: Capability-Gates.
- `core/runtime_state.py`: Runtimezustände.

## Cloud

Cloud ist optional. Der lokale Normalpfad bleibt Source of Truth. Aktuell ist OpenRouter als bevorzugter Provider vorbereitet, aber deaktiviert und ohne Modell konfiguriert. Anthropic ist nur ein optionaler expliziter Provider; es gibt keinen impliziten Claude-Fallback mehr.

## Sensor-/NPU-Schicht

Die NPU ist Sensor-/Vorverarbeitungsschicht, kein zweites Sprachmodell. Vorgesehen sind Presence, Bewegungs-/Frame-Vorfilterung und später Wake-Signal-Unterstützung. Der Supervisor meldete den NPU-Sensor nach Reboot als `STOPPED`, weil das Backend noch nicht initialisiert war. NPU-Wake bleibt nicht implementiert.
