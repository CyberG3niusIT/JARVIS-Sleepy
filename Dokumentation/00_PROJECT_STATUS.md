# Projektstatus (24.09.2026)

**Gesamt: PARTIAL / aktive Entwicklung.** Geprüft wurden Repository `Main`, `config.yaml`, `.env.example` (Namen/Platzhalter, keine lokale `.env`), Quellverzeichnisse und Git-Metadaten. Keine Live-Dienste, privaten Datenbanken oder externen Modellverzeichnisse wurden geprüft.

## Git-Evidenz

- Branch: `main`
- HEAD: `5603945ee0ff6fe6b7b1fac5cbadd3a64191cab6`
- Lokale Statusanzeige: `main...origin/main`; dies wurde nur aus lokalem Git-Status abgelesen, kein Remote kontaktiert.
- Arbeitsverzeichnis: zahlreiche vorhandene Änderungen und neue Dateien, unter anderem Pipeline/Reminder/TTS, Konfiguration, Mobility, School und Voice. Zusätzlich wurde in dieser Doku-Runde der README-Einstieg auf die zentrale Doku verlinkt.

Weitere getrennte Quellcheckouts im Workspace:

| Checkout | Branch / HEAD | Arbeitsstatus am Ende der Doku-Runde |
|---|---|---|
| `Architecture` | `claude/jarvis-architecture` / `833bcebd74e1c0da506c3c5e71bf93b8625190a8` | zuvor sauber; README in dieser Doku-Runde markiert |
| `Backend-RC` | `claude/jarvis-sleepy-backend-rc-nhtfgm` / `b8067965fe0514c8359b46807b8d97f187229b18` | zuvor sauber; README in dieser Doku-Runde markiert |
| `UI` | `claude/jarvis-ui` / `08c3c17bbdf6e3a2e112ae2eedd371d755530cc0` | zuvor sauber; README in dieser Doku-Runde markiert |
| `Mobile-App` | `J.A.R.V.I.S-Mobile-App` / `a5b87137926c81e205e7036e1cd89150f43cb03f` | vorbestehendes `.gitignore` geändert und `.gitattributes` untracked; README in dieser Doku-Runde markiert |

Der angezeigte Tracking-Name ist nur lokaler Git-Status; es wurde kein Remote kontaktiert.

## Komponentenstatus (Kurzform)

| Teil | Status | Nachweisgrenze |
|---|---|---|
| Python Core / TaskPlanner / Router / Memory / People / Skills / Reminder / Tools | implemented | Codepfade vorhanden; Runtime und persistente Daten nicht geprüft |
| Console / Web / Continuous Voice | partial | getrennte Frontends mit unterschiedlichen Startpfaden; Live-/Audio-Abnahme offen |
| lokale LLM-, STT-, TTS- und MCP-Anbindungen | partial | Adapter/Config vorhanden; Dienste/Modelle nicht live geprüft; MCP-Serverkonfiguration auskommentiert |
| School/Mobility | experimental | uncommitteter Code, Skill, Doku und Tests; Live-Abnahme offen |
| Vocal Directions | experimental | uncommitteter Parser-/Pipelinecode und Probes; Hörfreigabe nicht belegt |
| Ruflo, ECC, Agency Agents, OpenClaw, LM Studio | not implemented / not evidenced | keine aktive Main-Runtime-Integration festgestellt |
| Android | partial | separates Repo; UI vorhanden, echte Runtime-/Trust-Bindungen offen |

Reifezustände folgen den Definitionen in [02_COMPONENTS.md](02_COMPONENTS.md). `planned`, `blocked` und `deprecated` werden nur bei konkreter Planungs-, Blocker- oder Ablöse-Evidenz verwendet.

## Angegebene School/Mobility-Testhistorie

Die Zahlen 600 Unit-Tests und bestandener 65-Minuten-DORMANT-Soak sowie der Stand des Live-Canarys am 24.09. (Exitcode 1), die Vorbereitung für 25.09. und die noch offene Live-Abnahme stammen aus dem vom Auftraggeber gelieferten Status. Sie wurden in dieser Dokumentationsrunde nicht erneut ausgeführt und sind daher **historisch berichtet, nicht unabhängig verifiziert**.

## Modellstatus (25.09.2026, nicht committet)

| Teil | Status | Nachweisgrenze |
|---|---|---|
| Gemma 4 12B Primary (Audio/Vision) | partial | Logik nur Unit-Test (Fakes); Integration nicht auf Hardware getestet; Unit-Namen/mmproj Platzhalter |
| Qwen3.5-35B-A3B Expert + GPU-Handover | partial | Ladezeit ca. 90-100 s gemessen; Handover nur mit Fake-`systemctl` getestet |
| NPU-Präsenz (buffalo_l) | partial | auf Dateieingabe belegt; Live-Kamera auf NPU und NPU-Wake-Word NOT_IMPLEMENTED |
| Vision-Gate | experimental | standardmäßig aus (`vision.presence.llm_gate.enabled: false`) |

Details: [03](03_RUNTIME_AND_MODELS.md), [13](13_KNOWN_ISSUES.md).
