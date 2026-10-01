# 16 UI Control Hub (Desktop-UI)

Stand: 26.09.2026. Repository/Branch: `UI`-Worktree, `claude/jarvis-ui` (Ausgangs-HEAD `149a64e`; lokale Änderungen nicht committet).
Backend: lokaler `Main`-Worktree, derzeit stark geändert; Live-Integration ist getrennt zu verifizieren.
Evidenzklassen: **Code** = aus Quellcode gelesen; **Live** = am 24.09.2026 per GET gegen die laufende Umgebung geprüft; **Testdouble** = nur isolierter UI-Pfad gegen einen lokalen Mock (kein Live-Nachweis).

## 1. Übernahme Lovable → lokale UI

- Quelle: Lovable-Projekt *JARVIS Control Hub* (`1b94749c-b7fc-4242-9b1c-adab148d646d`), HEAD `39539d00818613559388818a928027c8c9649888` (bei der Nachprüfung weiterhin der letzte Edit). Lovable wurde nur gelesen (keine Nachrichten, Builds oder Credits).
- Übernommen: alle `src/` (46 shadcn-Komponenten, `components/jarvis/*`, `lib/jarvis/*`, Routen, Router, `server.ts`, `start.ts`, `styles.css`), `package.json`, `vite.config.ts`, `tsconfig.json`, `eslint.config.js`, `components.json`, `.gitignore`, `.prettierrc`, `.prettierignore`, `public/robots.txt`, `public/favicon.ico` (per HTTP-GET von der Lovable-Preview).
- Nicht übernommen: `bun.lock`, `bunfig.toml` (stattdessen `package-lock.json`), `AGENTS.md`, `.lovable/`, `roadmap.md`, Lovable-`README.md`, `src/routes/README.md`.
- Stichproben (`utils.ts`, `tabs.tsx`) sind identisch zu Lovable; ein vollständiger Byte-Vergleich aller 46 UI-Dateien wurde nicht durchgeführt.
- Design/Layout unverändert; alle 10 Bereiche vorhanden.

### Abweichungen von Lovable (bewusst)

| Datei | Änderung | Grund |
|---|---|---|
| `lib/jarvis/types.ts` | numerische Modell-/Voice-Felder, `toolCalling`, `ttsWarmup`, `metricsRetentionDays` jetzt `… \| null`; optional `memoryCounts` | Produktion darf keine Nullwerte erfinden |
| `lib/jarvis/transport.ts` (neu) | `JarvisTransport`-Interface, `fetchTransport`, `setJarvisTransport()` | einzige Netzwerkschicht, austauschbar (Tauri/native Bridge) |
| `lib/jarvis/production-adapter.ts` | Skelett → echte Anbindung | Auftrag |
| `lib/jarvis/adapter.ts` | `VITE_JARVIS_ADAPTER=production` wählt Produktion, Default Prototype | Parität zu Lovable im Default |
| `lib/jarvis/use-jarvis.ts` | `reload`, `isRefreshing`, `execute`, Cleanup, Polling | Auftrag |
| `components/jarvis/mode-context.ts` (neu) | Kontext „Prototype ja/nein“ | nur Wortwahl, keine Daten/Zustände |
| `components/jarvis/sections.tsx` | ehrliche Texte im Produktionsmodus, Dienst-Health aus `services`, `null`-Darstellung, Runtime-Panel ruft `execute()` | keine Behauptungen ohne Backend-Quelle |
| `routes/index.tsx` | Provider, `reload`/`execute` durchgereicht | Verdrahtung |
| `vite.config.ts` | Same-Origin-Proxy `/jarvis-api/*` (nur Dev/Preview) | fehlendes CORS im Backend |

Im Prototype-Modus bleiben alle Lovable-Texte und -Werte unverändert (`PROTOTYP`, `Offline, keine Live-Verbindung`, Beispielzeilen).

## 2. Runtime-Wahrheit (Korrektur)

