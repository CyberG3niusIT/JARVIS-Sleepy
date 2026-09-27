# Voice, STT und TTS

## Aktueller Stack

- Wake: Aura
- STT: Qwen3-ASR
- PRIMARY: Gemma 4 12B Direct-Audio
- Expert: Qwen3.5-35B-A3B on-demand
- TTS: Chatterbox
- Audio-Ausgabe: Windows-Audio-Brücke

Der offizielle Runtime-Snapshot meldete Voice-Daemon, STT, Chatterbox und Audio-Bridge nach einem vollständigen Windows-Neustart als READY.

## Zielpfad

```text
Audio -> VAD -> Wake/Turn -> Gemma Direct-Audio -> Antwort -> Chatterbox
                  \
                   -> paralleles STT -> Skill/Tool/Text-Route, wenn nötig
```

Gemma erhält im Direct-Audio-Pfad aktuell keine Tool-Schemas (`llm.primary.audio_tools: none`). Damit wird ein real beobachtetes Qualitätsproblem vermieden, bei dem Direct-Audio mit vielen Tools unzuverlässig wurde.

## Turn-Aggregation

`core/turn_assembler.py` soll natürliche kurze Pausen über mehrere VAD-Segmente hinweg zu einem Turn verbinden. Nur ein tatsächlich als Stop erkannter Fast-Path darf die normale Grace umgehen.

### Reale Acceptance 26.09.2026: NICHT BESTANDEN

Bei natürlichem Sprechen wurde `Aura` nach kurzer Pause als vollständiger Wake-only-Turn behandelt. JARVIS begann bereits mit dem Minimal-Greeting, während der folgende Satz separat verarbeitet wurde. Damit war die gewünschte Segmentaggregation im realen Fall nicht korrekt.

## Watchdog/TTS

Im selben Test setzte der Watchdog Speaking-Flags zurück und öffnete Listening, obwohl Chatterbox noch lief. Das ist ein echter TTS-/Listener-State-Race und keine reine Latenzfrage.

## Speculative Direct-Audio

Ein speculative Turn wurde bei Wake-only verworfen, erzeugte aber `LLM streaming error: 'NoneType' object has no attribute 'read'`. Ein erwarteter Cancel darf nicht als ERROR enden. Außerdem lief nach Conversation-Timeout ein alter LLM-Retry weiter; Turn-Cleanup muss Retry/Fallback terminal unterbinden.

## Erfolgreiche Teilbeobachtung

Eine anschließend vollständig neu gesprochene Anfrage wurde transkribiert und von Gemma beantwortet; Chatterbox gab die Antwort aus. Das belegt einen funktionsfähigen Voice-Teilpfad, **nicht** die vollständige Direct-Audio-Abnahme, weil im vorhandenen Log kein eindeutiger `DIRECT_AUDIO_ACCEPTED`-Marker vorhanden war.

## Logging-Anforderung

Für jeden Voice-Turn sollen eindeutige Turn-IDs und explizite Pfadmarker existieren:

- `DIRECT_AUDIO_STARTED`
- `DIRECT_AUDIO_ACCEPTED`
- `DIRECT_AUDIO_REJECTED(reason)`
- `DIRECT_AUDIO_CANCELLED(reason)`
- `TEXT_PATH_SELECTED(reason)`

## NPU-Wake

NPU-Wake ist weiterhin nicht implementiert. Qwen3-ASR bleibt daher Teil des parallelen Wake-/Routingpfads.
