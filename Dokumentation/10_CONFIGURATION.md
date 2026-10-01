# Konfiguration

## Quellen

`config.yaml` ist die zentrale Beispiel-/Runtime-Konfiguration; Variablen werden über `${...}` und Prozessumgebung eingebunden. `.env.example` enthält Namen/Beispiele. Die lokale `.env` wurde nicht gelesen und darf nicht publiziert werden.

## Relevante Gruppen

| Gruppe | Zweck | Statushinweis |
|---|---|---|
| `system`, `audio`, `vad`, `wake_word` | Spracheingabe/-ausgabe | Geräte/Berechtigungen müssen live verfügbar sein |
| `llm.local`, `llm.small`, `llm.api` | lokale/Cloud-Modellzugriffe | Endpunkte/Modelle nicht live geprüft |
| `stt`, `tts` | ASR/TTS-Auswahl | Engine-Wert sagt nichts über Servergesundheit |
| `skills` | Discovery/Safe Mode | Plugin-Verfügbarkeit zusätzlich prüfen |
| `conversational_memory`, `context_window` | Memory-Verhalten | persistente Daten extern; nicht gelesen |
| `people`, `school`, `mobility`, `reminders` | Fachkomponenten | IDs/Daten/Secrets bleiben extern |
| `metrics`, `logging` | Telemetrie und Logs | konkrete Datenpfade nicht veröffentlicht |

## Umgebungsvariablen

Im Code/Beispiel finden sich Schlüssel für API-Provider, Wakeword, School-Zielzuordnungen sowie Mobility-URL/API-Key und Chatterbox-Parameter. Hier werden nur Variablennamen erwähnt, keine Werte. Die vollständige lokale Variablenliste kann aus `.env.example` sicher durch den Betreiber geprüft werden.

Änderungen an `config.yaml` sind am dokumentierten HEAD uncommittet. Vor Deployment muss die lokale tatsächliche Konfiguration mit den Beispielen abgeglichen werden.

## Neue Schlüssel (Stand 2026-09-25)

Alle Schlüssel liegen in `Main/config.yaml`. Zielarchitektur: Gemma PRIMARY, Qwen EXPERT (siehe `03_RUNTIME_AND_MODELS.md`).

| Schlüssel | Bedeutung |
|---|---|
| `llm.primary.*` | Gemma 4 12B: Endpoint (Port 8080), `model_path`, `mmproj_path`, `context_size`, `audio_direct`, `text_fallback` (Default aus), `health_ttl_s`, `ready_wait_s`. Modell-/mmproj-Dateinamen sind Platzhalter (NEEDS HW VERIFY). |
| `llm.expert.*` | Qwen3.5-35B-A3B, Endpoint Port 8082, nur per Handover geladen. |
| `llm.local.*` | Kompatibilitäts-Alias, zeigt auf den Primary-Endpoint. |
| `turn.*` | Turn-Aggregation: `enabled`, `grace_ms` (1200), `max_turn_s` (20), `max_segments` (8), `min_segment_ms`, `fast_stop_max_s` (1.6). |
| `stt.wake_compat` | STT als paralleler Wake-Helfer, bis NPU-Wake real ist. |
| `handover.*` | GPU-Handover: `enabled` (Default `false`), Unit-Namen Primary/Expert, Timeouts, VRAM-Wartezeit, Queue-Wartezeit. |
| `vision.presence.llm_gate.*` | NPU-Ereignis -> ein Frame an Primary: `enabled` (Default `false`), `cooldown_s` (120). |

Auflösung der Primary-Unit (identisch in `start.sh --llm-unit`-Aufruf, `scripts/check_runtime_dependencies.py` und `scripts/runtime_status.py`): `JARVIS_LLM_UNIT` > `llm.primary.unit` > `handover.units.primary` (auch bei `handover.enabled: false`) > nur als explizites Kompatibilitäts-Fallback die Legacy-Unit `llama-server.service`. Expert-Unit: `llm.expert.unit` > `handover.units.expert`. `start.sh` lässt eine bereits laufende Primary-Unit unangetastet und bricht ab, wenn die Expert-Unit aktiv ist (keine parallele Residency).
