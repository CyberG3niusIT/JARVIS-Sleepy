# JARVIS Sleepy - Technische Dokumentation

**Stand: 27.09.2026.** Diese Dokumentation beschreibt den derzeit belegten Entwicklungsstand von `C:\Users\Alex\Projekte\JARVIS-Sleepy\Main`. Maßgeblich sind aktueller Runtime-Befund, aktueller Worktree und reale Tests. Ältere Branch-/HEAD-Angaben, UI-Prototypen und historische Doku sind nachrangig.

## Aktueller Gesamtstatus

**PARTIAL / aktive Entwicklung.** Der produktionsnahe Kern läuft lokal-first. Nach einem vollständigen Windows-Neustart meldete der offizielle Runtime-Supervisor am 26.09.2026 `READY` ohne Degraded-Gründe. Voice-Daemon, Gemma Primary, Qwen3-ASR, Chatterbox, Windows-Audio-Brücke und VVS wurden dabei als `READY` gemeldet. Expert-Qwen und FLUX waren erwartungsgemäß `STOPPED`/on-demand; NPU-Presence war `STOPPED` mit nicht initialisiertem Backend; Web war im Supervisor `NOT_IMPLEMENTED`.

Der erste reale Voice-Acceptance-Test nach diesem Neustart war **nicht bestanden**: Wake/Turn-Aggregation, Watchdog während TTS, speculative Stream-Cancel und ein verwaister Retry zeigten Fehler. Eine spätere vollständige Sprachfrage wurde beantwortet, der konkrete Direct-Audio-Pfad war im Log aber nicht eindeutig bewiesen. Diese Grenze ist in [06 Voice](06_VOICE_STT_TTS.md) und [13 Known Issues](13_KNOWN_ISSUES.md) dokumentiert.

## Aktuelle Modellrollen

- **Gemma 4 12B** ist PRIMARY auf Port 8080. Sie ist für normalen Dialog, Direct-Audio und Vision via mmproj vorgesehen.
- **Qwen3.5-35B-A3B** ist EXPERT auf Port 8082. Er wird nur bei gezielter Eskalation und GPU-Handover verwendet; das Handover ist derzeit weiterhin deaktiviert, bis die Hardware-Abnahme vollständig ist.
- **Qwen3-ASR** bleibt für STT und den parallelen Text-/Routing-Pfad aktiv.
- **Chatterbox** ist aktive TTS-Engine.
- **OpenRouter** ist als bevorzugter Cloud-Provider vorbereitet, aber aktuell deaktiviert und ohne Modell konfiguriert. Anthropic ist nur optional und darf nur bei expliziter Provider-Auswahl erreicht werden.

## Desktop-UI

Die bisherige Desktop-Anwendung gilt nicht mehr als visuelle Zielimplementierung. Sie wird neu aufgebaut. Die bestehende Doku `16_UI_CONTROL_HUB.md` wurde deshalb in eine aktuelle Backend-/State-Vertrags- und Redesign-Baseline überführt. Die neue visuelle Richtung und der Lovable-Handoff stehen in [18 Desktop Redesign / Lovable](18_DESKTOP_REDESIGN_LOVABLE.md).

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
- [16 Desktop Control Hub / Backend-State-Vertrag](16_UI_CONTROL_HUB.md)
- [17 Tooling und GitHub](17_TOOLING_UND_GITHUB.md)
- [18 Desktop Redesign / Lovable](18_DESKTOP_REDESIGN_LOVABLE.md)
- [Inventar](INVENTORY.md)
- [Komponentenregister](COMPONENTS/README.md)
- [Legacy](LEGACY/README.md)
- [ADR](ADR/README.md)

## Source-of-Truth

1. laufendes System / reale Runtime
2. aktueller `Main`-Worktree
3. Git-Stand und Konfiguration
4. reale Tests und Messwerte
5. diese zentrale Dokumentation
6. ältere Doku, Legacy-Checkouts und frühere UI-Prototypen

## Dokumentationsregeln

- Konfiguration ist kein Laufzeitbeweis.
- Code vorhanden ist kein Hardware-/E2E-Nachweis.
- Frontends dürfen keine Runtime-Zustände erfinden.
- Private Runtime-Daten, Secrets und personenbezogene Inhalte gehören nicht in diese Doku.
- Historische oder nicht erneut geprüfte Angaben werden ausdrücklich als solche markiert.
