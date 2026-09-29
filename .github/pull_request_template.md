## Was aendert sich?

<!-- Kurzbeschreibung -->

## Warum?

<!-- Welches Problem wird geloest? -->

## Betroffene Komponente(n)

<!-- STT, TTS, LLM, Routing, Tools, Vision, Memory, Runtime, Tests -->

## Tests

- [ ] Gezielte Unit-Tests gelaufen (Befehl und Ergebnis unten eintragen), z. B. `scripts\wsl-pytest.ps1 tests/unit/<datei>.py`
- [ ] Nicht getestete Teile benannt (z. B. Hardware, Live-Voice)
- [ ] Live-Voice-Test durchgefuehrt (falls Voice-Pfad betroffen)

```
<Befehl + Ausgabe>
```

## Privacy

- [ ] Keine neuen externen Netzwerkaufrufe (oder begruendet und nutzerinitiiert)
- [ ] Privacy-Gate nicht umgangen; keine Telemetrie
- [ ] Audio/Transkripte bleiben lokal

## Checkliste

- [ ] Keine Aenderung an `.env`, `config.yaml`, `*.service` ohne Absprache
- [ ] Neue Config-Schluessel in `config.yaml` und `Dokumentation/10_CONFIGURATION.md` eingetragen
- [ ] Betroffene Doku in `Dokumentation/` aktualisiert
- [ ] Keine unnoetigen neuen Abhaengigkeiten
