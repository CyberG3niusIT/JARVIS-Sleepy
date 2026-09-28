# Windows freshness regression checks

This is a zero-dependency executable check harness, not a `Microsoft.NET.Test.Sdk` project. Run it explicitly with:

```powershell
dotnet run --project tests/WindowsAppFreshness.Tests/WindowsAppFreshness.Tests.csproj --configuration Release
```

It uses the real WPF view model and dispatcher timer, with controlled in-memory telemetry and Runtime Supervisor snapshots. It does not call JARVIS, WSL, or any external service.

## Routing freshness and event-summary fallback

The checks verify that routing history older than five seconds is never labeled live, while a recent source timestamp can be; they also verify that the 24-hour event overview can combine only the real routing, STT, and TTS counters when `/api/events/aggregate` is missing. Fixed category labels are used, and transcript, prompt, query, skill, and dynamic route sentinel values must not appear in the overview.

Validation on 2026-09-27: the regression check first failed because the missing-aggregate path was absent, then passed after the fallback was implemented. `dotnet run --project tests/WindowsAppFreshness.Tests/WindowsAppFreshness.Tests.csproj -c Release --no-restore`, `dotnet build WindowsApp/Jarvis.ControlHub.csproj -c Release --no-restore`, `dotnet format WindowsApp/Jarvis.ControlHub.csproj whitespace --verify-no-changes --no-restore`, and `git diff --check` passed; build had zero warnings/errors. The checked-out Main API contract tests also passed (`25 passed`). No coverage tool is configured for this dependency-free harness.
