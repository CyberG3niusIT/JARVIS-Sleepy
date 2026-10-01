# JARVIS Main (Python-Backend)

Produktiver Backend-Worktree von **J.A.R.V.I.S / JARVIS Sleepy**.

Übergeordnete Regeln aus `../CLAUDE.md` gelten zusätzlich.

JARVIS ist ein zusammenhängendes technisches System. Änderungen immer im Kontext der bestehenden Runtime, Architektur, Governance und angrenzenden Komponenten betrachten.

Aktuellen Branch, HEAD, Worktrees, Modelle, Ports, Services und Runtime-Zustände **immer live ermitteln**. Angaben aus älteren Dokumenten, Übergaben oder früheren Agentenläufen sind keine Source of Truth.

## Layout

Vor relevanten Arbeiten zuerst:

```powershell
git status --short --branch
git rev-parse HEAD
git worktree list
```

Worktree- und Branch-Zuordnungen können sich ändern und werden daher nicht dauerhaft in dieser Datei festgeschrieben.

| Bereich | Zweck |
|---|---|
| Main | Produktiver Python-Backend- und Runtime-Code |
| UI | Desktop-/WinUI-Arbeiten, falls als eigener Worktree vorhanden |
| Mobile-App | Mobile Client, falls als eigener Worktree vorhanden |
| weitere Worktrees | Zweck und Branch immer über `git worktree list` und Git ermitteln |

Keine Änderungen anderer Worktrees oder Agenten ungefragt übernehmen, verwerfen oder zurücksetzen.

Ein schmutziger Working Tree ist kein Auftrag zum Aufräumen.

Unbekannte Änderungen zuerst verstehen.

## WSL-Aufruf

- Immer explizit `wsl.exe -d Ubuntu-24.04` verwenden. Nicht auf die Default-Distro vertrauen.
- Projektpfade zwischen Windows und WSL real prüfen.
- Für Python-Tests ist die etablierte Umgebung WSL mit `/home/alex/jarvis-venv/bin/python3`. Windows-Python ist nicht der vorgesehene pytest-Pfad.
- Git für Windows-Worktrees mit Windows-Git verwenden. Git nicht unnötig aus WSL gegen einen Windows-Worktree ausführen.
- Bei Git-Bash für WSL-Pfade `MSYS_NO_PATHCONV=1` verwenden, wenn Pfadkonvertierung sonst in die Argumente eingreift.
- Historischen Linux-Code nicht automatisch als Windows-/WSL-tauglich behandeln.
- Keine Pakete oder Systemkomponenten installieren, nur um einen Test schnell zum Laufen zu bringen.

## Gezielte Tests

Gezielte Tests vor breiten Suites bevorzugen.

Bestehende Wrapper verwenden, wenn sie für den aktuellen Stand noch gültig sind, zum Beispiel:

```powershell
scripts\wsl-pytest.ps1 <testdateien>
```

Direkter WSL-Aufruf nur mit explizitem Projektpfad und Interpreter.

Beispiel für den etablierten direkten Pfad:

```text
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -c 'cd /mnt/c/Users/Alex/Projekte/JARVIS-Sleepy/Main && /home/alex/jarvis-venv/bin/python3 -m pytest <dateien> -q -p no:cacheprovider'
```

`-All` beim Test-Wrapper nur bewusst verwenden. Es kann `tests/unit` und `tests/routing` starten; Routing-Tests können Modelle beziehungsweise Torch laden und entsprechend langsam oder ressourcenintensiv sein.

Vor breiten Testläufen prüfen, ob sie:

- Modelle laden
- GPU oder Hardware beanspruchen
- Netzwerkzugriffe ausführen
- externe Dienste ansprechen
- produktive Daten verändern
- lange Laufzeiten verursachen

Keine Vollsuite blind starten.

Tests niemals löschen, abschwächen oder skippen, nur damit eine Änderung grün wird.

Nicht ausgeführte Tests als **nicht getestet** beziehungsweise **nicht verifiziert** melden.

Plausibler Code ist kein bestandener Test.

Unit, Regression, Integration, Runtime, Windows, WSL, Hardware, Voice, E2E und Long-Run immer unterscheiden.

## Runtime

Der produktive JARVIS-Lifecycle gehört der vorhandenen Windows-Control-Plane.

Primärer Einstieg:

