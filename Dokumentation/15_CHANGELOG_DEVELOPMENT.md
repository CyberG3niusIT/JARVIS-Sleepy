# Entwicklungshistorie und Entscheidungen

## 01.10.2026: Deutsche Owner-Ausgaben gehärtet

Source-/Mock-Teständerung im Worktree `Main`, Branch `integration/desktop-backend-20260929`, Basis-HEAD `68da00ce056ee9bad9a41918c0a35c97002ef722`. Die Änderung ist als Safepoint-Commit `d43979c876db90dae201d1c3bc8c609f907efbdb` auf demselben Branch gesichert und normal gepusht (kein Branchwechsel, kein Merge/Rebase/Force-Push). Danach wurde die Runtime über `JARVIS-Runtime.ps1` gestartet: `READY`, Voice-Daemon und Desktop-API `READY`; Messwerte und Auffälligkeiten stehen in [12](12_TESTING_QA.md) und [13](13_KNOWN_ISSUES.md). Vorhandene Dirty-Änderungen einschließlich der vom Owner autorisierten Dokumentationsverschiebungen wurden erhalten.

Die zentrale Dokumentation bleibt unter `JARVIS-Sleepy\Dokumentation` erreichbar: Das ist ein Junction auf `Main\Dokumentation` (in WSL als Symlink sichtbar, kein zweiter Bestand). Versioniert werden nur geprüfte Textdokumente; `Dokumentation/LEGACY/` (Binärdateien und Übergaben, ≈ 2,6 GB) ist per `.gitignore` ausgeschlossen. Die 33 aus Root, `docs/`, `governance/`, `reports/`, `systemd/` und `tests/` entfernten Dokumente liegen inhaltsgleich unter `Dokumentation/FINDLINGE/Main/`.

Ursachen waren englische direkte Startup-/Router-/Skill-/Tool-/Web-/Konsolenliterale außerhalb der wirksamen deutschen Persona-Pools, fehlende zentrale Regeln in einzelnen Modellrequest-Pfaden und ungefasste fremde Werkzeugresultate in Planner-Fastpaths/Fallbacks. Die bestehende Persona enthält nun den verbindlichen Sprachvertrag mit Ausnahme nur für einen ausdrücklichen Sprachwunsch in der aktuellen Anfrage. Readback erhält diese aktuelle Anfrage ausdrücklich; es gibt keine Übersetzungsschicht oder zusätzliche Übersetzungsrunde.

Sprachhärtung betraf insbesondere `core/persona.py`, `jarvis_continuous.py`, `core/pipeline.py`, `core/conversation_router.py`, `core/skill_manager.py`, `core/task_planner.py`, `core/llm_router.py`, `core/mcp_client.py`, `core/tool_registry.py`, `core/web_research.py`, `core/context_window.py`, `core/readback_session.py`, `core/memory_manager.py`, `core/awareness.py`, `core/reminder_manager.py`, `core/news_manager.py`, `core/interaction_cache.py`, `core/tools/` sowie die betroffenen Personal-/System-Skillhandler. Web-/Desktop-Backend und Konsole wurden in `jarvis_web.py` und `jarvis_console.py` lokalisiert. Die fünf neuen German-Testmodule und präzise aktualisierte Sprachassertions bestehender Tests sichern die Änderung ab; technische Parser, Recurrence-Regeln, API-Felder und englische Eingaben bleiben erhalten.

