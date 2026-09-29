using Jarvis.ControlHub.WinUI.Domain;

namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>
/// Zuordnung realer Backend-Ereignisse (GET /api/events/recent, Sleepy-Backend jarvis_web.py) zu Brain-Aktivität.
/// Verwendet ausschließlich die privacy-reduzierten Felder category, event und severity. Jede Zeile ist an der
/// Emit-Stelle im Backend belegt; alles andere ergibt bewusst keine Aktivität.
/// </summary>
public static class BrainEventMapping
{
    // core/watchdog.py _emit_recovery: category error_recovery, severity warn, Eingriff bei hängender Komponente.
    private static readonly HashSet<string> WatchdogEvents = new(StringComparer.Ordinal)
    {
        "watchdog_command_hung",
        "watchdog_listener_stuck",
        "watchdog_speaking_stuck",
        "watchdog_stt_backlog",
        "watchdog_streaming_orphan",
    };

    public static BrainActivityType? Map(string category, string eventName, string severity) => (eventName, category, severity) switch
    {
        // core/stt.py, core/stt_qwen3.py: info = Transkript mit Text, debug = leeres Ergebnis (kein Puls), error = STT fehlgeschlagen.
        ("stt_transcription", "inference", "info") => BrainActivityType.InputReceived,
        ("stt_transcription", "inference", "error") => BrainActivityType.ErrorEvent,
        // core/conversation_router.py: nach abgeschlossenem _route_inner, immer severity info.
        ("route_completed", "decision", "info") => BrainActivityType.ModelRouting,
        // core/llm_router.py _record_call, core/claude_consultation.py: je tatsächlich ausgeführtem Modellaufruf.
        ("llm_call", "inference", "info") => BrainActivityType.ModelInference,
        ("llm_call", "inference", "error") => BrainActivityType.ErrorEvent,
        // core/tool_registry.py, core/pipeline.py, jarvis_web.py: erst nach Rückkehr des Tools. Kein ToolCall-Beleg.
        ("tool_completed", "tool_execution", "info") => BrainActivityType.ToolResult,
        ("tool_completed", "tool_execution", "error") => BrainActivityType.ErrorEvent,
        (var name, "error_recovery", "warn") when WatchdogEvents.Contains(name) => BrainActivityType.DegradedEvent,
        _ => null,
    };

    public static BrainActivityType? Map(EventItem item) => Map(item.Category, item.Event, item.Severity);
}

/// <summary>
/// Fortschreibung über aufeinanderfolgende Snapshots von /api/events/recent (Backend: newest-first, LIMIT).
/// Der erste lesbare Snapshot ist nur Baseline und wird nie abgespielt. Danach zählen nur Einträge, die noch nicht
/// gesehen wurden und nicht älter als der bisher neueste Zeitstempel abzüglich einer kleinen Nachzüglertoleranz sind.
/// Dedupliziert wird über die beobachtbaren Felder (Zeit, Kategorie, Ereignis, Schwere); das Backend liefert keine ID.
/// </summary>
public sealed class BrainEventCursor
{
    // Emit-Zeitpunkt und Commit in SQLite können sich über Threads hinweg leicht überholen.
    public static readonly TimeSpan LateArrivalTolerance = TimeSpan.FromSeconds(5);

    private readonly HashSet<EventItem> _seen = [];
    private DateTimeOffset? _watermark;

    public bool HasBaseline { get; private set; }

    public void Reset()
    {
        _seen.Clear();
        _watermark = null;
        HasBaseline = false;
    }

    /// <summary>Liefert die neuen Einträge dieses Snapshots in chronologischer Reihenfolge (ältester zuerst).</summary>
    public IReadOnlyList<EventItem> Advance(IReadOnlyList<EventItem> snapshot)
    {
        if (!HasBaseline)
        {
            foreach (var item in snapshot) _seen.Add(item);
            _watermark = snapshot.Count > 0 ? snapshot.Max(item => item.Time) : null;
            HasBaseline = true;
            return [];
        }

        var threshold = _watermark is { } mark ? mark - LateArrivalTolerance : DateTimeOffset.MinValue;
        // Gleiche Zeitstempel: das Backend liefert newest-first, also ist der spätere Index der ältere Eintrag.
        var fresh = snapshot
            .Select((item, index) => (Item: item, Index: index))
            .Where(entry => entry.Item.Time >= threshold && !_seen.Contains(entry.Item))
            .OrderBy(entry => entry.Item.Time)
            .ThenByDescending(entry => entry.Index)
            .Select(entry => entry.Item)
            .ToList();

        foreach (var item in fresh) _seen.Add(item);
        if (fresh.Count > 0)
        {
            var newest = fresh[^1].Time;
            if (_watermark is not { } current || newest > current) _watermark = newest;
        }

        if (_watermark is { } prune) _seen.RemoveWhere(item => item.Time < prune - LateArrivalTolerance);
        return fresh;
    }
}

