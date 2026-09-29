using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Jarvis.ControlHub;
using Jarvis.ControlHub.WinUI.Adapters;
using Jarvis.ControlHub.WinUI.Domain;
using Jarvis.ControlHub.WinUI.Views;

internal static class Program
{
    /// <summary>Synthetische Web-API-Antworten. Sie stammen nicht von einem echten Backend.</summary>
    private static (int Status, string Body, int DelayMs) Synthetic(string path) => path switch
    {
        "/api/stats" => (200, """{"llm":{"model":"test-model"},"memory":{"vectors":5},"skills_loaded":3,"context_window":{"segments":2,"tokens":100,"open":true,"usage_pct":4.5},"reminders":null}""", 0),
        "/api/desktop/snapshot" => (200, """{"llm":{"provider":"llama_cpp","endpoint":"http://127.0.0.1:8080","contextSize":4096},"voice":{"input":"mic-x","sttBackend":"qwen3","sttModel":"stt.onnx","tts":"chatterbox","outputBackend":"windows","wakeKeyword":"jarvis","language":"de"},"skills":[{"id":"s","name":"Skill","category":"system","enabled":true,"intents":1,"tools":1}],"tools":[{"id":"tool_a","registered":true,"skill":"s"},{"id":"tool_b","registered":false,"skill":null}],"capabilities":{"memory":true,"calendar":false},"memoryConfig":{"enabled":true,"proactiveSurfacing":false,"contextWindowEnabled":true}}""", 0),
        "/api/memory/summary" => (200, """{"facts":{"total":2,"by_category_user":[{"category":"preference","user_id":"u","count":2}]},"interactions":{"total_7d":1},"faiss":{"vectors":9,"size_bytes":2048},"context":{"usage_pct":1.0}}""", 0),
        "/api/events/recent" => (200, """{"events":[{"timestamp":1790000000,"category":"voice","event":"stt_transcription","severity":"info"},{"timestamp":1790000100,"category":"error_recovery","event":"watchdog_listener_stuck","severity":"warning"}]}""", 0),
        "/api/events/aggregate" => (200, """{"total":2,"severities":{"info":1,"warning":1}}""", 0),
        "/api/sessions" => (200, """{"sessions":[],"has_more":false,"total":4}""", 0),
        "/api/automations/status" => (200, """{"schedulers":[{"id":"health_snapshot","state":"running","configuredIntervalSeconds":60,"lastRunAvailable":false}]}""", 0),
        "/api/agents/status" => (503, """{"available":false,"state":"unavailable"}""", 0),
        "/api/webcam/status" => (200, """{"available":false,"running":false}""", 0),
        _ => (404, "{}", 0),
    };

    private static async Task<int> Main(string[] args)
    {
        if (args.Contains("--serve"))
        {
            // Manueller Modus für den UI-Lauf: synthetische API auf 127.0.0.1:JarvisApiClient.LoopbackPort, bis der Prozess beendet wird.
            using var serving = new MiniServer { Handler = Synthetic };
            Console.WriteLine($"SERVING (synthetisch) auf 127.0.0.1:{JarvisApiClient.LoopbackPort}");
            await Task.Delay(Timeout.Infinite);
            return 0;
        }

        var failures = new List<string>();
        var skipped = new List<string>();

        VerifyParsers(failures);
        VerifyRuntimeComponents(failures);
        VerifyFailureClassification(failures);
        VerifyMobileAdapter(failures);
        VerifyBrainActivity(failures);
        VerifyIconRegistry(failures);
        VerifyBrainEventMapping(failures);
        VerifyBrainEventCursor(failures);
        await VerifyBrainEventBridgeAsync(failures);
        VerifyBrainPrivacyAndReadOnly(failures);
        VerifyHeaderLayout(failures);
        VerifyProjectSources(failures);
        VerifyClientPathsAreDesktopAllowlisted(failures);
        VerifyPortedLegacyChecks(failures, skipped);
        await VerifyHubAsync(failures, skipped);

        foreach (var item in skipped) Console.WriteLine("SKIPPED: " + item);
        if (failures.Count == 0)
        {
            Console.WriteLine($"OK: alle Prüfungen bestanden ({skipped.Count} übersprungen).");
            return 0;
        }

        foreach (var failure in failures) Console.Error.WriteLine("FAIL: " + failure);
        return 1;
    }

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static void Check(bool condition, string message, ICollection<string> failures)
    {
        if (!condition) failures.Add(message);
    }

    // ---- Parser ------------------------------------------------------------------------------------------

    private static void VerifyParsers(ICollection<string> failures)
    {
        var stats = BackendParsers.ParseStats(Json("""
            {"llm":{"model":"test-model","api_fallback":null},"web_research":true,
             "memory":{"vectors":1234,"proactive":true},
             "context_window":{"segments":3,"tokens":900,"open":true,"usage_pct":12.5},
             "skills_loaded":42,"reminders":{"active":2},"news":null,"calendar":true}
            """));
        Check(stats is { Model: "test-model", MemoryVectors: 1234, SkillsLoaded: 42, ContextTokens: 900, RemindersActive: 2 }
                && stats.ContextUsagePercent == 12.5,
            "Stats wurden nicht korrekt gelesen.", failures);

        var emptyStats = BackendParsers.ParseStats(Json("""{"llm":null,"memory":null,"context_window":null,"reminders":null}"""));
        Check(emptyStats is { Model: null, MemoryVectors: null, ContextUsagePercent: null, RemindersActive: null, SkillsLoaded: null },
            "Fehlende Stats-Abschnitte müssen null bleiben, nicht 0.", failures);

        var desktop = BackendParsers.ParseDesktop(Json("""
            {"llm":{"provider":"llama_cpp","endpoint":"http://127.0.0.1:8080","contextSize":32768,"gpuLayers":99},
             "voice":{"input":"mic-a","device":null,"sttBackend":"qwen3","sttModel":"stt.onnx","sttLanguage":"de",
                      "tts":"chatterbox","outputBackend":"windows","wakeKeyword":"jarvis","language":"de"},
             "skills":[{"id":"s1","name":"Skill 1","category":"system","enabled":true,"intents":2,"tools":1},
                       {"id":"","name":"ohne id"},{"id":"s2","enabled":false}],
             "tools":[{"id":"t1","name":"t1","registered":true,"skill":"s1"},{"id":"t2","registered":false,"skill":null},{"name":"ohne id"}],
             "capabilities":{"reminders":true,"calendar":false,"pendingReminders":null,"pendingRemindersScoped":false,"memory":true},
             "memoryConfig":{"enabled":true,"proactiveSurfacing":false,"contextWindowEnabled":true}}
            """));
        Check(desktop.LlmProvider == "llama_cpp" && desktop.LlmContextSize == 32768 && desktop.WakeKeyword == "jarvis"
                && desktop.InputDevice == "mic-a" && desktop.TtsEngine == "chatterbox" && desktop.SttModel == "stt.onnx",
            "Desktop-Konfiguration wurde nicht korrekt gelesen (InputDevice muss auf input zurückfallen).", failures);
        Check(desktop.Tools.Count == 2 && desktop.Tools[0].Registered && !desktop.Tools[1].Registered && desktop.Tools[1].Skill is null,
            "Tool-Inventar wurde nicht korrekt gelesen; Einträge ohne id müssen entfallen.", failures);
        Check(desktop.Skills.Count == 2 && desktop.Skills[0].Enabled && !desktop.Skills[1].Enabled && desktop.Skills[1].Name == "s2",
            "Skill-Inventar wurde nicht korrekt gelesen.", failures);
        Check(desktop.Capabilities.Count == 3 && desktop.Capabilities["reminders"] && !desktop.Capabilities["calendar"]
                && !desktop.Capabilities.ContainsKey("pendingRemindersScoped"),
            "Capabilities dürfen nur bekannte Bool-Schlüssel enthalten.", failures);
        Check(desktop.MemoryEnabled == true && desktop.MemoryProactive == false && desktop.ContextWindowEnabled == true,
            "memoryConfig wurde nicht korrekt gelesen.", failures);

        var automations = BackendParsers.ParseAutomations(Json("""
            {"schedulers":[
              {"id":"reminder_poller","state":"running","configuredIntervalSeconds":30,"lastRunAt":null,"lastRunAvailable":false,
               "dailyRundownEnabled":true,"dailyRundownTime":"07:30","weeklyRundownEnabled":true,"weeklyRundownDay":"monday"},
              {"id":"observation_collector","state":"stopped","configuredIntervalSeconds":null,
               "lastRunAt":"2026-09-28T08:00:00+00:00","lastRunAvailable":true,"autoConsultEnabled":true},
              {"id":"health_snapshot","state":"disabled","lastRunAt":"2026-09-28T08:00:00+00:00","lastRunAvailable":false},
              {"state":"running"}]}
            """));
        Check(automations.Schedulers.Count == 3, "Scheduler ohne id müssen entfallen.", failures);
        Check(automations.Schedulers[0] is { State: "RUNNING", IntervalSeconds: 30, LastRunAt: null }
                && automations.Schedulers[0].Schedule == "alle 30 s, täglich 07:30, wöchentlich monday",
            "Scheduler-Zeitplan wurde nicht korrekt zusammengesetzt.", failures);
        Check(automations.Schedulers[1].LastRunAt == "2026-09-28T08:00:00+00:00" && automations.Schedulers[1].Schedule == "Auto-Consult",
            "lastRunAt muss bei lastRunAvailable=true übernommen werden.", failures);
        Check(automations.Schedulers[2].LastRunAt is null && automations.Schedulers[2].Schedule == "keine Angabe",
            "lastRunAt darf bei lastRunAvailable=false nie angezeigt werden.", failures);

        var owned = BackendParsers.ParseAutomations(Json("""
            {"schedulers":[
              {"id":"reminder_poller","state":"backend_owned","owner":"voice-daemon"},
              {"id":"observation_collector","state":"unavailable","owner":"web-standard-mode"},
              {"id":"legacy","state":"disabled"}]}
            """));
        Check(owned.Schedulers[0] is { State: "BACKEND OWNED", Owner: "voice-daemon" }
                && owned.Schedulers[1] is { State: "UNAVAILABLE", Owner: "web-standard-mode" }
                && owned.Schedulers[2] is { State: "DISABLED", Owner: null },
            "Scheduler-Owner und Zustände BACKEND OWNED/UNAVAILABLE müssen gelesen werden; ohne Owner bleibt null.", failures);
        Check(BackendParsers.StateWord(null) == "UNKNOWN" && BackendParsers.StateWord(" ") == "UNKNOWN",
            "Fehlender Zustandstext muss UNKNOWN sein.", failures);
        var ownedPlanner = BackendParsers.ParseAgents(Json("""{"available":false,"state":"backend_owned","stepCount":0}"""));
        Check(ownedPlanner is { Available: false, State: "BACKEND OWNED" },
            "Planner backend_owned muss als nicht verfügbar mit Zustand BACKEND OWNED gelesen werden.", failures);

        // Vollständige Nutzlast wie jarvis_web.py agents_status_handler (Flags, skippedSteps, observedAt).
        var planner = BackendParsers.ParseAgents(Json("""
            {"available":true,"state":"running","active":true,"paused":false,"awaitingConfirmation":false,"canPause":false,
             "stepCount":5,"completedSteps":2,"runningSteps":1,"failedSteps":0,"pendingSteps":2,"skippedSteps":0,
             "observedAt":"2026-09-29T12:00:00+00:00"}
            """));
        Check(planner is { Available: true, State: "RUNNING", Steps: 5, Completed: 2, Running: 1, Failed: 0, Pending: 2 },
            "Planner-Status wurde nicht korrekt gelesen.", failures);
        Check(!BackendParsers.ParseAgents(Json("""{"available":false,"state":"unavailable"}""")).Available,
            "Planner mit available=false muss als nicht verfügbar gelten.", failures);

        var memory = BackendParsers.ParseMemory(Json("""
            {"facts":{"total":7,"by_category_user":[{"category":"b","user_id":"u1","count":2},{"category":"a","user_id":"u1","count":3},{"category":"b","user_id":"u2","count":2}]},
             "interactions":{"total_7d":11,"by_type_user":[]},
             "faiss":{"vectors":100,"size_bytes":2048,"error":"/geheimer/pfad fehlt"},
             "context":{"usage_pct":3.25,"segments":1,"estimated_tokens":10}}
            """));
        Check(memory.FactsTotal == 7 && memory.Interactions7d == 11 && memory.FaissVectors == 100 && memory.FaissBytes == 2048
                && memory.ContextUsagePercent == 3.25,
            "Memory-Zusammenfassung wurde nicht korrekt gelesen.", failures);
        Check(memory.FactsByCategory.Count == 2 && memory.FactsByCategory[0] is { Key: "a", Value: 3 } && memory.FactsByCategory[1] is { Key: "b", Value: 4 },
            "Fakten müssen je Kategorie über Nutzer summiert und sortiert werden.", failures);
        Check(memory.PartialError == "faiss", "Teilfehler darf nur den Abschnittsnamen tragen, nie den Fehlertext des Backends.", failures);

        var events = BackendParsers.ParseEventsRecent(Json("""
            {"hours":24,"limit":40,"events":[
              {"timestamp":1790000000.5,"category":"voice","event":"stt_transcription","severity":"info"},
              {"timestamp":-5,"category":"voice","event":"x","severity":"info"},
              {"timestamp":9e12,"category":"voice","event":"x","severity":"info"},
              {"category":"voice","event":"ohne zeit","severity":"info"},
              {"timestamp":1790000100,"category":"unknown","event":"unknown","severity":"unknown"}]}
            """));
        Check(events.Items.Count == 2 && events.Items[0].Event == "stt_transcription" && events.Items[0].Time.ToUnixTimeSeconds() == 1790000000
                && events.Items[1].Severity == "unknown",
            "Ereignisse mit ungültigem Zeitstempel müssen entfallen.", failures);

        var aggregate = BackendParsers.ParseEventsAggregate(Json("""{"hours":24,"total":9,"severities":{"info":7,"error":2,"bad":"x"},"categories":{}}"""));
        Check(aggregate.Total == 9 && aggregate.Severities.Count == 2 && aggregate.Severities["error"] == 2,
            "Ereignis-Aggregat wurde nicht korrekt gelesen.", failures);
        Check(BackendParsers.ParseSessions(Json("""{"sessions":[{"id":"1"}],"has_more":true,"total":12}""")).Total == 12,
            "Sitzungsanzahl wurde nicht korrekt gelesen.", failures);
        var webcam = BackendParsers.ParseWebcam(Json("""{"available":true,"running":false,"mobile_supported":true}"""));
        Check(webcam is { Available: true, Running: false }, "Webcam-Status wurde nicht korrekt gelesen.", failures);
        Check(BackendParsers.ParseWebcam(Json("{}")) is { Available: false, Running: false },
            "Fehlende Webcam-Felder müssen als nicht verfügbar gelten.", failures);

        foreach (var invalid in new[] { "[]", "\"text\"", "12", "null" })
        {
            var threw = false;
            try
            {
                BackendParsers.ParseStats(Json(invalid));
            }
            catch (FormatException)
            {
                threw = true;
            }

            Check(threw, $"Nicht-Objekt-Antwort '{invalid}' muss als FormatException abgelehnt werden.", failures);
        }
    }

