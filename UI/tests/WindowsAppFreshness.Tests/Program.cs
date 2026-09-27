using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Windows.Threading;
using Jarvis.ControlHub;

internal static class Program
{
    [STAThread]
    private static int Main()
    {
        var failures = new List<string>();
        using var viewModel = new MainWindowViewModel();
        var type = typeof(MainWindowViewModel);
        var privateInstance = BindingFlags.Instance | BindingFlags.NonPublic;
        var updateFreshness = type.GetMethod("UpdateFreshnessText", privateInstance)
            ?? throw new InvalidOperationException("Freshness update method was not found.");
        var isActionAllowed = type.GetMethod("IsRuntimeActionAllowed", privateInstance)
            ?? throw new InvalidOperationException("Runtime action guard was not found.");
        var applyRuntime = type.GetMethod("ApplyRuntimeAsync", privateInstance)
            ?? throw new InvalidOperationException("Runtime snapshot apply method was not found.");
        var applyHealth = type.GetMethod("ApplyHealthHistoryAsync", privateInstance)
            ?? throw new InvalidOperationException("Health history apply method was not found.");
        var applySearchStats = type.GetMethod("ApplySearchStatsAsync", privateInstance)
            ?? throw new InvalidOperationException("Search stats apply method was not found.");
        var applySnapshot = type.GetMethod("ApplySnapshotAsync", privateInstance)
            ?? throw new InvalidOperationException("Desktop snapshot apply method was not found.");
        var applyStt = type.GetMethod("ApplySttAsync", privateInstance)
            ?? throw new InvalidOperationException("STT event apply method was not found.");
        var applyTts = type.GetMethod("ApplyTtsAsync", privateInstance)
            ?? throw new InvalidOperationException("TTS event apply method was not found.");
        var applyRoutingEvents = type.GetMethod("ApplyRoutingEventsAsync", privateInstance)
            ?? throw new InvalidOperationException("Routing event apply method was not found.");
        var markEventsAggregateMissing = type.GetMethod("MarkEventsAggregateMissing", privateInstance);
        var applyAgentStatus = type.GetMethod("ApplyAgentStatusAsync", privateInstance)
            ?? throw new InvalidOperationException("Agent status apply method was not found.");
        var applyAutomationsStatus = type.GetMethod("ApplyAutomationsStatusAsync", privateInstance)
            ?? throw new InvalidOperationException("Automation status apply method was not found.");
        var repositoryValidator = type.Assembly.GetType("Jarvis.ControlHub.RepositoryRootValidator")
            ?? throw new InvalidOperationException("Repository root validator was not found.");
        var discoverRoot = repositoryValidator.GetMethod("DiscoverFrom", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Repository root discovery method was not found.");
        var resolveConfiguredRoot = repositoryValidator.GetMethod("ResolveConfiguredRoot", BindingFlags.Static | BindingFlags.Public)
            ?? throw new InvalidOperationException("Configured repository root resolution method was not found.");
        var reparseGuard = repositoryValidator.GetMethod("HasReparsePointInPath", BindingFlags.Static | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Repository reparse-point guard was not found.");
        var validateRoot = repositoryValidator.GetMethod("Validate", BindingFlags.Static | BindingFlags.Public)
            ?? throw new InvalidOperationException("Repository validation method was not found.");
        var requiredFiles = (string[])(repositoryValidator.GetField("RequiredFiles", BindingFlags.Static | BindingFlags.NonPublic)?.GetValue(null)
            ?? throw new InvalidOperationException("Required repository files were not found."));
        SetField(type, viewModel, "_repositoryRoot", @"C:\JARVIS\Main");
        SetField(type, viewModel, "_runtimeRoot", @"C:\JARVIS\Main");

        var voiceEventsProperty = type.GetProperty("VoiceEvents");
        Check(voiceEventsProperty is not null,
            "The native Voice page does not expose a recent event timeline.", failures);
        if (voiceEventsProperty?.GetValue(viewModel) is System.Collections.ObjectModel.ObservableCollection<JarvisListItem> voiceEvents)
        {
            using var sttDocument = JsonDocument.Parse("""
                {"data_points":[
                  {"timestamp":"2026-09-27T00:50:00Z","status":"success","audio_duration_s":3.2,"segments":2,"transcript":"PRIVATE_TRANSCRIPT_SENTINEL"},
                  {"timestamp":"2026-09-27T00:52:00Z","status":"error","audio_duration_s":1.1,"transcript":"PRIVATE_ERROR_TRANSCRIPT_SENTINEL"}
                ]}
                """);
            using var ttsDocument = JsonDocument.Parse("""
                {"data_points":[
                  {"timestamp":"2026-09-27T00:51:00Z","generation_time_s":2.5,"audio_duration_s":1.8,"rtf":1.4,"ttfc_s":0.4,"engine":"Chatterbox","text_length":33,"text":"PRIVATE_SPOKEN_TEXT_SENTINEL"}
                ]}
                """);

            ((Task)(applyStt.Invoke(viewModel, [sttDocument.RootElement])
                ?? throw new InvalidOperationException("STT apply returned no task."))).GetAwaiter().GetResult();
            ((Task)(applyTts.Invoke(viewModel, [ttsDocument.RootElement])
                ?? throw new InvalidOperationException("TTS apply returned no task."))).GetAwaiter().GetResult();

            Check(voiceEvents.Count == 3 && voiceEvents[0].Name == "STT · Fehler" &&
                    !string.IsNullOrWhiteSpace(voiceEvents[0].Timestamp),
                "Recent STT/TTS events were not merged in descending event-time order.", failures);
            Check(voiceEvents.Any(item => item.Name.Contains("TTS", StringComparison.Ordinal) && item.Detail.Contains("2.50", StringComparison.Ordinal)),
                "TTS performance fields were not represented in the native timeline.", failures);
            Check(voiceEvents.All(item => !item.Name.Contains("PRIVATE_", StringComparison.Ordinal) &&
                    !item.Detail.Contains("PRIVATE_", StringComparison.Ordinal) &&
                    !item.Timestamp.Contains("PRIVATE_", StringComparison.Ordinal)),
                "Private transcript or speech text was copied into the Voice event timeline.", failures);

            var manySttPoints = Enumerable.Range(0, 12)
                .Select(index => new
                {
                    timestamp = DateTimeOffset.UtcNow.AddMinutes(-index).ToString("O"),
                    status = "success",
                    audio_duration_s = index + 1,
                    segments = index,
                });
            using var manySttDocument = JsonDocument.Parse(JsonSerializer.Serialize(new { data_points = manySttPoints }));
            ((Task)(applyStt.Invoke(viewModel, [manySttDocument.RootElement])
                ?? throw new InvalidOperationException("STT apply returned no task for the bounded timeline check."))).GetAwaiter().GetResult();
            Check(voiceEvents.Count(item => item.Name.StartsWith("STT", StringComparison.Ordinal)) == 10,
                "The Voice timeline did not limit STT history to its ten newest points.", failures);
        }

        var routingEventsProperty = type.GetProperty("RoutingEvents");
        Check(routingEventsProperty is not null,
            "The native Skills & Tools page does not expose recent routing activity.", failures);
        if (routingEventsProperty?.GetValue(viewModel) is System.Collections.ObjectModel.ObservableCollection<JarvisListItem> routingEvents)
        {
            using var routingDocument = JsonDocument.Parse("""
                {"data_points":[
                  {"timestamp":"2026-09-27T00:53:00Z","latency_ms":250.5,"intent":"llm_fallback","status":"fallback","skill":"PRIVATE_SKILL_SENTINEL","tools_called":"PRIVATE_TOOL_SENTINEL","prompt":"PRIVATE_PROMPT_SENTINEL"},
                  {"timestamp":"2026-09-27T00:52:00Z","latency_ms":42,"intent":"cal_l0_weather_skill","status":"handled","skill":"PRIVATE_SKILL_SENTINEL","query":"PRIVATE_QUERY_SENTINEL"},
                  {"timestamp":"2026-09-27T00:54:00Z","latency_ms":10,"intent":"skill:PRIVATE_CUSTOM_SKILL_SENTINEL","status":"handled","query":"PRIVATE_QUERY_SENTINEL"}
                ]}
                """);
            ((Task)(applyRoutingEvents.Invoke(viewModel, [routingDocument.RootElement])
                ?? throw new InvalidOperationException("Routing event apply returned no task."))).GetAwaiter().GetResult();

            Check(routingEvents.Count == 3 && routingEvents[0].Name == "Weitere Route · verarbeitet" &&
                    routingEvents[1].Name.StartsWith("LLM-Fallback", StringComparison.Ordinal),
                "Routing activity was not normalized into fixed labels and ordered newest first.", failures);
            Check(routingEvents.Any(item => item.Name.Contains("CAL-L0", StringComparison.Ordinal)) &&
                    routingEvents.Any(item => item.Detail.Contains("250.50 ms", StringComparison.Ordinal)),
                "Safe route family or latency data was not represented in the native routing timeline.", failures);
            Check(routingEvents.All(item => !item.Name.Contains("PRIVATE_", StringComparison.Ordinal) &&
                    !item.Detail.Contains("PRIVATE_", StringComparison.Ordinal) &&
                    !item.Timestamp.Contains("PRIVATE_", StringComparison.Ordinal)),
                "A private skill, tool, prompt, or query value escaped into the routing timeline.", failures);
            Check(viewModel.RoutingLiveStatus.Contains("Keine Runtime-Route in den letzten 5 Sekunden", StringComparison.Ordinal),
                "Historical routing events were incorrectly presented as current live activity.", failures);

            using var freshRoutingDocument = JsonDocument.Parse(JsonSerializer.Serialize(new
            {
                data_points = new[]
                {
                    new
                    {
                        timestamp = DateTimeOffset.UtcNow.ToString("O"),
                        latency_ms = 21,
                        intent = "llm_direct",
                        status = "handled",
                    },
                },
            }));
            ((Task)(applyRoutingEvents.Invoke(viewModel, [freshRoutingDocument.RootElement])
                ?? throw new InvalidOperationException("Routing apply returned no task for live freshness."))).GetAwaiter().GetResult();
            Check(viewModel.RoutingLiveStatus.StartsWith("Aktuelle Runtime-Route", StringComparison.Ordinal),
                "A routing event inside the five-second freshness window was not presented as current.", failures);

            using var staleRoutingDocument = JsonDocument.Parse("""
                {"data_points":[{"timestamp":"2020-01-01T00:00:00Z","intent":"llm_direct","status":"handled"}]}
                """);
            ((Task)(applyRoutingEvents.Invoke(viewModel, [staleRoutingDocument.RootElement])
                ?? throw new InvalidOperationException("Routing apply returned no task for stale freshness."))).GetAwaiter().GetResult();
            Check(viewModel.RoutingLiveStatus.Contains("Keine Runtime-Route in den letzten 5 Sekunden", StringComparison.Ordinal),
                "A stale routing event was presented as current live activity.", failures);

            var manyRoutingPoints = Enumerable.Range(0, 12)
                .Select(index => new
                {
                    timestamp = DateTimeOffset.UtcNow.AddMinutes(-index).ToString("O"),
                    latency_ms = index * 10,
                    intent = index % 2 == 0 ? "llm_direct" : "PRIVATE_DYNAMIC_ROUTE_SENTINEL",
                    status = "handled",
                });
            using var manyRoutingDocument = JsonDocument.Parse(JsonSerializer.Serialize(new { data_points = manyRoutingPoints }));
            ((Task)(applyRoutingEvents.Invoke(viewModel, [manyRoutingDocument.RootElement])
                ?? throw new InvalidOperationException("Routing apply returned no task for the bounded timeline check."))).GetAwaiter().GetResult();
            Check(routingEvents.Count == 10 && routingEvents.All(item =>
                    !item.Name.Contains("PRIVATE_DYNAMIC_ROUTE_SENTINEL", StringComparison.Ordinal)),
                "The routing timeline was not capped at ten points or exposed a dynamic route name.", failures);

            using var unixRoutingDocument = JsonDocument.Parse(JsonSerializer.Serialize(new
            {
                data_points = new[]
                {
                    new
                    {
                        timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000d,
                        latency_ms = 17.5,
                        intent = "llm_direct",
                        status = "handled",
                    },
                },
            }));
            ((Task)(applyRoutingEvents.Invoke(viewModel, [unixRoutingDocument.RootElement])
                ?? throw new InvalidOperationException("Routing apply returned no task for numeric timestamps."))).GetAwaiter().GetResult();
            Check(routingEvents.Count == 1 && routingEvents[0].Name.StartsWith("Direkter LLM-Pfad", StringComparison.Ordinal),
                "A numeric Unix-seconds timestamp from the live routing API was rejected.", failures);

            var capturedUnixMilliseconds = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            using var unixMillisecondsDocument = JsonDocument.Parse(JsonSerializer.Serialize(new
            {
                data_points = new[]
                {
                    new
                    {
                        timestamp = capturedUnixMilliseconds,
                        latency_ms = 17.5,
                        intent = "llm_direct",
                        status = "handled",
                    },
                },
            }));
            ((Task)(applyRoutingEvents.Invoke(viewModel, [unixMillisecondsDocument.RootElement])
                ?? throw new InvalidOperationException("Routing apply returned no task for millisecond timestamps."))).GetAwaiter().GetResult();
            var expectedUnixMillisecondsTime = DateTimeOffset.FromUnixTimeMilliseconds(capturedUnixMilliseconds)
                .ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss zzz", System.Globalization.CultureInfo.InvariantCulture);
            Check(routingEvents.Count == 1 && routingEvents[0].Timestamp == expectedUnixMillisecondsTime,
                "A current numeric Unix-millisecond timestamp was not formatted as a current event.", failures);
        }

        var eventsProperty = type.GetProperty("Events");
        Check(eventsProperty?.GetValue(viewModel) is System.Collections.ObjectModel.ObservableCollection<JarvisListItem>,
            "The native event overview collection is missing.", failures);
        if (eventsProperty?.GetValue(viewModel) is System.Collections.ObjectModel.ObservableCollection<JarvisListItem> events)
        {
            using var fallbackStt = JsonDocument.Parse("""
                {"total":8,"errors":2,"empty":1,"success_rate":62.5,"data_points":[],"transcript":"PRIVATE_TRANSCRIPT_SENTINEL"}
                """);
            ((Task)(applyStt.Invoke(viewModel, [fallbackStt.RootElement])
                ?? throw new InvalidOperationException("STT apply returned no task for event-summary fallback."))).GetAwaiter().GetResult();

            using var fallbackTts = JsonDocument.Parse("""
                {"total_syntheses":4,"errors":1,"cache_hits":2,"data_points":[],"text":"PRIVATE_TTS_SENTINEL"}
                """);
            ((Task)(applyTts.Invoke(viewModel, [fallbackTts.RootElement])
                ?? throw new InvalidOperationException("TTS apply returned no task for event-summary fallback."))).GetAwaiter().GetResult();

            using var fallbackRouting = JsonDocument.Parse("""
                {"total":54,"handled":52,"fallback":2,"data_points":[],"intent":"PRIVATE_ROUTE_SENTINEL"}
                """);
            ((Task)(applyRoutingEvents.Invoke(viewModel, [fallbackRouting.RootElement])
                ?? throw new InvalidOperationException("Routing apply returned no task for event-summary fallback."))).GetAwaiter().GetResult();

            Check(markEventsAggregateMissing is not null,
                "The native event overview has no explicit path for a missing aggregate endpoint.", failures);
            if (markEventsAggregateMissing is not null)
            {
                markEventsAggregateMissing.Invoke(viewModel, null);
                Check(events.Count == 3 && events.Any(item => item.Name == "Routing" && item.Detail.Contains("54", StringComparison.Ordinal)) &&
                        events.Any(item => item.Name == "STT" && item.Detail.Contains("8", StringComparison.Ordinal)) &&
                        events.Any(item => item.Name == "TTS" && item.Detail.Contains("4", StringComparison.Ordinal)),
                    "The event overview did not summarize the available real routing, STT, and TTS aggregates.", failures);
                Check(viewModel.EventsStatus.Contains("verfügbare 24-h-Quellen", StringComparison.Ordinal),
                    $"The reconstructed overview status did not disclose its available 24-hour aggregate sources: {viewModel.EventsStatus}", failures);
                Check(events.All(item => !item.Name.Contains("PRIVATE_", StringComparison.Ordinal) &&
                            !item.Detail.Contains("PRIVATE_", StringComparison.Ordinal) &&
                            !item.Timestamp.Contains("PRIVATE_", StringComparison.Ordinal)),
                    "Private payload content escaped into the reconstructed event overview.", failures);
            }
        }

        var currentStatusTimestamp = DateTimeOffset.UtcNow.ToString("O", System.Globalization.CultureInfo.InvariantCulture);
        using var agentStatusDocument = JsonDocument.Parse("""
            {
              "available":true,"state":"running","active":true,"paused":false,
              "awaitingConfirmation":false,"canPause":false,"stepCount":3,
              "completedSteps":1,"runningSteps":1,"failedSteps":0,"pendingSteps":1,"skippedSteps":0,
              "observedAt":"CURRENT_STATUS_TIMESTAMP",
              "original_request":"PRIVATE_AGENT_REQUEST_SENTINEL",
              "steps":[{"description":"PRIVATE_STEP_SENTINEL","input_text":"PRIVATE_INPUT_SENTINEL","result":"PRIVATE_RESULT_SENTINEL","skill_name":"PRIVATE_SKILL_SENTINEL"}]
            }
            """.Replace("CURRENT_STATUS_TIMESTAMP", currentStatusTimestamp, StringComparison.Ordinal));
        ((Task)(applyAgentStatus.Invoke(viewModel, [agentStatusDocument.RootElement])
            ?? throw new InvalidOperationException("Agent status apply returned no task."))).GetAwaiter().GetResult();
        var agentSummary = (string?)type.GetProperty("AgentSummary")?.GetValue(viewModel);
        var agentDetail = (string?)type.GetProperty("AgentDetail")?.GetValue(viewModel);
        Check(agentSummary == "Plan wird ausgeführt" && agentDetail?.Contains("1/3", StringComparison.Ordinal) == true,
            "The native Agents page did not present the current planner state and aggregate progress.", failures);
        Check(agentDetail is not null && !agentDetail.Contains("PRIVATE_", StringComparison.Ordinal),
            "Private plan or step content escaped into the native Agents page.", failures);

        using var staleAgentStatus = JsonDocument.Parse("""
            {"available":true,"state":"running","active":true,"paused":false,"awaitingConfirmation":false,"canPause":false,
             "stepCount":1,"completedSteps":0,"runningSteps":1,"failedSteps":0,"pendingSteps":0,"skippedSteps":0,
             "observedAt":"2020-01-01T00:00:00Z"}
            """);
        ((Task)(applyAgentStatus.Invoke(viewModel, [staleAgentStatus.RootElement])
            ?? throw new InvalidOperationException("Agent status apply returned no task for stale timestamp."))).GetAwaiter().GetResult();
        Check(agentSummary == "Plan wird ausgeführt" && viewModel.AgentSummary.Contains("veraltet", StringComparison.OrdinalIgnoreCase),
            "An old agent snapshot was presented as current.", failures);

        using var contradictoryAgentStatus = JsonDocument.Parse("""
            {"available":true,"state":"running","active":false,"paused":true,"awaitingConfirmation":false,"canPause":false,
             "stepCount":0,"completedSteps":0,"runningSteps":0,"failedSteps":0,"pendingSteps":0,"skippedSteps":0,
             "observedAt":"CURRENT_STATUS_TIMESTAMP"}
            """.Replace("CURRENT_STATUS_TIMESTAMP", currentStatusTimestamp, StringComparison.Ordinal));
        ((Task)(applyAgentStatus.Invoke(viewModel, [contradictoryAgentStatus.RootElement])
            ?? throw new InvalidOperationException("Agent status apply returned no task for contradictory flags."))).GetAwaiter().GetResult();
        Check(viewModel.AgentSummary == "Nicht verfügbar",
            "Contradictory agent state flags were accepted as a valid live plan.", failures);

        using var overflowingAgentStatus = JsonDocument.Parse("""
            {"available":true,"state":"running","active":true,"paused":false,"awaitingConfirmation":false,"canPause":false,
             "stepCount":0,"completedSteps":9223372036854775807,"runningSteps":2,"failedSteps":9223372036854775807,"pendingSteps":0,"skippedSteps":0,
             "observedAt":"CURRENT_STATUS_TIMESTAMP"}
            """.Replace("CURRENT_STATUS_TIMESTAMP", currentStatusTimestamp, StringComparison.Ordinal));
        ((Task)(applyAgentStatus.Invoke(viewModel, [overflowingAgentStatus.RootElement])
            ?? throw new InvalidOperationException("Agent status apply returned no task for overflowing counts."))).GetAwaiter().GetResult();
        Check(viewModel.AgentSummary == "Nicht verfügbar",
            "Overflowing planner counters were accepted as a valid progress total.", failures);

        using var automationsDocument = JsonDocument.Parse("""
            {
              "observedAt":"CURRENT_STATUS_TIMESTAMP",
              "schedulers":[
                {"id":"reminder_poller","state":"running","configuredIntervalSeconds":30,"lastRunAt":null,"lastRunAvailable":false,"dailyRundownEnabled":true,"dailyRundownTime":"08:15","weeklyRundownEnabled":true,"weeklyRundownDay":"monday","title":"PRIVATE_REMINDER_TITLE_SENTINEL"},
                {"id":"health_snapshot","state":"running","configuredIntervalSeconds":600,"lastRunAt":null,"lastRunAvailable":false,"metric":"PRIVATE_HEALTH_METRIC_SENTINEL"},
                {"id":"observation_collector","state":"running","configuredIntervalSeconds":7200,"lastRunAt":"2026-09-27T00:50:00Z","lastRunAvailable":true,"autoConsultEnabled":false,"finding":"PRIVATE_FINDING_SENTINEL"}
              ]
            }
            """.Replace("CURRENT_STATUS_TIMESTAMP", currentStatusTimestamp, StringComparison.Ordinal));
        ((Task)(applyAutomationsStatus.Invoke(viewModel, [automationsDocument.RootElement])
            ?? throw new InvalidOperationException("Automation status apply returned no task."))).GetAwaiter().GetResult();
        var automationSchedulersProperty = type.GetProperty("AutomationSchedulers");
        if (automationSchedulersProperty?.GetValue(viewModel) is System.Collections.ObjectModel.ObservableCollection<JarvisListItem> automationSchedulers)
        {
            Check(automationSchedulers.Count == 3 && automationSchedulers[0].Name == "JARVIS-Erinnerungsdienst" &&
                    automationSchedulers[0].Detail.Contains("30 s", StringComparison.Ordinal) &&
                    automationSchedulers[0].Detail.Contains("08:15", StringComparison.Ordinal),
                "Configured system scheduler metadata was not translated into the native Automation page.", failures);
            Check(automationSchedulers[0].Detail.Contains("kein Laufzeitpunkt erfasst", StringComparison.Ordinal) &&
                    automationSchedulers[2].Detail.Contains("2026-09-27", StringComparison.Ordinal),
                "Configured schedules were conflated with actual run evidence.", failures);
            Check(automationSchedulers.All(item => !item.Name.Contains("PRIVATE_", StringComparison.Ordinal) &&
                    !item.Detail.Contains("PRIVATE_", StringComparison.Ordinal) &&
                    !item.Timestamp.Contains("PRIVATE_", StringComparison.Ordinal)),
                "Private reminder, health, or observation content escaped into the Automation page.", failures);
        }
        else
        {
            failures.Add("The native Automation page does not expose the scheduler inventory.");
        }

        using var staleAutomationsDocument = JsonDocument.Parse(automationsDocument.RootElement.GetRawText()
            .Replace(currentStatusTimestamp, "2020-01-01T00:00:00Z", StringComparison.Ordinal));
        ((Task)(applyAutomationsStatus.Invoke(viewModel, [staleAutomationsDocument.RootElement])
            ?? throw new InvalidOperationException("Automation status apply returned no task for stale timestamp."))).GetAwaiter().GetResult();
        Check(automationSchedulersProperty?.GetValue(viewModel) is System.Collections.ObjectModel.ObservableCollection<JarvisListItem> staleAutomationSchedulers &&
                staleAutomationSchedulers.Count == 0 && viewModel.AutomationsStatus.Contains("veraltet", StringComparison.OrdinalIgnoreCase),
            "An old automation snapshot was presented as current.", failures);

        var uiRoot = new DirectoryInfo(AppContext.BaseDirectory);
        while (uiRoot is not null && !Directory.Exists(Path.Combine(uiRoot.FullName, "WindowsApp")))
            uiRoot = uiRoot.Parent;
        Check(uiRoot?.Parent is not null &&
                Equals(discoverRoot.Invoke(null, [AppContext.BaseDirectory]), Path.Combine(uiRoot.Parent.FullName, "Main")),
            "The native Control Hub did not discover the adjacent validated JARVIS-Main repository.", failures);
        if (uiRoot?.Parent is not null)
        {
            var expectedMainRoot = Path.Combine(uiRoot.Parent.FullName, "Main");
            Check(!(bool)reparseGuard.Invoke(null, [expectedMainRoot])!,
                "The actual JARVIS-Main checkout was unexpectedly rejected as a redirected path.", failures);
            Check(Equals(resolveConfiguredRoot.Invoke(null, [Array.Empty<string?>(), AppContext.BaseDirectory]), expectedMainRoot),
                "Automatic repository discovery did not run when no explicit roots were configured.", failures);
            Check(resolveConfiguredRoot.Invoke(null, [new string?[] { Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N")) }, AppContext.BaseDirectory]) is null,
                "An invalid explicit repository root silently fell back to a different discovered checkout.", failures);
            VerifySymlinkedSupervisorFileRejected(validateRoot, requiredFiles, expectedMainRoot, failures);
            VerifySymlinkedSupervisorDirectoryRejected(validateRoot, requiredFiles, expectedMainRoot, failures);
        }

        SetField(type, viewModel, "_liveObservedAt", DateTimeOffset.UtcNow.AddSeconds(-2));
        SetField(type, viewModel, "_cpuValue", "42.0 %");
        SetField(type, viewModel, "_memoryValue", "61.0 %");
        updateFreshness.Invoke(viewModel, null);
        Check(viewModel.CpuValue == "42.0 %" && viewModel.MemoryValue == "61.0 %",
            "A sample inside the freshness limit was hidden prematurely.", failures);

        var sampleAt = DateTimeOffset.UtcNow.AddSeconds(-4.5);
        SetField(type, viewModel, "_liveObservedAt", sampleAt);
        SetField(type, viewModel, "_cpuValue", "42.0 %");
        SetField(type, viewModel, "_memoryValue", "61.0 %");
        SetField(type, viewModel, "_memoryDetail", "7.0 GiB von 12.0 GiB");

        var frame = new DispatcherFrame();
        var timeout = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromMilliseconds(1400),
        };
        timeout.Tick += (_, _) =>
        {
            timeout.Stop();
            frame.Continue = false;
        };
        timeout.Start();
        Dispatcher.PushFrame(frame);

        Check(viewModel.CpuValue == "Nicht verfügbar",
            "CPU sample was still displayed after its 5-second freshness limit.", failures);
        Check(viewModel.MemoryValue == "Nicht verfügbar",
            "Memory sample was still displayed after its 5-second freshness limit.", failures);
        Check(viewModel.LiveAge.Contains("VERALTET", StringComparison.Ordinal),
            "Live age did not update independently while the next poll was pending.", failures);

        SetField(type, viewModel, "_runtime", Snapshot(DateTimeOffset.UtcNow.AddSeconds(-20)));
        updateFreshness.Invoke(viewModel, null);
        Check(!viewModel.CanStart && !viewModel.CanStop && !viewModel.CanRestart,
            "Runtime Supervisor actions remained enabled for a stale snapshot.", failures);
        Check((bool)isActionAllowed.Invoke(viewModel, [JarvisRuntimeAction.Stop, @"C:\JARVIS\Main"])! == false,
            "The action guard allowed a stale Runtime Supervisor snapshot.", failures);
        Check(viewModel.RuntimeState == "Veraltet",
            "A stale Runtime Supervisor snapshot was not visibly marked as stale.", failures);

        SetField(type, viewModel, "_runtime", Snapshot(DateTimeOffset.UtcNow));
        updateFreshness.Invoke(viewModel, null);
        Check(viewModel.CanStop, "A fresh Supervisor snapshot did not restore its allowed action.", failures);

        SetField(type, viewModel, "_runtimeRoot", @"C:\JARVIS\Old");
        SetField(type, viewModel, "_runtime", Snapshot(DateTimeOffset.UtcNow));
        updateFreshness.Invoke(viewModel, null);
        Check(!viewModel.CanStart && !viewModel.CanStop && !viewModel.CanRestart,
            "A fresh snapshot from a different repository enabled Supervisor actions.", failures);
        Check((bool)isActionAllowed.Invoke(viewModel, [JarvisRuntimeAction.Stop, @"C:\JARVIS\Main"])! == false,
            "The action guard accepted a snapshot belonging to a different repository.", failures);

        SetField(type, viewModel, "_repositoryRoot", @"C:\JARVIS\Old");
        SetField(type, viewModel, "_runtimeRoot", @"C:\JARVIS\Old");
        SetField(type, viewModel, "_runtime", Snapshot(DateTimeOffset.UtcNow));
        updateFreshness.Invoke(viewModel, null);
        Check(viewModel.CanStop, "A fresh snapshot for the newly selected repository was not accepted.", failures);
        Check((bool)isActionAllowed.Invoke(viewModel, [JarvisRuntimeAction.Stop, @"C:\JARVIS\Main"])! == false,
            "A confirmed action remained authorized after the selected repository changed.", failures);

        var runtimeComponents = new[]
        {
            new RuntimeComponent("api", "API Service", "READY", "HTTP erreichbar"),
            new RuntimeComponent("voice-daemon", "Voice Daemon", "DEGRADED", "Audio-Gerät fehlt"),
        };
        var runtimeSnapshot = Snapshot(DateTimeOffset.UtcNow) with { Components = runtimeComponents };
        ((Task)applyRuntime.Invoke(viewModel, [runtimeSnapshot, @"C:\JARVIS\Old"])!).GetAwaiter().GetResult();
        Check(viewModel.RuntimeComponents.Count == 2,
            "Runtime Supervisor components were not projected into the native UI collection.", failures);
        Check(viewModel.RuntimeComponents.Any(component => component.Name == "Voice Daemon" &&
                component.Detail.Contains("DEGRADED", StringComparison.Ordinal) &&
                component.Detail.Contains("Audio-Gerät fehlt", StringComparison.Ordinal) &&
                component.Timestamp == "ID: voice-daemon"),
            "Runtime Supervisor component state, detail, or identifier was not visible in the native UI projection.", failures);

        using var health = JsonDocument.Parse("""{"available_metrics":["cpu.load","ram.percent","gpu.temp","session.api_calls"],"trends":{"cpu.load":{"stats":{"mean":1.2,"min":0.5,"max":2.5,"count":12,"latest":2.3,"latest_ts":1790000000.375},"data":[]},"gpu.temp":{"stats":{},"data":[]},"session.api_calls":{"stats":{"count":0},"data":[]}}}""");
        ((Task)applyHealth.Invoke(viewModel, [health.RootElement])!).GetAwaiter().GetResult();
        Check(viewModel.HealthMetrics.Count == 4,
            "Health metric names returned as strings were not projected into the UI.", failures);
        Check(viewModel.HealthMetrics.Any(metric => metric.Name == "cpu.load" &&
                metric.Detail.Contains("zuletzt 2.3", StringComparison.Ordinal) &&
                metric.Detail.Contains("12 Messpunkte", StringComparison.Ordinal) &&
                metric.Timestamp == DateTimeOffset.FromUnixTimeMilliseconds(1790000000375)
                    .ToLocalTime().ToString("dd.MM.yyyy HH:mm:ss", System.Globalization.CultureInfo.InvariantCulture)),
            "Health history statistics or latest timestamp were not projected into the UI.", failures);
        Check(viewModel.HealthMetrics.Any(metric => metric.Name == "ram.percent" &&
                metric.Detail.Contains("nicht mitgeliefert", StringComparison.Ordinal)),
            "Health metrics omitted from the backend's selected trend set were mislabeled as empty.", failures);
        Check(viewModel.HealthMetrics.Any(metric => metric.Name == "gpu.temp" &&
                metric.Detail.Contains("Keine Messpunkte", StringComparison.Ordinal)),
            "An explicitly empty health trend was not identified as having no measurements.", failures);
        Check(viewModel.HealthMetrics.Any(metric => metric.Name == "session.api_calls" &&
                metric.Detail.Contains("Keine Messpunkte", StringComparison.Ordinal)) &&
                viewModel.HistoryStatus.Contains("davon 1 mit Messpunkten", StringComparison.Ordinal),
            "A zero-count trend was reported as sampled or included in the sampled total.", failures);

        using var searchStats = JsonDocument.Parse(
            "[{\"timestamp\":1790000000.375,\"search_pages_ok\":2,\"search_pages_total\":3,\"search_latency_ms\":120}," +
            "{\"timestamp\":1790000030,\"search_pages_ok\":4,\"search_pages_total\":4,\"search_latency_ms\":80}]");
        ((Task)applySearchStats.Invoke(viewModel, [searchStats.RootElement])!).GetAwaiter().GetResult();
        Check(viewModel.SearchPerformanceSummary.Contains("2 Suchanfragen", StringComparison.Ordinal) &&
                viewModel.SearchPerformanceSummary.Contains("6/7", StringComparison.Ordinal) &&
                viewModel.SearchPerformanceSummary.Contains("85.7", StringComparison.Ordinal) &&
                viewModel.SearchPerformanceSummary.Contains("100", StringComparison.Ordinal),
            "Search performance aggregates were not computed from the real endpoint contract.", failures);
        Check(viewModel.SearchPerformanceStatus.Contains("keine Suchbegriffe/URLs", StringComparison.Ordinal),
            "Search performance status did not make the aggregate-only privacy boundary explicit.", failures);

        using var emptySearchStats = JsonDocument.Parse("[]");
        ((Task)applySearchStats.Invoke(viewModel, [emptySearchStats.RootElement])!).GetAwaiter().GetResult();
        Check(viewModel.SearchPerformanceSummary.Contains("Keine Messpunkte", StringComparison.Ordinal),
            "An empty search endpoint response did not clear the previous aggregate and report no measurements.", failures);

        using var inconsistentSearchStats = JsonDocument.Parse(
            "[{\"timestamp\":1790000030,\"search_pages_ok\":9,\"search_pages_total\":7,\"search_latency_ms\":80}]");
        ((Task)applySearchStats.Invoke(viewModel, [inconsistentSearchStats.RootElement])!).GetAwaiter().GetResult();
        Check(!viewModel.SearchPerformanceSummary.Contains("%", StringComparison.Ordinal) &&
                viewModel.SearchPerformanceSummary.Contains("inkonsistente Seitensummen", StringComparison.Ordinal),
            "An impossible search page count was reported as a success rate.", failures);

        using var desktopSnapshot = JsonDocument.Parse("""
            {
              "llm": {"provider":"gemma","contextSize":32768,"gpuLayers":60,"batchSize":512,"ubatchSize":128,"temperature":0.6,"topP":0.9,"topK":40,"toolCalling":true,"endpoint":"https://private.example/secret"},
              "voice": {"sampleRate":24000,"channels":1,"outputBackend":"windows","language":"de-DE","wakeKeyword":"jarvis","sttBackend":"qwen3","sttModel":"qwen3-model","sttProvider":"cpu","sttThreads":6,"tts":"chatterbox","ttsNormalization":true,"ttsEndpoint":"https://private.example/voice"},
              "capabilities": {"reminders":true,"calendar":false,"news":true,"weather":false,"memory":true,"contextWindow":true,"metrics":true},
              "memoryConfig": {"enabled":true,"proactiveSurfacing":false,"contextWindowEnabled":true},
              "metricsRetentionDays":180
            }
            """);
        ((Task)applySnapshot.Invoke(viewModel, [desktopSnapshot.RootElement])!).GetAwaiter().GetResult();
        Check(viewModel.LlmConfigurationSummary.Contains("Provider gemma", StringComparison.Ordinal) &&
                viewModel.LlmConfigurationSummary.Contains("Kontext 32768 Tokens", StringComparison.Ordinal) &&
                viewModel.LlmConfigurationSummary.Contains("Tool Calling aktiv", StringComparison.Ordinal),
            "The sanitized desktop snapshot's actual LLM configuration was not projected to the native view model.", failures);
        Check(viewModel.VoiceConfigurationSummary.Contains("STT qwen3 (qwen3-model)", StringComparison.Ordinal) &&
                viewModel.VoiceConfigurationSummary.Contains("24000 Hz", StringComparison.Ordinal) &&
                viewModel.VoiceConfigurationSummary.Contains("Wake-Keyword jarvis", StringComparison.Ordinal) &&
                viewModel.VoiceConfigurationSummary.Contains("TTS-Normalisierung aktiv", StringComparison.Ordinal),
            "The desktop snapshot's voice configuration was not projected to the native view model.", failures);
        Check(viewModel.RuntimeCapabilitiesSummary.Contains("Erinnerungen: Manager vorhanden", StringComparison.Ordinal) &&
                viewModel.RuntimeCapabilitiesSummary.Contains("Kalender: nicht vorhanden", StringComparison.Ordinal) &&
                viewModel.RuntimeCapabilitiesSummary.Contains("Wetter: nicht vorhanden", StringComparison.Ordinal),
            "The desktop snapshot's runtime capabilities were not mapped truthfully.", failures);
        Check(viewModel.MemoryConfigurationSummary.Contains("Konversations-Memory aktiviert", StringComparison.Ordinal) &&
                viewModel.MemoryConfigurationSummary.Contains("proaktives Surfacing deaktiviert", StringComparison.Ordinal) &&
                viewModel.MemoryConfigurationSummary.Contains("Metrik-Aufbewahrung 180 Tage", StringComparison.Ordinal),
            "The snapshot's non-content memory configuration and retention policy were not mapped into the native view.", failures);
        Check(!viewModel.LlmConfigurationSummary.Contains("private.example", StringComparison.Ordinal) &&
                !viewModel.VoiceConfigurationSummary.Contains("private.example", StringComparison.Ordinal),
            "A service endpoint from the snapshot leaked into user-visible configuration summaries.", failures);

        using var unavailableSnapshot = JsonDocument.Parse("{}");
        ((Task)applySnapshot.Invoke(viewModel, [unavailableSnapshot.RootElement])!).GetAwaiter().GetResult();
        Check(!viewModel.LlmConfigurationSummary.Contains("Provider gemma", StringComparison.Ordinal) &&
                !viewModel.VoiceConfigurationSummary.Contains("STT qwen3", StringComparison.Ordinal) &&
                !viewModel.RuntimeCapabilitiesSummary.Contains("Erinnerungen: Manager vorhanden", StringComparison.Ordinal) &&
                !viewModel.MemoryConfigurationSummary.Contains("Konversations-Memory aktiviert", StringComparison.Ordinal),
            "Missing snapshot fields left stale configuration or capability data visible.", failures);

        SetField(type, viewModel, "_repositoryRoot", @"C:\JARVIS\Main");
        SetField(type, viewModel, "_runtimeRoot", @"C:\JARVIS\Main");
        SetField(type, viewModel, "_runtime", Snapshot(DateTimeOffset.UtcNow));
        updateFreshness.Invoke(viewModel, null);

        SetField(type, viewModel, "_runtime", Snapshot(null));
        updateFreshness.Invoke(viewModel, null);
        Check(!viewModel.CanStart && !viewModel.CanStop && !viewModel.CanRestart,
            "Supervisor actions were enabled for a snapshot without an update timestamp.", failures);

        SetField(type, viewModel, "_runtime", Snapshot(DateTimeOffset.UtcNow.AddSeconds(10)));
        updateFreshness.Invoke(viewModel, null);
        Check(!viewModel.CanStart && !viewModel.CanStop && !viewModel.CanRestart,
            "Supervisor actions were enabled for a timestamp outside future clock-skew tolerance.", failures);

        if (failures.Count == 0)
        {
            Console.WriteLine("Windows freshness regression checks passed.");
            return 0;
        }

        foreach (var failure in failures) Console.Error.WriteLine($"FAIL: {failure}");
        return 1;
    }

    private static RuntimeSnapshot Snapshot(DateTimeOffset? updatedAt) => new(
        "READY",
        Array.Empty<string>(),
        updatedAt,
        Array.Empty<RuntimeComponent>(),
        CanStart: true,
        CanStop: true,
        CanRestart: true,
        Detail: "Test snapshot");

    private static void VerifySymlinkedSupervisorFileRejected(
        MethodInfo validateRoot,
        IReadOnlyList<string> requiredFiles,
        string actualMainRoot,
        ICollection<string> failures)
    {
        var testRoot = Path.Combine(Path.GetTempPath(), $"JarvisSupervisorLinkTest-{Guid.NewGuid():N}");
        var candidateRoot = Path.Combine(testRoot, "Main");
        try
        {
            Directory.CreateDirectory(candidateRoot);
            foreach (var relativePath in requiredFiles)
            {
                var targetPath = Path.Combine(candidateRoot, relativePath);
                Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
                if (relativePath == "JARVIS.Runtime.psm1")
                {
                    try
                    {
                        File.CreateSymbolicLink(targetPath, Path.Combine(actualMainRoot, relativePath));
                    }
                    catch (Exception exception) when (exception is UnauthorizedAccessException or PlatformNotSupportedException or IOException)
                    {
                        Console.WriteLine("Symlink-specific path guard check skipped: this Windows account cannot create file symlinks.");
                        return;
                    }
                }
                else
                {
                    File.WriteAllText(targetPath, string.Empty);
                }
            }

            try
            {
                _ = validateRoot.Invoke(null, [candidateRoot]);
                failures.Add("A repository with a symlinked Runtime Supervisor module was accepted.");
            }
            catch (TargetInvocationException exception) when (exception.InnerException is InvalidOperationException)
            {
                // Expected: repository validation rejects a linked supervisor source file.
            }
        }
        finally
        {
            try { if (Directory.Exists(testRoot)) Directory.Delete(testRoot, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static void VerifySymlinkedSupervisorDirectoryRejected(
        MethodInfo validateRoot,
        IReadOnlyList<string> requiredFiles,
        string actualMainRoot,
        ICollection<string> failures)
    {
        var testRoot = Path.Combine(Path.GetTempPath(), $"JarvisSupervisorDirectoryLinkTest-{Guid.NewGuid():N}");
        var candidateRoot = Path.Combine(testRoot, "Main");
        var scriptDirectory = Path.Combine(candidateRoot, "scripts");
        try
        {
            Directory.CreateDirectory(candidateRoot);
            try
            {
                Directory.CreateSymbolicLink(scriptDirectory, Path.Combine(actualMainRoot, "scripts"));
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException or PlatformNotSupportedException or IOException)
            {
                Console.WriteLine("Symlinked-directory path guard check skipped: this Windows account cannot create directory symlinks.");
                return;
            }

            foreach (var relativePath in requiredFiles.Where(path => !path.StartsWith($"scripts{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)))
            {
                var targetPath = Path.Combine(candidateRoot, relativePath);
                Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
                File.WriteAllText(targetPath, string.Empty);
            }

            try
            {
                _ = validateRoot.Invoke(null, [candidateRoot]);
                failures.Add("A repository with a symlinked scripts directory was accepted.");
            }
            catch (TargetInvocationException exception) when (exception.InnerException is InvalidOperationException)
            {
                // Expected: repository validation rejects a linked required-file ancestor.
            }
        }
        finally
        {
            try { if (Directory.Exists(testRoot)) Directory.Delete(testRoot, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static void SetField(Type type, object instance, string name, object? value)
    {
        var field = type.GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException($"Field {name} was not found.");
        field.SetValue(instance, value);
    }

    private static void Check(bool condition, string message, ICollection<string> failures)
    {
        if (!condition) failures.Add(message);
    }
}
