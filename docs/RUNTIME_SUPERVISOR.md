# Runtime-Supervisor (Übergabestand)

Native Control Plane für die Desktop/Tauri-Anbindung. Stand: uncommitted auf
`backup/jarvis-runtime-voice-2026-09-24` (Basis `a977e1e`).

```
Tauri -> JARVIS-Runtime.ps1 -> JARVIS.Runtime.psm1 -> wsl.exe -> scripts/runtime_status.py -> Dienste
```

## Bedienung

| Aktion | Aufruf | Ausgabe |
|---|---|---|
| getRuntime | `powershell.exe -NoProfile -File JARVIS-Runtime.ps1 -Action getRuntime` | `RuntimeControlSnapshot` als ASCII-JSON |
| start / stop / restart | `... -Action start\|stop\|restart` | `{"accepted":bool,"message":str}` (Lifecycle läuft detached; `-Wait` = synchron) |

`-Action` ist per `ValidateSet` auf diese vier Werte geschlossen. Es gibt keine
Möglichkeit, Befehle oder Skripte zu übergeben. Die Aktion bestätigt nur; den
Zustand liefert das nächste `getRuntime` (Polling, Button bis dahin sperren).

## Zustandsvertrag (identisch zu `UI/src/lib/jarvis/runtime-control.ts`)

`state`, `degradedReasons: string[]`, `updatedAt` (ISO 8601 UTC), `components: [{id,name,state,detail?}]`,
`capabilities: {start,stop,restart}`, optional `detail`. Limits: 64 Einträge, 500 Zeichen.

Der Zustand wird nur in `scripts/runtime_status.py::derive_state` entschieden. Windows ergänzt nur
OFFLINE (WSL läuft nicht) und STARTING (Lifecycle bootet WSL).

| State | Bedingung |
|---|---|
| READY | Voice-Daemon aktiv **mit frischem Heartbeat** (PID/Invocation passen, Listener läuft), Haupt-LLM, STT-Modell, kanonisches Chatterbox bereit |
| DEGRADED | Pflichtkomponente nicht bereit (auch fehlender/alter/fremder Heartbeat) oder optionale eingeschränkt; verwaister Lifecycle-Record bei gesundem Backend; laufender Stop |
| STARTING | kontrollierter Start/Restart läuft (lebender Lifecycle-Prozess) oder Unit `activating` |
| ERROR | `jarvis.service` failed/crasht, letzter Start fehlgeschlagen, Lifecycle abgebrochen bei nicht gesundem Backend, systemd/Config nicht lesbar, Probe nicht auswertbar |
| STOPPED | `jarvis.service` wirklich inaktiv oder nicht installiert (LLM/Chatterbox laufen laut `stop.sh` weiter und werden einzeln gemeldet) |
| OFFLINE | WSL-Distribution läuft nicht (nur Windows-Seite) |
| NOT_IMPLEMENTED | nur auf Komponentenebene: `web` (kein Lifecycle-Owner), `vvs` ohne URL |

Capabilities: START nur bei STOPPED/ERROR/OFFLINE, STOP/RESTART bei READY/DEGRADED/ERROR.
Während ein kontrollierter Lifecycle läuft, sind alle drei false.

Zustandsdateien (nur `core/runtime_state.py`, atomar, `schema:1`):
`$XDG_RUNTIME_DIR/jarvis-runtime/voice-heartbeat.json` (Watchdog, alle 10 s) und `lifecycle.json`
(start/stop/restart.sh). Windows-Marker: `%LOCALAPPDATA%\JARVIS\Runtime\<hash>\lifecycle.json`
(verfällt nach 30 min, PID muss PowerShell sein).

## Windows-Audio-Brücke (Komponente `audio-bridge`)

JARVIS spielt mit `audio.output_backend: windows` über `powershell.exe` aus WSL (`core/tts.py::_play_wav_windows`).
Die Probe prüft das passiv (es wird nichts ausgeführt oder abgespielt) und nur, solange der Daemon aktiv ist:

1. `/proc/sys/fs/binfmt_misc/WSLInterop` vorhanden, `enabled`, Magic `4d5a` (fehlt/deaktiviert/korrupt/unlesbar -> DEGRADED)
2. `powershell.exe` und `wslpath` sind im PATH des Daemons (`/proc/<MainPID>/environ`) auffindbar und ausführbar
   (unlesbare Umgebung -> DEGRADED)

