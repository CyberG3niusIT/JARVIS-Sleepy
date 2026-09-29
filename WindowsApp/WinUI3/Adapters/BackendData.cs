using Jarvis.ControlHub.WinUI.Domain;

namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>Bereiche der Oberfläche, die eigene Backend-Quellen lesen.</summary>
public enum BackendDomain
{
    Home,
    Chat,
    Memory,
    Models,
    Voice,
    Tools,
    Automations,
    Vision,
    Observability,
    Settings,
}

/// <summary>Lesende Endpunkte der lokalen JARVIS-Web-API.</summary>
public enum WebEndpoint
{
    Stats,
    Desktop,
    Agents,
    Automations,
    MemorySummary,
    EventsRecent,
    EventsAggregate,
    Sessions,
    Webcam,
}

/// <summary>
/// Ergebnis einer einzelnen Backend-Abfrage. <see cref="State"/> trennt Ready, Offline,
/// Unavailable und Error; <see cref="Data"/> ist nur bei Ready gesetzt.
/// </summary>
public sealed record WebReading(RuntimeState State, string Message, object? Data, DateTimeOffset ObservedAt)
{
    public bool IsReady => State == RuntimeState.Ready && Data is not null;

    public T? As<T>() where T : class => Data as T;

    public static WebReading NotQueried { get; } =
        new(RuntimeState.Unavailable, "Noch nicht abgefragt.", null, DateTimeOffset.MinValue);
}

public sealed record StatsInfo(
    string? Model,
    long? MemoryVectors,
    long? SkillsLoaded,
    double? ContextUsagePercent,
    long? ContextTokens,
    long? RemindersActive);

public sealed record ToolInfo(string Id, string? Skill, bool Registered);

public sealed record SkillInfo(string Id, string Name, string Category, bool Enabled, long Intents, long Tools);

public sealed record DesktopInfo(
    string? LlmProvider,
    string? LlmEndpoint,
    long? LlmContextSize,
    string? SttBackend,
    string? SttModel,
    string? SttLanguage,
    string? TtsEngine,
    string? OutputBackend,
    string? WakeKeyword,
    string? Language,
    string? InputDevice,
    IReadOnlyList<ToolInfo> Tools,
    IReadOnlyList<SkillInfo> Skills,
    IReadOnlyDictionary<string, bool> Capabilities,
    bool? MemoryEnabled,
    bool? MemoryProactive,
    bool? ContextWindowEnabled);

public sealed record SchedulerInfo(
    string Id,
    string State,
    long? IntervalSeconds,
    string? LastRunAt,
    string Schedule,
    string? Owner = null);

public sealed record AutomationsInfo(IReadOnlyList<SchedulerInfo> Schedulers);

public sealed record PlannerInfo(
    bool Available,
    string State,
    long Steps,
    long Completed,
    long Running,
    long Failed,
    long Pending,
    // Client-seitige Bewertung, kein Backend-Zustand: die Antwort verletzt die Invarianten von agents_status_handler.
    bool Implausible = false);

public sealed record MemoryInfo(
    long? FactsTotal,
    long? Interactions7d,
    long? FaissVectors,
    long? FaissBytes,
    double? ContextUsagePercent,
    IReadOnlyList<KeyValuePair<string, long>> FactsByCategory,
    string? PartialError);

public sealed record EventItem(DateTimeOffset Time, string Category, string Event, string Severity);

public sealed record EventsInfo(IReadOnlyList<EventItem> Items);

public sealed record EventsAggregateInfo(long Total, IReadOnlyDictionary<string, long> Severities);

public sealed record SessionsInfo(long Total);

public sealed record WebcamInfo(bool Available, bool Running);