/// <summary>
/// Lesende Live-Brücke von /api/events/recent zur Brain-Stage. Eine einzige Schleife, keine überlappenden Abfragen,
/// endet mit dem übergebenen CancellationToken. Transportfehler, OFFLINE und UNAVAILABLE erzeugen nie Aktivität;
/// nach jeder Unterbrechung ist der nächste lesbare Snapshot wieder nur Baseline (kein Nachholen verpasster Last).
/// </summary>
public sealed class BrainEventBridge
{
    public static readonly TimeSpan LiveInterval = TimeSpan.FromSeconds(2.5);
    public static readonly TimeSpan RecoveryInterval = TimeSpan.FromSeconds(10);
    public static readonly TimeSpan Stagger = TimeSpan.FromMilliseconds(220);

    // Pro Abfrage höchstens so viele Ereignisse wie gleichzeitig sichtbare Impulse; ältere Anteile eines Bursts entfallen.
    public const int MaxEventsPerBatch = BrainActivityScheduler.MaxConcurrentPulses;

    private readonly Func<CancellationToken, Task<WebReading>> _read;
    private readonly Func<TimeSpan, CancellationToken, Task> _delay;
    private readonly BrainEventCursor _cursor = new();

    public BrainEventBridge(Func<CancellationToken, Task<WebReading>> read, Func<TimeSpan, CancellationToken, Task>? delay = null)
    {
        _read = read;
        _delay = delay ?? Task.Delay;
    }

    /// <summary>Zustand der Eventquelle nach der letzten Abfrage; null, solange noch keine Abfrage fertig ist.</summary>
    public RuntimeState? SourceState { get; private set; }

    public event Action<RuntimeState>? SourceChanged;

    /// <summary>Alle neuen Einträge einer Abfrage (auch nicht zugeordnete), chronologisch.</summary>
    public event Action<IReadOnlyList<EventItem>>? EventsArrived;

    public event Action<BrainActivityType>? Activity;

    public async Task RunAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            try
            {
                WebReading reading;
                try
                {
                    reading = await _read(token);
                }
                catch (Exception exception) when (exception is not OperationCanceledException || !token.IsCancellationRequested)
                {
                    // Unerwarteter Lesefehler: Quelle gilt als nicht lesbar, keine Aktivität, nächster Versuch später.
                    reading = new WebReading(RuntimeState.Unavailable, "Eventquelle nicht lesbar.", null, DateTimeOffset.Now);
                }

                await ProcessAsync(reading, token);
                await _delay(reading.IsReady ? LiveInterval : RecoveryInterval, token);
            }
            catch (OperationCanceledException) when (token.IsCancellationRequested)
            {
                return;
            }
        }
    }

    public async Task ProcessAsync(WebReading reading, CancellationToken token)
    {
        var state = reading.IsReady ? RuntimeState.Ready : reading.State == RuntimeState.Ready ? RuntimeState.Unavailable : reading.State;
        if (SourceState != state)
        {
            SourceState = state;
            SourceChanged?.Invoke(state);
        }

        if (!reading.IsReady || reading.As<EventsInfo>() is not { } info)
        {
            _cursor.Reset();
            return;
        }

        var fresh = _cursor.Advance(info.Items);
        if (fresh.Count == 0) return;
        EventsArrived?.Invoke(fresh);

        var activities = fresh
            .Select(BrainEventMapping.Map)
            .Where(type => type.HasValue)
            .Select(type => type!.Value)
            .TakeLast(MaxEventsPerBatch)
            .ToList();
        for (var i = 0; i < activities.Count; i++)
        {
            token.ThrowIfCancellationRequested();
            Activity?.Invoke(activities[i]);
            if (i < activities.Count - 1) await _delay(Stagger, token);
        }
    }
}

/// <summary>
/// Texte des Status-Overlays der Brain-Stage. AKTIV nur, solange der Renderer echte (oder als TEST markierte)
/// Ereignisse zeigt; ohne Ereignisse steht der ehrliche Zustand der Eventquelle.
/// </summary>
public static class BrainStageStatus
{
    public static (string Title, string Note) Describe(bool active, bool isTest, RuntimeState? source)
    {
        if (active && isTest) return ("AKTIV. TESTSEQUENZ.", "Markierte Verifikationssequenz (TEST-ONLY). Keine Runtime-Ereignisse.");
        if (active) return ("AKTIV.", "Beobachtete Systemereignisse. Keine Gedanken oder Chain-of-Thought.");
        return source switch
        {
            RuntimeState.Ready => ("IDLE. READY.", "Eventquelle verbunden. Derzeit keine neuen Systemereignisse. Keine Gedanken oder Inhalte."),
            RuntimeState.Offline => ("IDLE. OFFLINE.", "Eventquelle nicht erreichbar. Keine Aktivität wird simuliert."),
            { } other => ($"IDLE. {RuntimeStateText.ToDisplayText(other)}.", "Eventquelle nicht lesbar. Keine Aktivität wird simuliert."),
            null => ("IDLE. UNAVAILABLE.", "Keine Live-Eventquelle. Keine Gedanken, Memories oder Aktivität werden simuliert."),
        };
    }
}
