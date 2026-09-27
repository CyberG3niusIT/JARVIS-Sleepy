# Runtime und Modelle

## Offizieller Runtimepfad

Der aktuelle Windows-/WSL-Betrieb wird über folgende Kette geführt:

```text
JARVIS-Runtime.ps1
  -> JARVIS.Runtime.psm1
  -> WSL Ubuntu-24.04
  -> Runtime-Probes / systemd user services
```

Nach einem vollständigen Windows-Neustart meldete der Supervisor am 26.09.2026 `READY` ohne Degraded-Gründe. Das belegt den aktuellen Betriebszustand, nicht automatisch den konkreten Autostartmechanismus.

## Komponenten und Ports

| Rolle | Komponente | Port | Runtimebefund |
|---|---|---:|---|
| PRIMARY | Gemma 4 12B + mmproj | 8080 | READY |
| EXPERT | Qwen3.5-35B-A3B | 8082 | STOPPED / on-demand |
| STT | Qwen3-ASR | intern | READY |
| TTS | Chatterbox | 8765 | READY |
| VVS | WIMAEDV VVS API | 8088 | READY |
| FLUX | Bildgenerierung | 8190 | STOPPED / on-demand |
| NPU Sensor | Presence | - | STOPPED, Backend nicht initialisiert |
| Web | JARVIS Web API | 8091 vorgesehen | NOT_IMPLEMENTED im Supervisor |

`llm-main` bleibt als Alias auf `llm-primary` bestehen.

## PRIMARY: Gemma 4 12B

Gemma ist das Standardmodell für normalen Dialog sowie Direct-Audio und Vision. Der Primary läuft über llama.cpp mit mmproj auf Port 8080. Der reale Runtime-Snapshot meldete den Dienst als READY. In einem späteren Voice-Test antwortete Gemma auf eine vollständig gesprochene Anfrage. Der konkrete erfolgreiche Direct-Audio-Pfad war im vorhandenen Log jedoch nicht eindeutig markiert; deshalb bleibt Direct-Audio als Acceptance-Punkt offen.

Gemma-Direct-Audio erhält aktuell **keine Tools** (`llm.primary.audio_tools: none`). Der parallele STT-/Textpfad entscheidet, ob eine Skill-/Toolroute benötigt wird.

## EXPERT: Qwen3.5-35B-A3B

Qwen ist kein zweites Standardmodell, sondern Expert-Fallback für explizite oder harte Eskalation. Er wird GPU-exklusiv geladen. `handover.enabled` bleibt derzeit false, bis echter Hardware-Handover inklusive Recovery erneut akzeptiert ist. Der Runtime-Snapshot zeigt den Expert-Dienst korrekt als `STOPPED` / on-demand.

Historisch wurde eine Ladezeit um 90-100 Sekunden gemessen. Dieser Wert ist nicht als aktueller Benchmark zu behandeln, solange keine neue Messung erfolgt.

## Cloud

Aktuell eingecheckte Konfiguration:

```yaml
llm:
  api:
    enabled: false
    provider: openrouter
    model: null
    endpoint: https://openrouter.ai/api/v1/chat/completions
    api_key_env: OPENROUTER_API_KEY
```

Damit ist Cloud-Fallback aktuell dormant. Der Router hat keinen impliziten Anthropic- oder Claude-Default mehr. Anthropic bleibt nur als optionaler Provider erreichbar, wenn `provider: anthropic`, Cloud enabled, Modell/Credential vorhanden und `PrivacyGate(CLOUD_LLM)` erlaubt.

`self_evolution.auto_consult` ist false.

## Small LLM

Der frühere Small-LLM-Pfad auf 8081 ist in der aktuellen Config deaktiviert. Ein fehlender Small-LLM-Dienst darf den Runtime-Gesamtzustand nicht degradieren.

## GPU-Handover

Zielablauf:

1. Primary stoppen und GPU freigeben.
2. Expert starten und Health abwarten.
3. Expert-Anfrage ausführen.
4. Expert stoppen.
5. Primary wiederherstellen.

Der Handover bleibt deaktiviert, bis Lifecycle, Eigentümerprüfung, Timeouts, Restart/Recovery und echte Hardware-Abnahme belastbar sind.

## NPU

Die NPU ist Sensor- und Vorverarbeitungsschicht. Presence-/Face-Pfade und ein OpenVINO-Worker existieren. Im Supervisor war `npu-sensor` nach Reboot `STOPPED` mit `backend not initialised`. NPU-Wake-Word ist weiterhin nicht implementiert.

## Web und VVS

Die alte Portkollision 8088 ist im aktuellen Configstand aufgelöst: VVS nutzt 8088, die JARVIS-Web-API ist für 8091 vorgesehen. Trotzdem ist Web im aktuellen Runtime-Supervisor noch `NOT_IMPLEMENTED`, d. h. der Supervisor startet oder bewertet diesen Dienst noch nicht autoritativ.
