# Entwicklungshistorie und Entscheidungen

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
