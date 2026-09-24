# JARVIS Control Hub (Desktop-UI)

Frontend des JARVIS-Sleepy-Workspace: React 19, TanStack Start, TypeScript, Tailwind 4, shadcn/ui.
Quelle des Designs ist das Lovable-Projekt *JARVIS Control Hub* (`1b94749c-b7fc-4242-9b1c-adab148d646d`,
übernommen bei Lovable-HEAD `39539d00818613559388818a928027c8c9649888`). Das Backend bleibt die
Wahrheitsquelle; die UI zeigt nur, was das Backend liefert.

Vollständige Dokumentation (Übernahme, Backend-Mapping, Runtime-State-Vertrag, Lifecycle,
NOT_IMPLEMENTED, offene Punkte): `../Dokumentation/16_UI_CONTROL_HUB.md`.

## Befehle

```sh
npm install
npm run dev      # Prototype-Adapter (statisch, als PROTOTYP markiert)
npm run build
npm run lint
```

Echtes Backend anbinden (nur Dev/Preview, Same-Origin-Proxy in `vite.config.ts`):

```sh
# .env.local
VITE_JARVIS_ADAPTER=production
# in der Shell, die `npm run dev` startet (Token bleibt serverseitig):
JARVIS_WEB_AUTH_TOKEN=...
```

Optional überschreibbare Ziele: `JARVIS_WEB_URL` (8088), `JARVIS_LLM_MAIN_URL` (8080),
`JARVIS_LLM_SMALL_URL` (8081), `JARVIS_TTS_URL` (8765), `JARVIS_FLUX_URL` (8190),
`JARVIS_VVS_URL` (8088). Achtung: `JARVIS_WEB_URL` und `JARVIS_VVS_URL` haben denselben Default-Port; der Web-Token
wird an `JARVIS_WEB_URL` gesendet (siehe Dokumentation Kapitel 16, Abschnitt 5).

Hinweis: Runtime-Zustand und Lifecycle kommen ausschließlich von einem (noch nicht vorhandenen) nativen
Supervisor über `RuntimeControlTransport` (`src/lib/jarvis/runtime-control.ts`). Ohne ihn zeigt die UI
`Nicht implementiert`; sie leitet nie einen Zustand aus Health-Probes ab. Der Dev-Proxy sendet
`JARVIS_WEB_AUTH_TOKEN` nur an ein als `jarvis_web.py` identifiziertes Loopback-Ziel.

## Architektur

```
React-Komponenten -> useJarvis() -> JarvisAdapter -> PrototypeAdapter | ProductionAdapter -> transport.ts -> Backend
```

Komponenten enthalten keine Systemsteuerung (kein `systemctl`, `wsl.exe`, PowerShell, Subprozess).
Daten: `BackendDataTransport` (`transport.ts`). Runtime/Lifecycle: `RuntimeControlTransport` (`runtime-control.ts`).