```powershell
.\JARVIS-Runtime.ps1 -Action getRuntime
.\JARVIS-Runtime.ps1 -Action start
.\JARVIS-Runtime.ps1 -Action stop
.\JARVIS-Runtime.ps1 -Action restart
```

Unterstützte Parameter vor Verwendung am aktuellen Code prüfen.

Der Windows-Runtime-Supervisor besitzt auch den WSL-Keepalive. JARVIS deshalb **nicht** direkt mit einem isolierten `wsl ... start.sh` starten. Ein solcher Direktstart kann den User-systemd-Lifecycle verlieren, sobald die WSL-Session endet. Start, Stop und Restart immer über `JARVIS-Runtime.ps1`.

Nicht einzelne JARVIS-Services ad hoc starten, stoppen oder killen, wenn der Runtime-Supervisor zuständig ist.

Insbesondere nicht auf Verdacht:

```text
kill -9
pkill
taskkill
wsl --terminate
```

`accepted=true` bedeutet nur, dass eine Lifecycle-Aktion angenommen wurde. Danach den tatsächlichen Zustand über `getRuntime` prüfen.

Eine laufende READY-Runtime während Source- und Unit-Arbeiten nicht unnötig stören.

Wenn geänderter Python-Code von bereits laufenden Prozessen verwendet wird, gilt:

```text
Code geändert != Live-Code geladen
```

Ein notwendiger Restart erfolgt kontrolliert über die Runtime-Control-Plane.

Logs für den Voice-/Backend-Daemon:

```powershell
wsl.exe -d Ubuntu-24.04 --exec journalctl --user -u jarvis.service -n 100 --no-pager
```

Live:

```powershell
wsl.exe -d Ubuntu-24.04 --exec journalctl --user -f -o short-iso-precise -u jarvis.service
```

Andere Service-Namen und Units immer am aktuellen System ermitteln.

## Architektur (Kurz)

- JARVIS bleibt **Local First**, modular, testbar, beobachtbar und fehlertolerant.
- Backend und Runtime sind Source of Truth. Clients dürfen Zustände nicht erfinden.
- Deterministische APIs, Skills, Tools und Betriebssystem-Schnittstellen haben Vorrang vor generativer Automation.
- Agenten und LLMs werden dort eingesetzt, wo Planung, Flexibilität oder Mehrschrittlogik benötigt wird.
- Provider-spezifische Implementierungen gehören hinter klare Adapter beziehungsweise Interfaces.
- Der Core soll nicht unnötig an Claude, Anthropic, OpenAI oder andere einzelne Provider gekoppelt werden.
- Neue Integrationen sollen vorhandene Capability-, Tool-, Skill-, Provider- oder Registry-Pfade wiederverwenden, bevor neue Infrastruktur entsteht.
- Self Extension bedeutet neue Adapter, Provider und Capabilities. Es bedeutet **keine Self Modification der Governance**.
- Neue Fähigkeiten dürfen niemals selbstständig Privacy, Security, Permissions, Tool-Gates oder Governance erweitern.
- Computer Control bevorzugt stabile semantische Schnittstellen. Native API, Betriebssystem-API, PowerShell, UI Automation und Browser Automation haben Vorrang vor visuellem Computer Use.
- Memory Learning ist keine Berechtigung zur Code-, Policy- oder Rechteänderung.
- Experimente vom produktiven Pfad trennen.

Konkrete Modelle, Ports, Service-Namen und Entwicklungsstände gehören nicht als dauerhafte Annahmen in diese Datei. Sie sind live beziehungsweise aus aktueller Konfiguration zu ermitteln.

## Regeln