**Es gibt im Backend keine autoritative Runtime-State-Quelle und keine Lifecycle-Schnittstelle** (Code-Audit, `origin/backup/…`, `main`, RC; erneut komplett geprüft):
- `STARTING/READY/DEGRADED/ERROR/STOPPED` existieren nur als stdout-Präfixe von `start.sh`/`stop.sh` (`STARTING`, `READY:`, `DEGRADED:`, `ERROR:`, `STOPPED:`, deutscher Freitext, Exit 0 sowohl bei READY als auch DEGRADED). READY wird per journal-Suche nach `Continuous listening active` entschieden (`start.sh:420`). DEGRADED-Gründe sind Freitextzeilen aus `scripts/check_runtime_dependencies.py --required` (kein JSON). `OFFLINE` existiert im Code nicht.
- `jarvis_web.py` (alle Routen `:4873–4936` geprüft): kein `/health`, `/ready`, `/status`, `/api/runtime`, `/api/state`; kein WS-Frame mit Zustand. `/ws` `{"type":"restart"}` ist nur ein `os.execv` des Web-Prozesses.
- Weder Statusdatei, Socket, Named Pipe, PID-/Heartbeat-Datei noch `Type=notify`/`WatchdogSec`. Einzige lesbare Statusdatei: `.jarvis_privacy_status` (`"<normal|privacy|privacy_lock> <epoch>"`, nur Privacy-Modus, WSL-Runtimeverzeichnis, bleibt nach Prozessende stehen). `Watchdog.get_background_health()` existiert, hat keinen Aufrufer.
- Start/Stop/Restart: nur `JARVIS-Start/Stop/Restart.ps1` → `JARVIS.Runtime.psm1` → `wsl.exe … start.sh|stop.sh|restart.sh`. Diese starten `jarvis_continuous.py`, nicht `jarvis_web.py`.

**Entscheidung (25.09.2026):** Runtime/Lifecycle gehören nicht in `jarvis_web.py`. Ziel ist ausdrücklich eine installierbare native Windows-`.exe`: `JARVIS.exe / Tauri (Rust) → Runtime Supervisor / Native Control Plane → WSL2 → JARVIS-Backend`. Korrektur des historischen Befunds: Im aktuellen lokalen UI-Worktree existiert `src-tauri/` mit geschlossenem Rust-Command-Set; im Backend-Worktree existieren `JARVIS-Runtime.ps1`, `JARVIS.Runtime.psm1` und `scripts/runtime_status.py`. Am 26.09.2026 wurde der NSIS-Installer auf diesem Rechner erfolgreich gebaut (Tauri Release-Build, 2.78 MiB). `npm run build:desktop` prüft jetzt vor dem Tauri-Build, dass `index.html` und alle referenzierten Assets tatsächlich vorhanden sind; dieser Gate und der Release-Build sind erfolgreich. Die Installation und Abnahme der gestarteten `.exe` gegen den Live-Supervisor ist noch offen.

Der Supervisor-Einstiegspunkt liegt im Bundle unter `runtime/JARVIS-Runtime.ps1`. Der Rust-Host verlangt ein vollständiges JARVIS-Checkout (per nativer Ordnerauswahl gespeichert oder `JARVIS_REPOSITORY_ROOT`), prüft die erforderlichen Supervisor-/Probe-Dateien und reicht den Pfad explizit an PowerShell weiter. Tauri benötigt für `frontendDist` eine `index.html`; TanStack Start erzeugte vorher nur Client-Assets, sodass das gebaute Fenster keinen startbaren App-Einstieg hatte. Der Build aktiviert nun den SPA-Shell-Prerender nach `.output/public/index.html`; ein permanenter Build-Gate prüft die HTML-Datei und alle referenzierten Assets. Nach dem Fix wurde die Release-`.exe` gestartet und ihr Kindprozess mit exakt `JARVIS-Runtime.ps1 -Action getRuntime` beobachtet; das gebündelte Skript liefert separat mit demselben Checkout `DEGRADED` und 11 Komponenten. Damit ist der Aufrufpfad Tauri → PowerShell-Supervisor nachgewiesen, aber noch kein sichtbarer UI-State gegen die Antwort abgenommen. Installer-Installation und nativer Checkout-Dialog sind ebenfalls noch nicht end-to-end abgenommen.

**Konsequenz in der UI:** Der ProductionAdapter leitet **keinen** Runtime-Zustand aus HTTP-Probes ab. Der Zustand kommt ausschließlich aus dem `RuntimeControlTransport`; ohne Supervisor gilt `runtime.state = NOT_IMPLEMENTED` und alle Lifecycle-Capabilities sind `false` (Start/Stop/Neustart deaktiviert, „Nicht implementiert“). Aus React werden keine Shell-Skripte, `wsl.exe`/PowerShell oder generische Kommandos aufgerufen. Die UI-Typen `STARTING…STOPPED` und die Darstellung (`runtime-status.ts`, DEGRADED-Grund im Runtime-Panel) bleiben aus Lovable erhalten und greifen erst, wenn ein Backend echte Werte liefert.

Fehlende Backend-Schnittstelle (für später): ein Supervisor-Endpoint (z. B. `GET /runtime/state` + Stream) mit `state`, `degraded_reasons[]`, `since/updated_at` und Komponentenzuständen; Liveness des Voice-Daemons (Heartbeat/`Type=notify`); `--json` der Preflight-Skripte; authentifiziertes, idempotentes `POST /runtime/start|stop|restart` (oder ein definierter Host-Aufruf mit Statusmodus).