Die zentralen Kapitel 01, 06, 07 und 12 beschreiben Sprachvertrag und Nachweis. Gemeinsamer gezielter Lauf: **876 bestanden**; die Detailgrenzen stehen in [12 Testing und QA](12_TESTING_QA.md#deutsch-invariante-gezielte-prufung). Privacy-, Security- und Confirmation-Prüfungen wurden nicht gelockert; Fehlerpräfix-Verbraucher wurden um deutsche Entsprechungen ergänzt. Secrets, Auth-Konfiguration, produktive Daten und Mail-/MCP-Freischaltungen wurden nicht verändert.

Runtime-/Audio-/Hardware-Abnahme bleibt ausdrücklich **offen**. Die rein lesende Control-Plane-Prüfung zeigte den Voice-Daemon als `STOPPED`; Desktop-API meldete einen bestehenden Lifecycle-Fehler. Das ist keine Sprach- oder E2E-Abnahme und wurde in diesem Auftrag nicht durch einen Start übergangen.

## Verifizierte Git-Basis am 24.09.2026

Branch `main`, HEAD `5603945ee0ff6fe6b7b1fac5cbadd3a64191cab6`; Änderungen im Arbeitsbaum sind nicht Teil dieses HEAD. Der separate Mobile-App-Stand hat eigenen Branch und HEAD (siehe [00 Status](00_PROJECT_STATUS.md)).

## Lokale Commit-Zeitlinie

Die folgenden Punkte stammen aus lokalem `git log` auf `main`; sie sind kein vollständiges Release-Changelog. Dazwischenliegende Arbeitsschritte sind ausgelassen. Commits nach dem aktuellen HEAD gibt es nicht; September-24-Arbeit liegt im Dirty Worktree.

| Datum | Commit-Anker | Entwicklung |
|---|---|---|
| 2026-02-18 | `d721e10` | erster öffentlicher Voice-Assistant-Stand |
| 2026-02-21 | `0b99ed7`, `fd0d922` | ConversationRouter als gemeinsamer Prioritäts-Router und eigene Routertests |
| 2026-09-14 | `f4a8484`, `fc510fb` | Windows/WSL2-Port, deutsche Voice-Stack-Basis und Qwen3-ASR-Evaluator |
| 2026-09-15 | `89333b3`, `eb0e12a`, `91487b6`, `5bf74f1` | German voice mode, Chatterbox-TTS, Streaming-/Timeout-/Backpressure-Arbeit |
| 2026-09-19 | `c4574e4`, `bd0e530` | PrivacyGate eingeführt; systemd-Änderungen ausdrücklich mit Hardwareprüfung offen |
| 2026-09-20 | `cbf65d2`, `028ed63`, `568660d` | Privacy-Pfade für Audio/Camera/Persistenz gehärtet; Memory-Decays/Konsolidierung ergänzt |
| 2026-09-21 | `9338f3a`, `770ba32`, `1d94a8f`, `bfd5d27`, `6bbf704` | Entwickler-Tool-Sicherheitsklassifikator neu ausgelegt; Inhaltslogs/Gates, privacy sentinels, TaskPlanner-Abbruch und Watchdog-Sichtbarkeit bearbeitet |
| 2026-09-24 | lokaler Worktree, kein Commit | School/Mobility- und Vocal-Direction-Änderungen vorhanden; Canary/Livefreigabe laut Arbeitsstatus offen |

Commits belegen Änderungen, nicht dauerhaft erreichten Runtimezustand.

## Architekturentscheidungen und verworfene Ansätze

- **Router gemeinsam nutzen:** Routinglogik wurde in `ConversationRouter` extrahiert statt pro Frontend getrennt zu halten (`0b99ed7`).
- **Privacy ohne STT-Bypass beenden:** Privacy blockiert Mic/STT; die Stimme ist daher kein Exitkanal. Ein lokaler Control-Watcher adressiert den headless Prozess (`be56b36`, `c4574e4`); ein Bypass würde das Privacy-Versprechen schwächen.
- **Tool-Safety strukturell prüfen:** Shell-Ketten/Pipes und Argumente werden segmentiert und befehlsspezifisch klassifiziert; weitergehende Prozessausführung ohne Shell war laut historischer Architekturquelle außerhalb des Fixumfangs (`9338f3a`, `e9e1c4e`).
- **Keine stale TTS-Fallback-Ausgabe:** nach Chatterbox-Timeout soll keine veraltete Piper-Antwort den aktuellen Turn vortäuschen (`836a8b7`).
- **Mobility-Daten nicht erraten:** EFA-/GTFS-RT-Identitäten werden nicht ungeprüft zusammengeführt; partielle oder stale Schätzungen werden nicht als vollständige Echtzeit ausgegeben.
- **Ein bestehender Poller:** School-Reisebedarf wird über den vorhandenen ReminderManager-Scheduler als befristete Lease synchronisiert; kein zweiter Sleepy-Poller.
- **Kein `LLMServerClient`-Transport behaupten:** Modul ist vorhanden, im geprüften Aufrufgraph aber nicht verbunden; tatsächlicher Router verwendet seinen eigenen HTTP-Pfad.

Dies sind nachvollziehbare Richtungen aus Code/Commit-Historie; sie sind keine nachträglich formalisierten ADRs.

## Aus Code und überlieferten Dokumenten erkennbare Richtungen

- Repository-Artefakte enthalten Windows/WSL2- und Linux-Betriebsannahmen; aktuelles Zielsystem und Dienstzustand wurden hier nicht live geprüft.
- Core und Skills bilden modulare Fähigkeiten; direkte Routes und lokale Modell-/Toolpfade koexistieren.
- School und Mobility sind getrennt: Fakten/Schulereignisse gegenüber Route/Transportplanung.
- Mobility-Demand soll den bestehenden Reminder-Scheduler wiederverwenden und bei fehlender Nachfrage keine periodischen Realtime-Abfragen auslösen.
- Stale/partial Realtime wird als degradierte bzw. fahrplanbasierte Information behandelt; fehlende Fakten nicht schätzen.
- Android-Port bildet Web-Referenz als native Compose-App ab, hält aber nicht entschiedene Runtime-/Trust-/Privacy-Verträge offen.

## Experimente / Sackgassen

Frühere Dokumente enthalten viele historische Modell-/GPU-/Latenz- und Testzahlen sowie nicht mehr passende Systembeschreibungen. Sie sind im Inventar als LEGACY oder EXPERIMENTAL klassifiziert, nicht als aktuelle Produktfakten. Ein früherer Chatterbox-Turbo-Versuch war laut dokumentiertem Verlauf durch fehlende WSL-GPU-Geräte blockiert; erneute aktuelle Prüfung fehlt.

## Offene Entscheidungen

Keine verbindliche ADR-Entscheidung zu Mobile Trust/Pairing, Privacy-Regelmatrix, Android-Rechten oder konkreter Modellruntime gefunden. Auch die operative Abnahme der jüngsten Mobility-Arbeit fehlt.

## 2026-09-25: Modellarchitektur Primary/Expert, Direct-Audio, NPU-Sensor

Nicht committet. Evidenz überwiegend Unit-Tests mit Fakes.

- Gemma 4 12B (llama.cpp + mmproj, Audio + Vision, `llm.primary`, Port 8080) ist Primary; Qwen3.5-35B-A3B nur als Expert bei Eskalation (`llm.expert`, Port 8082, GPU-exklusiv). GPU-Handover mit Lifecycle-Records; Qwen-Ladezeit ca. 90-100 s gemessen.
- Turn-Aggregation (`core/turn_assembler.py`), Direct-Audio (`core/direct_audio.py`), spekulativer Turn ohne Nebenwirkungen (`core/speculative_turn.py`).
- Expert-Policy (`core/expert_policy.py`), Tool `delegate_to_expert`.
- NPU-Sensor: Präsenz (buffalo_l) auf Dateieingabe belegt; Vision-Gate (`core/vision_gate.py`) standardmäßig aus.
- Neue Tests: siehe [12](12_TESTING_QA.md). Neue User-Unit-Vorlagen und Supervisor-Komponenten: `Main/systemd/README.md`, `Main/docs/RUNTIME_SUPERVISOR.md`.
- Offen: siehe [13](13_KNOWN_ISSUES.md).

## 01.10.2026 – Dokumentation für den Safepoint versionierbar

Die 1395 zentralen Dateien wurden ohne Inhaltskopien physisch nach `Main/Dokumentation` verschoben. Der kanonische Windows-Pfad `C:\Users\Alex\Projekte\JARVIS-Sleepy\Dokumentation` ist eine Junction auf diesen Bestand. Alle SHA256-Inhalte blieben beim Verschieben identisch; der kanonische Pfad ist auch über WSL erreichbar. Git versioniert reguläre Dateien im Main-Worktree, keine Junction. Historische Backups, Binärdateien, sensitive Logs und fremde Handoff-Evidence werden nicht pauschal aufgenommen. Die isolierte ältere Capability-Registry samt ihren Tests und Fixtures bleibt separat uncommittet.

Vor dem Commit wurden vier verbliebene englische Owner-Textfragmente in NewsManager und Webnavigation korrigiert und fünf Regressionen ergänzt. Privacy-/Authorization-Gates wurden dabei nicht geändert. Commit, Push und anschließende Live-Abnahme werden erst nach realer Durchführung als erfolgreich dokumentiert.
