# JARVIS Sleepy

> Zentrale technische Dokumentation: [JARVIS Sleepy Dokumentation](../Dokumentation/README.md). Die folgenden Hardware-, Modell- und Runtime-Angaben stammen aus einem früheren Snapshot; aktuellen Entwicklungsstand bitte gegen Code, Konfiguration und [Git-Status](../Dokumentation/00_PROJECT_STATUS.md) prüfen.

Lokaler Sprachassistent für Windows 11 mit Ubuntu 24.04 unter WSL2, AMD ROCm, lokalem LLM, deutscher Spracherkennung und Windows-Steuerung.

Dieses Repository enthält den aktuellen Sleepy-Stand meiner JARVIS-Anpassung. Die Basis stammt aus `InterGenJLU/jarvis`, wurde aber für meinen Windows- und WSL2-Stack deutlich umgebaut.

Es gibt hier bewusst keine eingebetteten Demo-Videos, Audioaufnahmen oder externen Medienlinks. Die README beschreibt nur den tatsächlich verwendeten Stand.

## Aktueller Stand

Der erste funktionierende Sicherungspunkt ist als Tag vorhanden:

```text
sleepy-jarvis-working-v1
```

Der zugehörige Stand umfasst unter anderem:

- Windows 11 als Hostsystem
- Ubuntu 24.04 unter WSL2
- systemd in WSL2
- funktionierendes WSLInterop für Windows-Programme
- AMD RX 7900 XTX mit ROCm
- lokales Qwen3.5 LLM über llama.cpp
- deutsches Qwen3-ASR über sherpa-onnx
- Whisper als möglicher Fallback
- deutsche Piper-TTS
- deutsches semantisches Matching
- deutsche Persona- und Antwortanpassungen
- Windows-App-Start aus JARVIS heraus
- lokale Daten-, Modell- und Cachepfade außerhalb des Git-Repositories

## Hardware des aktuellen Builds

```text
CPU:  Intel Core Ultra 5 245K
GPU:  AMD Radeon RX 7900 XTX 24 GB
RAM:  32 GB DDR5
OS:   Windows 11 Pro for Workstations
WSL:  Ubuntu 24.04
```

Der Code kann grundsätzlich auch auf anderer Hardware laufen. Dieser Branch wird aber primär auf genau diesem System entwickelt und getestet.

## Architektur

Der aktuelle Voice-Pfad sieht vereinfacht so aus:

```text
Mikrofon
   |
   v
VAD / Continuous Listener
   |
   v
Qwen3-ASR 0.6B INT8
sherpa-onnx
Hotwords: Jarvis, Hey Jarvis
   |
   v
Wakeword-Prüfung
   |
   v
Intent / Skill / Tool Routing
   |
   +--> lokales Qwen3.5 LLM über llama.cpp
   |
   +--> Windows-Steuerung über WSLInterop
   |
   v
Piper TTS
   |
   v
WSLg / PulseAudio
```

## Sprachmodell

Das lokale LLM läuft über `llama.cpp` als persistenter Server.

Aktuell verwendet:

```text
Qwen3.5-35B-A3B-abliterated-Q3_K_M.gguf
```

Der llama.cpp-Server läuft lokal auf:

```text
127.0.0.1:8080
```

Die Modellgewichte selbst liegen nicht im Git-Repository.

## Spracherkennung

Für den deutschen Voice-Betrieb wird derzeit Qwen3-ASR über sherpa-onnx verwendet.

Aktuelles Modell:

```text
sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25
```

Die Hotwords sind derzeit:

```text
Jarvis,Hey Jarvis
```

Das war für diesen Build deutlich zuverlässiger als Whisper Base bei der Erkennung des Eigennamens "Jarvis".

Qwen3-ASR läuft in der aktuellen sherpa-onnx-Integration auf der CPU. Der Recognizer wird beim Start einmal geladen und anschließend wiederverwendet.

## TTS

Die aktuelle deutsche Sprachausgabe verwendet Piper.

Modellpfad im aktuellen System:

```text
/home/alex/jarvis-data/models/piper/jarvis-de-high/
```

Die Stimme ist vorerst eine funktionierende Zwischenlösung und noch nicht als endgültige JARVIS-Stimme festgelegt.