`WSL_INTEROP` ist bewusst **keine** Bedingung: Der Socket des Daemons gehört zur kurzlebigen wsl.exe-Sitzung, die `start.sh`
ausgeführt hat, und ist Minuten später weg. Live belegt (2026-09-25, Handler registriert): `powershell.exe` läuft aus einem
transienten systemd-Dienst mit dem veralteten Manager-Env **und** mit leerer Variable, ebenso aus einer Sitzung ohne Variable
(`/init` fällt zurück). Eine frühere Version der Probe meldete den veralteten Socket als DEGRADED, das war ein False Positive.

Alle unabhängigen Ursachen werden zusammen gemeldet. Eine Pflichtkomponente: ohne Ausgabe kein READY.
`derive_state` ist unverändert; die Komponente kommt nur als weiterer Befund hinein.

### Befund 2026-09-25 (live)

- `WSLInterop` ist in `binfmt_misc` **nicht registriert** (Verzeichnis geändert 01:04:43, kein einziger Eintrag). Deshalb
  scheitert jede Windows-`.exe` aus WSL (`Exec format error`), erster Fehler im Journal 05:45:43, **vor** dem Restart.
- Es existiert bereits `/etc/systemd/system/wsl-interop-binfmt.service` (enabled, 2026-09-14): ein `oneshot` mit
  `RemainAfterExit`, der beim Boot (21:55:23) erfolgreich registrierte, aber nie erneut läuft. Was den Eintrag um 01:04
  entfernt hat, ist nicht bewiesen (System-Journal und `kern.log` sind für den Benutzer nicht lesbar).
- Der `WSL_INTEROP`-Socket des Daemons (`/run/WSL/71159_interop`, Sitzung des Restarts) war ebenfalls weg. `start.sh`
  importiert den Socket der *aktuellen* wsl.exe-Sitzung in den systemd-User-Manager, er stirbt mit dieser Sitzung. Das ist
  **harmlos** (siehe oben, live verifiziert) und daher kein Befund der Probe; `start.sh` bleibt unverändert.

### Reparatur (2026-09-25 07:41, ausdrücklich freigegeben und ausgeführt)

Einzige Root-Änderung: `wsl.exe -d Ubuntu-24.04 -u root -- systemctl restart wsl-interop-binfmt.service` (vorhandene Unit,
`Result=success`). Danach `WSLInterop`: `enabled`, `interpreter /init`, `flags: PF`, `offset 0`, `magic 4d5a`.
Windows-Test ohne Audio (`powershell.exe -Command Write-Output ...`) erfolgreich, `wslpath` ok. Danach kontrollierter Restart,
`audio-bridge` live READY. Das persistiert **nicht** über einen erneuten Verlust des Eintrags hinaus (siehe unten).
Die ursprünglich geplanten Schritte zur Nachvollziehbarkeit:

```powershell
# 1. Handler erneut registrieren: führt den vorhandenen, abgesicherten ExecStart aus (idempotent)
wsl.exe -d Ubuntu-24.04 -u root -- systemctl restart wsl-interop-binfmt.service
# 2. Daemon mit gültiger Sitzung neu starten (neuer WSL_INTEROP-Socket)
powershell.exe -NoProfile -File .\JARVIS-Runtime.ps1 -Action restart -Wait
# Rollback von 1.:
wsl.exe -d Ubuntu-24.04 -u root -- sh -c "echo -1 > /proc/sys/fs/binfmt_misc/WSLInterop"
```

Danach muss `getRuntime` `audio-bridge` READY zeigen; sonst verbleibt der konkrete Grund im Snapshot.

### Warum verschwindet der Eintrag? (Analyse, nichts installiert)

- Die vorhandene Unit ist ein `oneshot` mit `RemainAfterExit=yes`: Sie registriert einmal beim Boot und gilt danach als
  `active (exited)`. Ein `systemctl start` auf eine bereits aktive Unit ist ein No-op, ein Timer allein würde also nichts bewirken.
