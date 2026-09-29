using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Jarvis.ControlHub;
using Jarvis.ControlHub.WinUI.Adapters;
using Jarvis.ControlHub.WinUI.Domain;

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
            // Manueller Modus für den UI-Lauf: synthetische API auf 127.0.0.1:8091, bis der Prozess beendet wird.
            using var serving = new MiniServer { Handler = Synthetic };
            Console.WriteLine("SERVING (synthetisch) auf 127.0.0.1:8091");
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

        var planner = BackendParsers.ParseAgents(Json("""
            {"available":true,"state":"running","stepCount":5,"completedSteps":2,"runningSteps":1,"failedSteps":0,"pendingSteps":2}
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

    // ---- Hub gegen echten Loopback-Server auf 127.0.0.1:8091 ------------------------------------------------

    private static async Task VerifyHubAsync(ICollection<string> failures, ICollection<string> skipped)
    {
        using var hub = new BackendHub();

        // 1) Nichts lauscht: OFFLINE, kein Datensatz, übrige Endpunkte werden nicht einzeln abgefragt.
        if (!PortFree())
        {
            skipped.Add("Hub-Tests: Port 127.0.0.1:8091 ist belegt (echte Web-API läuft?). Es wird nichts gegen sie getestet.");
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
            var probe = new TcpListener(IPAddress.Loopback, 8091);
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
        private readonly TcpListener _listener = new(IPAddress.Loopback, 8091);
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
