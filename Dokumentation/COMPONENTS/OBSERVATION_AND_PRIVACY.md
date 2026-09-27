# Beobachtung und Privacy-Gates

## ObservationCollector

`core/observation_collector.py` führt unabhängige Detektoren über EventLogger-Daten aus (unter anderem STT-Fehler, ausbleibende Bestätigungen, TTS-/Routing-/Watchdog-Muster), sortiert Findings und kann sie als Scores/Eventbelege speichern. Web startet den Collector, wenn EventLogger initialisiert werden konnte. Der Collector wartet beim Start fünf Minuten und führt anschließend standardmäßig in zweistündigem Abstand aus; der Lookback überlappt mit vier Stunden.

`self_evolution.auto_consult` ist in der geprüften Config `true`. Bei kritischen/hohen/mittleren Findings kann `_consult_claude()` Claude API aufrufen. Das ist ein realer codekonfigurierter Cloud-Datenpfad für Finding-Details. Ein veralteter Kommentar im Web-Einstieg sagt „OFF by default“; Config und Collectorcode steuern den Wert. Es wurde kein Cloud-Aufruf ausgelöst.

## PrivacyGate

`core/privacy_gate.py` implementiert Modi `NORMAL`, `PRIVACY`, `PRIVACY_LOCK` und eine Capability-Matrix. Konkrete Gates sind unter anderem in Listener/STT, Memory-Write/Extract, Cloud-LLM, MCP/Remote-Tool, Kamera/Screen/Clipboard und Logging eingebunden. Die Coverage ist verteilt, nicht automatisch vollständig.

Der Gate-Singleton ist prozesslokal. Continuous Voice, Console und Web sind getrennte Prozesse; ein Moduswechsel in einem Prozess teilt den Zustand nicht automatisch mit den anderen. Der PrivacyControlWatcher dient dem headless Voice-Prozess für lokalen Datei-basierten Steuerzugriff im selben Prozess. Seine Runtime-Verfügbarkeit wurde nicht überprüft.

## Datenschutzstatus

Finding-Detailtexte können aus Events abgeleitete Betriebsinformationen enthalten. Wegen aktiviertem Auto-Consult ist die externe Datenweitergabe im aktuellen Configstand zu prüfen. In dieser Dokumentation werden keine Findings, persönlichen Inhalte, DB-Pfade oder API-Schlüssel festgehalten.
