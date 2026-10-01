# Entrypoints, Dienste und Audio-Grenzen

## Startup-Komposition

| Einstieg | Code-gebundene Komponenten | Nicht ableitbar |
|---|---|---|
| `jarvis_continuous.py` | STT-Auswahl, ConversationManager, LLMRouter, TTS/Audio, SkillManager, optional MCP, Memory/Context, Reminder-/Awareness-/Hintergrundkomponenten | dass benötigte Geräte, Server oder DBs aktuell verfügbar sind |
| `jarvis_console.py` | ConversationManager, LLMRouter, SkillManager, TaskPlanner, optional MCP, Reminder-/Kalenderpfad | dass Terminalmodus zugleich den Voice-Poller startet |
| `jarvis_web.py` | HTTP/WebSocket, ConversationManager, LLMRouter, SkillManager, Reminder, News/Weather, Memory/Context, Metrics/EventLogger, Health snapshots, ObservationCollector, TaskPlanner | dass jede Console-/Voice-Funktion gleich implementiert ist |

Der Web-Reminder-Manager wird im Web-Modus für explizite Aufrufe bereitgestellt, aber seine Hintergrundpolling-Schleife wird dort laut Code nicht gestartet; Voice behandelt Reminder-Polling. Calendar-, Weather-, News- und Memory-Pfade werden einzeln anhand ihrer Konfigurationsflags initialisiert.

## Voice und WSL

Der Continuous-Pfad unterstützt konfigurierbares STT und koppelt Mic-Ingest, VAD/Wakeword, Pipeline und TTS. Die YAML nutzt PulseAudio-Input/Output und enthält Windows-Audio-/Temp-Optionen. TTS-Code löst Linux-Audiogeräte auf; Windows-Programme können über WSLInterop gestartet werden. Reale Audiohardware und WSLInterop wurden nicht getestet.

## Port- und Laufzeitgrenzen

`config.yaml` verwendet `web.port: 8088` als Default. Der Mobility-Einsatzwert nennt ebenso `127.0.0.1:8088` für den separaten lokalen VVS-Dienst. Wenn beide Prozesse im selben Netzwerk-Namespace lauschen, können sie nicht beide denselben Socket belegen. Aktuelle Overrides und Namespaces sind offen; siehe [Known Issues](../13_KNOWN_ISSUES.md).

Systemd-Dateien und Startskripte dokumentieren gewünschte Prozessstarts. Installierte Units, laufende Prozesse, Secrets und API-Health wurden nicht geprüft.
