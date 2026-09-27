# Security und Privacy

## PrivacyGate

`core/privacy_gate.py` implementiert Capability-Gates für unter anderem Mikrofon/STT, Memory, Cloud-LLM, MCP/Remote-Tools, Kamera/Screen/Clipboard und Content-Logging. Coverage ist verteilt und muss weiterhin an realen Call-Sites auditiert werden.

Der Gate-Singleton ist prozesslokal. Mehrere Prozesse teilen Privacy-State nicht automatisch.

## Cloud

Aktueller checked-in Zustand:

- OpenRouter ist bevorzugter Cloud-Provider, aber `llm.api.enabled: false`.
- `llm.api.model: null`.
- Anthropic ist kein impliziter Default mehr.
- Anthropic darf nur bei expliziter Provider-Auswahl, aktivierter Cloud, Modell/Credential und `PrivacyGate(CLOUD_LLM)` erreicht werden.
- `self_evolution.auto_consult: false`.

Damit gibt es aktuell keinen automatisch aktiven Observation->Claude-Datenfluss mehr.

## Voice-/Turn-Cleanup

Privacy-Flush, stale generation und Turn-Cancel müssen laufende/speculative Requests terminal beenden. Ein später Retry oder Cloud-Fallback aus einem verworfenen Turn wäre ein Privacy- und Zustandsfehler. Der reale Voice-Test zeigte einen verwaisten Retry nach Conversation-Timeout; dieser Punkt bleibt vor Produktivfreigabe zu schließen.

## Secrets

`.env`, API-Keys, Tokens, private DBs und persönliche Logs gehören weder in Git noch in den Lovable-Handoff. `.env.example` darf nur Variablennamen/Platzhalter enthalten.