- Der Eintrag verschwand um 01:04:43 (Verzeichniszeitstempel), ohne dass `systemd-binfmt` lief (es ist inaktiv, sonst wären auch die
  `binfmt.d`-Einträge, z. B. `python3.12`, registriert; es sind keine registriert). Auch `apt`/`dpkg` liefen nicht (nur 06:07).
  Windows zeigt um 01:04 keinen WSL-/VM-Prozessstart und keine passenden Events. Der Auslöser bleibt **unbelegt**
  (System-Journal/`kern.log` sind für den Benutzer nicht lesbar).
- Ein `binfmt.d`-Eintrag hilft nicht: Er wirkt nur, wenn `systemd-binfmt` läuft (hier nie), und nicht bei einem Verlust im Betrieb.

### Empfehlung (kleinste dauerhafte Lösung, noch nicht installiert, braucht Freigabe)

Die vorhandene, bereits abgesicherte Registrierung periodisch erneut ausführen:
1. In `wsl-interop-binfmt.service` `RemainAfterExit=yes` entfernen (die Guard `[ ! -e .../WSLInterop ]` macht jeden Lauf idempotent).
2. Neue `wsl-interop-binfmt.timer` (`OnBootSec=30s`, `OnUnitActiveSec=1min`, `WantedBy=timers.target`), die diese Unit auslöst.
Zwei Root-Dateien, keine neue Logik, Rollback = beide entfernen. Der Supervisor meldet einen erneuten Verlust ohnehin innerhalb
eines Polls als `audio-bridge` DEGRADED; die Reparatur bleibt der eine `wsl -u root`-Befehl von oben, bis die Timer-Lösung freigegeben ist.

## SIGKILL beim Stopp des Voice-Daemons (Analyse, nichts geändert)

Journal des alten Daemons (PID 4061): `Shutdown signal received` 06:25:47 -> alle Teilsysteme gestoppt ->
`Jarvis stopped` 06:25:58 (11 s) -> **Prozess beendet sich danach nicht** -> `stop-sigterm timed out` 06:26:06
(`TimeoutStopSec=20`) -> SIGKILL für den Hauptprozess und den `multiprocessing.resource_tracker`-Kindprozess.

- Der Anwendungs-Shutdown ist vollständig, es fehlt kein Cleanup-Schritt. Er dauert 11 s (News, Wetter, Reminder werden
  nacheinander mit je 3-4 s gestoppt), lässt also nur ~9 s für das Beenden eines Prozesses mit 8,7 GB Peak-Speicher
  (1,1 GB Swap) und ~95 Threads.
- Im JARVIS-Code gibt es keinen selbst erzeugten nicht-daemonischen Thread (statisch geprüft). Das genügt **nicht** als Beleg:
  `ThreadPoolExecutor`-Worker (z. B. `core/task_planner.py:628`) werden beim Interpreter-Ende per `atexit` gejoint, und
  native Bibliotheks-Threads (Torch/CUDA/ONNX/PortAudio) liegen nicht im JARVIS-Code. Die These "langsamer Teardown eines
  8,7-GB-Prozesses" ist plausibel, aber **unbewiesen**. Der `resource_tracker` ist Folge, nicht Ursache (er endet erst mit dem Hauptprozess).
- **Zweiter Stopp (2026-09-25 07:42, kontrollierter Restart): kein SIGKILL.** Signal 07:42:49 -> `Jarvis stopped` 07:42:51
  (2 s) -> Prozessende 07:43:00, also wieder **~9 s** zwischen Anwendungsende und Exit (Peak 6,3 GB, 0 Swap), gesamt 11 s.
  Der erste Stopp brauchte 11 s für die Teilsysteme + ~8-9 s Exit = 19-20 s und riss die Grenze von 20 s.
  Messbild: der Exit-Nachlauf ist konstant (~9 s), die Anwendungsphase schwankt (2-11 s); die Reserve zu `TimeoutStopSec=20`
  ist dünn. Das erklärt das SIGKILL, ohne die Ursache des Nachlaufs zu klären.
- Messen statt raten, beim nächsten *gewollten* Stopp: kurz nach `Jarvis stopped` `py-spy dump --pid <MainPID>` (falls
  installiert) oder `faulthandler.dump_traceback_later(...)`, um `threading.enumerate()` und Executor-Worker zu sehen.
