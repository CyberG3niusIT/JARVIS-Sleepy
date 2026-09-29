# J.A.R.V.I.S native desktop (WinUI 3)

The production desktop client is `WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj`: WinUI 3, C#, .NET, Windows App SDK, XAML. There is no other desktop client in this repository.

`WindowsPackageType=None` selects unpackaged execution for this development baseline. Production distribution (MSIX, unpackaged, or another supported model) is intentionally undecided and must be reviewed before release.

The shell reads the local runtime through `Adapters/BackendHub.cs` (JARVIS web API, read-only, loopback `127.0.0.1:8091`) and `WindowsApp/RuntimeSupervisorClient.cs` (Runtime Supervisor snapshot via the embedded `JARVIS-Runtime.ps1` from the repository root). Values without a backend source stay `UNAVAILABLE`, `NOT_IMPLEMENTED` or `NO LIVE DATA`. Mobile Connection is a separate area from Mobility/VVS, with no device or pairing data fabricated.

`WindowsApp/JarvisApiClient.cs` and `WindowsApp/RuntimeSupervisorClient.cs` sit outside the project folder and are linked into it; `JarvisApiClient` is used only behind `BackendHub`.

The Lovable project remains a design/interaction reference only. Its React/Tailwind implementation is not a dependency of this project.

### Legacy WPF client (removed)

The earlier WPF Control Hub (`Jarvis.ControlHub.csproj`, `MainWindowViewModel`) is not part of this repository and is not a supported target. Its remaining test harness `tests/WindowsAppFreshness.Tests` referenced that missing project and could not build; the checks that still apply to the WinUI code were ported to `tests/WinUiBackendAdapters.Tests` (`VerifyPortedLegacyChecks`) before the harness was removed. WPF-only data records (`JarvisListItem`, `MetricBreakdown`, `MetricBucket`) that the WinUI client never used were removed with it.

## Backend wiring

Contract source: `jarvis_web.py` on the integration branch (backend handoff `handoff/opus-backend-20260929-1821`). All requests are `GET`; the client has no write path.

### Desktop mode and port

- `python jarvis_web.py --desktop-mode` is the read-only second process for this client: fixed to `127.0.0.1:8091`, no TLS, no voice, only the nine `GET`/`HEAD` paths below (`_DESKTOP_READ_ALLOWLIST`); every other path, including all `/api/mail/*`, `/ws` and static files, is refused with HTTP 403 and `desktopMode: true`. Memory and context are opened read-only; calendar, news, weather, health scheduler and observation collector are not started.
- The standard web process also listens on `127.0.0.1:8091` (`config.yaml` `web.port`). Only one of the two can run at a time; `scripts/runtime_status.py` reports which mode owns the port. The client works against either.
- Authentication: the client sends `Authorization: Bearer <JARVIS_WEB_AUTH_TOKEN>` when that variable is set in the Windows environment. Desktop mode needs no token. The standard mode needs the same value as its own `JARVIS_WEB_AUTH_TOKEN` when a token is configured. HTTP 401 is reported as an authentication problem, HTTP 403 as a path outside the desktop allowlist.
- No repository script starts the web process in either mode. Starting it, and reaching WSL's `127.0.0.1:8091` from Windows, is part of local verification.

### Planner and lifecycle safety

- `/api/agents/status`: the page shows the backend's `state` as reported. Step counts are shown only if the payload satisfies the invariants `agents_status_handler` itself guarantees (`paused` implies state `paused`; otherwise `awaitingConfirmation` implies `awaiting_confirmation`; otherwise `active` is true exactly for `running`; the five step counters sum to `stepCount`). A payload that breaks them is marked implausible on the client side (`PlannerInfo.Implausible`) and shown without numbers; this is a client presentation check, not a runtime state. `observedAt` is the backend's request time, so the client does not derive staleness from it. In desktop mode the planner is `BACKEND OWNED`.
- Start, stop and restart are decided only from Runtime Supervisor facts: the client queries the supervisor for the selected checkout before the confirmation dialog and again after it, and runs the action only if both answers allow it for that same checkout (`Adapters/RuntimeActionGuard.cs`). There is no wall-clock comparison between the WSL-generated `updatedAt` and the Windows clock.

### Endpoints in use

| Endpoint | Used by | Notes |
|---|---|---|
| `/api/stats` | Chat, Memory, Models | 503 when components are not initialized. |
| `/api/desktop/snapshot` | Memory, Models, Voice, Tools, Settings | Allowlisted configuration and capability inventory. |
| `/api/events/recent?hours=24&limit=40` | Home (Recent Activity, Brain), Voice, Observability | Projection `timestamp`, `category`, `event`, `severity` only; event names outside the backend allowlist arrive as `unknown`. Newest first. |
| `/api/events/aggregate?hours=24` | Observability | Counts only. |
| `/api/memory/summary` | Home, Memory, Observability | Section errors are reduced to the section name. |
| `/api/agents/status` | Automations | Desktop mode: `available: false`, `state: backend_owned`. Standard mode: validated as described above. |
| `/api/automations/status` | Automations | System schedulers; no user rule engine. |
| `/api/sessions?limit=1` | Chat | Only `total` is read. |
| `/api/webcam/status` | Vision | `available`, `running`; no frames are requested. |

