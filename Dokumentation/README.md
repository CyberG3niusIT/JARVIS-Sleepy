# JARVIS Sleepy — Technische Dokumentation

Diese Dokumentation beschreibt den überprüften Stand des Repositorys `Main` am 24.09.2026. Quellcode, aktive Konfiguration und der lokale Git-Arbeitsstand sind maßgeblich. Statusangaben unterscheiden implementierte Software von historischen Behauptungen, Planung und nicht verifizierter Runtime.

## Was ist JARVIS Sleepy?

Ein modularer, primär lokaler Sprachassistent mit Python-Core, Skill-/Tool-Routing, Memory- und Reminder-Komponenten sowie Voice-, Konsolen- und Web-Einstiegspunkten. Er läuft in einer Windows/WSL-Entwicklungsumgebung. Externe Dienste und lokale Modelle sind konfigurierbare Integrationen; ihre Verfügbarkeit wird hier nicht aus Konfiguration abgeleitet.

## Gesamtstatus

**PARTIAL / in Entwicklung.** Core, Router, Skills, Tools, STT/TTS-Adapter und Web-/Konsolenpfade sind im Code vorhanden. Das aktuelle Checkout enthält umfangreiche uncommittete Änderungen. School/Mobility und Vocal Directions sind neu hinzugekommene, noch nicht live abgenommene Bereiche. Android ist ein separates Repository und ein UI-Port mit wesentlichen Runtime-Bindungen offen. Reale Produktivlaufzeit, Modelle, Datenbanken und persönliche Daten sind nicht Bestandteil dieser Dokumentation.

## Architekturüberblick

`jarvis_console.py`, `jarvis_continuous.py` und `jarvis_web.py` initialisieren gemeinsam genutzte Core-Komponenten. `core/pipeline.py` koordiniert Ereignisse und den Voice-Ablauf; `ConversationRouter`, `TaskPlanner`, `SkillManager`, `ToolRegistry` und `MemoryManager` übernehmen Routing, Zerlegung, Fähigkeiten, Tools und Gedächtnis. Weitere Manager decken Personen, Reminder, Awareness, Beobachtung, MCP, Audio und Desktop ab. Details: [01 Architektur](01_ARCHITECTURE.md), [02 Komponenten](02_COMPONENTS.md).

## Dokumentenindex

- [00 Projektstatus](00_PROJECT_STATUS.md)
- [01 Architektur](01_ARCHITECTURE.md)
- [02 Komponenten](02_COMPONENTS.md)
- [03 Runtime und Modelle](03_RUNTIME_AND_MODELS.md)
- [04 Agents und Orchestrierung](04_AGENTS_AND_ORCHESTRATION.md)
- [05 Memory](05_MEMORY.md)
- [06 Voice, STT und TTS](06_VOICE_STT_TTS.md)
- [07 Tools, MCP und Skills](07_TOOLS_MCP_SKILLS.md)
- [08 School und Mobility](08_SCHOOL_MOBILITY.md)
- [09 Security und Privacy](09_SECURITY_PRIVACY.md)
- [10 Konfiguration](10_CONFIGURATION.md)
- [11 Installation und Betrieb](11_INSTALLATION_OPERATION.md)
- [12 Testing und QA](12_TESTING_QA.md)
- [13 Bekannte Probleme](13_KNOWN_ISSUES.md)
- [14 Roadmap](14_ROADMAP.md)
- [15 Entwicklungshistorie](15_CHANGELOG_DEVELOPMENT.md)
- `16_UI_CONTROL_HUB.md`: aktuelle Fassung wird in Phase 3 gegen den realen Repository-/Runtime-Stand neu aufgebaut. Historischer Stand: [Legacy/UI_CONTROL_HUB_HISTORY_2026-09-26.md](<16_UI_CONTROL_HUB.md>)
- [Historisches Dokumentationsinventar vom 24.09.2026](<INVENTORY.md>)
- [Historisches Quellenregister](Legacy/SOURCE_REGISTER.md)
- [Komponentenregister](COMPONENTS/README.md)
- [Legacy-Bestände und historische Evidence-Snapshots](Legacy/README.md)
- `17_TOOLING_UND_GITHUB.md`: aktuelle Fassung wird in Phase 3 neu aufgebaut. Historischer Vorschlag: [Legacy/TOOLING_UND_GITHUB_PROPOSAL_2026-09-26.md](<17_TOOLING_UND_GITHUB.md>)
- [ADR](ADR/README.md)

## Wichtigste Quellpfade

Core: `core/`; Skills: `skills/`; Tools: `core/tools/`, `tools/`; Services: `services/`; Konfiguration: `config.yaml`, `.env.example`; Tests: `tests/`; Betrieb: `systemd/`, `*.service`, `*.sh`; Mobile getrennt: `../Mobile-App/`.

## Entwicklungsregeln

1. Laufzeitbehauptungen nur mit aktueller Runtime-Evidenz; `enabled: true` bedeutet nicht, dass ein Dienst erreichbar oder live abgenommen ist.
2. Private Runtime-Daten und Modellbestände bleiben außerhalb der Dokumentation. Keine Secrets, personenbezogenen Angaben oder DB-Inhalte aufnehmen.
3. Vor Änderungen Git-Status prüfen und bestehende Änderungen bewahren. Die Dokumentation nennt den am Prüftag sichtbaren Branch und HEAD.
4. Entwürfe, Experimente, Codeimplementierung, Tests und Live-Abnahme getrennt kennzeichnen.
5. Keine Git-Remote-Aktionen oder Historienumschreibungen im Rahmen dieser Dokumentation.

## Offene Punkte

Live-Abnahme der School/Mobility-Integration, nachvollziehbarer Runtime-Nachweis für konfigurierbare lokale/Cloud-Dienste, WSL ROCm-Passthrough für GPU-Experimente, kanonische Entscheidung über verteilte/alte Dokuquellen und fehlende ADR-Belege. Das Mobile-Pairing sowie Privacy-/Permission-Enforcement bleiben offen.
