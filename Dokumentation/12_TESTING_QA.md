# Testing und QA

## Teststruktur

`tests/unit/`, `tests/integration/`, `tests/routing/` und `tests/components/` enthalten getrennte Testbereiche. Mobile hat einen eigenen Android-Test-/Buildpfad im separaten Repository. Kein Test wurde für diese Dokumentationsarbeit ausgeführt.

## Deutsch-Invariante: gezielte Prüfung

Die neuen Tests `test_german_startup_runtime.py`, `test_german_router_skill_contract.py`, `test_german_model_tool_contract.py` und `test_german_web_console_contract.py` prüfen Startup-TTS-Spies, reale Router-/Skillhandler, Bestätigungen und Abbruch, Wetter-/Systemantworten, Kalender-/Reminder-Fehler, MCP-Timeouts, tatsächliche Modellrequest-Payloads und deutsche Web-/Konsolenrahmen. Englische Quellinhalte bleiben Daten; das Verhalten wird mit Mocks und Spies ohne produktive Schreiboperationen geprüft.

`test_german_review_regressions.py` ergänzt die unabhängig gefundenen Cloud-Generate-, Planner-Fastpath-/Fehler-, Datei-/Kontakt-/App-Rahmen-, Rekurrenz- und Alters-Consumer-Fälle. Die fünf neuen Module umfassen zusammen **149 bestandene Tests**. Der gemeinsame Lauf mit bestehenden Regressionen aus 34 gezielt ausgewählten Modulen bestand am 01.10.2026 mit **876 Tests, 306 Warnungen, 45,09 Sekunden**. Die Warnungen betreffen vor allem vorhandene aiohttp-App-Key-/Lifecycle-Meldungen; sie wurden nicht durch Test-Skips unterdrückt. Nach Formatierung der neuen Testdateien bestanden erneut 149 Tests (7,86 Sekunden); nach den letzten vier reinen Pipeline-Statuslokalisierungen bestanden Startup/Voice-Finalisierung erneut mit 79 Tests (2,85 Sekunden).

Unabhängige ECC-Python-/Code-Reviews prüften die behobenen Befunde erneut mit eigenen gezielten Läufen; zusätzlich wurde der projektspezifische Voice-Integrations-Review angewendet. `git diff --check` und der AST-Syntaxcheck von 146 Core-/Skill-/Einstiegspunkt-Dateien bestanden. Keine Vollsuite, keine reale Cloud-/MCP-/Mail-Aktivierung und keine hörbasierte Abnahme wurden ausgeführt. Ruff/Mypy/Pylint waren nicht verfügbar und wurden nicht installiert.

Regressionen prüfen unter anderem englische Bestätigungseingaben, deutsche Vorleseangebote mit „ja“ und „yes“, die Abgrenzung zu Sachanfragen wie „Java“/„Januar“, erhaltene Parser-/APIwerte sowie Cache-Sperren für transiente deutsche und englische Fehlerrückmeldungen. Ein positiver Cachetest bewahrt normale englische Quellinhalte. Vorhandene Privacy-, Lifecycle- und Confirmation-Tests werden zusätzlich gezielt ausgeführt.

Reale Modellqualität, Audiohardware, hörbare Startup-/Voice-Ausgabe und Live-E2E sind für diese Sprachhärtung noch nicht abgenommen. Der Owner hat die Runtime bewusst gestoppt; eine spätere Live-Abnahme benötigt seine Freigabe.

## Aussagekraft

Unit-Tests mit Fakes/Fixtures belegen Logik unter Testbedingungen, keine Erreichbarkeit externer Dienste, Modellqualität, Hardwareleistung oder reale Datenkorrektheit. Live-Abnahme braucht getrennte Evidenz mit Zeit, Build/HEAD, Dienstgesundheit, Eingabequelle und Resultat.

## School/Mobility

Im Arbeitsbaum liegen neue Testmodule für Contract, Planner, DB, Flow, Skill-Loading und Reiseevents. Auftraggeberseitig wurde zuletzt ein Umfang von 600 Unit-Tests genannt; hier nicht erneut verifiziert. 65-Minuten-DORMANT-Soak und Canary-Angaben sind in [08](08_SCHOOL_MOBILITY.md) als berichtet markiert.

## Voice

Neue Vocal-Direction- und Runtime-Check-Tests liegen uncommittet. Ein erfolgreicher Unit-Test wäre keine hörbasierte Produktfreigabe und kein Nachweis GPU-fähiger Chatterbox-Turbo-Ausführung.

## Modell-/Voice-Umbau (25.09.2026)