## 3. Real angeschlossene Daten (Quelle, Schema)

Alle Mappings sind im ProductionAdapter dokumentiert. „Live“ heißt: am 24.09.2026 gegen die laufende Umgebung gelesen; Web-API-Endpunkte waren dort nicht erreichbar (siehe 6) und sind nur per Code und Testdouble belegt.

| UI-Feld | Quelle | Schema / Nachweis |
|---|---|---|
| Dienst „Main LLM“ (Health) | `GET :8080/health` | `{"status":"ok"}` — Live |
| AI Core: Modellname, Quantisierung, Kontext, Parameter, Runtime | `GET :8080/v1/models` (llama-server, extern) | `data[0].id`, `.owned_by:"llamacpp"`, `.meta.{n_ctx,n_params,ftype}` — Live (`Qwen3.5-35B-A3B-abliterated-Q3_K_M.gguf`, `Q3_K - Medium`, 32768, 34 660 610 688). Das Repo selbst ruft nur `/health` und `/v1/chat/completions`; `/v1/models` ist Verhalten des laufenden llama.cpp-Builds. |
| Dienste Small LLM / FLUX | `GET :8081/health`, `:8190/health` | `{"status":"ok"}` bzw. `{"status":"ready"\|"loading",model,device}` (`services/flux_server.py:119`) — beide am 24.09. nicht erreichbar |
| Dienst Chatterbox | `GET :8765/health` | Code: `{"status":"ok"}` (`tools/chatterbox_server.py:123`). Live: Windows-Dienst antwortet `401 missing or invalid bearer token`, über den Browser-Proxy `403 browser context not allowed` (in keinem geprüften Ref vorhanden). Anzeige: „Erreichbar, Zugriff verweigert (HTTP 401/403)“. |
| Dienst VVS | `GET :8088/health`, `/ready` | Live: `{"ok":true,"static":{"ready":true,…}}` / `{"ready":true}`; gleiche Bedingung wie `check_runtime_dependencies.py` (`ready.ready == true`, `ok/healthy != false`) |
| Dienst Web-API | `GET /api/stats` (`jarvis_web.py:3352`) | nur Erreichbarkeit + `llm.model` (Fallback für Modellname), `memory` (null = kein Memory-Manager). Live: Port 8088 antwortet 404 (VVS). |
| Logs / Dashboard-Feed | `GET /api/events/watchdog?hours=24` (`:4056`) | `{total,by_type,events:[{timestamp,event,message,severity}]}`; `timestamp` = float Epoch-Sekunden (`time.time()`); Kategorie nur `error_recovery`, Severities dort nur `warn`/`fatal`; max. 50 Ereignisse. Das ist eine Teilmenge (keine vollständigen Logs); `id/source/context` liefert das Backend nicht. Testdouble. |
| CPU- und RAM-Karte | `GET /api/events/health?hours=24&metrics=cpu.load,ram.percent` (`:4087`) | `trends.<metric>.stats.{latest,latest_ts}`; Werte sind Health-Snapshots (alle 10 min, aus Text der Health-Checks geparst, `HealthSnapshotScheduler`), **keine Live-Telemetrie**; Anzeige „Snapshot <Zeit>“. `latest` ignoriert das Zeitfenster und kann alt sein (Zeitpunkt wird angezeigt). Einheit Prozent laut `health_check.py:108/205` (`load=…%`, `percent=…`). GPU/VRAM sind **nicht** angeschlossen: der Health-Check setzt bei fehlendem `rocm-smi`-Wert den Fallback `'0%'` (`health_check.py:172-173`), ein gespeicherter Wert ist also nicht von „unbekannt“ unterscheidbar. Testdouble. |
| Memory-Zähler | `GET /api/memory/summary` (`:4128`) | `facts.total`, `faiss.vectors`; nur verwendet, wenn `/api/stats.memory != null` und kein `error` (das Backend liefert sonst `total:0` ohne Fehler). Testdouble. |
| PrivacyGate-Flags | Code-Tatsache (`core/privacy_gate.py` existiert) | keine Laufzeitdaten; Zustand/Modus nicht lesbar |

## 4. Nicht angeschlossen (bewusst) / NOT_IMPLEMENTED

