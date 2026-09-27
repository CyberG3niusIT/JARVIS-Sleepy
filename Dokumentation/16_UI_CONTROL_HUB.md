# Desktop Control Hub - aktueller Backend-/State-Vertrag

**Stand: 27.09.2026.** Die bisherige Desktop-Anwendung wird visuell neu aufgebaut. Dieses Dokument hält nur noch die technischen Verträge fest, die der neue Client respektieren muss.

## 1. Source of Truth

Der Client darf Zustände nicht aus hübschen Screens, statischen Beispieldaten oder einzelnen Health-Probes erfinden.

Priorität:

1. Runtime-Supervisor für Gesamtzustand und Lifecycle-Capabilities
2. Web-/Service-APIs für fachliche Daten und Telemetrie
3. explizite `NOT_IMPLEMENTED`, `UNAVAILABLE`, `STOPPED`, `DEGRADED`, `ERROR`-Darstellung, wenn Daten fehlen

## 2. RuntimeSnapshot

Unterstützte Zustände:

```text
STARTING
READY
DEGRADED
ERROR
STOPPED
OFFLINE
NOT_IMPLEMENTED
```

Realer Snapshot nach Reboot 26.09.2026:

- Gesamt `READY`, keine Degraded-Gründe
- Voice READY
- Gemma Primary READY
- Qwen Expert STOPPED/on-demand
- STT READY
- Chatterbox READY
- Audio-Bridge READY
- VVS READY
- FLUX STOPPED/on-demand
- NPU STOPPED/backend not initialised
- Web NOT_IMPLEMENTED

Diese Werte sind Beispiel für einen realen Snapshot, keine fest verdrahteten UI-Defaults.

## 3. Desktop-Neuaufbau

Die alte Tauri/Lovable-Implementierung ist **LEGACY DESIGN REFERENCE**. Bestehende Runtime-Brücken und State-Ideen können wiederverwendet werden, aber Layout, Visualisierung, Navigation und Informationsarchitektur werden neu erstellt.

Neue visuelle Referenzseiten:

- Home / Systemübersicht
- Chat
- Vision / Presence / NPU
- Tools & Integrationen
- Memory
- System / Modelle & Runtime
- Voice & Audio
- Automationen / Workflows
- Mobility / VVS
- Settings / Observability

Details stehen in [18 Desktop Redesign / Lovable](18_DESKTOP_REDESIGN_LOVABLE.md).

## 4. Memory & Thinking

Die zentrale Gehirn-/Synapsenansicht visualisiert live beobachtbare Vorgänge:

- Context retrieval
- Memory retrieval
- semantische Verknüpfungen
- Tool-/Skill-Route
- Primary/Expert-Routing
- Antwortgenerierung
- bestätigte neue Memory-Verknüpfungen

Sie darf keine verborgene Chain-of-Thought vortäuschen. Wenn kein Live-Datum vorliegt, zeigt die UI keinen simulierten Gedankenfluss.

## 5. Modellanzeige

Aktuell erwartete Rollen:

- PRIMARY: Gemma 4 12B
- EXPERT: Qwen3.5-35B-A3B, on-demand
- STT: Qwen3-ASR
- TTS: Chatterbox
- Cloud: OpenRouter optional/deaktiviert

Keine historischen Modellnamen oder GPU-Werte hardcoden.

## 6. Telemetrie

Charts und Leistungswerte dürfen nur erscheinen, wenn eine reale Quelle vorhanden ist. Keine erfundenen GPU-, CPU-, VRAM-, Token/s-, Latenz-, Memory-Confidence- oder Knowledge-Growth-Werte. Bei fehlender Quelle: `Keine Live-Daten` / `Unavailable`.

## 7. Privacy

- keine Secrets im Frontend
- keine privaten DB-Inhalte ohne explizite Backendroute und Nutzerbindung
- Kamera/Mikrofon/Screen nur entsprechend Privacy-/Capability-Gates
- Cloudstatus sichtbar und ehrlich
- PrivacyGate darf nicht durch Frontendtoggle umgangen werden

## 8. Lifecycle

Start/Stop/Restart nur über die vom Supervisor gemeldeten Capabilities. Ein READY-System darf `start` ablehnen. Der Client zeigt diesen Zustand, statt die Aktion lokal zu erzwingen.