    // ---- Runtime-Komponenten -----------------------------------------------------------------------------

    private static void VerifyRuntimeComponents(ICollection<string> failures)
    {
        var snapshot = new RuntimeSnapshot(
            "DEGRADED",
            ["Chatterbox TTS: ERROR"],
            DateTimeOffset.UtcNow,
            [
                new RuntimeComponent("llm-primary", "Primary", "READY", ""),
                new RuntimeComponent("llm-main", "Primary Alias", "READY", ""),
                new RuntimeComponent("llm-expert", "Expert", "STOPPED", "Läuft nur bei Bedarf"),
                new RuntimeComponent("chatterbox", "TTS", "ERROR", "nicht bereit"),
                new RuntimeComponent("weird", "Seltsam", "SUPER_READY", ""),
            ],
            false, true, true, "");

        Check(RuntimeComponents.Find(snapshot, RuntimeComponents.Primary) is { State: RuntimeState.Ready, Reported: true },
            "Primary muss READY sein.", failures);
        Check(RuntimeComponents.Find(snapshot, RuntimeComponents.Expert) is { State: RuntimeState.Stopped, Detail: "Läuft nur bei Bedarf" },
            "Expert STOPPED ist ein gültiger Zustand und muss unverändert bleiben.", failures);
        Check(RuntimeComponents.Find(snapshot, RuntimeComponents.Chatterbox).State == RuntimeState.Error,
            "Chatterbox ERROR muss ERROR bleiben.", failures);
        Check(RuntimeComponents.Find(snapshot, RuntimeComponents.Vvs) is { State: RuntimeState.Unavailable, Reported: false },
            "Nicht gemeldete Komponente muss UNAVAILABLE und nicht gemeldet sein.", failures);
        Check(RuntimeComponents.Find(snapshot, "weird").State == RuntimeState.Unavailable,
            "Unbekannte Zustandswörter dürfen nie als READY oder ERROR gedeutet werden.", failures);
        Check(RuntimeComponents.Find(null, RuntimeComponents.Primary) is { State: RuntimeState.Unavailable, Reported: false },
            "Ohne Snapshot muss jede Komponente UNAVAILABLE sein.", failures);
        Check(RuntimeComponents.Distinct(snapshot).All(item => item.Id != "llm-main") && RuntimeComponents.Distinct(snapshot).Count == 4,
            "Der llm-main-Alias darf nicht doppelt gezählt werden.", failures);
        Check(RuntimeComponents.Distinct(null).Count == 0, "Ohne Snapshot ist die Komponentenliste leer.", failures);
        Check(RuntimeStateText.ToDisplayText(RuntimeState.NoLiveData) == "NO LIVE DATA",
            "NoLiveData muss als 'NO LIVE DATA' angezeigt werden.", failures);
    }