- Antworten und technische Berichte auf Deutsch. Code, APIs, Dateinamen und Commit-Messages dürfen Englisch bleiben.
- Vor Codeänderungen zuerst Problem, Root Cause, Call-Sites, bestehende Architektur, Config/Gates und relevante Tests prüfen.
- Kleinste saubere Änderung bevorzugen. Keine Nebenrefactorings.
- Funktionierende Logik nicht nur aus Eleganzgründen ersetzen.
- Vor neuer Implementierung prüfen, ob geeigneter Code, Skill, Tool, Adapter, Provider, ADR oder früherer verworfener Ansatz bereits existiert.
- Keine Doppelimplementierungen.
- Keine Änderung an `.env`, `config.yaml`, Credentials, Secrets, Firewall, WSL-Konfiguration oder systemd-Units ohne ausdrückliche Notwendigkeit und Freigabe.
- Privacy-Gates niemals umgehen.
- Audio, Transkripte, Screens, Webcam, Clipboard, Memory-Inhalte oder Secrets nicht ungegatet persistieren oder loggen.
- Bei fehlender oder fehlerhafter Privacy-/Permission-Prüfung für sensitive Writes grundsätzlich fail closed.
- Confirmation ersetzt keine Authorization. Authorization ersetzt keine Privacy-Prüfung.
- Keine vereinfachte parallele Confirmation-Logik bauen, wenn ein zentraler Vertrag existiert.
- Keine Substring-Heuristiken für sicherheitsrelevante Zustimmung.
- Keine neue Dependency ohne Prüfung vorhandener Lösungen, Lizenz, Wartungsstatus, Windows/WSL-Support, Security und Offline-Fähigkeit.
- Keine produktionsnahen Fake-Daten oder Fake-Telemetrie.
- Keine erfundenen Test-, Runtime- oder Hardwareergebnisse.
- Keine Commits oder Pushes ohne ausdrücklichen Auftrag.
- Kein Pull, Merge, Rebase, Reset, Clean, Stash, Branchwechsel, History-Rewrite oder Force-Push ohne ausdrückliche Freigabe.
- Keine Änderungen anderer Entwickler oder Agenten verwerfen.
- Keine automatische Änderung von Git-Autor, E-Mail oder Commit-Metadaten.
- Keine `Co-Authored-By`-Einträge für Claude, Anthropic oder andere Agenten.
- Keine Agentenbranches, Agenten-Tags oder Agenten-Metadaten erzeugen, sofern dies nicht ausdrücklich verlangt wird.
- Claude ist Entwicklungswerkzeug und **kein Bestandteil des Produkts**.
- Keine Kommentare wie `Generated by Claude`, `Claude fix`, `AI generated`, `implemented by Claude` oder ähnliche Autorenmarker.
- Keine Klassen, Dateien, Helper, TODOs, Logs oder UI-Bezeichnungen nach Claude benennen, nur weil Claude sie erstellt hat.
- Keine versteckten Agentenmarker oder Autoreninformationen im Code.
- Keine Claude-spezifische Pflichtabhängigkeit in generische Core-Komponenten einbauen.
- Wenn Claude später als Provider benötigt wird, muss dies ein klar abgegrenzter optionaler Provider sein.
- Code muss nach Abschluss wie normaler JARVIS-Projektcode aussehen und ohne Wissen über den erzeugenden Agenten verständlich sein.
- Keine dauerhafte Agenten-Infrastruktur nur deshalb einbauen, damit Claude seine eigene Arbeit leichter fortsetzen kann.
- Generierter Code besitzt keinen Sonderstatus. Er muss dieselben Architektur-, Security- und Testanforderungen erfüllen wie manuell geschriebener Code.
- Generierten Integrationscode nicht ungeprüft direkt in einen produktiven Pfad aktivieren.
- Neue Security-/Privacy-Befunde außerhalb des Auftrags dokumentieren statt nebenbei zu reparieren, außer es besteht unmittelbare Gefahr für Secrets oder Datenintegrität.
- Wenn eine Änderung einen nachweislich guten Zustand verschlechtert: stoppen, letzten guten Zustand identifizieren, Ursache bestimmen, dann erst weiterarbeiten.
- Keine Fix-on-Fix-Ketten.
- Keine Behauptungen wie `fertig`, `funktioniert`, `getestet`, `verifiziert` oder `produktionsreif`, wenn der behauptete Umfang nicht belegt ist.

## Arbeitsweise

Source of Truth:

```text
1. reale Runtime
2. aktueller Repository-Inhalt
3. aktueller Git-Stand und Konfiguration
4. reale Tests und Messwerte
5. aktuelle zentrale Dokumentation
6. ältere Dokumentation, Handoffs und Agentenberichte
```

Vor relevanten Änderungen:

```text
1. Zustand prüfen
2. Problem reproduzieren oder nachvollziehen
3. Root Cause bestimmen
4. bestehende Implementierung und Call-Sites prüfen
5. Konfiguration und Gates prüfen
6. Tests prüfen
7. kleinsten sauberen Fix festlegen
8. gezielt implementieren
9. gezielt testen
10. relevante Regression prüfen
11. Runtime-/Hardware-/E2E-Grenze klar benennen
12. Dokumentation aktualisieren, wenn erforderlich
```