- **Aktionen:** Runtime Start/Stop/Restart, Agent-/Tool-/Automations-Aktionen, Logs-Export, Voice-Aufnahme, Schnellprompt, PrivacyGate-Steuerung — keine Backend-Schnittstelle.
- **Nicht eindeutig:** GPU-/VRAM-Snapshots (Fallback `0%` im Backend, s. o.).
- **Keine Quelle:** Voice-/STT-/Listener-/Wake-Word-Zustand und -Konfiguration, Speaker-ID (nur Statistik `/api/events/speaker_id`), School/Mobility (nur VVS-Health), Agenten-/Werkzeugliste, Hardware-Live-Telemetrie, Version/Build, Netzwerk, Plattform/OS.
- **Vorhanden, Schema passt nicht (nicht zurechtgebogen):**
  - `/api/metrics/*`: Zähler/ms/USD, bare Arrays, kein 0–100-Bereich → Charts bleiben „Keine Live-Daten“. Zusätzlich teilt Lovable `performance` zwischen „Modellleistung“ und „CPU und Arbeitsspeicher“; ein Wert würde eine falsche Semantik bedienen.
  - `/api/memory/facts`: keine Ebenen (Working/Candidate/Confirmed), keine Evidenzzahl, `superseded` gefiltert, Konfidenz 0–1 → keine Eintragsliste.
  - `/api/gpu-status`: nur In-Process-Besitzer (`llama|flux|unknown`), keine VRAM-Messung.
  - llama-server `/props`, `/slots`: Sampling-Werte sind Server-Defaults bzw. Werte der letzten Anfrage, nicht die konfigurierten JARVIS-Parameter → nicht als „Temperatur/Top-K“ angezeigt. Batchgröße/GPU-Layer werden nicht ausgeliefert → `null` („Keine Live-Daten“).
  - `/api/events/health`-Werte außerhalb von Prozent (Temperaturen, MB, ms) passen nicht auf 0–100-Karten und sind nicht angeschlossen.
  - `/ws/dashboard` (nur `new_metric`-Push) und `/ws` (Chat): nicht verwendet.

## 5. Transport, Auth, Produktion

- Zwei getrennte Quellen: **`BackendDataTransport`** (`transport.ts`: HTTP/API-Daten, GET/JSON, Timeout, `TransportError`: `unreachable|timeout|http|invalid-json|no-transport`, austauschbar mit `setBackendDataTransport()`) und **`RuntimeControlTransport`** (`runtime-control.ts`: Runtime-Zustand + Lifecycle, für den späteren nativen Supervisor, installierbar mit `setRuntimeControlTransport()`). Das bestehende Interface wurde erweitert (Umbenennung, ein zweites Interface daneben), keine weitere Architektur eingeführt.
- Browser können ohne CORS-Header (`jarvis_web.py`, llama-server, Chatterbox, FLUX senden keine) keine Cross-Origin-Antworten lesen. Deshalb ruft die UI `/jarvis-api/<web|llm-main|llm-small|tts|flux|vvs>/…` auf derselben Origin auf; `vite.config.ts` leitet **nur im Dev-/Preview-Server** an die Loopback-Dienste weiter. Ein Produktions-Build hat diesen Proxy nicht; dort ist ein nativer/serverseitiger Transport nötig (`VITE_JARVIS_API_BASE`, `setJarvisTransport`).
- Keine Secrets in React. Der Web-Token (`JARVIS_WEB_AUTH_TOKEN`) wird nur vom Proxy im Node-Prozess gesetzt. **Token-Guard (Dev-Proxy):** Der Token wird nur an ein Ziel gesendet, das als `jarvis_web.py` identifiziert ist: Ziel-Host ist Loopback **und** ein unauthentifiziertes `GET /api/stats` antwortet mit der Auth-Ablehnung von `jarvis_web.py` (HTTP 401, Body „Invalid or missing auth token“). Die Prüfung läuft in einer Middleware vor jedem Proxy-Request (Ergebnis ≈1 s gecacht, Redirects werden nicht verfolgt); ein unbekanntes, totes, umleitendes oder nicht-loopback Ziel bekommt den Token nie, ein Zielwechsel (z. B. `jarvis_web.py` stoppt, VVS bleibt auf 8088) entzieht ihn innerhalb ca. einer Sekunde. Zusätzlich lehnt die Middleware `/jarvis-api/*`-Anfragen mit nicht-lokalem `Host`/`Origin` mit 403 ab (DNS-Rebinding). Restrisiko: ein lokaler Prozess, der die 401-Antwort von `jarvis_web.py` auf dem konfigurierten Loopback-Port fälscht (er könnte die Umgebung ohnehin lesen). Getestet mit Testdouble: kein Token an VVS-artiges Ziel, Token nur nach Identifikation, Entzug nach Zielwechsel, 403 bei fremdem Host/Origin. **Port 8088:** dort antwortet aktuell die VVS-API, `jarvis_web.py` ist dort nicht aktiv; der Default von `JARVIS_WEB_URL` (`127.0.0.1:8088`) ist daher aktuell falsch. Es wurde nichts umkonfiguriert; `JARVIS_VVS_URL` und `JARVIS_WEB_URL` haben weiterhin denselben Default.
- Die Chatterbox-Zugriffsbeschränkung (Bearer + Browser-Kontext) wird nicht umgangen; Auth wird nicht abgeschwächt.
- Ohne Proxy (Produktions-Build) beantwortet der App-Host `/jarvis-api/*` selbst. Der Proxy markiert seine Antworten mit `x-jarvis-proxy`; fehlt der Marker (und ist keine eigene `VITE_JARVIS_API_BASE` gesetzt), meldet `transport.ts` „kein Transport verfügbar“ statt eine 404/HTML-Antwort als Dienstantwort zu lesen.
- Proxy-Ausfall (Dienst nicht erreichbar): Antwort `200` mit Marker-Header `x-jarvis-proxy-error`, damit erwartete Ausfälle keine Browser-Konsolenfehler erzeugen. Echte Upstream-Antworten (401/403/404) bleiben unverändert und werden vom Browser als „Failed to load resource“ geloggt; das lässt sich nicht unterdrücken.