- Optionen erst danach (Nutzerentscheidung): `TimeoutStopSec` in `systemd/jarvis.service` auf ~45 s (die Repo-Unit ist verlinkt),
  oder ein expliziter harter Prozess-Exit nach dem Cleanup.

### Bekannte Regelabweichung Bash/Python

`start.sh` verlangt für die Windows-Audio-Umgebung exakt `/mnt/c/Windows/System32/WindowsPowerShell/v1.0` im PATH des Daemons;
die Probe akzeptiert jedes auffindbare `powershell.exe` (und prüft zusätzlich den Interop-Handler, den `start.sh` nicht prüft).
Die Probe ist die weitergehende Prüfung; `start.sh` würde den heutigen Ausfall (Handler fehlt) nicht bemerken und meldet weiter READY/DEGRADED nur wegen des Small-LLM.

## Port-Audit

`jarvis_web` nutzt **8091** (HTTPS 8443 unverändert). 8088 gehört der VVS API
(`wimaedv-vvs-api.service`), 8089 dem Webcam-Frame-Server (`core/webcam_server.py`).

Verbleibende 8088 im Repo sind ausschließlich VVS: `.env`, `docs/SCHOOL_MOBILITY.md`, `docs/ARCHITECTURE.md` (Hinweis),
`config.yaml` (Kommentar), VVS-Tests (`test_runtime_dependencies`, `test_mobility_demand`, `test_school_mobility_flow`,
`test_runtime_status`). Bewusst unverändert, weil sie ein mögliches Secret enthalten (siehe Token-Audit):
`tests/components/test_pres_engine.py:737`, `test_pres_flex.py:864` (manuelle Skripte, meinen `jarvis_web`).

**Später in der UI zu ändern (read-only, nicht geändert):**
- `UI/vite.config.ts:17` `target("JARVIS_WEB_URL", "http://127.0.0.1:8088")` -> `8091`
- `UI/vite.config.ts:13` und `:24` Kommentare (`jarvis_web.py 8088`, `port 8088`) -> `8091`
- `UI/README.md:29` (`JARVIS_WEB_URL (8088)`) -> `8091`; `:31` Hinweis "gleicher Default-Port" entfällt
- `UI/vite.config.ts:138` `JARVIS_VVS_URL` bleibt `8088` (korrekt)
- Außerhalb der Worktrees veraltet: `Dokumentation/13_KNOWN_ISSUES.md:6`, `COMPONENTS/ENTRYPOINTS.md:19`,
  `16_UI_CONTROL_HUB.md:119/130`, `08_SCHOOL_MOBILITY.md:11`

## Token-Audit (keine Werte hier)

- `tests/components/test_pres_engine.py:737` und `test_pres_flex.py:864`: **derselbe** 43-Zeichen-Wert,
  Format wie `secrets.token_urlsafe(32)` in einer `?token=`-URL des Web-WebSockets. **Möglicherweise echt.**
- Git-Historie betroffen: seit Commit `5b9c40b`/`7ed8fc2` (2026-03-05, Web-Auth-Layer) und den Presentation-Test-Commits
  (2026-03-11); mehrere dieser Commits sind auf `origin/main` und allen Remote-Branches. Ein Commit vom 2026-03-12
  erwähnt ein "token-exposed image".
- Kein aktuell konfiguriertes Secret auf diesem System stimmt überein (`JARVIS_WEB_AUTH_TOKEN` ist nirgends gesetzt);
  das beweist nicht, dass der Wert nie echt war.
- `docs/SETUP_GUIDE.md:182`: 15-Zeichen-Platzhalter, kein Secret.
- **Nicht verändert, nicht rotiert.** Entscheidung beim Nutzer: Token rotieren (falls je verwendet), Tests auf
  Umgebungsvariable umstellen, Historie bereinigen nur bei nicht öffentlichem Remote.

## Chatterbox / OpenClaw (Port 8765)

- Windows-Loopback `127.0.0.1:8765` gehört `OpenClaw.Tray.WinUI.exe` (http.sys, `Microsoft-HTTPAPI/2.0`) und antwortet auf
  jede Anfrage mit **401**. Das ist die Quelle des gemeldeten Auth-Verhaltens.
