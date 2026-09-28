using System.Globalization;
using System.Text.Json;

namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>
/// Defensive Parser für die JSON-Antworten von jarvis_web.py. Fehlende oder falsch typisierte Felder
/// werden zu <c>null</c>; nur eine Antwort, die kein JSON-Objekt ist, wirft <see cref="FormatException"/>.
/// </summary>
public static class BackendParsers
{
    private static readonly string[] CapabilityKeys =
        ["reminders", "calendar", "news", "weather", "memory", "contextWindow", "metrics"];

    public static StatsInfo ParseStats(JsonElement root)
    {
        RequireObject(root);
        var llm = Obj(root, "llm");
        var memory = Obj(root, "memory");
        var context = Obj(root, "context_window");
        var reminders = Obj(root, "reminders");
        return new StatsInfo(
            llm is { } l ? Str(l, "model") : null,
            memory is { } m ? Long(m, "vectors") : null,
            Long(root, "skills_loaded"),
            context is { } c ? Dbl(c, "usage_pct") : null,
            context is { } c2 ? Long(c2, "tokens") : null,
            reminders is { } r ? Long(r, "active") : null);
    }

    public static DesktopInfo ParseDesktop(JsonElement root)
    {
        RequireObject(root);
        var llm = Obj(root, "llm");
        var voice = Obj(root, "voice");
        var memoryConfig = Obj(root, "memoryConfig");
        var capabilities = new Dictionary<string, bool>();
        if (Obj(root, "capabilities") is { } caps)
        {
            foreach (var key in CapabilityKeys)
            {
                if (Bool(caps, key) is { } value) capabilities[key] = value;
            }
        }

        var tools = new List<ToolInfo>();
        foreach (var item in Array(root, "tools"))
        {
            if (Str(item, "id") is not { Length: > 0 } id) continue;
            tools.Add(new ToolInfo(id, Str(item, "skill"), Bool(item, "registered") ?? false));
        }

        var skills = new List<SkillInfo>();
        foreach (var item in Array(root, "skills"))
        {
            if (Str(item, "id") is not { Length: > 0 } id) continue;
            skills.Add(new SkillInfo(
                id,
                Str(item, "name") ?? id,
                Str(item, "category") ?? "unknown",
                Bool(item, "enabled") ?? false,
                Long(item, "intents") ?? 0,
                Long(item, "tools") ?? 0));
        }

        return new DesktopInfo(
            llm is { } a ? Str(a, "provider") : null,
            llm is { } b ? Str(b, "endpoint") : null,
            llm is { } c ? Long(c, "contextSize") : null,
            voice is { } d ? Str(d, "sttBackend") : null,
            voice is { } e ? Str(e, "sttModel") : null,
            voice is { } f ? Str(f, "sttLanguage") : null,
            voice is { } g ? Str(g, "tts") : null,
            voice is { } h ? Str(h, "outputBackend") : null,
            voice is { } i ? Str(i, "wakeKeyword") : null,
            voice is { } j ? Str(j, "language") : null,
            voice is { } k ? Str(k, "device") ?? Str(k, "input") : null,
            tools,
            skills,
            capabilities,
            memoryConfig is { } m1 ? Bool(m1, "enabled") : null,
            memoryConfig is { } m2 ? Bool(m2, "proactiveSurfacing") : null,
            memoryConfig is { } m3 ? Bool(m3, "contextWindowEnabled") : null);
    }

    public static AutomationsInfo ParseAutomations(JsonElement root)
    {
        RequireObject(root);
        var result = new List<SchedulerInfo>();
        foreach (var item in Array(root, "schedulers"))
        {
            var id = Str(item, "id");
            if (string.IsNullOrEmpty(id)) continue;
            var parts = new List<string>();
            var interval = Long(item, "configuredIntervalSeconds");
            if (interval is > 0) parts.Add($"alle {interval} s");
            if (Bool(item, "dailyRundownEnabled") == true && Str(item, "dailyRundownTime") is { } daily)
            {
                parts.Add($"täglich {daily}");
            }

            if (Bool(item, "weeklyRundownEnabled") == true && Str(item, "weeklyRundownDay") is { } day)
            {
                parts.Add($"wöchentlich {day}");
            }

            if (Bool(item, "autoConsultEnabled") == true) parts.Add("Auto-Consult");
            var lastRun = Bool(item, "lastRunAvailable") == true ? Str(item, "lastRunAt") : null;
            result.Add(new SchedulerInfo(
                id,
                StateWord(Str(item, "state")),
                interval,
                lastRun,
                parts.Count == 0 ? "keine Angabe" : string.Join(", ", parts),
                Str(item, "owner")));
        }

        return new AutomationsInfo(result);
    }

    public static PlannerInfo ParseAgents(JsonElement root)
    {
        RequireObject(root);
        return new PlannerInfo(
            Bool(root, "available") ?? false,
            StateWord(Str(root, "state")),
            Long(root, "stepCount") ?? 0,
            Long(root, "completedSteps") ?? 0,
            Long(root, "runningSteps") ?? 0,
            Long(root, "failedSteps") ?? 0,
            Long(root, "pendingSteps") ?? 0);
    }

