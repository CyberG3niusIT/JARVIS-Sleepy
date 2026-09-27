# Beobachtung und Privacy-Gates

## ObservationCollector

`core/observation_collector.py` analysiert Eventdaten und kann Findings speichern. Automatische Cloud-Beratung ist im aktuellen Configstand deaktiviert:

```yaml
self_evolution:
  auto_consult: false
```

Die optionale Anthropic-Consultation bleibt ein expliziter Providerpfad und ist ohne `provider: anthropic`, aktivierte Cloud, Modell/Credential und PrivacyGate nicht erreichbar.

## PrivacyGate

`core/privacy_gate.py` kapselt Modi und Capability-Gates. Relevante Fähigkeiten umfassen Mic/STT, Memory, Cloud LLM, MCP/Remote Tools, Camera/Screen/Clipboard und Logging. Die Coverage bleibt an realen Call-Sites zu prüfen.

## Offener Punkt

Turn-/Conversation-Cleanup muss speculative und laufende Requests terminal stoppen. Ein realer Test zeigte einen späteren Retry nach Conversation-Timeout; dieser Pfad ist Privacy- und Zustandsrelevant.
