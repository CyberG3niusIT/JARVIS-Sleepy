# Runtime und Modelle

## Im Code konfigurierte Integrationen

`config.yaml` setzt lokales LLM mit konfiguriertem llama.cpp-Pfad/Modellwert, einen kleinen lokalen Chat-Completions-Endpunkt, einen API-Provider, Qwen3-STT sowie Chatterbox-TTS. Piper/Kokoro-Optionen sind ebenfalls vorhanden, teils ausdrücklich inaktiv abhängig von `tts.engine`. Werte sind Konfiguration, kein Beleg installierter Modelle oder laufender Dienste.

## Prozess- und Netzwerkgrenzen

Konfiguration verwendet Loopback-Endpunkte für Modell-/TTS-Dienste; Systemd-Units und Startskripte beschreiben zusätzliche Prozesse. Der aktuelle Zustand dieser Prozesse wurde nicht abgefragt. Für School/Mobility ist der vom Auftrag beschriebenen lokalen VVS-API-Endpunkt `127.0.0.1:8088` vorgesehen; externe Health-/Readiness-Anfragen wurden nicht ausgeführt.

## Weitere externe Dienste

Quellmodule und Konfiguration zeigen Integrationspfade für Google Calendar (`core/google_calendar.py`), CalDAV (`core/caldav_calendar.py`), Wetter (`core/weather_poller.py`), News (`core/news_manager.py`), Web-Recherche (`core/web_research.py`), Nominatim-Reverse-Geocoding im Web-Frontend, optionale Bildgenerierung und MCP-Server. Welche davon in der Laufzeit tatsächlich aktiviert und erreichbar sind, ist nicht festgestellt. Der Mobility-Client akzeptiert HTTP(S)-Loopback-Adressen und folgt keinen Redirects.

Google Calendar, News und Weather sind in der geprüften YAML aktiviert. CalDAV ist dort deaktiviert; die Config kommentiert, dass das App-Passwort noch fehlt. Anthropic ist als Cloud-LLM-Provider konfiguriert. Diese Schalter sagen nichts über vorhandene Credentials, erfolgreiche Authentisierung oder Dienstgesundheit aus.

## LM Studio, llama.cpp und Cloud

llama.cpp ist über Konfigurations-/Serviceartefakte repräsentiert. Ein konkreter LM-Studio-Laufzeitpfad ist nicht nachgewiesen. Cloud-Provider-Einstellungen referenzieren Secret-Environment-Variablen; weder Werte noch Schlüssel sind Bestandteil der Doku. Cloud-Zugriff, Netzwerkpfad und Fallback-Verhalten müssen zur Laufzeit separat verifiziert werden.

## GPU und WSL

Skripte und Units enthalten Linux/WSL-/GPU-Betriebsannahmen. Die frühere Prüfung vom 22.09. meldete fehlende ROCm-Geräte im WSL-Kontext; dieser historische Stand ist nicht als Zustand am 24.09. bestätigt. Vor GPU-Abnahme aktuelle Geräteverfügbarkeit und echte Inferenz nachweisen.

## Modellarchitektur Stand 25.09.2026 (Primary / Expert / NPU / Output)

Evidenzklassen in diesem Abschnitt: **Hardware belegt** = auf echter Hardware gemessen/beobachtet; **nur Unit-Test (Fakes)** = Logik gegen Testdoubles; **NOT_IMPLEMENTED**. Die ältere Beschreibung oben (ein lokales LLM, Qwen3-STT) ist damit teilweise überholt.

| Schicht | Komponente | Config-Schlüssel / Port | Rolle | Status |
|---|---|---|---|---|
| PRIMARY | Gemma 4 12B über llama.cpp mit mmproj (Audio + Vision) | `llm.primary`, Port 8080 | Standardantwort, nimmt Audio direkt entgegen | Integration nur Unit-Test (Fakes); das `input_audio`-Schema von llama.cpp wurde vom Nutzer in einem früheren manuellen Test auf echter Hardware als funktionierend bestätigt, die JARVIS-Integration selbst ist **nicht** auf Hardware getestet |
| EXPERT | Qwen3.5-35B-A3B | `llm.expert`, Port 8082, GPU-exklusiv | nur bei Eskalation (siehe [04](04_AGENTS_AND_ORCHESTRATION.md)) | Ladezeit ca. 90-100 s, pro Phase in den Lifecycle-Records gemessen (Hardware belegt, nicht optimiert); Handover-Logik nur mit Fake-`systemctl` getestet |
| SENSOR | NPU-Schicht (`npu_sensor`) | - | Präsenzerkennung | Präsenz real: buffalo_l det/rec auf der Intel NPU auf Dateieingabe belegt; Live-Kamera auf NPU und NPU-Wake-Word = **NOT_IMPLEMENTED**; Identitätsschwelle nicht kalibriert |
| OUTPUT | Chatterbox TTS | wie bisher | Sprachausgabe | unverändert |

Grundregel: Gemma und Qwen sind **nie gleichzeitig** im GPU-Speicher. Gemma 12B + Chatterbox parallel im VRAM ist nicht verifiziert.

### GPU-Handover-Lebenszyklus

Ablauf beim Wechsel Primary -> Expert (und zurück) über User-Scope-systemd-Units (`JARVIS_LLM_UNIT`, `handover.*`, siehe `Main/docs/RUNTIME_SUPERVISOR.md`):

1. Primary stoppen und Beendigung/Freigabe der GPU abwarten,
2. Expert starten und auf Health warten (Ladephase, ca. 90-100 s),
3. Anfrage an Expert beantworten,
4. Expert stoppen, Primary im Hintergrund wiederherstellen.

Jede Phase wird mit Zeitstempel in einem Lifecycle-Record festgehalten; die Reihenfolge stellt sicher, dass nie beide Modelle resident sind. Nach außen erscheint der Wechsel als `STARTING` (siehe [16](16_UI_CONTROL_HUB.md)). Nachgewiesen nur mit Fake-`systemctl` (`test_model_handover.py`, `test_expert_handover_integration.py`); Eigentümer-Prüfungen (FragmentPath/ExecStart/Port-Besitzer) existieren in `start.sh`, **nicht** im Python-Handover.

### Veraltet: `core/gpu_swap.py`

`core/gpu_swap.py` ist **stale**: nutzt System-Scope-`sudo` und kennt nur FLUX. Es gehört nicht zum neuen Handover. `/api/gpu-status` hängt noch daran und zeigt daher nicht den Primary/Expert-Zustand.

### Unit-Dateien

`systemd/llama-server-primary.service` und `llama-server-expert.service` sind User-Scope-Vorlagen; Gemma-/mmproj-Dateinamen und Port 8082 sind Platzhalter (NEEDS HW VERIFY). Der Nutzer muss die Units selbst installieren; die tatsächlich laufende Unit liegt außerhalb des Repos. Details: `Main/systemd/README.md`.

### Vision-Gate (`core/vision_gate.py`)

Leitet pro DETECTED-Präsenzereignis genau **einen** In-RAM-Frame an Primary weiter. Standardmäßig aus (`vision.presence.llm_gate.enabled: false`), Cooldown 120 s. Privacy-Gates: WEBCAM_CAPTURE und PROACTIVE_OBSERVATION (CLOUD_LLM bei Cloud-Route: noch nicht verdrahtet). Keine Persistenz. Das MOTION-Event wird noch nicht emittiert. `get_status()` liefert `npu_sensor` und `vision_gate`. Nur per Unit-Test (`test_vision_gate.py`) belegt.
