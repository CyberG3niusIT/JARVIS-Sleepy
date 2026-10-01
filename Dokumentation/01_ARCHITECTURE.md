# Architektur

## Systemgrenzen

Das aktive Python-Projekt befindet sich in `Main`. Einstiegspunkte sind `jarvis_console.py`, `jarvis_continuous.py` und `jarvis_web.py`. Der Core ist in `core/` organisiert; Skills liegen in `skills/`, zusätzliche Server/Adapter in `tools/` und `services/`. Mobile-App unter `../Mobile-App/` ist ein separates Repository, keine nachgewiesene Laufzeitkopplung.

Die drei Einstiegspunkte haben unterschiedliche Initialisierung: Continuous baut Voice-/Eventpfad und konfigurierte Hintergrunddienste auf; Console nutzt den Core im Text-/Konsolenbetrieb; Web ergänzt HTTP/WebSocket-Routen, Health-/Event-Komponenten und Beobachtungsfunktionen. Nicht jede Komponente wird von jedem Frontend gestartet.

## Verbindliche Owner-Sprache

Owner-facing natural language defaults to German (de-DE). JARVIS-eigene natürliche Antworten, Startup-Ansagen, Bestätigungen und Fehler sind standardmäßig ausschließlich deutsch. Eine andere Ausgabesprache ist nur auf ausdrücklichen Wunsch in der aktuellen Anfrage erlaubt. Englische Eingaben bleiben verständlich; technische Identifikatoren, API-Felder, Dateinamen und genaue fremde Zitate bleiben unverändert.

Die bestehende Persona enthält `DEFAULT_LANGUAGE = "de-DE"` und `OWNER_LANGUAGE_RULE`. Alle effektiven Persona-Prompts und die relevanten Chat-, Planner-, Tool-Continuation- und Readback-Kontexte verwenden diese Regel. Deterministische Ausgaben werden direkt deutsch formuliert. Es gibt keine Sprachdetektor- oder nachträgliche Übersetzungsschicht und keinen zusätzlichen Modellaufruf zur Übersetzung. Privacy-, Authorization- und Confirmation-Gates gelten unverändert.

## Daten- und Kontrollfluss

```text
Mikrofon -> VAD/Wake word -> STT -> Pipeline/Event Queue
    -> ConversationRouter -> direkte Routen / Skill / Tool / TaskPlanner / LLM
    -> Antwortaufbereitung -> TTS -> Audiowiedergabe

Console/Web -> gemeinsame Router-/Core-Komponenten
School-Ereignis -> ReminderManager-Scheduler -> Mobility-Demand/Provider
```

Die konkrete Auswahl hängt an `config.yaml`, Umgebungsvariablen und erreichbaren Prozessen. Das Diagramm ist Codefluss, keine Aussage über aktuell laufende Infrastruktur.

## Zentrale Bausteine

- `core/pipeline.py`: Ereignisverarbeitung und Voice-/Antwortkoordination.
- `core/conversation_router.py`: priorisierte Intent- und Fähigkeitsrouten.
- `core/task_planner.py`: Zerlegung und Ausführung zusammengesetzter Aufgaben.
- `core/skill_manager.py`, `core/tool_registry.py`, `core/tool_executor.py`: Skill-/Tool-Erkennung und Ausführung.
- `core/memory_manager.py`, `core/context_window.py`, `core/interaction_cache.py`: persistente Fakten-/Konversations- und Arbeitskontexte.
- `core/people_manager.py`, `core/reminder_manager.py`, `core/observation_collector.py`: Personen-, Reminder- und Beobachtungsfunktionen.
- `core/mcp_client.py`: MCP-Bridge; konkrete Server hängen von Konfiguration ab.
- `core/stt*.py`, `core/tts.py`, `core/continuous_listener.py`: Sprachpfad.
- `jarvis_web.py`, `jarvis_console.py`: weitere Frontends.

## Modell- und Prozessgrenzen

`core/llm_router.py` und `core/llm_server_client.py` bilden Modellzugriff ab. Konfiguration nennt lokale llama.cpp-kompatible Endpunkte und einen API-Provider; `tools/chatterbox_server.py` ist ein separater TTS-Prozess. Modelldateien und Datenbanken sind externe Runtime-Ressourcen. LM Studio ist in der aktuellen aktiven Konfiguration nicht als konkret gebundener Dienst nachgewiesen. Windows/WSL-Betriebsskripte existieren; erfolgreicher Interop-/GPU-Betrieb ist hier nicht geprüft.

`LLMRouter` ist der in Console, Web und Voice konstruierte Router. Seine lokale Anfrage nutzt einen localhost Chat-Completions-Endpunkt; Anfragen an das kleine Modell verwenden einen separat konfigurierten Endpoint; Cloud-Aufrufe nutzen den konfigurierten Provider. `core/llm_server_client.py` existiert, aber ein Aufrufpunkt im geprüften Python-Quellbaum wurde nicht gefunden. `llama_cli`-/`llama_completion`-Konfigurationswerte belegen daher nicht, dass der Router diesen Binary-Pfad verwendet.

## Windows/WSL und Audio

Die YAML-Konfiguration kombiniert Pulse-Eingabe/-Ausgabe, einen Windows-Audio-Ausgabepfad und einen Windows-Temp-Pfad. Audio-Device-Auflösung ist in Audio-/TTS-Code enthalten; Windows-Programme können über WSLInterop gestartet werden. Das beschreibt eine gemischte OS-Grenze, nicht den aktuellen Interop-/Hardwarezustand.

## Externe Dienste

Quellmodule/Config enthalten Integrationspfade für Google Calendar, CalDAV, Weather, News, Web-Recherche, Nominatim im Webfrontend, optionale Bildgenerierung, MCP und den lokalen VVS-Client. Erreichbarkeit und Aktivierung sind je Dienst unbestätigt. Der Mobility-Client akzeptiert nur HTTP(S)-Loopback-Adressen und folgt keinen Redirects.

## Erweiterte Agents

Im Repository wurde keine belastbare aktive Integration für Ruflo, ECC, Agency Agents oder OpenClaw gefunden. Sie sind externe Entwicklungswerkzeuge bzw. offene Integrationsfragen, keine JARVIS-Runtime-Komponenten.

Siehe auch [Komponentenregister](COMPONENTS/README.md), [Runtime und Modelle](03_RUNTIME_AND_MODELS.md) und [Agents](04_AGENTS_AND_ORCHESTRATION.md).