`/api/sessions` counts the sessions of the backend's default user (`user`); the client does not pass a user.

Existing but not used (and refused in desktop mode): `/api/desktop/live`, `/api/events/{stt,tts,routing,speaker_id,watchdog,health}`, `/api/metrics/*`, `/api/history`, `/api/session/{id}`, `/api/memory/{facts,interactions,timeseries,db-health}`, `/api/governance/*`, `/api/observations/*`, `/api/gpu-status`, `/api/webcam/{stream,snapshot}`, `/ws`, `/ws/dashboard`. `/ws` is the web chat transport (write path); it is not a released desktop chat contract, so Chat stays `NOT_IMPLEMENTED`.

### Areas without a backend contract

Privacy gates (microphone, camera, screen, clipboard), cloud permission, remote tools and MCP, presence and sensors, expert model identity, rule engine, Mobility/VVS connections and route context, mobile pairing and devices, structured log stream, configuration writes. These keep their honest state.

### Brain stage: observable events

Pipeline: `/api/events/recent` -> `BrainEventCursor` -> `BrainEventMapping` -> `BrainActivityRenderer.Raise`. Only `category`, `event` and `severity` are evaluated. No prompt, user, assistant, memory, tool argument or tool result content is read or created.

| Backend event (category, severity) | BrainActivityType | Emit site |
|---|---|---|
| `stt_transcription` (inference, info) | InputReceived | `core/stt.py`, `core/stt_qwen3.py`: transcript with text |
| `stt_transcription` (inference, error) | ErrorEvent | STT failed |
| `route_completed` (decision, info) | ModelRouting | `core/conversation_router.py` after routing |
| `llm_call` (inference, info) | ModelInference | `core/llm_router.py` `_record_call`, `core/claude_consultation.py` |
| `llm_call` (inference, error) | ErrorEvent | failed model call |
| `tool_completed` (tool_execution, info) | ToolResult | `core/tool_registry.py` (only when the privacy gate allows content logging), `core/pipeline.py`, `jarvis_web.py` (web search) |
| `tool_completed` (tool_execution, error) | ErrorEvent | tool raised |
| `watchdog_*` (error_recovery, warn) | DegradedEvent | `core/watchdog.py` `_emit_recovery` |

Not mapped on purpose: `stt_transcription` with severity debug (empty result), `tts_synthesis`, `tts_cache_hit`, `turn_latency`, `speaker_identified`, `skill_intent_completed`, `conversation_opened`, `conversation_closed`, `cloud_consultation`, `config_*`, `governance_*`, `proposal_*`, `unknown`.

No real source, never raised by live wiring: ToolCall (no tool start event), MemoryRetrieval, ContextBuild, ResponseGeneration, MemoryWriteConfirmed.

### Live event bridge

- `BrainEventBridge` runs one loop per loaded `ShellPage`; it starts in `Loaded` and ends when the page lifetime token is cancelled in `Unloaded`. No overlapping requests.
- Poll interval 2.5 s while the source is readable, 10 s after `OFFLINE`, `UNAVAILABLE` or `ERROR`. The same `BackendHub` probe and failure classification are used.
- The first readable snapshot is a baseline and is never animated. After any interruption the next readable snapshot is a baseline again, so missed history is not replayed.
- Deduplication uses the observable fields (time, category, event, severity); the backend has no event id. Two identical events in the same millisecond across two polls count once.
- New events are processed oldest first; equal timestamps follow the backend order reversed.
- Events older than the newest seen timestamp minus 5 s are treated as history.
- Per poll at most `BrainActivityScheduler.MaxConcurrentPulses` mapped events, the most recent ones, 220 ms apart. The renderer additionally admits at most `MaxConcurrentPulses` concurrent pulses.
- Transport errors, `OFFLINE` and `UNAVAILABLE` never create brain activity. Backend offline means the stage stays idle.
- Events are shown only while Home is visible; the cursor still advances, so returning to Home does not replay them.
- Status overlay: `AKTIV.` only while real events animate; otherwise `IDLE. READY.` (source reachable, no new events), `IDLE. OFFLINE.`, or `IDLE. UNAVAILABLE.`.
- `JARVIS_BRAIN_TEST_SEQUENCE` (`1`, `loop`, `single`) is TEST-ONLY. When it is set the live bridge does not start.

### Header layout

The title bar chooses its density from the available width of the navigation column, not the window width: status labels (Runtime, Privacy, Cloud) are hidden first, then tabs switch to the compact size of the reference (`min-width 4.4rem`, `padding-inline 0.45rem`). Tabs are 2.4 apart (`.jx-tabs gap`). If even the compact tabs do not fit, the NavigationView overflow button remains reachable with 9.6 spacing to the last tab; items inside the overflow menu use the horizontal `.jx-menu-item` layout because the overflow row template has a fixed height of 36.

### Windows verification required

Cloud runs cover `tests/WinUiBackendAdapters.Tests` and a C# type check against the Windows App SDK reference assemblies. Real XAML compilation, app start, header spacing and overflow behaviour at several window widths, backend connection (desktop and standard mode) and recovery, supervisor lifecycle actions, and live brain animation must be verified on Windows.