## 5a. Runtime-Control-Vertrag (transportneutral, `runtime-control.ts`)

```ts
RuntimeControlSnapshot {
  state: "STARTING"|"READY"|"DEGRADED"|"ERROR"|"STOPPED"|"OFFLINE"|"NOT_IMPLEMENTED"
  degradedReasons: string[]          // Freitext, bei DEGRADED
  updatedAt: string                  // ISO 8601, Beobachtungszeit des Supervisors
  components: { id, name, state, detail? }[]
  capabilities: { start, stop, restart }   // vom Supervisor bestimmt (z. B. start nur bei STOPPED)
  detail?: string
}
RuntimeControlTransport { getRuntime(); start(); stop(); restart() }   // -> RuntimeActionResult { accepted, message }
```

- Der Supervisor ist die einzige Zustandsquelle. Die UI liest, fragt Aktionen an (`start()/stop()/restart()`, ohne Argumente, **keine generische Kommandoausführung**) und lädt danach neu. `RuntimeActionResult` ist nur eine Bestätigung, kein Zustand; nach `execute()` zeigt die UI den nächsten Supervisor-Wert, nie eine Annahme.
- Eingehende Werte einer nativen Bridge werden validiert (`parseRuntimeSnapshot`); ungültige oder unbeantwortete Lesungen werden nicht repariert, sondern zu `NOT_IMPLEMENTED` mit Capabilities `false` (kein erfundener Zustand). Lokal erzeugte `NOT_IMPLEMENTED`-Lesungen zeigen kein „Stand“.
- Ohne Supervisor: `unavailableRuntimeControl` → `NOT_IMPLEMENTED`, Capabilities `false`. Zustand, Gründe und Komponenten erscheinen im System-Runtime-Panel und in der Kopfzeile, sobald ein Supervisor sie liefert. `detail` erscheint in der Kopfzeile nach dem Zustandslabel (erstes Zeichen wird kleingeschrieben) — Detailtexte sollten deshalb als Satzfortsetzung formuliert sein.
- Test (Testdouble, kein Supervisor-Nachweis): 30 Vertragsprüfungen (`ALL PASS`): Default `NOT_IMPLEMENTED` auch bei gesunden Diensten; ausgefallene Dienste erzeugen kein `OFFLINE`; Zustand/Gründe/Komponenten/`updatedAt`/Capabilities kommen nur vom Supervisor; `execute` ohne Capability wird abgewiesen und ruft nichts auf; Bestätigung ändert den Zustand nicht; ungültige Payloads und werfender Supervisor → `NOT_IMPLEMENTED`; alle 7 Zustände werden akzeptiert.

## 5b. Datenprüfung (Code, Schema, Semantik, Live wo möglich)

Zusätzlich angeschlossen: `GET /api/metrics/summary?hours=24` → AI-Core-Zeilen „Anfragen (24 h)“ (`total_interactions`) und „Ø Latenz“ (`avg_latency_ms`, nur bei `total_interactions > 0`, weil `get_summary()` sonst `0` liefert). Testdouble.

