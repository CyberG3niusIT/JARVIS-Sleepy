# Entrypoints, Dienste und Audio-Grenzen

## Entrypoints

- `jarvis_continuous.py`: Voice-/Event-Runtime
- `jarvis_console.py`: Text-/Operatorpfad
- `jarvis_web.py`: Web/API-Pfad
- `JARVIS-Runtime.ps1` / `JARVIS.Runtime.psm1`: autoritative Windows-Runtime-Steuerung

## Audio

Continuous Voice bindet VAD, Wake, TurnAssembler, Direct-Audio, Qwen3-ASR, Gemma und Chatterbox. Die Windows-Audio-Brücke wurde im Runtime-Snapshot als READY gemeldet.

## Ports

- 8080 Gemma Primary
- 8082 Qwen Expert
- 8088 VVS
- 8091 JARVIS Web vorgesehen
- 8190 FLUX on-demand
- 8765 Chatterbox

Die frühere Web/VVS-Kollision auf 8088 ist im aktuellen Configstand aufgelöst. Web bleibt im Supervisor noch NOT_IMPLEMENTED.
