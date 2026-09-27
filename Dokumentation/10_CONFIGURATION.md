# Konfiguration

`config.yaml` ist die zentrale Runtime-Konfiguration; Secrets kommen über Environment. `.env` wird nicht dokumentiert oder weitergegeben.

## Aktuelle Kernschlüssel

| Gruppe | Bedeutung | aktueller Stand |
|---|---|---|
| `llm.primary.*` | Gemma 4 12B, Port 8080, Audio/Vision | aktiv |
| `llm.expert.*` | Qwen3.5-35B-A3B, Port 8082 | on-demand |
| `llm.small.*` | historischer Small-LLM-Pfad | `enabled: false` |
| `llm.api.*` | Cloud-Fallback | OpenRouter vorbereitet, `enabled: false`, `model: null` |
| `stt.*` | Qwen3-ASR | aktiv |
| `tts.*` | Chatterbox | aktiv |
| `turn.*` | Turn-Aggregation | aktiv, reale Pause/Wake-Abnahme offen |
| `handover.*` | Primary/Expert GPU-Handover | `enabled: false` |
| `vision.presence.*` | Presence/NPU/Vision-Gate | NPU-Backend noch nicht runtimebereit |
| `mobility.*` | lokale VVS-Integration | VVS Dienst READY |
| `web.port` | JARVIS Web API | 8091 vorgesehen |
| `self_evolution.auto_consult` | automatische externe Findings-Beratung | false |

## Direct-Audio

`llm.primary.audio_direct: true` ist Teil des aktuellen Designs. `llm.primary.audio_tools: none` trennt Direct-Audio von Tool-Schemas. Tool-/Skill-Turns werden über paralleles STT/Text-Routing behandelt.

## Cloud

```yaml
llm:
  api:
    enabled: false
    provider: openrouter
    model: null
    endpoint: https://openrouter.ai/api/v1/chat/completions
    api_key_env: OPENROUTER_API_KEY
```

Kein Provider darf aus fehlender Konfiguration stillschweigend zu Anthropic/Claude werden.

## Runtime Units

Primary- und Expert-Units werden über aktuelle Config/Runtime-Auflösung ermittelt. Legacy-Unitnamen bleiben nur Kompatibilität. Der Runtime-Snapshot ist für die UI maßgeblich, nicht das Vorhandensein einer Unit-Datei allein.