Geprüft und **nicht** angeschlossen:
- `/api/events/stt`, `/api/events/tts`: Der aktive Qwen3-ASR- und Chatterbox-Pfad emittiert jetzt ebenfalls `stt_transcription` bzw. `tts_synthesis` mit Engine, Status, Textlänge und Zeiten, ohne Transkript/Text im Event. Die STT-Statistikroute liefert kein `text_preview` mehr. Direkter isolierter Verhaltenstest mit gemocktem Recognizer/HTTP-Antwort bestand für beide Emitter; das formale pytest wurde nicht ausgeführt. Live liefern die Endpunkte am 26.09. jeweils 0 Events in 24 h, weil der laufende Prozess den geänderten Quellcode noch nicht geladen hat. Die Endpunkte Desktop-Snapshot und Event-Aggregat antworten live je mit 404; kein Dienst wurde für diese Arbeit neu gestartet.
- `/api/events/speaker_id`: Ereignisse mit `best_id` (personenbezogen), kein Sprecherverzeichnis, keine passende UI-Komponente.
- `/api/gpu-status`: In-Process-Zustand des Web-Prozesses (`active_service`, `is_llm_available`, `is_swapping`), keine Messung.
- `/api/stats.context_window.usage_pct`: liefert `0.0`, wenn das ContextWindow deaktiviert ist (nicht von echtem 0 unterscheidbar) und bezieht sich auf das JARVIS-Token-Budget, nicht auf `n_ctx` des Modells → „Kontextlast“ bleibt „Keine Live-Daten“.
- `/api/metrics/{timeseries,skills,routes,…}`, `/api/memory/{facts,interactions,timeseries,db-health}`: siehe Abschnitt 4 (Schema/Semantik passt nicht bzw. Pfad hartkodiert).
- `/api/events/health`: nur Prozentwerte `cpu.load`, `ram.percent` verwendet; GPU/VRAM wegen Fallback `'0%'` nicht.
- Live nur für llama-server (`/health`, `/v1/models`, `/props`, `/slots`) und VVS (`/health`, `/ready`) prüfbar; die Web-API läuft nicht.

**Live-Nachprüfung 26.09.2026:** Die aktuelle Web-API antwortet auf `127.0.0.1:8091`. `/api/stats`, `/api/metrics/summary`, `/api/metrics/timeseries`, `/api/memory/summary`, `/api/events/health`, `/api/metrics/tools`, `/api/events/{stt,tts,watchdog}` liefern HTTP 200; `/api/desktop/snapshot` und `/api/events/aggregate` liefern im laufenden Prozess weiterhin 404, obwohl die aktuelle Backend-Quelle diese Routen enthält. Gelesene aggregierte Werte: 53 LLM-Interaktionen und 68.698 Tokens in 24 h, 1 Memory-Faktum, 21 Watchdog-Ereignisse; STT/TTS jeweils 0 Ereignisse. Die API liefert 6 Stunden-Buckets für LLM-Messwerte; UI und native Allowlist schließen `/api/metrics/timeseries` nun an und zeigen deren mittlere Latenz statt irrtümlich CPU/RAM als Inferenzkurve. Memory liefert zusätzlich 40 ContextWindow-Segmente, 501 geschätzte Tokens und 2,1 % Nutzung. Diese Kontextwerte werden unabhängig vom Memory-Manager übernommen, weil das Backend die ContextWindow-Funktion separat initialisiert. `/api/stats` meldet Memory-Manager mit 34 Vektoren und proaktivem Surfacing sowie ein aktives ContextWindow. Die UI verwendet diese `/api/stats`-Felder nun als Fallback für die drei Memory-Funktionszeilen, wenn der Desktop-Snapshot-Endpunkt fehlt; „unbekannt“ bleibt als „Keine Live-Daten“ sichtbar. Leere STT/TTS-Fenster zeigen keine gemessene Erfolgsrate oder Laufzeit von 0 an; TTS-Durchschnitte erscheinen nur bei positiven Einzelmessungen, Cache-Raten berücksichtigen Cache-Treffer auch ohne Synthese. Der echte Supervisor-JSON-Output wurde unverändert durch `parseRuntimeSnapshot` geprüft: `DEGRADED`, 11 Komponenten und ein Degraded-Grund werden akzeptiert. Keine Lifecycle-Aktion und kein Dienstneustart wurden ausgeführt; eine sichtbare Abnahme der Werte im installierten UI bleibt offen.

## 6. Live-Befunde (24.09.2026, per GET)

- `:8080` Main LLM erreichbar (`/health`, `/v1/models`, `/props`, `/slots`; `/metrics` → 501 „nicht mit `--metrics` gestartet“).
- `:8088` beantwortet die **WIMAEDV VVS API** (uvicorn; `/health`, `/ready`, `/api/v1/…`), nicht `jarvis_web.py` (`/api/stats` → 404). Der dokumentierte Portkonflikt ist real; `jarvis_web.py` wird von keinem Start-Skript gestartet.
- `:8765` Windows-Dienst (`Microsoft-HTTPAPI/2.0`) verlangt einen Bearer-Token (401); die Strings „missing or invalid bearer token“/„browser context not allowed“ stehen in keinem geprüften Ref (`primary`, `main`, RC, `claude/jarvis-architecture`, `safe/pre-claude-20260915`, `claude/jarvis-ui`); die Herkunft ist unbekannt.
- `:8081` (Small LLM), `:8190` (FLUX), `:8089` (Webcam-Server) nicht erreichbar.