    public static MemoryInfo ParseMemory(JsonElement root)
    {
        RequireObject(root);
        var facts = Obj(root, "facts");
        var interactions = Obj(root, "interactions");
        var faiss = Obj(root, "faiss");
        var context = Obj(root, "context");
        var byCategory = new SortedDictionary<string, long>(StringComparer.Ordinal);
        if (facts is { } f)
        {
            foreach (var row in Array(f, "by_category_user"))
            {
                if (Str(row, "category") is not { Length: > 0 } category) continue;
                byCategory[category] = byCategory.GetValueOrDefault(category) + (Long(row, "count") ?? 0);
            }
        }

        var failed = new List<string>();
        foreach (var (name, section) in new[] { ("facts", facts), ("interactions", interactions), ("faiss", faiss), ("context", context) })
        {
            // Nur den Abschnittsnamen übernehmen: der Fehlertext des Backends kann Pfade enthalten.
            if (section is { } s && s.TryGetProperty("error", out _)) failed.Add(name);
        }

        return new MemoryInfo(
            facts is { } f1 ? Long(f1, "total") : null,
            interactions is { } i1 ? Long(i1, "total_7d") : null,
            faiss is { } s1 ? Long(s1, "vectors") : null,
            faiss is { } s2 ? Long(s2, "size_bytes") : null,
            context is { } c1 ? Dbl(c1, "usage_pct") : null,
            byCategory.ToList(),
            failed.Count == 0 ? null : string.Join(", ", failed));
    }

    public static EventsInfo ParseEventsRecent(JsonElement root)
    {
        RequireObject(root);
        var items = new List<EventItem>();
        foreach (var item in Array(root, "events"))
        {
            var seconds = Dbl(item, "timestamp");
            if (seconds is not { } value || !double.IsFinite(value) || value < 0 || value > 4_000_000_000d) continue;
            items.Add(new EventItem(
                DateTimeOffset.FromUnixTimeMilliseconds((long)(value * 1000)),
                Str(item, "category") ?? "unknown",
                Str(item, "event") ?? "unknown",
                Str(item, "severity") ?? "unknown"));
        }

        return new EventsInfo(items);
    }

    public static EventsAggregateInfo ParseEventsAggregate(JsonElement root)
    {
        RequireObject(root);
        var severities = new SortedDictionary<string, long>(StringComparer.Ordinal);
        if (Obj(root, "severities") is { } map)
        {
            foreach (var property in map.EnumerateObject())
            {
                if (LongValue(property.Value) is { } count) severities[property.Name] = count;
            }
        }

        return new EventsAggregateInfo(Long(root, "total") ?? 0, severities);
    }

    public static SessionsInfo ParseSessions(JsonElement root)
    {
        RequireObject(root);
        return new SessionsInfo(Long(root, "total") ?? 0);
    }

    public static WebcamInfo ParseWebcam(JsonElement root)
    {
        RequireObject(root);
        return new WebcamInfo(Bool(root, "available") ?? false, Bool(root, "running") ?? false);
    }

    /// <summary>"backend_owned" -> "BACKEND OWNED": backend state words are shown as display words.</summary>
    public static string StateWord(string? state) =>
        string.IsNullOrWhiteSpace(state) ? "UNKNOWN" : state.Replace('_', ' ').ToUpperInvariant();

    public static string FormatPercent(double value) => value.ToString("0.#", CultureInfo.InvariantCulture) + " %";

    private static void RequireObject(JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.Object) throw new FormatException("Antwort ist kein JSON-Objekt.");
    }

    private static JsonElement? Obj(JsonElement parent, string name) =>
        parent.ValueKind == JsonValueKind.Object && parent.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.Object
            ? value
            : null;

    private static IEnumerable<JsonElement> Array(JsonElement parent, string name)
    {
        if (parent.ValueKind != JsonValueKind.Object || !parent.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Array)
        {
            yield break;
        }

        foreach (var item in value.EnumerateArray())
        {
            if (item.ValueKind == JsonValueKind.Object) yield return item;
        }
    }

    private static string? Str(JsonElement parent, string name) =>
        parent.ValueKind == JsonValueKind.Object && parent.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static bool? Bool(JsonElement parent, string name)
    {
        if (parent.ValueKind != JsonValueKind.Object || !parent.TryGetProperty(name, out var value)) return null;
        return value.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            _ => null,
        };
    }

    private static long? Long(JsonElement parent, string name) =>
        parent.ValueKind == JsonValueKind.Object && parent.TryGetProperty(name, out var value) ? LongValue(value) : null;

    private static long? LongValue(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Number) return null;
        if (value.TryGetInt64(out var integer)) return integer;
        return value.TryGetDouble(out var number) && double.IsFinite(number) && Math.Abs(number) < long.MaxValue
            ? (long)number
            : null;
    }

    private static double? Dbl(JsonElement parent, string name) =>
        parent.ValueKind == JsonValueKind.Object && parent.TryGetProperty(name, out var value)
            && value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out var number) && double.IsFinite(number)
            ? number
            : null;
}
