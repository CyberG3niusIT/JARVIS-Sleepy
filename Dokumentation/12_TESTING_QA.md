# Testing und QA

## Testklassen

Code vorhanden != Unit-Test != Integrationstest != Runtime-Test != Hardware-/E2E-Test. Jede Statusbehauptung muss die tatsächlich erreichte Stufe nennen.

## Berichtete aktuelle Regression

Vor dem späteren Live-Voice-Test wurde ein gezielter Regressionslauf mit **583 passed, 1 skipped (Hardware-Smoke)** berichtet. Zusätzlich wurden `py_compile`, `bash -n`, YAML-Load und Zeilenenden geprüft. Diese Ergebnisse wurden im Rahmen dieses Doku-Refreshs nicht erneut ausgeführt.

Nach der Cloud-/Provider-Bereinigung berichtete Codex **80 fokussierte Router/Provider/Privacy-Tests bestanden**, außerdem `py_compile`, YAML Parsing und `git diff --check`. Es wurden keine echten Cloud-Calls ausgeführt und kein Daemon für diesen Testlauf neu gestartet.

## Reale Runtime-/Hardware-Evidenz

### Reboot

`getRuntime` nach vollständigem Windows-Neustart: READY, keine Degraded-Gründe.

### Voice Acceptance 26.09.2026

**Nicht bestanden.** Reproduzierte Punkte:

- Wake-only/Turn-Aggregation trennt natürliche Pause falsch.
- Watchdog öffnet Listening während laufender TTS.
- speculative Stream-Cancel endet mit `NoneType ... read`.
- stale/orphaned Retry läuft nach Conversation-Timeout weiter.
- eine danach vollständig gesprochene Anfrage wird beantwortet, aber der Direct-Audio-Pfad ist im Log nicht eindeutig beweisbar.

Daher darf Voice trotz funktionierender Teilpfade noch nicht als E2E-verifiziert bezeichnet werden.

## Nächste Acceptance-Matrix

1. normaler Aura-Dialog, ein Turn, Gemma Direct-Audio
2. Satz mit natürlicher Pause, weiterhin ein Turn
3. Zeit/Tool-/Skill-Frage über Textpfad
4. bare `Aura` erst nach Grace als Minimal-Greeting
5. `Aura, stopp` während TTS unterbricht sauber
6. Privacy während aktivem Request verwirft Turn ohne spätere Antwort
7. kein orphaned Retry nach Cleanup
8. explizite Pfadmarker belegen Direct-Audio vs. Textpfad