    private static void VerifyFailureClassification(ICollection<string> failures)
    {
        (RuntimeState State, string Message) Classify(JarvisApiFailureKind kind, HttpStatusCode? status = null) =>
            RuntimeComponents.ClassifyFailure(new JarvisApiException("x", kind, status));

        Check(Classify(JarvisApiFailureKind.ConnectionRefused).State == RuntimeState.Offline,
            "Verbindung abgelehnt muss OFFLINE sein.", failures);
        Check(Classify(JarvisApiFailureKind.Timeout).State == RuntimeState.Unavailable,
            "Timeout darf nicht automatisch OFFLINE sein.", failures);
        Check(Classify(JarvisApiFailureKind.ConnectionFailed).State == RuntimeState.Unavailable,
            "Sonstiger Verbindungsfehler darf nicht OFFLINE sein.", failures);
        Check(Classify(JarvisApiFailureKind.InvalidResponse).State == RuntimeState.Unavailable,
            "Parse-/Größenfehler darf nicht ERROR sein.", failures);
        Check(Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.Unauthorized).State == RuntimeState.Unavailable
                && Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.Forbidden).State == RuntimeState.Unavailable,
            "401/403 muss UNAVAILABLE sein.", failures);
        Check(Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.Unauthorized).Message.Contains("JARVIS_WEB_AUTH_TOKEN", StringComparison.Ordinal)
                && !Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.Forbidden).Message.Contains("Anmeldung", StringComparison.Ordinal)
                && !Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.Forbidden).Message.Contains("TOKEN", StringComparison.Ordinal),
            "403 ist im Backend kein Auth-Fehler (401), sondern ein nicht freigegebener Pfad; kein Token-Hinweis.", failures);
        Check(Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.NotFound).State == RuntimeState.Unavailable,
            "404 muss UNAVAILABLE sein.", failures);
        Check(Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.ServiceUnavailable).State == RuntimeState.Unavailable,
            "503 (nicht bereit) muss UNAVAILABLE sein.", failures);
        Check(Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.InternalServerError).State == RuntimeState.Error
                && Classify(JarvisApiFailureKind.HttpStatus, HttpStatusCode.BadGateway).State == RuntimeState.Error,
            "500/502 muss ERROR sein.", failures);
        Check(Classify(JarvisApiFailureKind.Unspecified).State == RuntimeState.Unavailable,
            "Unspezifizierter Fehler muss UNAVAILABLE sein.", failures);
    }

    private static void VerifyMobileAdapter(ICollection<string> failures)
    {
        var status = new MobileConnectionAdapter().GetStatusAsync(CancellationToken.None).GetAwaiter().GetResult();
        Check(status.State == MobileConnectionState.NotImplemented && status.DeviceName is null && status.LastContact is null,
            "Mobile Connection muss NOT_IMPLEMENTED ohne Geräte melden.", failures);
        Check(MobileConnectionAdapter.StateText(status.State) == "NOT_IMPLEMENTED", "Mobile-Zustandstext muss NOT_IMPLEMENTED sein.", failures);
    }

    /// <summary>
    /// Jedes in den Views referenzierte Lucide-Icon muss in der zentralen Registry stehen (ein fehlender Name rendert in
    /// WinUI stillschweigend nichts), und jede Pfadangabe muss syntaktisch vollständig sein (Befehl mit passender Anzahl Werte).
    /// </summary>
    private static void VerifyIconRegistry(ICollection<string> failures)
    {
        var registry = Jarvis.ControlHub.WinUI.Icons.LucideIcons.Kinds.ToHashSet(StringComparer.Ordinal);
        foreach (var kind in registry)
        {
            Jarvis.ControlHub.WinUI.Icons.LucideIcons.TryGet(kind, out var data);
            Check(PathDataWellFormed(data), $"Icon {kind}: Pfaddaten unvollständig oder ungültig.", failures);
        }

        var views = FindRepoFile(Path.Combine("WindowsApp", "WinUI3", "Views"));
        if (views is null)
        {
            failures.Add("Icon-Registry: Views-Verzeichnis nicht gefunden.");
            return;
        }

        var source = string.Concat(Directory.GetFiles(views, "*.cs").Concat(Directory.GetFiles(views, "*.xaml")).Select(File.ReadAllText));
        var used = new HashSet<string>(StringComparer.Ordinal);
        void Collect(string text, string pattern)
        {
            foreach (System.Text.RegularExpressions.Match match in System.Text.RegularExpressions.Regex.Matches(text, pattern)) used.Add(match.Groups[1].Value);
        }

        // Direkte Aufrufe und XAML-Attribute.
        Collect(source, @"Kind=""(\w+)""");
        Collect(source, @"Kind = ""(\w+)""");
        Collect(source, @"(?:Lucide|SlotIcon|JxModule|JxSlot|Panel|LucideIcon\.Create)\(""(\w+)""");
        Collect(source, @"SystemGroup\(""[^""]+"", ""(\w+)""");
        // Tabellen, deren Icon-Spalte nur im jeweiligen Block gilt.
        Collect(Block(source, "FlowStrip(", ");", all: true), @"\(""(\w+)"", ""[^""]*"", ""[^""]*""\)");
        Collect(Block(source, "SettingsGroups =", "];"), @"\(""[^""]+"", ""(\w+)""\)");
        Collect(Block(source, "StateKind(string state) => state switch", "};"), @"=> \(""(\w+)"", ");
        Collect(Block(source, "Sections =", "};"), @"\(""[^""]+"", ""[^""]+"", ""(\w+)""\)");

        Check(used.Count >= 60, $"Icon-Registry: nur {used.Count} Icon-Verweise gefunden, Extraktion vermutlich defekt.", failures);
        foreach (var kind in used.Where(kind => !registry.Contains(kind)).Order(StringComparer.Ordinal))
        {
            failures.Add($"Icon-Registry: '{kind}' wird in den Views verwendet, fehlt aber in LucideIcons.");
        }
    }

    private static string Block(string source, string start, string end, bool all = false)
    {
        var builder = new StringBuilder();
        var index = 0;
        while ((index = source.IndexOf(start, index, StringComparison.Ordinal)) >= 0)
        {
            var stop = source.IndexOf(end, index, StringComparison.Ordinal);
            if (stop < 0) break;
            builder.Append(source, index, stop - index).Append('\n');
            index = stop;
            if (!all) break;
        }

        return builder.ToString();
    }

    private static bool PathDataWellFormed(string? data)
    {
        if (string.IsNullOrWhiteSpace(data)) return false;
        var tokens = System.Text.RegularExpressions.Regex.Matches(data, @"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE]-?\d+)?")
            .Select(match => match.Value).ToList();
        if (string.Concat(tokens).Length != System.Text.RegularExpressions.Regex.Replace(data, @"[\s,]", string.Empty).Length) return false;
        if (tokens.Count == 0 || tokens[0] is not ("M" or "m")) return false;
        var i = 0;
        while (i < tokens.Count)
        {
            var command = char.ToUpperInvariant(tokens[i++][0]);
            var arity = command switch { 'M' or 'L' or 'T' => 2, 'H' or 'V' => 1, 'C' => 6, 'S' or 'Q' => 4, 'A' => 7, 'Z' => 0, _ => -1 };
            if (arity < 0) return false;
            var count = 0;
            while (i < tokens.Count && !char.IsLetter(tokens[i][0])) { count++; i++; }
            if (arity == 0 ? count != 0 : count == 0 || count % arity != 0) return false;
        }

        return true;
    }

    private static string? FindRepoFile(string relative)
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            var candidate = Path.Combine(dir.FullName, relative);
            if (Directory.Exists(candidate) || File.Exists(candidate)) return candidate;
        }

        return null;
    }

    private static readonly DateTimeOffset EventBase = DateTimeOffset.FromUnixTimeSeconds(1_790_000_000);

    private static EventItem Ev(int second, string eventName, string category, string severity = "info") =>
        new(EventBase.AddSeconds(second), category, eventName, severity);

    /// <summary>Mapping nur mit Backend-Vokabular (core/event_logger.py CATEGORIES/SEVERITIES, Emit-Stellen).</summary>
    private static void VerifyBrainEventMapping(ICollection<string> failures)
    {
        (string Category, string Event, string Severity, BrainActivityType? Expected)[] cases =
        [
            ("inference", "stt_transcription", "info", BrainActivityType.InputReceived),
            ("inference", "stt_transcription", "debug", null),
            ("inference", "stt_transcription", "error", BrainActivityType.ErrorEvent),
            ("decision", "route_completed", "info", BrainActivityType.ModelRouting),
            ("inference", "llm_call", "info", BrainActivityType.ModelInference),
            ("inference", "llm_call", "error", BrainActivityType.ErrorEvent),
            ("tool_execution", "tool_completed", "info", BrainActivityType.ToolResult),
            ("tool_execution", "tool_completed", "error", BrainActivityType.ErrorEvent),
            ("error_recovery", "watchdog_listener_stuck", "warn", BrainActivityType.DegradedEvent),
            ("error_recovery", "watchdog_stt_backlog", "warn", BrainActivityType.DegradedEvent),
            // Unbekannt, projiziert oder ohne belegte Semantik: keine Aktivität.
            ("unknown", "unknown", "unknown", null),
            ("inference", "unknown", "info", null),
            ("user_interaction", "conversation_opened", "info", null),
            ("inference", "tts_synthesis", "info", null),
            ("tool_execution", "skill_intent_completed", "info", null),
            ("performance", "turn_latency", "info", null),
            ("self_assessment", "cloud_consultation", "info", null),
            // Falsche Kategorie oder Schwere für ein bekanntes Ereignis: nicht raten.
            ("decision", "llm_call", "info", null),
            ("inference", "route_completed", "info", null),
            ("error_recovery", "watchdog_listener_stuck", "info", null),
            ("error_recovery", "tool_completed", "error", null),
        ];
        foreach (var (category, name, severity, expected) in cases)
        {
            var actual = BrainEventMapping.Map(category, name, severity);
            Check(actual == expected, $"BrainEventMapping {category}/{name}/{severity}: erwartet {expected?.ToString() ?? "keine"}, erhalten {actual?.ToString() ?? "keine"}.", failures);
        }

        // Ohne belegte Quelle darf keine Zeile diese Typen erzeugen.
        var produced = cases.Select(c => BrainEventMapping.Map(c.Category, c.Event, c.Severity)).OfType<BrainActivityType>().ToHashSet();
        foreach (var forbidden in new[] { BrainActivityType.ToolCall, BrainActivityType.MemoryRetrieval, BrainActivityType.ContextBuild, BrainActivityType.ResponseGeneration, BrainActivityType.MemoryWriteConfirmed })
        {
            Check(!produced.Contains(forbidden), $"BrainEventMapping erzeugt {forbidden} ohne reale Quelle.", failures);
        }
    }

    private static void VerifyBrainEventCursor(ICollection<string> failures)
    {
        var cursor = new BrainEventCursor();
        // Backend: ORDER BY timestamp DESC.
        IReadOnlyList<EventItem> first = [Ev(30, "llm_call", "inference"), Ev(20, "route_completed", "decision"), Ev(10, "stt_transcription", "inference")];
        Check(cursor.Advance(first).Count == 0, "Cursor: erster Snapshot darf nicht abgespielt werden (Baseline).", failures);
        Check(cursor.HasBaseline, "Cursor: Baseline nach erstem Snapshot nicht gesetzt.", failures);

        IReadOnlyList<EventItem> second = [Ev(42, "tool_completed", "tool_execution"), Ev(41, "llm_call", "inference"), .. first];
        var fresh = cursor.Advance(second);
        Check(fresh.Count == 2, $"Cursor: nur neue Ereignisse erwartet (2), erhalten {fresh.Count}.", failures);
        Check(fresh.Count == 2 && fresh[0].Time < fresh[1].Time && fresh[0].Event == "llm_call", "Cursor: neue Ereignisse nicht chronologisch (ältestes zuerst).", failures);

        Check(cursor.Advance(second).Count == 0, "Cursor: identischer Snapshot erzeugt erneut Ereignisse (Deduplizierung).", failures);

        // Gleicher Zeitstempel: newest-first bedeutet, der spätere Index ist der ältere Eintrag.
        IReadOnlyList<EventItem> sameTime = [Ev(50, "tool_completed", "tool_execution"), Ev(50, "llm_call", "inference"), .. second];
        var tie = cursor.Advance(sameTime);
        Check(tie.Count == 2 && tie[0].Event == "llm_call" && tie[1].Event == "tool_completed", "Cursor: Reihenfolge bei gleichem Zeitstempel folgt nicht der Backend-Reihenfolge.", failures);

        // Weit ältere, bisher unbekannte Einträge sind Historie, keine Live-Ereignisse.
        IReadOnlyList<EventItem> historic = [.. sameTime, Ev(1, "llm_call", "inference")];
        Check(cursor.Advance(historic).Count == 0, "Cursor: historischer Eintrag wurde als neu abgespielt.", failures);

        // Nachzügler innerhalb der Toleranz zählt.
        IReadOnlyList<EventItem> late = [Ev(48, "route_completed", "decision"), .. sameTime];
        Check(cursor.Advance(late).Count == 1, "Cursor: Nachzügler innerhalb der Toleranz verloren.", failures);

        cursor.Reset();
        Check(cursor.Advance(late).Count == 0 && cursor.HasBaseline, "Cursor: nach Reset muss der nächste Snapshot wieder Baseline sein.", failures);

        var empty = new BrainEventCursor();
        Check(empty.Advance([]).Count == 0 && empty.HasBaseline, "Cursor: leerer erster Snapshot muss Baseline setzen.", failures);
        Check(empty.Advance([Ev(5, "llm_call", "inference")]).Count == 1, "Cursor: nach leerer Baseline muss ein neues Ereignis zählen.", failures);
    }

    private static WebReading EventsReading(params EventItem[] items) =>
        new(RuntimeState.Ready, string.Empty, new EventsInfo(items), DateTimeOffset.Now);

    private static async Task VerifyBrainEventBridgeAsync(ICollection<string> failures)
    {
        static Task NoDelay(TimeSpan _, CancellationToken token) { token.ThrowIfCancellationRequested(); return Task.CompletedTask; }

        // Baseline, danach nur neue, gemappte Ereignisse in chronologischer Reihenfolge.
        var bridge = new BrainEventBridge(_ => Task.FromResult(WebReading.NotQueried), NoDelay);
        var raised = new List<BrainActivityType>();
        var sources = new List<RuntimeState>();
        bridge.Activity += raised.Add;
        bridge.SourceChanged += sources.Add;
        await bridge.ProcessAsync(EventsReading(Ev(10, "llm_call", "inference")), CancellationToken.None);
        Check(raised.Count == 0, "Bridge: Baseline-Snapshot hat Aktivität ausgelöst.", failures);
        await bridge.ProcessAsync(EventsReading(Ev(13, "tool_completed", "tool_execution"), Ev(12, "conversation_opened", "user_interaction"), Ev(11, "route_completed", "decision"), Ev(10, "llm_call", "inference")), CancellationToken.None);
        Check(raised.SequenceEqual([BrainActivityType.ModelRouting, BrainActivityType.ToolResult]), $"Bridge: erwartet ModelRouting, ToolResult; erhalten {string.Join(",", raised)}.", failures);
        Check(sources.SequenceEqual([RuntimeState.Ready]), "Bridge: Quellzustand READY nicht gemeldet.", failures);

        // OFFLINE, UNAVAILABLE, ERROR: keine Aktivität, Quelle gemeldet, Cursor zurückgesetzt (kein Nachholen).
        raised.Clear();
        foreach (var state in new[] { RuntimeState.Offline, RuntimeState.Unavailable, RuntimeState.Error })
        {
            await bridge.ProcessAsync(new WebReading(state, "x", null, DateTimeOffset.Now), CancellationToken.None);
        }

        Check(raised.Count == 0, "Bridge: OFFLINE/UNAVAILABLE/ERROR hat Aktivität ausgelöst.", failures);
        Check(bridge.SourceState == RuntimeState.Error && sources.Contains(RuntimeState.Offline) && sources.Contains(RuntimeState.Unavailable), "Bridge: Quellzustände nicht weitergegeben.", failures);
        await bridge.ProcessAsync(EventsReading(Ev(99, "llm_call", "inference"), Ev(98, "stt_transcription", "inference")), CancellationToken.None);
        Check(raised.Count == 0, "Bridge: nach Wiederverbindung wurden verpasste Ereignisse abgespielt (Recovery muss Baseline sein).", failures);

        // Burst: höchstens MaxEventsPerBatch, und zwar die jüngsten, chronologisch.
        raised.Clear();
        var burst = Enumerable.Range(0, 30).Select(i => Ev(200 + i, i % 2 == 0 ? "llm_call" : "route_completed", i % 2 == 0 ? "inference" : "decision")).Reverse().ToArray();
        await bridge.ProcessAsync(EventsReading([.. burst, Ev(99, "llm_call", "inference"), Ev(98, "stt_transcription", "inference")]), CancellationToken.None);
        Check(raised.Count == BrainEventBridge.MaxEventsPerBatch, $"Bridge: Burst nicht begrenzt ({raised.Count}).", failures);
        Check(BrainEventBridge.MaxEventsPerBatch <= BrainActivityScheduler.MaxConcurrentPulses, "Bridge: Batch-Grenze über MaxConcurrentPulses.", failures);
        Check(raised.Count > 0 && raised[^1] == BrainActivityType.ModelRouting, "Bridge: Burst endet nicht mit dem jüngsten Ereignis.", failures);

        // Transportfehler: Ausnahme beim Lesen ergibt UNAVAILABLE und keinen erfundenen Fehlerpuls.
        var throwing = new BrainEventBridge(_ => throw new HttpRequestException("kaputt"), (_, token) => Task.Delay(Timeout.Infinite, token));
        var throwingRaised = 0;
        throwing.Activity += _ => throwingRaised++;
        using (var cts = new CancellationTokenSource())
        {
            var run = throwing.RunAsync(cts.Token);
            await Task.Delay(50);
            Check(throwing.SourceState == RuntimeState.Unavailable, "Bridge: Lesefehler nicht als UNAVAILABLE gemeldet.", failures);
            Check(throwingRaised == 0, "Bridge: Transportfehler hat Brain-Aktivität erzeugt.", failures);
            cts.Cancel();
            Check(await Task.WhenAny(run, Task.Delay(2000)) == run && run.IsCompletedSuccessfully, "Bridge: Schleife endet nicht nach Cancellation.", failures);
        }

        // Cancellation / Unload: danach keine Abfragen und keine Aktivität mehr.
        var reads = 0;
        var second = 300;
        var live = new BrainEventBridge(_ =>
        {
            Interlocked.Increment(ref reads);
            second++;
            return Task.FromResult(EventsReading(Ev(second, "llm_call", "inference")));
        }, (_, token) => Task.Delay(5, token));
        var liveRaised = 0;
        live.Activity += _ => Interlocked.Increment(ref liveRaised);
        using (var cts = new CancellationTokenSource())
        {
            var run = live.RunAsync(cts.Token);
            await Task.Delay(120);
            cts.Cancel();
            var finished = await Task.WhenAny(run, Task.Delay(2000)) == run;
            Check(finished && run.IsCompletedSuccessfully, "Bridge: RunAsync endet nicht sauber nach Cancellation.", failures);
            Check(liveRaised > 0, "Bridge: laufende Schleife hat keine neuen Ereignisse verarbeitet.", failures);
            var readsAfter = Volatile.Read(ref reads);
            var raisedAfter = Volatile.Read(ref liveRaised);
            await Task.Delay(80);
            Check(Volatile.Read(ref reads) == readsAfter && Volatile.Read(ref liveRaised) == raisedAfter, "Bridge: nach Cancellation laufen noch Abfragen oder Aktivität.", failures);
        }

        // Cancellation während eines gestaffelten Bursts bricht die restliche Ausgabe ab.
        var staggered = new BrainEventBridge(_ => Task.FromResult(WebReading.NotQueried), (_, token) => Task.Delay(Timeout.Infinite, token));
        var staggeredRaised = 0;
        staggered.Activity += _ => staggeredRaised++;
        await staggered.ProcessAsync(EventsReading(Ev(1, "llm_call", "inference")), CancellationToken.None);
        using (var cts = new CancellationTokenSource())
        {
            var process = staggered.ProcessAsync(EventsReading(Ev(4, "llm_call", "inference"), Ev(3, "llm_call", "inference"), Ev(2, "llm_call", "inference"), Ev(1, "llm_call", "inference")), cts.Token);
            cts.Cancel();
            try { await process; } catch (OperationCanceledException) { }
            Check(staggeredRaised == 1, $"Bridge: nach Cancellation wurden weitere gestaffelte Ereignisse ausgegeben ({staggeredRaised}).", failures);
        }

        // Statustexte: AKTIV nur mit Aktivität; ohne Ereignisse der ehrliche Quellzustand.
        Check(BrainStageStatus.Describe(false, false, RuntimeState.Ready).Title == "IDLE. READY.", "BrainStageStatus: READY ohne Ereignisse muss IDLE sein.", failures);
        Check(BrainStageStatus.Describe(false, false, RuntimeState.Offline).Title == "IDLE. OFFLINE.", "BrainStageStatus: OFFLINE falsch.", failures);
        Check(BrainStageStatus.Describe(false, false, null).Title == "IDLE. UNAVAILABLE.", "BrainStageStatus: ohne Quelle falsch.", failures);
        Check(BrainStageStatus.Describe(true, false, RuntimeState.Ready).Title == "AKTIV.", "BrainStageStatus: aktiv falsch.", failures);
        Check(BrainStageStatus.Describe(true, true, null).Title == "AKTIV. TESTSEQUENZ.", "BrainStageStatus: Testsequenz falsch.", failures);
    }

    private static void VerifyBrainPrivacyAndReadOnly(ICollection<string> failures)
    {
        // Brain-Eventmodell trägt nur Zeit, Kategorie, Ereignisname und Schwere.
        var fields = typeof(EventItem).GetProperties().Select(p => p.Name).Order(StringComparer.Ordinal).ToArray();
        Check(fields.SequenceEqual(["Category", "Event", "Severity", "Time"]), $"EventItem enthält unerwartete Felder: {string.Join(",", fields)}.", failures);
        var activityFields = typeof(BrainActivityEvent).GetProperties().Select(p => p.Name).Order(StringComparer.Ordinal).ToArray();
        Check(activityFields.SequenceEqual(["IsTest", "Type"]), $"BrainActivityEvent enthält unerwartete Felder: {string.Join(",", activityFields)}.", failures);
        var parsed = BackendParsers.ParseEventsRecent(Json("""{"events":[{"timestamp":1790000000,"category":"inference","event":"llm_call","severity":"info","message":"GEHEIM-PROMPT","metadata":{"arguments":"GEHEIM-ARG"}}]}"""));
        var rendered = string.Join("|", parsed.Items.Select(item => item.ToString()));
        Check(parsed.Items.Count == 1 && !rendered.Contains("GEHEIM", StringComparison.Ordinal), "ParseEventsRecent übernimmt Inhaltsfelder.", failures);

        // Kein Schreibpfad: Adapter und API-Client senden nur GET.
        var root = FindRepoFile(Path.Combine("WindowsApp", "WinUI3", "Adapters"));
        var client = FindRepoFile(Path.Combine("WindowsApp", "JarvisApiClient.cs"));
        if (root is null || client is null)
        {
            failures.Add("Read-only-Prüfung: Quellen nicht gefunden.");
            return;
        }

        var source = string.Concat(Directory.GetFiles(root, "*.cs").Append(client).Select(File.ReadAllText));
        foreach (var write in new[] { "HttpMethod.Post", "HttpMethod.Put", "HttpMethod.Delete", "HttpMethod.Patch", "PostAsync", "PutAsync", "DeleteAsync", "PatchAsync", "ClientWebSocket" })
        {
            Check(!source.Contains(write, StringComparison.Ordinal), $"Read-only verletzt: {write} in Adapter oder API-Client.", failures);
        }

        Check(source.Contains("http://127.0.0.1:", StringComparison.Ordinal) && !System.Text.RegularExpressions.Regex.IsMatch(source, @"https?://(?!127\.0\.0\.1)[a-z0-9.-]+[:/]"), "Loopback-only verletzt: Nicht-Loopback-Adresse im Adapter oder API-Client.", failures);
    }

    /// <summary>
    /// Anliegen des entfernten Legacy-Harness (siehe docs/DESKTOP_ARCHITECTURE.md), geprüft
    /// gegen den aktuellen Backend-Vertrag (jarvis_web.py agents_status_handler, JARVIS.Runtime.psm1) und den WinUI-Code:
    /// Planner ohne Inhalte und nur mit plausiblen Zählern, Lifecycle-Freigabe nur aus dem Supervisor-Zustand desselben
    /// Checkouts, Repository-Erkennung und Reparse-Point-Schutz. Die WPF-Zeitschwellen sind bewusst nicht übernommen.
    /// </summary>
    private static void VerifyPortedLegacyChecks(ICollection<string> failures, ICollection<string> skipped)
    {
        string Agent(string state, string flags, string counts, string extra = "") =>
            "{\"available\":true,\"state\":\"" + state + "\"," + flags + "," + counts + ",\"canPause\":false,\"observedAt\":\"2026-09-29T12:00:00+00:00\"" + extra + "}";
        const string running = "\"active\":true,\"paused\":false,\"awaitingConfirmation\":false";
        const string counts = "\"stepCount\":3,\"completedSteps\":1,\"runningSteps\":1,\"failedSteps\":0,\"pendingSteps\":1,\"skippedSteps\":0";

        var live = BackendParsers.ParseAgents(Json(Agent("running", running, counts,
            ",\"original_request\":\"PRIVATE_AGENT_REQUEST_SENTINEL\",\"steps\":[{\"description\":\"PRIVATE_STEP_SENTINEL\",\"result\":\"PRIVATE_RESULT_SENTINEL\"}]")));
        Check(live is { Available: true, Implausible: false, State: "RUNNING", Steps: 3, Completed: 1 }, "Planner: gültiger laufender Plan nicht gelesen.", failures);
        Check(!live.ToString().Contains("PRIVATE_", StringComparison.Ordinal), "Planner: Plan- oder Schrittinhalt im Planner-Modell.", failures);

        // Alle Flag-Kombinationen, die agents_status_handler tatsächlich erzeugt, sind gültig.
        (string State, string Flags)[] backendCombinations =
        [
            ("paused", "\"active\":false,\"paused\":true,\"awaitingConfirmation\":false"),
            ("paused", "\"active\":false,\"paused\":true,\"awaitingConfirmation\":true"),
            ("awaiting_confirmation", "\"active\":true,\"paused\":false,\"awaitingConfirmation\":true"),
            ("awaiting_confirmation", "\"active\":false,\"paused\":false,\"awaitingConfirmation\":true"),
            ("pending", "\"active\":false,\"paused\":false,\"awaitingConfirmation\":false"),
            ("completed", "\"active\":false,\"paused\":false,\"awaitingConfirmation\":false"),
        ];
        foreach (var (state, flags) in backendCombinations)
        {
            Check(BackendParsers.ParseAgents(Json(Agent(state, flags, counts))) is { Available: true, Implausible: false, Steps: 3 },
                $"Planner: vom Backend erzeugte Kombination {state}/{flags} wurde verworfen.", failures);
        }

        // Kombinationen, die das Backend nie erzeugt: Backend-Aussage bleibt, Zahlen werden nicht gezeigt.
        var contradictory = BackendParsers.ParseAgents(Json(Agent("running", "\"active\":false,\"paused\":true,\"awaitingConfirmation\":false", counts)));
        Check(contradictory is { Available: true, Implausible: true, State: "RUNNING", Steps: 0 },
            "Planner: paused=true mit state running muss client-seitig unplausibel sein, Backend-Zustand bleibt erhalten.", failures);
        Check(BackendParsers.ParseAgents(Json(Agent("pending", running, counts))) is { Implausible: true },
            "Planner: active=true außerhalb von running/awaiting_confirmation wurde akzeptiert.", failures);
        Check(BackendParsers.ParseAgents(Json(Agent("running",
                running, "\"stepCount\":0,\"completedSteps\":9223372036854775807,\"runningSteps\":2,\"failedSteps\":9223372036854775807,\"pendingSteps\":0,\"skippedSteps\":0"))) is { Implausible: true, Steps: 0 },
            "Planner: überlaufende Schrittzähler wurden als Fortschritt akzeptiert.", failures);
        Check(BackendParsers.ParseAgents(Json(Agent("running", running, counts.Replace("\"stepCount\":3", "\"stepCount\":4", StringComparison.Ordinal)))) is { Implausible: true },
            "Planner: Schrittsumme ungleich stepCount wurde akzeptiert.", failures);

        // observedAt ist der Abfragezeitpunkt des Backends, kein Planalter: kein client-seitiges STALE.
        Check(BackendParsers.ParseAgents(Json(Agent("running", running, counts).Replace("2026-09-29T12:00:00+00:00", "2020-01-01T00:00:00Z", StringComparison.Ordinal))) is { Available: true, Implausible: false },
            "Planner: observedAt darf nicht als Frische des Plans bewertet werden.", failures);

        // Lifecycle-Freigabe: nur Supervisor-capabilities des Snapshots, der für den gewählten Checkout abgefragt wurde.
        Jarvis.ControlHub.RuntimeSnapshot Snap() => new("READY", [], null, [], CanStart: false, CanStop: true, CanRestart: true, string.Empty);
        const string root = "/srv/jarvis/Main";
        var stop = Jarvis.ControlHub.JarvisRuntimeAction.Stop;
        Check(RuntimeActionGuard.IsAllowed(stop, Snap(), root, root), "Lifecycle: vom Supervisor erlaubte Aktion nicht freigegeben.", failures);
        Check(RuntimeActionGuard.IsAllowed(stop, Snap(), root + "/", root), "Lifecycle: gleicher Checkout mit abschließendem Trenner abgelehnt.", failures);
        Check(!RuntimeActionGuard.IsAllowed(Jarvis.ControlHub.JarvisRuntimeAction.Start, Snap(), root, root), "Lifecycle: vom Supervisor nicht erlaubte Aktion freigegeben.", failures);
        Check(!RuntimeActionGuard.IsAllowed(stop, Snap(), "/srv/jarvis/Old", root), "Lifecycle: Snapshot eines anderen Checkouts gibt Aktion frei.", failures);
        Check(!RuntimeActionGuard.IsAllowed(stop, null, root, root) && !RuntimeActionGuard.IsAllowed(stop, Snap(), null, root)
                && !RuntimeActionGuard.IsAllowed(stop, Snap(), root, null),
            "Lifecycle: ohne Snapshot, Snapshot-Checkout oder gewählten Checkout freigegeben.", failures);
        var shell = FindRepoFile(Path.Combine("WindowsApp", "WinUI3", "Views", "ShellPage.xaml.cs"));
        var shellText = shell is null ? string.Empty : File.ReadAllText(shell);
        var request = shellText.IndexOf("private async Task RequestRuntimeActionAsync", StringComparison.Ordinal);
        var dialog = request < 0 ? -1 : shellText.IndexOf("dialog.ShowAsync()", request, StringComparison.Ordinal);
        var send = request < 0 ? -1 : shellText.IndexOf("_supervisor.RequestActionAsync", request, StringComparison.Ordinal);
        var checkBefore = request < 0 ? -1 : shellText.IndexOf("IsRuntimeActionAllowedAsync(action, root)", request, StringComparison.Ordinal);
        var checkAfter = dialog < 0 ? -1 : shellText.IndexOf("IsRuntimeActionAllowedAsync(action, root)", dialog, StringComparison.Ordinal);
        Check(request >= 0 && checkBefore > request && checkBefore < dialog && checkAfter > dialog && checkAfter < send,
            "Lifecycle: Supervisor-Freigabe muss vor und nach dem Bestätigungsdialog neu abgefragt werden.", failures);
        Check(request >= 0 && shellText.IndexOf("_runtimeActionInFlight) return;", request, StringComparison.Ordinal) is > 0 and var guard && guard < dialog
                && shellText.IndexOf("_runtimeActionInFlight = false;", request, StringComparison.Ordinal) > 0,
            "Lifecycle: parallele Aktionen (zweiter Klick während Dialog oder Supervisor-Abfrage) müssen ausgeschlossen sein.", failures);

        // Repository-Erkennung: im integrierten Repo ist der Root selbst der validierte Checkout; ungültige explizite
        // Roots fallen nicht still auf einen anderen Checkout zurück.
        var repoRoot = FindRepoFile("JARVIS-Runtime.ps1") is { } script ? Path.GetDirectoryName(script) : null;
        Check(repoRoot is not null && Equals(Jarvis.ControlHub.RepositoryRootValidator.DiscoverFrom(AppContext.BaseDirectory), repoRoot),
            "Legacy-Port: Repository-Root wurde vom App-Verzeichnis aus nicht erkannt.", failures);
        Check(Equals(Jarvis.ControlHub.RepositoryRootValidator.ResolveConfiguredRoot([], AppContext.BaseDirectory), repoRoot),
            "Legacy-Port: ohne konfigurierten Root lief keine automatische Erkennung.", failures);
        Check(Jarvis.ControlHub.RepositoryRootValidator.ResolveConfiguredRoot([Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"))], AppContext.BaseDirectory) is null,
            "Legacy-Port: ungültiger expliziter Root fiel auf einen anderen Checkout zurück.", failures);
        if (repoRoot is not null)
        {
            VerifyLinkedCheckoutRejected(repoRoot, linkFile: true, failures, skipped);
            VerifyLinkedCheckoutRejected(repoRoot, linkFile: false, failures, skipped);
        }
    }

    /// <summary>Ein Kandidat mit verlinktem Supervisor-Modul bzw. verlinktem scripts-Ordner muss abgelehnt werden.</summary>
    private static void VerifyLinkedCheckoutRejected(string repoRoot, bool linkFile, ICollection<string> failures, ICollection<string> skipped)
    {
        var testRoot = Path.Combine(Path.GetTempPath(), $"JarvisLinkedCheckout-{Guid.NewGuid():N}");
        var candidate = Path.Combine(testRoot, "Main");
        var required = new[]
        {
            "JARVIS.Runtime.psm1", "JARVIS-Runtime.ps1", "jarvis_web.py", "config.yaml", "start.sh", "stop.sh", "restart.sh",
            Path.Combine("scripts", "check_runtime_dependencies.py"), Path.Combine("scripts", "check_chatterbox_runtime.py"),
            Path.Combine("scripts", "runtime_status.py"), Path.Combine("core", "runtime_state.py"),
        };
        try
        {
            Directory.CreateDirectory(candidate);
            try
            {
                if (linkFile) File.CreateSymbolicLink(Path.Combine(candidate, "JARVIS.Runtime.psm1"), Path.Combine(repoRoot, "JARVIS.Runtime.psm1"));
                else Directory.CreateSymbolicLink(Path.Combine(candidate, "scripts"), Path.Combine(repoRoot, "scripts"));
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException or PlatformNotSupportedException or IOException)
            {
                skipped.Add($"Legacy-Port: Symlink-Prüfung ({(linkFile ? "Datei" : "Ordner")}) – Konto darf keine Symlinks anlegen.");
                return;
            }

            foreach (var relative in required)
            {
                var target = Path.Combine(candidate, relative);
                if (File.Exists(target) || (!linkFile && relative.StartsWith("scripts", StringComparison.Ordinal))) continue;
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                File.WriteAllText(target, string.Empty);
            }

            var rejected = false;
            try { Jarvis.ControlHub.RepositoryRootValidator.Validate(candidate); }
            catch (InvalidOperationException) { rejected = true; }
            Check(rejected, $"Legacy-Port: Checkout mit verlinkt{(linkFile ? "em Supervisor-Modul" : "em scripts-Ordner")} wurde akzeptiert.", failures);
        }
        finally
        {
            try { if (Directory.Exists(testRoot)) Directory.Delete(testRoot, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    /// <summary>
    /// Vertrag Client ↔ Backend: jeder Pfad, den JarvisApiClient abfragen kann, steht samt Query-Schlüsseln in
    /// _DESKTOP_READ_ALLOWLIST von jarvis_web.py. Sonst würde der Desktop-Modus ihn mit 403 ablehnen.
    /// </summary>
    private static void VerifyClientPathsAreDesktopAllowlisted(ICollection<string> failures)
    {
        var client = FindRepoFile(Path.Combine("WindowsApp", "JarvisApiClient.cs"));
        var backend = FindRepoFile("jarvis_web.py");
        if (client is null || backend is null)
        {
            failures.Add("Allowlist-Vertrag: JarvisApiClient.cs oder jarvis_web.py nicht gefunden.");
            return;
        }

        var block = System.Text.RegularExpressions.Regex.Match(File.ReadAllText(backend), @"_DESKTOP_READ_ALLOWLIST = \{(?<body>.*?)\n\}", System.Text.RegularExpressions.RegexOptions.Singleline);
        var allow = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        foreach (System.Text.RegularExpressions.Match entry in System.Text.RegularExpressions.Regex.Matches(block.Groups["body"].Value, @"'(?<path>/api/[^']+)':\s*frozenset\((?:\{(?<keys>[^}]*)\})?\)"))
        {
            allow[entry.Groups["path"].Value] = entry.Groups["keys"].Value.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(key => key.Trim('\'')).ToHashSet(StringComparer.Ordinal);
        }

        Check(allow.Count == 9, $"Allowlist-Vertrag: erwartet 9 Desktop-Pfade im Backend, gefunden {allow.Count}.", failures);

        // Port-Vertrag: der Client spricht genau den Port des Desktop-Modus an, nie den Standard-Webport.
        var backendText = File.ReadAllText(backend);
        var desktopPort = System.Text.RegularExpressions.Regex.Match(backendText, @"^DESKTOP_MODE_PORT = (\d+)$", System.Text.RegularExpressions.RegexOptions.Multiline);
        var configFile = FindRepoFile("config.yaml");
        var webPort = configFile is null ? null : System.Text.RegularExpressions.Regex.Match(File.ReadAllText(configFile), @"^web:\s*\n\s+port:\s*(\d+)", System.Text.RegularExpressions.RegexOptions.Multiline);
        Check(desktopPort.Success && int.Parse(desktopPort.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture) == JarvisApiClient.LoopbackPort,
            $"Port-Vertrag: JarvisApiClient.LoopbackPort ({JarvisApiClient.LoopbackPort}) muss jarvis_web.DESKTOP_MODE_PORT entsprechen.", failures);
        Check(webPort is { Success: true } && int.Parse(webPort.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture) != JarvisApiClient.LoopbackPort,
            "Port-Vertrag: Desktop-API darf nicht auf dem Standard-Webport (config.yaml web.port) liegen.", failures);
        var requests = System.Text.RegularExpressions.Regex.Matches(File.ReadAllText(client), @"GetJsonAsync\(""(?<path>[^""]+)""")
            .Select(match => match.Groups["path"].Value).ToList();
        Check(requests.Count == 9, $"Allowlist-Vertrag: erwartet 9 Client-Pfade, gefunden {requests.Count}.", failures);
        foreach (var request in requests)
        {
            var parts = request.Split('?', 2);
            var path = "/" + parts[0];
            var keys = parts.Length > 1 ? parts[1].Split('&').Select(pair => pair.Split('=')[0]) : [];
            Check(allow.TryGetValue(path, out var allowed) && keys.All(allowed.Contains),
                $"Allowlist-Vertrag: Client-Pfad {request} ist im Desktop-Modus nicht freigegeben.", failures);
        }
    }

    /// <summary>Alle relativen Quellen des WinUI-Projekts liegen im Repository (kein Workspace-Layout außerhalb).</summary>
    private static void VerifyProjectSources(ICollection<string> failures)
    {
        var project = FindRepoFile(Path.Combine("WindowsApp", "WinUI3", "Jarvis.ControlHub.WinUI.csproj"));
        var repoRoot = FindRepoFile("jarvis_web.py") is { } web ? Path.GetDirectoryName(web) : null;
        if (project is null || repoRoot is null)
        {
            failures.Add("Projektquellen: WinUI-Projekt oder Repository-Root nicht gefunden.");
            return;
        }

        var directory = Path.GetDirectoryName(project)!;
        var includes = System.Xml.Linq.XDocument.Load(project).Descendants()
            .Select(element => (string?)element.Attribute("Include"))
            .Where(include => include is not null && include.StartsWith("..", StringComparison.Ordinal) && !include.Contains('*'))
            .ToList();
        Check(includes.Count > 0, "Projektquellen: keine relativen Includes gefunden.", failures);
        foreach (var include in includes)
        {
            var full = Path.GetFullPath(Path.Combine(directory, include!.Replace('\\', Path.DirectorySeparatorChar)));
            Check(full.StartsWith(repoRoot + Path.DirectorySeparatorChar, StringComparison.Ordinal), $"Projektquelle außerhalb des Repositorys: {include}.", failures);
            Check(File.Exists(full), $"Projektquelle fehlt: {include}.", failures);
        }
    }

    private static void VerifyHeaderLayout(ICollection<string> failures)
    {
        // Geschätzte natürliche Inhaltsbreiten der acht Tabs (Segoe UI Variable 11.52; Icon 18 über Label).
        double[] tabs = [30, 25, 42, 92, 74, 28, 40, 52];
        const double statusWith = 526, statusWithout = 396;
        // Verfügbare Navigationsbreite = Fenster - 22.4 - 146 - 2 * 20 - 159.3 - 8.
        static double Available(double window) => window - 22.4 - 146 - 40 - 159.3 - 8;

        var wide = HeaderLayout.Choose(Available(1920), tabs, statusWith, statusWithout);
        Check(wide == new HeaderFit(TabDensity.Wide, true), $"HeaderLayout 1920: erwartet Wide mit Labels, erhalten {wide}.", failures);
        var laptop = HeaderLayout.Choose(Available(1536), tabs, statusWith, statusWithout);
        Check(!laptop.SystemLabels, "HeaderLayout 1536: Statuslabels dürfen die Tabs nicht ins Overflow drängen.", failures);
        Check(HeaderLayout.TabsWidth(tabs, laptop.Tabs) + statusWithout + HeaderLayout.FitReserve <= Available(1536), "HeaderLayout 1536: gewählte Dichte passt nicht (Overflow).", failures);
        var narrow = HeaderLayout.Choose(Available(1300), tabs, statusWith, statusWithout);
        Check(narrow == new HeaderFit(TabDensity.Compact, false), $"HeaderLayout 1300: erwartet Compact ohne Labels, erhalten {narrow}.", failures);
        Check(HeaderLayout.TabsWidth(tabs, TabDensity.Compact) < HeaderLayout.TabsWidth(tabs, TabDensity.Wide), "HeaderLayout: Compact ist nicht schmaler als Wide.", failures);
        Check(tabs.All(t => HeaderLayout.MinWidth(TabDensity.Compact) >= 70.4 && t + 2 * HeaderLayout.Padding(TabDensity.Compact) > t), "HeaderLayout: Compact-Maße unter Referenz.", failures);

        // Statische Layoutursachen: Overflow-Abstand, Tab-Rhythmus, Spaltenaufbau der Titelleiste.
        var tokens = FindRepoFile(Path.Combine("WindowsApp", "WinUI3", "Resources", "DesignTokens.xaml"));
        var shell = FindRepoFile(Path.Combine("WindowsApp", "WinUI3", "Views", "ShellPage.xaml"));
        if (tokens is null || shell is null)
        {
            failures.Add("Header: XAML-Quellen nicht gefunden.");
            return;
        }

        var tokenText = File.ReadAllText(tokens);
        var overflow = System.Text.RegularExpressions.Regex.Match(tokenText, @"x:Key=""TopNavigationViewOverflowButtonMargin"">([^<]+)<");
        Check(overflow.Success && overflow.Groups[1].Value.Split(',').Select(double.Parse).First() >= 8, "Header: Overflow-Button ohne Abstand zur Primärnavigation.", failures);
        Check(tokenText.Contains(@"x:Key=""TopNavigationViewItemMargin""", StringComparison.Ordinal), "Header: Tab-Abstand (.jx-tabs gap) fehlt.", failures);
        Check(tokenText.Contains(@"x:Key=""TopNavigationViewItemContentPresenterMargin"">0,-1,0,-1<", StringComparison.Ordinal), "Header: asymmetrischer Standard-Innenabstand der Tabs aktiv.", failures);

        var xaml = System.Xml.Linq.XDocument.Load(shell);
        System.Xml.Linq.XNamespace ns = "http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        System.Xml.Linq.XNamespace x = "http://schemas.microsoft.com/winfx/2006/xaml";
        var bar = xaml.Descendants(ns + "Grid").FirstOrDefault(e => (string?)e.Attribute(x + "Name") == "SystemBar");
        var widths = bar?.Element(ns + "Grid.ColumnDefinitions")?.Elements(ns + "ColumnDefinition").Select(c => (string?)c.Attribute("Width")).ToArray();
        Check(widths is ["Auto", "*", "Auto"], "Header: Titelleiste muss Auto | * | Auto sein (Navigation in der Restspalte).", failures);
        var nav = xaml.Descendants(ns + "NavigationView").FirstOrDefault();
        Check(nav is not null && (string?)nav.Attribute("Grid.Column") == "1" && (string?)nav.Attribute("PaneDisplayMode") == "Top", "Header: NavigationView nicht als Top-Navigation in der Restspalte.", failures);
        Check(nav?.Element(ns + "NavigationView.MenuItems")?.Elements(ns + "NavigationViewItem").Count() == 8, "Header: erwartet 7 Primär-Tabs plus System.", failures);
        Check(nav?.Attribute("MinWidth") is null && nav?.Attribute("Width") is null, "Header: feste Breite an der NavigationView verhindert Anpassung.", failures);
    }

    private static void VerifyBrainActivity(ICollection<string> failures)
    {
        // Jede vom Mapper referenzierte Knoten-ID muss im Graph existieren, und jede Kante (From->To) mit Ziel
        // muss eine tatsächlich definierte neuronale Verbindung sein (kein Blitz außerhalb des Synapsennetzes).
        var nodeIds = BrainNeuralGraph.Nodes.Select(n => n.Id).ToHashSet();
        foreach (BrainActivityType type in Enum.GetValues<BrainActivityType>())
        {
            foreach (var step in BrainActivityMapper.Steps(type))
            {
                Check(nodeIds.Contains(step.FromNodeId), $"{type}: unbekannter Startknoten {step.FromNodeId}.", failures);
                if (step.ToNodeId is { } to)
                {
                    Check(nodeIds.Contains(to), $"{type}: unbekannter Zielknoten {to}.", failures);
                    Check(BrainNeuralGraph.HasEdge(step.FromNodeId, to), $"{type}: Kante {step.FromNodeId}->{to} existiert nicht im Graph.", failures);
                }
            }
        }

        // Determinismus: zweimaliger Aufruf desselben Typs liefert exakt dieselbe Schrittfolge.
        Check(BrainActivityMapper.Steps(BrainActivityType.ModelInference).SequenceEqual(BrainActivityMapper.Steps(BrainActivityType.ModelInference)),
            "Event-Mapping muss deterministisch sein (gleicher Typ -> gleiche Schrittfolge).", failures);

        // Jeder reale Ereignistyp hat mindestens einen Schritt (keine stumme Kategorie, siehe Abschnitt 9 des Auftrags).
        foreach (BrainActivityType type in Enum.GetValues<BrainActivityType>())
        {
            Check(BrainActivityMapper.Steps(type).Count > 0, $"{type} sollte mindestens einen Impulsschritt ergeben.", failures);
        }

        // Ein unbekannter/nicht zugeordneter Typ (außerhalb des Enums) erzeugt bewusst keine erfundene Aktivität.
        Check(BrainActivityMapper.Steps((BrainActivityType)999).Count == 0,
            "Unbekannter Ereignistyp darf keine Aktivität erzeugen.", failures);

        // Obergrenze gleichzeitig sichtbarer Impulse: Burst darf sie nie überschreiten, auch nicht knapp am Limit.
        Check(BrainActivityScheduler.Admit(currentlyActive: 0, requested: 5, max: 8) == 5, "Admit muss unterhalb der Grenze alles zulassen.", failures);
        Check(BrainActivityScheduler.Admit(currentlyActive: 6, requested: 5, max: 8) == 2, "Admit muss auf die Restkapazität begrenzen.", failures);
        Check(BrainActivityScheduler.Admit(currentlyActive: 8, requested: 3, max: 8) == 0, "Admit darf am Limit nichts mehr zulassen.", failures);
        Check(BrainActivityScheduler.Admit(currentlyActive: 20, requested: 3, max: 8) == 0, "Admit darf bei Überschreitung nie negativ zulassen.", failures);
        var burstAdmitted = BrainActivityScheduler.Admit(0, BrainActivityMapper.Steps(BrainActivityType.ResponseGeneration).Count);
        Check(burstAdmitted <= BrainActivityScheduler.MaxConcurrentPulses, "Ein einzelner Event-Burst darf die Obergrenze nicht überschreiten.", failures);

        // Alle Knoten und jeder Stützpunkt jeder Bahn liegen innerhalb der realen Gehirnkontur des Assets
        // (keine Aktivität außerhalb der Hirnform, kein Pfad über Hirnstamm oder Bodenreflex).
        foreach (var node in BrainNeuralGraph.Nodes)
        {
            Check(BrainSilhouette.Contains(node.X, node.Y), $"Knoten {node.Id} liegt außerhalb der Gehirnkontur.", failures);
            Check(node.Depth is >= 0 and <= 1, $"Knoten {node.Id} hat eine Tiefe außerhalb 0..1.", failures);
        }

        var ids = BrainNeuralGraph.Nodes.Select(n => n.Id).ToHashSet();
        foreach (var edge in BrainNeuralGraph.Edges)
        {
            Check(ids.Contains(edge.FromId) && ids.Contains(edge.ToId), $"Bahn {edge.FromId}->{edge.ToId} referenziert unbekannte Knoten.", failures);
            Check(edge.Path.Count >= 4, $"Bahn {edge.FromId}->{edge.ToId} hat zu wenige Stützpunkte.", failures);
            foreach (var (x, y) in edge.Path)
            {
                Check(BrainSilhouette.Contains(x, y), $"Bahn {edge.FromId}->{edge.ToId} verlässt die Gehirnkontur.", failures);
            }

            // Eine Bahn beginnt und endet auf ihren Somata (Signal läuft von Synapse zu Synapse).
            var from = BrainNeuralGraph.Node(edge.FromId);
            var to = BrainNeuralGraph.Node(edge.ToId);
            Check(Math.Abs(edge.Path[0].X - from.X) < 0.004 && Math.Abs(edge.Path[0].Y - from.Y) < 0.006
                  && Math.Abs(edge.Path[^1].X - to.X) < 0.004 && Math.Abs(edge.Path[^1].Y - to.Y) < 0.006,
                $"Bahn {edge.FromId}->{edge.ToId} liegt nicht an ihren Knoten an.", failures);
        }

        // Jeder Funktionsknoten hat Strukturbahnen, über die sich ein Signal verzweigen kann.
        foreach (var node in BrainNeuralGraph.Nodes.Where(n => !n.IsRelay))
        {
            Check(BrainNeuralGraph.Branches(node.Id).Count > 0, $"Funktionsknoten {node.Id} hat keine Verzweigungsbahn.", failures);
        }

        // Umkehrung einer Strukturbahn startet am angefragten Knoten.
        var branch = BrainNeuralGraph.Branches("core1")[0];
        var reversed = BrainNeuralGraph.PathFrom(branch, BrainNeuralGraph.OtherEnd(branch, "core1"));
        Check(reversed[^1] == BrainNeuralGraph.PathFrom(branch, "core1")[0], "PathFrom muss die Laufrichtung korrekt umkehren.", failures);

        // Mapper steuert nie Strukturknoten an; sie tragen nur das Netz.
        foreach (BrainActivityType type in Enum.GetValues<BrainActivityType>())
        {
            foreach (var step in BrainActivityMapper.Steps(type))
            {
                Check(!BrainNeuralGraph.Node(step.FromNodeId).IsRelay && (step.ToNodeId is null || !BrainNeuralGraph.Node(step.ToNodeId).IsRelay),
                    $"{type}: Strukturknoten dürfen nicht Ziel eines Ereignisses sein.", failures);
            }
        }

        // Aktivierungskanäle: jede Kategorie mit Kanal trifft genau einen Legendeneintrag, Eingang/Fehler erfinden keinen.
        Check(Enum.GetValues<BrainActivityChannel>().Length == 6, "Es muss genau sechs Aktivierungskanäle geben (Legende).", failures);
        Check(BrainActivityMapper.Channel(BrainActivityType.ToolResult) == BrainActivityChannel.ToolSelection, "ToolResult gehört zur Werkzeugauswahl.", failures);
        Check(BrainActivityMapper.Channel(BrainActivityType.InputReceived) is null && BrainActivityMapper.Channel(BrainActivityType.ErrorEvent) is null,
            "Eingang und Fehler dürfen keinen Aktivierungskanal erfinden.", failures);

        // Testevents sind explizit als Test markiert und getrennt vom Produktionswert (Default false).
        Check(new BrainActivityEvent(BrainActivityType.InputReceived).IsTest == false, "BrainActivityEvent muss standardmäßig IsTest=false sein.", failures);
        Check(new BrainActivityEvent(BrainActivityType.InputReceived, IsTest: true).IsTest, "Test-Events müssen explizit markierbar sein.", failures);
    }

    // ---- Hub gegen echten Loopback-Server auf dem Desktop-API-Port ------------------------------------------------

    private static async Task VerifyHubAsync(ICollection<string> failures, ICollection<string> skipped)
    {
        using var hub = new BackendHub();

        // 1) Nichts lauscht: OFFLINE, kein Datensatz, übrige Endpunkte werden nicht einzeln abgefragt.
        if (!PortFree())
        {
            skipped.Add($"Hub-Tests: Port 127.0.0.1:{JarvisApiClient.LoopbackPort} ist belegt (echte Desktop-API läuft?). Es wird nichts gegen sie getestet.");
            return;
        }

        var watch = System.Diagnostics.Stopwatch.StartNew();
        await hub.RefreshAsync(BackendDomain.Memory, CancellationToken.None);
        watch.Stop();
        var offline = hub.Get(WebEndpoint.MemorySummary);
        Console.WriteLine($"INFO: Abfrage ohne Listener dauerte {watch.ElapsedMilliseconds} ms, Zustand {offline.State}: {offline.Message}");
        Check(offline.State == RuntimeState.Offline && offline.Data is null,
            $"Ohne Listener muss OFFLINE gemeldet werden (war {offline.State}).", failures);
        Check(hub.Get(WebEndpoint.Stats).State == RuntimeState.Offline && hub.Get(WebEndpoint.Desktop).State == RuntimeState.Offline,
            "Nach OFFLINE der Probe müssen alle Endpunkte der Seite OFFLINE melden.", failures);
        Check(hub.Get(WebEndpoint.Webcam) == WebReading.NotQueried,
            "Nicht abgefragte Endpunkte bleiben 'nicht abgefragt'.", failures);

        using var server = new MiniServer();
        server.Handler = Synthetic;

        // 2) Erreichbar: echte Daten mit Zustand READY.
        await hub.RefreshAsync(BackendDomain.Memory, CancellationToken.None);
        Check(hub.Get(WebEndpoint.MemorySummary) is { State: RuntimeState.Ready } summary && summary.As<MemoryInfo>()?.FactsTotal == 2,
            "MemorySummary muss READY mit Daten sein.", failures);
        Check(hub.Get(WebEndpoint.Stats).As<StatsInfo>()?.Model == "test-model", "Stats-Modellname wurde nicht übernommen.", failures);
        Check(hub.Get(WebEndpoint.Desktop).As<DesktopInfo>()?.Tools.Count == 2, "Desktop-Inventar wurde nicht übernommen.", failures);

        await hub.RefreshAsync(BackendDomain.Chat, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Sessions).As<SessionsInfo>()?.Total == 4, "Sitzungsanzahl wurde nicht übernommen.", failures);
        await hub.RefreshAsync(BackendDomain.Observability, CancellationToken.None);
        Check(hub.Get(WebEndpoint.EventsRecent).As<EventsInfo>()?.Items.Count == 2
                && hub.Get(WebEndpoint.EventsAggregate).As<EventsAggregateInfo>()?.Total == 2,
            "Ereignisse und Aggregat müssen übernommen werden.", failures);

        // 3) 503 = nicht bereit: UNAVAILABLE, kein ERROR; parallel weiterhin andere Endpunkte READY.
        await hub.RefreshAsync(BackendDomain.Automations, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Automations).IsReady && hub.Get(WebEndpoint.Automations).As<AutomationsInfo>()?.Schedulers.Count == 1,
            "Automations muss READY sein.", failures);
        Check(hub.Get(WebEndpoint.Agents).State == RuntimeState.Unavailable && hub.Get(WebEndpoint.Agents).Data is null,
            "HTTP 503 muss UNAVAILABLE ohne Daten sein.", failures);

        // 4) 404, 401, 500, kaputtes JSON, zu große Antwort.
        server.Handler = path => path == "/api/webcam/status" ? (404, "{}", 0) : (200, "{}", 0);
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Webcam).State == RuntimeState.Unavailable, "HTTP 404 muss UNAVAILABLE sein.", failures);

        server.Handler = _ => (401, "no", 0);
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Webcam).State == RuntimeState.Unavailable && hub.Get(WebEndpoint.Webcam).Message.Contains("JARVIS_WEB_AUTH_TOKEN", StringComparison.Ordinal),
            "HTTP 401 muss UNAVAILABLE mit Token-Hinweis sein.", failures);

        server.Handler = _ => (500, "{}", 0);
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Webcam).State == RuntimeState.Error, "HTTP 500 muss ERROR sein.", failures);

        server.Handler = _ => (200, "das ist kein json", 0);
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Webcam).State == RuntimeState.Unavailable, "Kaputtes JSON darf nicht ERROR sein.", failures);

        server.Handler = _ => (200, "[1,2,3]", 0);
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Webcam).State == RuntimeState.Unavailable, "Gültiges JSON mit falscher Form darf nicht ERROR sein.", failures);

        server.Handler = _ => (200, new string('x', 3 * 1024 * 1024), 0);
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        Check(hub.Get(WebEndpoint.Webcam).State == RuntimeState.Unavailable, "Zu große Antwort muss UNAVAILABLE sein.", failures);

        // 5) Zeitüberschreitung: UNAVAILABLE, niemals automatisch OFFLINE.
        server.Handler = _ => (200, "{}", 8000);
        var timeoutWatch = System.Diagnostics.Stopwatch.StartNew();
        await hub.RefreshAsync(BackendDomain.Vision, CancellationToken.None);
        timeoutWatch.Stop();
        var timedOut = hub.Get(WebEndpoint.Webcam);
        Check(timedOut.State == RuntimeState.Unavailable && timedOut.Message.Contains("Zeitüberschreitung", StringComparison.Ordinal),
            $"Zeitüberschreitung muss UNAVAILABLE sein (war {timedOut.State}).", failures);
        Check(timeoutWatch.ElapsedMilliseconds < 7500, "Die Abfrage muss vor dem Serverantwort-Delay abbrechen.", failures);

        // 6) Abbruch durch den Aufrufer wird durchgereicht, nicht als Fehlerzustand gespeichert.
        server.Handler = _ => (200, "{}", 0);
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();
        var propagated = false;
        try
        {
            await hub.RefreshAsync(BackendDomain.Vision, cancelled.Token);
        }
        catch (OperationCanceledException)
        {
            propagated = true;
        }

        Check(propagated, "Abbruch durch den Aufrufer muss als OperationCanceledException ankommen.", failures);

        // 7) IJarvisApiAdapter spiegelt die Stats-Probe.
        server.Handler = _ => (200, """{"llm":null}""", 0);
        var status = await ((IJarvisApiAdapter)hub).GetStatusAsync(CancellationToken.None);
        Check(status.State == RuntimeState.Ready, "IJarvisApiAdapter muss bei erreichbarer API READY melden.", failures);

        // 8) Desktop-Allowlist-Drift: die App darf nie etwas anderes anfragen als das, was
        //    jarvis_web.py --desktop-mode freigibt (Main/jarvis_web.py::_DESKTOP_READ_ALLOWLIST).
        var allowlist = new Dictionary<string, string[]>
        {
            ["/api/stats"] = [],
            ["/api/desktop/snapshot"] = [],
            ["/api/agents/status"] = [],
            ["/api/automations/status"] = [],
            ["/api/memory/summary"] = [],
            ["/api/events/recent"] = ["hours", "limit"],
            ["/api/events/aggregate"] = ["hours"],
            ["/api/sessions"] = ["limit"],
            ["/api/webcam/status"] = [],
        };
        var seen = new HashSet<string>();
        foreach (var target in server.Requests)
        {
            var parts = target.Split('?', 2);
            seen.Add(parts[0]);
            var keys = parts.Length > 1
                ? parts[1].Split('&', StringSplitOptions.RemoveEmptyEntries).Select(pair => pair.Split('=', 2)[0])
                : [];
            Check(allowlist.TryGetValue(parts[0], out var allowedKeys) && keys.All(allowedKeys.Contains),
                $"Die App hat '{target}' angefragt, das der Desktop-Modus nicht freigibt.", failures);
        }

        Check(seen.SetEquals(allowlist.Keys),
            "Die App muss genau die Allowlist-Endpunkte nutzen (keiner fehlt, keiner ist zu viel): " + string.Join(", ", seen.OrderBy(x => x)),
            failures);
    }

    private static bool PortFree()
    {
        try
        {
            var probe = new TcpListener(IPAddress.Loopback, JarvisApiClient.LoopbackPort);
            probe.Start();
            probe.Stop();
            return true;
        }
        catch (SocketException)
        {
            return false;
        }
    }

    private sealed class MiniServer : IDisposable
    {
        private readonly TcpListener _listener = new(IPAddress.Loopback, JarvisApiClient.LoopbackPort);
        private readonly CancellationTokenSource _stop = new();

        public MiniServer()
        {
            _listener.Start();
            _ = Task.Run(AcceptLoopAsync);
        }

        public Func<string, (int Status, string Body, int DelayMs)> Handler { get; set; } = _ => (200, "{}", 0);

        /// <summary>Every request target (path and query) the app sent, in arrival order.</summary>
        public ConcurrentQueue<string> Requests { get; } = new();

        private async Task AcceptLoopAsync()
        {
            while (!_stop.IsCancellationRequested)
            {
                TcpClient client;
                try
                {
                    client = await _listener.AcceptTcpClientAsync(_stop.Token);
                }
                catch (Exception)
                {
                    return;
                }

                _ = Task.Run(() => ServeAsync(client));
            }
        }

        private async Task ServeAsync(TcpClient client)
        {
            using (client)
            {
                try
                {
                    var stream = client.GetStream();
                    var buffer = new byte[8192];
                    var received = new StringBuilder();
                    while (!received.ToString().Contains("\r\n\r\n", StringComparison.Ordinal))
                    {
                        var read = await stream.ReadAsync(buffer, _stop.Token);
                        if (read == 0) return;
                        received.Append(Encoding.ASCII.GetString(buffer, 0, read));
                    }

                    var requestLine = received.ToString().Split("\r\n", 2)[0].Split(' ');
                    Requests.Enqueue(requestLine.Length > 1 ? requestLine[1] : "/");
                    var path = requestLine.Length > 1 ? requestLine[1].Split('?', 2)[0] : "/";
                    var (status, body, delay) = Handler(path);
                    if (delay > 0) await Task.Delay(delay, _stop.Token);
                    var payload = Encoding.UTF8.GetBytes(body);
                    var header = $"HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {payload.Length}\r\nConnection: close\r\n\r\n";
                    await stream.WriteAsync(Encoding.ASCII.GetBytes(header), _stop.Token);
                    await stream.WriteAsync(payload, _stop.Token);
                }
                catch (Exception)
                {
                    // Testserver: abgebrochene Verbindungen sind erwartet.
                }
            }
        }

        public void Dispose()
        {
            _stop.Cancel();
            _listener.Stop();
            _stop.Dispose();
        }
    }
}
