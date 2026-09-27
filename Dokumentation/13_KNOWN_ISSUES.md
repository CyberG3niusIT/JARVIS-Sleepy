# Bekannte Probleme und Widersprüche

## P0 / vor weiterer Voice-Freigabe

1. **Turn-Aggregation / Wake-only:** `Aura` kann bei natürlicher Pause zu früh als vollständiger Turn abgeschlossen werden.
2. **Watchdog während TTS:** reale Abnahme zeigte Reset der Speaking-Flags, obwohl Chatterbox noch lief.
3. **Speculative Cancel:** Cancel kann als `NoneType ... read`-ERROR enden.
4. **Orphaned Retry:** nach Conversation-Timeout kann ein alter LLM-Retry weiterlaufen. Cleanup muss Retry/Fallback terminal verhindern.
5. **Pfadbeweis:** Logs müssen Direct-Audio/Textpfad pro Turn eindeutig markieren.

## Cloud / Provider

- Impliziter Anthropic-/Claude-Default wurde entfernt.
- OpenRouter ist vorbereitet, aber aktuell deaktiviert und ohne Modell.
- Eine Policy-Inkonsistenz wurde beim Review gefunden: alle automatischen Primary-Text-Cloud-Callsites müssen zentral `llm.primary.text_fallback` respektieren. Vor Aktivierung von OpenRouter erneut prüfen.
- Anthropic bleibt optional; die Provider-spezifischen Imports sind zulässig, solange sie nur hinter expliziter `provider: anthropic`-Konfiguration erreichbar sind.

## Expert / GPU

- Handover aktuell disabled.
- echter Primary->Expert->Primary-Hardware-Acceptance-Test offen.
- frühere Ladezeitmessung ~90-100 s ist kein aktueller Benchmark.

## NPU

- Supervisor meldet NPU-Sensor STOPPED, Backend nicht initialisiert.
- NPU-Wake weiterhin NOT_IMPLEMENTED.
- Live-Presence/Frame-Pipeline und Privacy müssen end-to-end abgenommen werden.

## Web / UI

- Web-API ist im Supervisor weiterhin NOT_IMPLEMENTED.
- Bisherige Desktop-UI wird verworfen und neu aufgebaut.
- Neue UI muss Runtime-/Backendzustände strikt aus autoritativen Quellen beziehen und `Unavailable/Not Implemented/Stopped/Degraded` ehrlich darstellen.

## Doku-/Code-Drift

- ältere Kommentare/Prompts nennen teilweise Qwen als Main, Kokoro/Whisper oder historische Hardware.
- `claude_consultation.py` enthält historische Namen und einen veralteten Selbstbeschreibungs-Prompt; funktional gegated, aber inhaltlich zu bereinigen, falls Feature behalten wird.
- Legacy-Checkouts `Architecture`, `Backend-RC`, alte `UI` und Mobile dürfen nicht als aktuelle Backend-Source-of-Truth verwendet werden.
