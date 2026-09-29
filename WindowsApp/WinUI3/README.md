# WinUI 3 migration baseline

This project is a native WinUI 3 / C# / .NET / Windows App SDK shell. The existing WPF project remains beside it as a technical reference.

`WindowsPackageType=None` selects unpackaged execution for this initial development baseline. Production distribution (MSIX, unpackaged, or another supported model) is intentionally undecided and must be reviewed before release.

The shell reads the local runtime through `Adapters/BackendHub.cs` (JARVIS web API, read-only, loopback `127.0.0.1:8091`) and `RuntimeSupervisorClient.cs` (Runtime Supervisor snapshot). Values without a backend source stay `UNAVAILABLE`, `NOT_IMPLEMENTED` or `NO LIVE DATA`. Mobile Connection is a separate area from Mobility/VVS, with no device or pairing data fabricated.

The WinUI project links (does not copy) the framework-neutral `JarvisApiClient.cs`, `JarvisListItem.cs`, `MetricBreakdown.cs`, and `MetricBucket.cs` source files from the preserved WPF folder. `JarvisApiClient` is used only behind `BackendHub`.

## WPF source classification

| Existing file / responsibility | Class | Evidence-based disposition |
|---|---|---|
| `Jarvis.ControlHub.csproj` | C | `UseWPF`, WPF WinExe and publish properties define the old target; retain it and create a separate WinUI project. |
| `App.xaml`, `App.xaml.cs` | C | WPF Application resources, `StartupUri`, and `System.Windows.Application` lifecycle require native WinUI equivalents. |
| `MainWindow.xaml`, `MainWindow.xaml.cs` | C | WPF Window, controls, routed events, visibility/brush APIs and visual-tree calls are framework-specific. |
| `MainWindowViewModel.cs` | B | Useful data shaping and freshness logic exists, but dispatcher, timer and WPF dialog dependencies need extraction behind platform-neutral services. Do not copy wholesale. |
| `JarvisApiClient.cs` | A | Uses BCL HTTP/JSON and fixed loopback endpoint policy; suitable for direct reuse after namespace/project reference review. |
| Runtime snapshot/action contracts in `RuntimeSupervisorClient.cs` | A | Records and action/result data contracts are framework-neutral. |
| Process launch, embedded PowerShell and repository discovery in `RuntimeSupervisorClient.cs` | B | Windows operations and repository-root access need an adapter boundary before reuse. |
| `RepositoryRootValidator` | A | Filesystem and reparse-point validation uses framework-neutral .NET APIs. |
| `JarvisListItem.cs`, `MetricBreakdown.cs`, `MetricBucket.cs` | A | Plain data records without WPF types. |
| `app.manifest` | B | Execution identity may remain relevant, but WinUI packaging/runtime settings need review. |
| `publish.ps1` | D | Current script publishes the WPF project; do not treat it as the WinUI release pipeline. |
| `bin/`, `obj/`, `artifacts/` | D | Generated output, not source to migrate. |

The Lovable project remains a design/interaction reference only. Its React/Tailwind implementation is not a dependency of this project.

## Backend wiring

Contract source: branch `Sleepy-Aktuell-|-27.09` (reference commit `3ef09b2ec9d54f97485eaa0fa072dddc9b0de2c2`), `jarvis_web.py`. UI safepoint for this wiring: `49302e39e8844bd72d8bb9169c3449e6ef934400`. All requests are `GET`; the client has no write path.

### Endpoints in use

| Endpoint | Used by | Notes |
|---|---|---|
| `/api/stats` | Chat, Memory, Models | 503 when components are not initialized. |
| `/api/desktop/snapshot` | Memory, Models, Voice, Tools, Settings | Allowlisted configuration and capability inventory. |
| `/api/events/recent?hours=24&limit=40` | Home (Recent Activity, Brain), Voice, Observability | Projection `timestamp`, `category`, `event`, `severity` only; event names outside the backend allowlist arrive as `unknown`. Newest first. |
| `/api/events/aggregate?hours=24` | Observability | Counts only. |
| `/api/memory/summary` | Home, Memory, Observability | Section errors are reduced to the section name. |
| `/api/agents/status` | Automations | 503 with `available: false` when no planner exists. |
| `/api/automations/status` | Automations | System schedulers; no user rule engine. |
| `/api/sessions?limit=1` | Chat | Only `total` is read. |
| `/api/webcam/status` | Vision | `available`, `running`; no frames are requested. |

Existing but not used: `/api/desktop/live`, `/api/events/{stt,tts,routing,speaker_id,watchdog,health}`, `/api/metrics/*`, `/api/history`, `/api/session/{id}`, `/api/memory/{facts,interactions,timeseries,db-health}`, `/api/governance/*`, `/api/observations/*`, `/api/gpu-status`, `/api/webcam/{stream,snapshot}`, `/ws`, `/ws/dashboard`. `/ws` is the web chat transport (write path); it is not a released desktop chat contract, so Chat stays `NOT_IMPLEMENTED`.

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
| `tool_completed` (tool_execution, info) | ToolResult | `core/tool_registry.py`, `core/pipeline.py`, `jarvis_web.py`; emitted only when the privacy gate allows content logging |
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

Cloud runs cover the adapter test harness and a C# type check against the Windows App SDK reference assemblies. Real XAML compilation, app start, header spacing and overflow behaviour at several window widths, backend connection and recovery, and live brain animation must be verified on Windows.