## Windows-Integration

Windows-Programme werden aus WSL2 über WSLInterop gestartet.

Aktuell funktionieren unter anderem:

```text
Explorer
Chrome
Microsoft Edge
VS Code
Windows Terminal
PowerShell
cmd
Editor
Rechner
Windows Einstellungen
```

Die ursprüngliche Desktop-Steuerung des Upstream-Projekts ist stark auf GNOME ausgelegt. Vollständige Windows-Fenstersteuerung wie Minimieren, Maximieren, Schließen, Fokuswechsel und Lautstärkesteuerung ist noch nicht vollständig portiert.

## Start

Virtuelle Umgebung aktivieren:

```bash
cd /home/alex/jarvis
source /home/alex/jarvis-venv/bin/activate
```

Textkonsole:

```bash
python jarvis_console.py
```

Voice-Modus:

```bash
python jarvis_console.py --speech
```

Hybrid-Modus:

```bash
python jarvis_console.py --hybrid
```

## Lokaler llama.cpp-Server

Der lokale LLM-Server wird als systemd-User-Service betrieben.

Status prüfen:

```bash
systemctl --user status llama-server.service
```

Starten:

```bash
systemctl --user start llama-server.service
```

Stoppen:

```bash
systemctl --user stop llama-server.service
```

Logs:

```bash
journalctl --user -u llama-server.service -f
```

## Verzeichnisstruktur

Wichtige Pfade des aktuellen Builds:

```text
/home/alex/jarvis
    Git-Repository und Quellcode

/home/alex/jarvis-venv
    Python-Umgebung für JARVIS

/home/alex/qwen3-asr-venv
    separate Testumgebung für sherpa-onnx / Qwen3-ASR

/home/alex/jarvis-data
    Modelle, Datenbanken, Cache, Logs und Laufzeitdaten

/home/alex/llama.cpp
    lokal gebautes llama.cpp
```

## Daten und Secrets

Modelle, Audiodateien, Datenbanken, Logs, lokale Backups und `.env` werden nicht in Git eingecheckt.

API-Keys und Auth-Tokens gehören ausschließlich in `.env` oder andere lokale Secret-Stores.

Beispiel:

```text
JARVIS_WEB_AUTH_TOKEN=...
ANTHROPIC_API_KEY=...
PORCUPINE_ACCESS_KEY=...
```

Die Datei `.env` ist über `.gitignore` ausgeschlossen.

## Noch nicht vollständig portiert

Der aktuelle Stand funktioniert bereits als lokaler deutscher Voice-Assistent, ist aber noch kein abgeschlossener Windows-Port.

Noch offen oder nur teilweise umgesetzt sind insbesondere:

- vollständige Windows-Fenstersteuerung
- weitere GNOME-spezifische Funktionen ersetzen
- einzelne englische Skill-Ausgaben vollständig eindeutschen
- Reminder-Parser für natürliches Deutsch erweitern
- finale deutsche JARVIS-Stimme
- weitere Tests für Wakeword und Umgebungsgeräusche
- allgemeine Installation auf einem frischen Windows-System vereinfachen

## Git-Struktur

Dieses Repository ist der eigene Entwicklungsstand:

```text
origin
https://github.com/CyberG3niusIT/JARVIS-Sleepy.git
```

Das ursprüngliche Projekt bleibt als Upstream eingebunden:

```text
upstream
https://github.com/InterGenJLU/jarvis.git
```

Dadurch können spätere Änderungen des Originalprojekts verglichen oder gezielt übernommen werden, ohne den Sleepy-Branch zu überschreiben.

## Wiederherstellungspunkt

Der erste stabile Voice-Stand ist markiert mit:

```bash
git checkout sleepy-jarvis-working-v1
```

Oder als neuer Branch:

```bash
git switch -c restore-sleepy-v1 sleepy-jarvis-working-v1
```

## Herkunft und Lizenz

Dieses Projekt basiert auf `InterGenJLU/jarvis` und enthält eigene Anpassungen für Windows 11, WSL2, deutsche Sprachverarbeitung, Qwen3-ASR, Piper-TTS und die aktuelle Sleepy-Systemarchitektur.

Die Lizenz des ursprünglichen Projekts bleibt erhalten. Siehe `LICENSE`.
