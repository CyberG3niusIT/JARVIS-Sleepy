# Desktop architecture decision

Status: accepted, 2026-09-29.

## Decision

- **Production desktop client: WinUI 3** — `WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj` (C#, .NET, Windows App SDK, XAML). It is the only desktop client in this repository.
- **WPF: retired legacy.** No WPF project, WPF reference or WPF test may exist in build, runtime or test paths. WPF must not be reintroduced.
- React, Tailwind, Vite, WebView, Node or a browser shell are not desktop client targets. Lovable is a design reference only.
- The backend (`jarvis_web.py`) is the source of truth. The desktop client reads the read-only desktop mode on `127.0.0.1:8091` and never writes to it.

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