Neue Testdateien: `test_turn_assembler`, `test_direct_audio_routing`, `test_speculative_audio_side_effects`, `test_model_handover`, `test_expert_delegation`, `test_vision_gate`, `test_expert_handover_integration`, `test_stop_fastpath_integration`. Sie arbeiten mit Fakes (u. a. Fake-`systemctl`, Fake-LLM) und belegen Logik, keine Hardware-Funktion.

Ausführung (WSL Ubuntu-24.04, venv):

```
wsl.exe -d Ubuntu-24.04 -- /home/alex/jarvis-venv/bin/python3 -m pytest <Testdatei>
```

Es wird **keine** Aussage über eine vollständige Suite gemacht; nur die genannten Dateien wurden gezielt betrachtet. Nicht getestet auf Hardware: Direct-Audio mit Gemma, Handover mit echtem systemd, NPU-Live-Kamera.

## Safepoint-Verifikation am 01.10.2026

Vor Commit und Push wurden drei verbliebene englische Nachrichtenrahmen und der Ergebniszähler beim Zurückblättern einer Websuche korrigiert. Fünf zusätzliche Regressionen prüfen alle Nachrichten-Templatevarianten, erhaltene Originalschlagzeilen, den Schlagzeilenzähler und die vorige Suchseite. Der gezielte Lauf der bisherigen Sprachtests bestand mit 153 Tests; nach der letzten Webkorrektur bestanden alle 16 Review-Regressionen. Die fünf Sprachtestdateien umfassen damit 154 Fälle. Der frühere Lauf mit 876 Tests bleibt historische Evidenz und wurde nicht blind wiederholt. Runtime und gehörte Audioausgabe sind zu diesem Zeitpunkt noch offen.

Vor dem Safepoint-Commit wurden am 01.10.2026 drei gezielte WSL-Läufe (Unit, ohne Modelle/GPU/Netzwerk) erneut ausgeführt: Review-Regressionen plus Web-Search-Verträge **131 bestanden**; die Deutsch-Verträge mit Web-/Wetter-Privacy **260 bestanden**; Startup-/Voice-/Lifecycle-Tests **138 bestanden** (110,8 s). Keine Fehler, Skips oder Errors. Die Sprachmodule zählen 16 + 51 + 15 + 33 + 39 = 154 Fälle. `git diff --check` und der AST-Syntaxcheck von 90 geänderten/neuen Python-Dateien bestanden. Ein rein lesender Secret-/Privacy-Review des Commit-Kandidaten fand keine kritischen, hohen oder mittleren Befunde. Für `news_manager` und `web_navigation` gibt es keine eigenen Testmodule; ihre Sprachrahmen sind nur über die Review-Regressionen abgedeckt. Nicht ausgeführt: Vollsuite, `tests/routing`, Integration, Hardware.

Der Safepoint ist Commit `d43979c876db90dae201d1c3bc8c609f907efbdb` (Basis `68da00ce056ee9bad9a41918c0a35c97002ef722`, 189 Dateien), normal gepusht auf `origin/integration/desktop-backend-20260929`; lokal und Remote stimmen überein.

### Runtime-Start nach dem Safepoint (01.10.2026)

Start nur über `JARVIS-Runtime.ps1 -Action start`. Vorher: Voice `STOPPED`, Desktop-API `ERROR`. Gemessen: Runtime `READY` etwa 40 s nach dem Start (16:43:49Z), Voice-Daemon `READY`, Desktop-API `READY`. Danach war Chatterbox von 16:44:34Z bis 16:44:51Z kurz nicht erreichbar (`DEGRADED`) und anschließend wieder `READY` (16:45:05Z). Web-API (8091) und NPU-Sensor blieben `OFFLINE`/`STOPPED`.

Aus dem Journal belegt: Die Startup-Sprachausgabe (85 Zeichen) wurde um 18:44:12 ausgelöst und von Chatterbox nach 48,89 s abgeschlossen; zwei LLM-Streaming-Timeouts (90 s) um 18:46:23 und 18:46:38. Einordnung siehe [13](13_KNOWN_ISSUES.md).

**Nicht durchgeführt und damit nicht verifiziert:** die gesprochene Live-Abnahme (Startup-Hörprobe, „Wie spät ist es?“, „Wie ist das Wetter?“, deutscher Fehlerpfad, Sprachwunsch Englisch und automatischer Rückfall auf Deutsch, fremder englischer Originalinhalt) sowie die Audioqualität (Hörbarkeit, Doppel-/Stale-/abgeschnittene Ausgabe, Fallback-Stimme). Dafür sind Sprecher und Gehör erforderlich. Der Wortlaut der Startup-Ausgabe wird aus Datenschutzgründen nicht im Journal protokolliert (nur Zeichenzahl).
