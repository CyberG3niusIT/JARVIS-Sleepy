# Security und Privacy

## Projektgrenzen

Secrets werden ausschließlich als erforderliche Environment-Variablen benannt, niemals mit Werten dokumentiert. Keine lokale `.env`, Datenbank, Logdatei, persönliche Aufzeichnung oder Modellablage wird in diese Dokumentation kopiert. `.env.example` dient als Platzhalterquelle.

## Codepfade

Das Repository enthält `core/privacy_gate.py`, `core/privacy_control_watcher.py`, Tool-Gates und eine `SECURITY.md`. Deren Existenz beweist nicht, dass alle Fähigkeiten zentral policy-geprüft werden. Tool-, Skill-, MCP-, Netzwerk- und Beobachtungspfade müssen einzeln geprüft werden.

`PrivacyGate` ist ein prozesslokales Singleton; der Watcher ist für den langlebigen Voice-Prozess ausgelegt. Ein Privacy-Modus in einem anderen Prozess teilt nicht automatisch denselben Singletonzustand. Im Code existieren konkrete Gates unter anderem für Mikrofon/STT, Memory-Schreib-/Extraktionspfade, Cloud-LLM, MCP und Kamera-/Desktopfunktionen. Daraus folgt keine vollständige zentrale Policy-Abdeckung.

`self_evolution.auto_consult` ist in der geprüften Konfiguration aktiviert, und Observation-Findings können an Claude gesendet werden. Dieser mögliche externe Datenfluss ist bei Betriebsfreigabe und Privacy-Bewertung zu berücksichtigen.

## Mobile-Grenze

Das separate Android-Projekt hält offene Entscheidungen zu Pairing/Trust, Privacy-Gating, Permissions und Local Runtime in `android/OPEN_DECISIONS.md`. Konkrete Sleepy-Verbindung und vollständiges Enforcement sind dort nicht als fertig belegt.

## Dokumentationsregeln

Keine Credentials, personenbezogenen Daten, internen DB-Inhalte, persönlichen Schul-/Mobilitätsdaten, private Stopp-IDs oder realen Logauszüge aufnehmen. Netzwerkendpunkte nur soweit erforderlich und bereits ausdrücklich als lokale Schnittstelle freigegeben nennen.