## 7. useJarvis

Erstladen, `reload()` (parallele Aufrufe werden zusammengelegt), `isRefreshing` (im Hook vorhanden, in der UI nicht visualisiert), Fehlerzustand, Cleanup (Mounted-Flag, Intervall, `visibilitychange`-Listener), `execute(cap)` → `adapter.execute()` → `reload()`. Polling alle 15 s nur im Produktionsmodus und nur bei sichtbarem Tab; zusätzlicher Refresh bei `visibilitychange`. Gepollt werden nur Health-/Reachability-Probes, Modellmetadaten, Watchdog-Ereignisse, Health-Snapshots und Memory-Zähler — der Runtime-Zustand wird nicht erfunden. `execute()` wartet auf einen laufenden Refresh und liest danach erneut (kein veralteter Zustand nach einer Aktion). Kein zweiter Poller (Testdouble: 2 Anfragen in 33 s bei 15 s Intervall).

## 8. Offene Punkte / Entscheidungen

1. **Native Runtime Supervisor live verifizieren**: Quellcode-Brücke Tauri → `JARVIS-Runtime.ps1` → `JARVIS.Runtime.psm1` → WSL-Probe ist vorhanden; Release-`.exe` und Installer bauen, der Tauri-`getRuntime`-Aufruf wurde als Kindprozess aus der gestarteten `.exe` beobachtet und das Supervisor-Skript liefert separat einen echten Status. Offen: erfolgreich zurückgeparsten Status im gerenderten Runtime-Panel belegen sowie Installer-/Checkout-Dialog abnehmen. Lifecycle-Aktionen separat und nur mit Freigabe prüfen; derzeit kein Start/Stop/Restart im Rahmen der UI-Abnahme.
2. **Web-API-Betrieb/Portkonflikt 8088** (VVS vs. `jarvis_web.py`); außerdem startet keines der Start-Skripte `jarvis_web.py`. Ohne laufende Web-API sind Watchdog, Health-Snapshots und Memory-Zähler nicht live nachgewiesen.
3. **Chatterbox-Auth-Vertrag** (Token, Browser-Kontext) — im Repo nicht dokumentiert.
4. **Produktionsdaten und Runtime-UI vollständig abnehmen**: derzeit vorhandene Datenquellen sind nicht gleichbedeutend mit vollständig belegten UI-Feldern; fehlende Quellen/Mapping bleiben offen. Der Tauri-Produktions-Transport ist im Quellcode ergänzt, muss aber mit dem Installer verifiziert werden.
5. `web.host` wird von `jarvis_web.py` ignoriert (HTTP bindet fest `127.0.0.1`); kein CORS.
6. Backend-Auffälligkeiten (Code): `/api/memory/db-health` mit hartkodiertem `/mnt/storage/jarvis/data`; `MetricsTracker.prune`/`EventLogger.prune` ohne Aufrufer; unset `${JARVIS_WEB_AUTH_TOKEN}` bleibt wörtlich Token; Health-Check-GPU-Labels hartkodiert („RX 7600“/„RX 7900 XT“).
7. Weitere Daten sind noch anzubinden bzw. fachlich zu mappen: Memory-Fakten dürfen erst nach sicherer Nutzerbindung aus `/api/memory/facts` gelesen werden (die Route liefert ohne `user_id` alle Nutzer); `/api/metrics/*` (Chart-Modell) und `/api/events/{stt,tts,speaker_id}` (Statistik) brauchen Feld- und Datenschutzprüfung. Neu angeschlossen (Code/Test, kein nativer Live-Nachweis): inhaltsfreies `/api/events/aggregate` (Counts nach Severity/Kategorie), 24h Tool-Aufruf-Aggregat, Metrik-Retention, Memory-Konfigurationsflags ohne DB-Pfade sowie CPU/RAM-Health-Historie auf gemeinsamer Zeitachse.
8. **Native Release-Verifikation:** Installer liegt als erfolgreicher lokaler Release-Build vor; die gebündelte Supervisor-Datei und der `getRuntime`-Aufrufpfad aus der gestarteten `.exe` sind nachgewiesen. Noch ausstehend sind Installation/Start in sauberem Installationspfad, sichtbare UI-Abnahme der Supervisor-Antwort und Verifikation der erreichbaren Backend-Felder. Ein Vite-Build allein ist kein Ersatz.

## 9. Tests (24./25.09.2026)

