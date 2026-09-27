# Projektstatus (27.09.2026)

## Git-Evidenz

Aktuell zuletzt verifiziert für `Main`:

- Branch: `backup/jarvis-runtime-voice-2026-09-24`
- HEAD: `a977e1e77ff7f2531dbdfe1a9251b4341541586a`
- Worktree: umfangreich dirty; der reale Entwicklungsstand liegt deutlich über dem HEAD.
- Keine Historienumschreibung, kein Reset/Clean und kein automatischer Commit im Rahmen der dokumentierten Arbeiten.

Branch/HEAD sind nur Baseline. Für Funktionsstatus ist der aktuelle Worktree maßgeblich.

## Reale Runtime-Evidenz nach Windows-Neustart

Am 26.09.2026 meldete `JARVIS-Runtime.ps1 -Action getRuntime`:

- Gesamtzustand `READY`
- `degradedReasons: []`
- `voice-daemon`: READY
- `llm-primary` / Alias `llm-main`: READY
- `stt-model`: READY
- `chatterbox`: READY
- `audio-bridge`: READY
- `vvs`: READY
- `llm-expert`: STOPPED, on-demand
- `flux`: STOPPED, on-demand
- `npu-sensor`: STOPPED, Backend nicht initialisiert
- `web`: NOT_IMPLEMENTED im Supervisor

`start` wurde im Zustand `READY` korrekt abgewiesen. Daraus folgt nicht automatisch, welcher Boot-/Autostartmechanismus den Zustand hergestellt hat.

## Komponentenstatus

| Teil | Status | Nachweisgrenze |
|---|---|---|
| Core / Router / Skills / Tools / Memory | implemented / partial | Code und breite Tests vorhanden; einzelne Runtimepfade weiter in Abnahme |
| Runtime Supervisor | implemented, live belegt | READY-Snapshot nach Reboot; Lifecycle-State-Guard belegt |
| Gemma 4 12B Primary | partial, live geladen | Primary-Service READY; reale Voice-Acceptance noch fehlerhaft |
| Qwen3.5-35B-A3B Expert | partial | Service on-demand/STOPPED; Handover weiterhin nicht für normalen Betrieb freigegeben |
| Qwen3-ASR | live | STT-Ausgaben im realen Voice-Test beobachtet |
| Chatterbox | live | reale TTS-Ausgabe beobachtet; Watchdog/TTS-State-Interaktion fehlerhaft |
| Direct-Audio / Turn Aggregation | partial | realer Acceptance-Test durchgeführt, aber nicht bestanden |
| NPU Presence | partial | Backendpfad vorhanden; Runtime nach Reboot nicht initialisiert; NPU-Wake weiterhin nicht implementiert |
| VVS / Mobility API | partial / live service | Supervisor meldete VVS READY; fachliche School/Mobility-End-to-End-Abnahme bleibt separat |
| Web API | partial | Quellcode vorhanden; Supervisor behandelt Web weiterhin als NOT_IMPLEMENTED |
| Desktop UI | redesign | bisherige Desktop-Implementierung wird ersetzt; Backend-/State-Vertrag bleibt relevant |
| Android | separates Projekt | nicht Teil des Desktop-Neuaufbaus |

## Cloud-Status

Nach dem Anthropic-/Provider-Audit:

- kein impliziter `anthropic`-Default mehr im Router
- kein Claude-Modell als Default
- `llm.api.provider: openrouter`
- `llm.api.enabled: false`
- `llm.api.model: null`
- `OPENROUTER_API_KEY` als vorgesehener Credential-Name
- Anthropic bleibt optional und nur explizit auswählbar
- `self_evolution.auto_consult: false`
- keine projektlokale Co-Author-Automatik gefunden

Die Cloud kann mit dieser checked-in Konfiguration aktuell keinen Request ausführen.

## Reale Voice-Abnahme 26.09.2026

Der erste Hardware-/E2E-Test zeigte:

1. Wake-only `Aura` wurde bei einer natürlichen Pause zu früh abgeschlossen.
2. Watchdog setzte Speaking-Flags während noch laufender Chatterbox-Ausgabe zurück.
3. speculative Direct-Audio-Cancel erzeugte `NoneType ... read` statt eines sauberen Cancel-Pfads.
4. nach Conversation-Timeout lief ein alter LLM-Retry weiter und erreichte anschließend den Cloud-Fallbackpfad.
5. eine danach vollständig erneut gesprochene Anfrage wurde von Gemma beantwortet; der genaue Direct-Audio-vs-Text-Pfad war im vorhandenen Log nicht eindeutig markiert.

Bis diese Punkte erneut auf Hardware bestanden sind, gilt Voice nicht als abgenommen.
