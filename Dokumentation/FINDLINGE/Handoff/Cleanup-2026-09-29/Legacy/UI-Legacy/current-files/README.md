# J.A.R.V.I.S Control Hub — native Windows app

The deliverable is a real WPF `WinExe` (`WindowsApp/Jarvis.ControlHub.csproj`). It renders directly with Windows Presentation Foundation and does not host a browser or WebView. React/Vite and the existing Tauri tree are retained as older design/prototype work; they are not the native app build path.

## Build the executable

On Windows with the .NET 10 SDK and Windows Desktop targeting pack:

```powershell
.\WindowsApp\publish.ps1
```

The self-contained x64 executable is written to `WindowsApp/artifacts/publish/Jarvis.ControlHub.exe`. The first launch asks for the JARVIS `Main` checkout; the selected, validated repository path is stored in `%APPDATA%\JARVIS\ControlHub\runtime-root.txt`.

## Runtime and data

The native client calls only the closed `Main/JARVIS-Runtime.ps1` actions. Startup and refresh perform the read-only `getRuntime` query; lifecycle actions require both a Supervisor capability and an explicit confirmation. The script is bundled into the executable. The repository module and WSL supervisor remain in the selected `Main` checkout.

API reads use fixed HTTP loopback `127.0.0.1:8091` endpoints. `/api/desktop/live` is polled once per second and its source timestamp is shown as the measurement age; it is not replaced with historical health data. Routing points are polled every two seconds, but only a source event no older than five seconds is presented as live; older points remain explicitly historical. API statistics, voice aggregates, and tool metrics are polled less often. If `/api/events/aggregate` is unavailable, the event overview combines only the real 24-hour routing, STT, and TTS counters from their individual endpoints and identifies that fallback.

The Main source includes `/api/desktop/live`, `/api/desktop/snapshot`, `/api/agents/status`, and `/api/automations/status`. The deployed service may not yet expose the same routes as the checkout: the app reports HTTP 404/unavailable states as-is and never infers agent or automation data from skills/tools. Verify the live endpoints after deploying or reloading the Main web service.

`JARVIS_WEB_AUTH_TOKEN`, when present in the Windows process environment, is sent only as a bearer token to this loopback API. It is never written to app configuration or logs.