- Zweiter unabhängiger Review-Agent (read-only) zur Runtime-Control-Arbeit: Regeln „kein abgeleiteter Runtime-State“, „keine Shell“, „Token nur an identifiziertes Ziel“ gelten; Befunde behoben: Token-Identifikation jetzt pro Request statt periodisch, Redirects nicht verfolgt, Host-/Origin-Prüfung, Timeout (3 s) für den Supervisor, Capability-Cache wird pro Lesung zurückgesetzt und vor jeder Aktion erneut beim Supervisor erfragt, Validierung (Größenlimits, eindeutige Komponenten-IDs, ISO-Datum), Form-Prüfung der `/api/stats`-Antwort (ein fremder Dienst mit 200 gilt nicht als Web-API), eigene Wortwahl „Vom Supervisor derzeit nicht erlaubt“ statt „Nicht implementiert“, exakte Proxy-Prefix-Regeln. Offen/akzeptiert: `VITE_JARVIS_API_BASE` überspringt die Marker-Prüfung; `busy`-Zustand des Runtime-Panels ist komponentenlokal.
- Secret-Scan: Build mit Canary-Token `JARVIS_WEB_AUTH_TOKEN` → weder Token noch Variablenname im Build-Output; keine Shell-/`wsl`-/`child_process`-Aufrufe in `src/`.
- Fenstergrößen: alle 10 Bereiche inkl. Tabs ohne horizontalen Überlauf bei 1100×680 (App-Mindestgröße), 1280×720, 1366×768, 1672×941, 1920×1080, 2560×1440. Bei 1100 brach der Kopfzeilen-Status auf drei Zeilen um → jetzt einzeilig mit Ellipse und Tooltip (`app-shell.tsx`; Prototype-Text unverändert kurz).

- Unabhängiger Review-Agent (read-only): Regeln „kein abgeleiteter Runtime-State“, „keine Secrets/Shell in React“, „Netzwerk nur über `transport.ts`“ ohne Verstoß; gefundene Restpunkte (hartkodierte „Nicht verbunden“-Texte im Produktionsmodus, Logs-Auswahl, veralteter Refresh nach `execute`, Proxy-Marker, Provider-Default) sind behoben. Nicht behoben: `isRefreshing` ohne UI, Logs-Quellenfilter ohne Funktion (Lovable), In-Flight-Abbruch bei Unmount, Ersetzen der UI durch den Fehlerzustand bei Ladefehler (bewusst ehrlich).

- `npm run build` ✔, `npx tsc --noEmit` ✔ (0 Fehler), `npm run lint` ✔ (0 Fehler, 6 shadcn-`react-refresh`-Warnungen). Das Projekt hat keine automatisierten Tests.
- Browser-QA bei 1672×941, 1920×1080, 2560×1440 (Prototype-Modus und Produktionsmodus gegen die echte Umgebung): alle 10 Bereiche ohne horizontalen Überlauf und ohne Skript-/React-Fehler; alle Tabs und Einstellungskategorien wurden bei 1672×941 (Produktion zusätzlich bei 1920×1080) durchgeklickt, bei den übrigen Größen nur die Bereichsnavigation. Zusätzlich im Prototype: Agent-Auswahl, Memory-/Logs-Filter, Automations-Sheet, Einstellungs-Schalter (localStorage), Bereichssuche.
- Produktion (live): Runtime `Nicht implementiert`; Dienstzeilen: Web-API „Antwortet mit HTTP 404“, Main LLM „Erreichbar, Health ok“, Small LLM/FLUX „Nicht erreichbar“, Chatterbox „Zugriff verweigert“, VVS „Erreichbar, ready“; Modell live aus `/v1/models`.
- Testdouble (nur UI-Pfade, kein Live-Nachweis): Watchdog-Zeiten, CPU-Snapshot-Karte, Memory-Zähler inkl. `memory:null`-Fall, Polling-Takt.

## 10. Modell-Komponenten und Ports (Stand 25.09.2026, Code/Testdouble)

Backend-seitig neue Komponenten im Runtime-Snapshot (siehe `Main/docs/RUNTIME_SUPERVISOR.md`); noch nicht auf Hardware gegen die UI geprüft.

| Komponente | Bedeutung | Port |
|---|---|---|
| `llm-primary` | Gemma 4 12B (`llm-main` bleibt als Alias) | 8080 |
| `llm-expert` | Qwen3.5-35B-A3B, Ruhezustand `STOPPED` | 8082 |
| `npu-sensor` | NPU-Sensorschicht (Präsenz) | - |

Der GPU-Handover (Primary -> Expert -> Primary) erscheint als `STARTING`. Zustände bleiben `STARTING/READY/DEGRADED/ERROR/STOPPED/OFFLINE/NOT_IMPLEMENTED`. Hinweis: Abschnitt 3 nennt für den Dienst Main LLM Port 8080 mit dem Qwen-Modell (Live-Stand vom 24.09.); das ist historisch. `get_status()` enthält zusätzlich `npu_sensor` und `vision_gate`.
