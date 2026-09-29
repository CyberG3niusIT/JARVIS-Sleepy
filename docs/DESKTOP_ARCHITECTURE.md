# Desktop architecture decision

Status: accepted, 2026-09-29.

## Decision

- **Production desktop client: WinUI 3** — `WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj` (C#, .NET, Windows App SDK, XAML). It is the only desktop client in this repository.
- **WPF: retired legacy.** No WPF project, WPF reference or WPF test may exist in build, runtime or test paths. WPF must not be reintroduced.
- React, Tailwind, Vite, WebView, Node or a browser shell are not desktop client targets. Lovable is a design reference only.
- The backend (`jarvis_web.py`) is the source of truth. The desktop client reads the read-only desktop API on `127.0.0.1:8092` and never writes to it.

## Process and port ownership

| Process | Bind | Lifecycle owner | Clients |
|---|---|---|---|
| Voice daemon `jarvis_continuous.py` | — | `systemd/jarvis.service` via `start.sh`/`stop.sh` | — (single writer of memory, context, event log) |
| Desktop API `jarvis_web.py --desktop-mode` | `127.0.0.1:8092`, fixed | `systemd/jarvis-desktop-api.service` via `start.sh` (after voice is ready, readiness wait up to 90 s), `stop.sh` (before voice), `restart.sh`; `Restart=on-failure` | WinUI client only |
| Standard web `jarvis_web.py` | `web.port` (8091) on loopback, TLS `web.tls.port` (8443) when certificates exist | none in this repository (started by hand when needed) | browser UI, `scripts/jarvis-confirm`, `scripts/jarvis-circuit-reset`, `scripts/test_suite_v3`, `scripts/ws_test.py`, `tests/integration` |

Why a separate desktop process instead of an existing one: the voice daemon has no HTTP server and adding one would change the voice architecture; the standard web process starts its own reminder/news/weather pollers, health scheduler and observation collector (duplicates of the voice daemon's), serves write paths and has no lifecycle owner. The desktop mode already exists for exactly this role: read-only memory and context, no daemon workers, GET-only allowlist.

Readiness and health: `scripts/runtime_status.py` probes the unit state, that the unit's main process is this checkout's `jarvis_web.py --desktop-mode` and the only listener on 8092, that it listens on loopback only, and `/api/stats` (component `desktop-api`). `start.sh` waits on the same probe (`--desktop-api-ready`). A desktop API that is down or not ready never rolls back or blocks the voice backend: the start reports DEGRADED, and a broken or foreign listener degrades the runtime snapshot. Recovery is systemd's `Restart=on-failure`, or restart from the app. Port 8092 was chosen because no file in the repository uses it; whether a Windows program holds it can only be checked locally.

## What happened to the WPF code

The WPF Control Hub was not present in the integrated tree. Its last artefact, the harness `tests/WindowsAppFreshness.Tests`, set `UseWPF`, referenced the missing WPF project and drove the WPF view model through reflection, so it could not build. Before removal, each of its assertions was classified against the current backend contracts and the WinUI code:

| Legacy concern | Current rule | Where it lives now |
|---|---|---|
| Planner status without plan or step content | kept: the planner model carries only state and counters | `VerifyPortedLegacyChecks` in `tests/WinUiBackendAdapters.Tests` |
| Contradictory planner flags, overflowing or inconsistent step counters | adapted: checked against the invariants `agents_status_handler` guarantees (the WPF flag table would have rejected real `paused`+`awaitingConfirmation` and `running`+`awaitingConfirmation` payloads). A violation is a client-side presentation flag (`PlannerInfo.Implausible`); backend `available` and `state` are kept | `BackendParsers.ParseAgents`, same test |
| Stale planner snapshot via `observedAt` (15 s) | dropped: `observedAt` is the backend's request time, not plan age | test asserts no client-side staleness |
| Supervisor actions only on a fresh snapshot of the selected checkout | adapted: no clock comparison (the snapshot time comes from WSL, the check runs on Windows). The supervisor is queried before and again after the confirmation dialog; both answers must allow the action for the same checkout; one action at a time | `Adapters/RuntimeActionGuard.cs`, `ShellPage.RequestRuntimeActionAsync`, same test |
| Repository discovery, no silent fallback from an invalid explicit root, symlinked module or scripts folder rejected | kept (shared `RuntimeSupervisorClient.cs`, still used by WinUI) | same test |
| Routing/STT/TTS timelines, CPU/RAM live values, health history, search statistics, WPF summary strings | dropped: WinUI does not use these endpoints; desktop mode refuses them | — |
| Desktop snapshot endpoint hidden from summaries | not carried over: WinUI shows the allowlisted, non-secret LLM endpoint from `/api/desktop/snapshot` by design | — |

WPF-only view-model records (`JarvisListItem`, `MetricBreakdown`, `MetricBucket`) that WinUI compiled but never used were removed. `RuntimeSupervisorClient.cs` and `JarvisApiClient.cs` stay: WinUI uses them. What decides is current use, not origin.

## Enforcement

`tests/unit/test_no_wpf_desktop.py` is a static repository test (plain Python, no Windows SDK) and runs in CI (`.github/workflows/ci-python.yml`, step "WPF-Gate"). It fails when:

- any of these appear, case-insensitively, in any file under `WindowsApp/` (code, XAML, project files and its Markdown), in .NET test files under `tests/`, or in any `.csproj`/`.sln`/`.props`/`.targets` in the repository: `UseWPF`, `System.Windows`, `PresentationFramework`, `PresentationCore`, `WindowsBase`, `Microsoft.WindowsDesktop.App.WPF`, `Microsoft.NET.Sdk.WindowsDesktop`, a reference to the former WPF project file;
- `WindowsApp/` contains any project other than the WinUI 3 project (which must declare `UseWinUI` and the Windows App SDK);
- any `ProjectReference` in any project file points to a file that does not exist.

There are no exemptions inside that scope. This record lives in `docs/`, outside the scanned paths; it is the only place that names the retired technology in detail.
