# Desktop Redesign / Lovable Handoff

## Ziel

Die Desktop-Anwendung wird neu aufgebaut. Die bisherige Desktop-UI ist keine visuelle Source of Truth. Lovable erhält aktuelle Backend-/Architektur-Dokumentation plus ausgewählte Designreferenzen.

## Designrichtung

Professionelles dunkles Desktop-Control-Center mit J.A.R.V.I.S.-Branding, präziser technischer Typografie, zurückhaltendem Blau/Cyan und klaren Statusfarben. Kein generisches Sci-Fi-HUD, keine erfundene Telemetrie, keine Gaming-Optik.

## Geplante Hauptseiten

1. **Home** - Conversation, Memory & Thinking, Runtime Summary, Recent Activity
2. **Chat** - Gespräch, Kontext, Tasks, Memory-Hinweise, Tool-/Model-Routing
3. **Vision** - Camera/Presence/NPU/Privacy/Frame Pipeline
4. **Tools** - Skills, Tools, MCP, Integrationen, Berechtigungen
5. **Memory** - Gehirn-/Synapsenvisualisierung, Search, Recall, Knowledge Graph, Memory Health
6. **System** - Modelle, Runtime, Primary/Expert, Handover, Services, Ressourcen
7. **Voice & Audio** - Mic/VAD/Wake/STT/Direct-Audio/TTS/Listener-State
8. **Automationen** - deterministische Workflows, Trigger, Bedingungen, Aktionen
9. **Mobility / VVS** - lokale ÖPNV-/School-Mobility-Daten, Demand-State, Alerts
10. **Settings / Observability** - Konfiguration, Logs, Latency, Privacy, Updates, Diagnostics

## Memory & Thinking Visualisierung

Zentral ist ein semi-transparentes 3D-Gehirn mit neuronalen/synaptischen Verbindungen. Aktivität bleibt innerhalb des Gehirns. Keine externen Blitze. Live-Animationen repräsentieren beobachtbare Systemereignisse:

- Orange: aktive Verarbeitung
- Blau: episodisches/abgerufenes Memory
- Violett: semantisches Wissen
- Cyan: Kontext/Kurzzeit
- Grün: Planung/Optionen

Das Bild ist UI-Metapher. Es darf keine verborgenen Modellgedanken oder nicht vorhandene Reasoning-Daten behaupten.

## Backend-Vertrag

- Runtime Supervisor = Gesamtzustand und Lifecycle
- Web-/Service-APIs = fachliche Daten/Telemetrie
- Backend entscheidet `READY/STOPPED/DEGRADED/NOT_IMPLEMENTED/...`
- Frontend zeigt fehlende Daten ehrlich
- kein Mock im Produktionsmodus

## Aktuelle technische Kernrollen

- Gemma 4 12B = Primary
- Qwen3.5-35B-A3B = Expert on-demand
- Qwen3-ASR = STT/Text-Routing
- Chatterbox = TTS
- OpenRouter = optionaler Cloud-Fallback, aktuell deaktiviert
- NPU = Sensor-/Vorverarbeitungsschicht
- VVS = lokaler Mobility-Dienst

## Lovable darf nicht übernehmen

- alte Desktop-UI als Designvorlage
- Mobile-App-Layout
- historische Qwen-Primary-Darstellung
- erfundene RTX-/VRAM-/Latency-Werte
- automatische Claude-/Anthropic-Annahmen
- harte `READY`-Defaults
- Fake Memory Confidence oder Knowledge Growth
- simulierte Agentenaktivität ohne Backendereignis