Wenn die nächste Handlung eindeutig und reversibel ist, weiterarbeiten.

Nur bei echter Entscheidung, Sicherheitsgrenze, irreversibler Aktion oder nicht ermittelbarem Fakt nachfragen.

Keine Annahme als Fakt darstellen.

Relevante Aussagen in Berichten bei Bedarf mit:

```text
[Sicher]
[Wahrscheinlich]
[Vermutung]
[Unverifiziert]
```

kennzeichnen.

## Agenten und Subagenten

Subagenten nur mit klar begrenztem:

```text
Ziel
Kontext
Tools
Rechten
Budget
Timeout
Privacy-Kontext
Abbruchbedingungen
```

verwenden.

Subagenten dürfen niemals mehr Rechte als der aufrufende Kontext besitzen.

Keine parallelen Änderungen an denselben Dateien, wenn Konflikte entstehen können.

Subagenten dürfen Governance-, Privacy- oder Tool-Gates nicht umgehen.

Ein Agent darf keine neue dauerhafte Agentenplattform in JARVIS einbauen, nur um seine eigene Tätigkeit zu unterstützen.

## Integrationen

Neue Integrationen zuerst gegen bestehende Architektur prüfen.

Bevorzugte Reihenfolge:

```text
bestehender JARVIS Adapter
offizielle lokale API
offizielle Remote API
standardisiertes Protokoll
MCP
offizielles CLI
Windows-/OS-Schnittstelle
PowerShell / WMI / CIM
Windows UI Automation
Browser Automation
visuelles Computer Use als Fallback
```

Integrationen sollen Capabilities deklarieren statt Core-Logik mit Provider-Sonderfällen zu füllen.

Beispiel:

```text
calendar.read
calendar.create
filesystem.read
filesystem.write
desktop.application.launch
```

Eine Integration darf neue Fähigkeiten hinzufügen.

Sie darf nicht selbst:

```text
Governance ändern
Privacy abschalten
Permissions erweitern
Adminrechte beschaffen
Cloud aktivieren
OAuth-Scopes eigenmächtig erweitern
Secrets umgehen
Security Policies lockern
```

Capability Growth ist nicht Permission Growth.

## Abschlussprüfung

Vor Abschluss jeder relevanten Änderung prüfen:

```text
Ziel erfüllt?
Root Cause behoben?
bestehende Architektur erhalten?
fremde Änderungen erhalten?
Tests ausgeführt?
Regression geprüft?
Runtime relevant?
Windows/WSL relevant?
Hardware relevant?
Privacy relevant?
Security relevant?
Memory relevant?
Dokumentation relevant?
offene Risiken benannt?
```

Nicht ausgeführte Prüfungen ausdrücklich nennen.

## Doku-Zuordnung (`../Dokumentation/`)

Vor Änderung der Dokumentation prüfen, ob die aufgeführten Dateien noch die aktuelle zentrale Dokumentationsstruktur darstellen.

| Änderung | Datei |
|---|---|
| Komponenten/Architektur | `01_ARCHITECTURE.md`, `02_COMPONENTS.md` |
| Runtime, Modelle, Handover, systemd | `03_RUNTIME_AND_MODELS.md` |
| Voice/STT/TTS/Turns | `06_VOICE_STT_TTS.md` |
| Tools/MCP/Skills/Integrationen | `07_TOOLS_MCP_SKILLS.md` |
| Privacy/Security | `09_SECURITY_PRIVACY.md` |
| Config-Schlüssel | `10_CONFIGURATION.md` |
| Installation/Betrieb | `11_INSTALLATION_OPERATION.md` |
| Tests | `12_TESTING_QA.md` |
| Bekannte Probleme | `13_KNOWN_ISSUES.md` |
| Changelog/Entwicklungsstand | `15_CHANGELOG_DEVELOPMENT.md` |
| Tooling/GitHub | `17_TOOLING_UND_GITHUB.md` |

Veraltete Dokumentation nicht als aktuellen Systemzustand übernehmen.

## Leitsatz

JARVIS soll durch deine Arbeit leistungsfähiger werden, aber nicht stärker von Claude abhängig.

Wenn eine generische stabile Lösung möglich ist, darf die Implementierung deine eigene Existenz als Agent später nicht benötigen.
