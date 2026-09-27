# Entwicklungshistorie und Entscheidungen

## Aktuelle Git-Baseline

Zuletzt verifiziert:

- Branch `backup/jarvis-runtime-voice-2026-09-24`
- HEAD `a977e1e77ff7f2531dbdfe1a9251b4341541586a`
- umfangreicher Dirty Worktree; aktueller Implementierungsstand liegt über HEAD.

## Wichtige Entwicklungslinie

- 14.-20.09.: Windows/WSL-Port, Qwen3-ASR, Chatterbox, PrivacyGate, Memory-/Voice-Härtung.
- 21.-24.09.: School/Mobility, Runtime-/Tooling-Arbeit, Desktop-/Mobile-Experimente.
- 25.09.: Gemma 4 12B als PRIMARY, Qwen3.5-35B-A3B als EXPERT, Direct-Audio, Turn-Assembler, speculative Audio, NPU-/Vision-Gate und Runtime-Supervisor-Komponenten.
- 26.09.: Runtime nach Reboot READY; realer Voice-Acceptance-Test zeigt Turn-/Watchdog-/Cancel-/Retry-Probleme. Danach Anthropic-/Provider-Audit und Bereinigung: OpenRouter vorbereitet, Cloud disabled, Anthropic nur explizit, Auto-Consult aus.
- 27.09.: Desktop-Design wird neu aufgesetzt. Alte Desktop-Implementierung bleibt historische Referenz, ist aber nicht mehr visuelle Source of Truth. Zentrale Dokumentation wird vor Lovable-Handoff aktualisiert.

## Aktuelle Architekturentscheidungen

- Gemma ist Primary, Qwen Expert.
- GPU-Modelle nicht gleichzeitig resident.
- Direct-Audio ohne Tool-Schemas; paralleles STT übernimmt deterministisches Routing.
- Expert antwortet direkt; keine Pflicht-Reformulierung durch Gemma.
- Cloud optional, providerneutral; OpenRouter bevorzugt, aktuell deaktiviert.
- Anthropic nie implizit.
- Backend/Supervisor ist Source of Truth für UI-State.
- NPU ist Sensor-/Vorverarbeitungsschicht, kein zweites Gehirn.
- Memory-Learning ist keine Self-Modification.

## Verwarfene bzw. nicht mehr gültige Annahmen

- Qwen als dauerhaftes Main-Modell.
- Small-LLM auf 8081 als notwendige Runtime-Komponente.
- Web und VVS beide auf 8088.
- automatische Claude-/Anthropic-Beratung als Default.
- bisherige Desktop-UI als Design-Baseline.