- Der echte Chatterbox (`/home/alex/chatterbox-venv/.../tools/chatterbox_server.py`, WSL) bindet `127.0.0.1:8765`,
  hat **keine** Auth im Code und antwortet in WSL mit 200 auf `/health` und `/config`.
- Der Supervisor prüft aus WSL und ist nicht betroffen. Ein Windows-Client, der `127.0.0.1:8765` anspricht,
  erreicht OpenClaw statt Chatterbox (und sendet ggf. Text an ein fremdes Programm).
- Mögliche spätere Lösung (Entscheidung offen, nichts geändert): Windows-Clients sprechen Chatterbox nie direkt an
  (nur über Supervisor/JARVIS-API), oder Chatterbox bekommt einen freien Port und ein Shared Secret.

## jarvis_web als Dienst (nur Analyse)

- Es gibt keine `jarvis-web.service` im Repo (historisch dokumentiert, nie geliefert; `developer_tools.py:339` vermerkt das).
- `on_startup` startet eigene Reminder-, News-, Wetter-Poller, Health-Scheduler und Observation-Collector, wie der
  Voice-Daemon. Beide Prozesse parallel = doppelte Hintergrund-Worker.
- `.certs` fehlt: HTTPS ist faktisch aus. `web.host` ist `0.0.0.0`, `web.auth_token` kommt aus einer nicht gesetzten Variable.
- Alle Routen außer statischen Dateien verlangen Auth; einen Identity-/Health-Endpunkt ohne Token gibt es nicht.
- Kleinste saubere Lösung später: User-Unit `jarvis-web.service` (`--port 8091`, Loopback), ein minimaler Endpunkt
  `{"service":"jarvis_web"}`, dann `probe_web` mit Identitätsprüfung. **Vorab entscheiden:** Poller-Duplikate
  (Web ohne Hintergrund-Worker starten?), Token-Politik, `web.host`.

## Modell-Komponenten und GPU-Handover (Stand 2026-09-25)

Evidenz: Logik nur mit Fakes getestet (Fake-`systemctl`); **nicht** auf Hardware gegen den Supervisor geprüft.

Neue Komponenten im Snapshot (`components`):

| id | Bedeutung | Ruhezustand |
|---|---|---|
| `llm-primary` | Gemma 4 12B (Port 8080); `llm-main` bleibt als Alias | - |
| `llm-expert` | Qwen3.5-35B-A3B (Port 8082, GPU-exklusiv) | `STOPPED` (normal) |
| `npu-sensor` | NPU-Sensorschicht (Präsenz) | - |

Ein laufender Handover Primary -> Expert -> Primary wird als `STARTING` gemeldet. Gemma und Qwen sind nie gleichzeitig resident.

Handover-Record: pro Wechsel schreibt der Python-Handover einen Lifecycle-Record mit Zeitstempeln je Phase (Primary stoppen, GPU frei, Expert starten, Health, Antwort, Expert stoppen, Primary wiederherstellen). Daraus stammt die Messung Qwen-Laden ca. 90-100 s.

Konfiguration: Block `handover.*` in `config.yaml`; die Primary-Unit kommt aus `handover.units.primary` bzw. `llm.primary.unit` (Override: `JARVIS_LLM_UNIT`; Legacy `llama-server.service` nur als Fallback). Dieselbe Auflösung nutzen `start.sh` und der Supervisor. Hinweis: Ohne Linger beendet WSL den User-systemd, wenn die letzte Session endet; der Start über `JARVIS-Runtime.ps1` hält dafür einen Keepalive, ein direkter `wsl -e bash start.sh` nicht. Die Units laufen im **User-Scope** (`systemctl --user`).

Grenzen: Die Eigentümer-Prüfungen (FragmentPath, ExecStart, Port-Besitzer) existieren in `start.sh`, nicht im Python-Handover. `core/gpu_swap.py` ist stale (System-Scope-sudo, nur FLUX); `/api/gpu-status` nutzt es noch. NPU: Präsenz auf Dateieingabe belegt, Live-Kamera auf NPU und NPU-Wake-Word NOT_IMPLEMENTED.
