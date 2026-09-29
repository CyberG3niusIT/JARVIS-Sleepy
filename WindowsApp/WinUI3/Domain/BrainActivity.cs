namespace Jarvis.ControlHub.WinUI.Domain;

/// <summary>
/// Beobachtbare Systemereignis-Kategorien für die Brain-Stage-Visualisierung (Memory &amp; Thinking).
/// Dies sind reine UI-/Observability-Kategorien für reale Verarbeitungsschritte. Sie behaupten keine
/// Chain-of-Thought und keine "Gedanken" von J.A.R.V.I.S, nur beobachtbare Systemaktivität.
/// </summary>
public enum BrainActivityType
{
    InputReceived,
    MemoryRetrieval,
    ContextBuild,
    ModelRouting,
    ModelInference,
    ToolCall,
    ToolResult,
    ResponseGeneration,
    MemoryWriteConfirmed,
    ErrorEvent,
    DegradedEvent,
}

/// <summary>
/// Ein einzelnes beobachtetes Ereignis für die Brain-Stage. <see cref="IsTest"/> markiert Testaktivität aus dem
/// TEST-ONLY-Verifikationspfad; sie darf nie automatisch im normalen Produktionsstart auftreten.
/// </summary>
public readonly record struct BrainActivityEvent(BrainActivityType Type, bool IsTest = false);
