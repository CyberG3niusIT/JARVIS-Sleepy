namespace Jarvis.ControlHub.WinUI.Domain;

/// <summary>Visuelle Einordnung eines Pulses. Steuert nur Farbe/Akzent im Renderer, keine Aussage über Bedeutung.</summary>
public enum BrainPulseKind
{
    Normal,
    /// <summary>Optisch dominanter, sichtbar hervorgehobener Pfad (MODEL_ROUTING: "ein Pfad wird sichtbar dominant").</summary>
    Dominant,
    Error,
    Degraded,
}

/// <summary>
/// Ein einzelner Schritt eines Aktivitätsablaufs. Wenn <see cref="ToNodeId"/> null ist, blitzt nur der Startknoten
/// auf (kein Signallauf entlang einer Kante). <see cref="DelayMs"/> ist relativ zum Beginn des auslösenden Events.
/// </summary>
public readonly record struct BrainPulseStep(string FromNodeId, string? ToNodeId, int DelayMs, BrainPulseKind Kind = BrainPulseKind.Normal);

/// <summary>
/// Rein deterministisches, zustandsloses Mapping von beobachtbaren Systemereignissen auf visuelle Impulsabläufe
/// im Synapsennetz (<see cref="BrainNeuralGraph"/>). Interpretiert keinen Systemzustand selbst, sondern übersetzt
/// nur die vom Aufrufer übergebene Ereigniskategorie 1:1 in eine feste Schrittfolge. Ein unbekannter oder nicht
/// zugeordneter Typ ergibt bewusst eine leere Liste statt einer erfundenen Aktivität.
/// </summary>
public static class BrainActivityMapper
{
    public static IReadOnlyList<BrainPulseStep> Steps(BrainActivityType type) => type switch
    {
        // Einzelner Startimpuls an einem peripheren Knoten.
        BrainActivityType.InputReceived =>
        [
            new("input", null, 0),
        ],

        // Mehrere kurze Suchpfade innerhalb des Memory-Bereichs.
        BrainActivityType.MemoryRetrieval =>
        [
            new("mem1", null, 0),
            new("mem1", "mem2", 40),
            new("mem1", "ctx1", 40),
            new("mem2", "ctx2", 170),
        ],

        // Mehrere Aktivierungen laufen zu den zentralen Knoten zusammen.
        BrainActivityType.ContextBuild =>
        [
            new("ctx1", "core1", 0),
            new("ctx2", "core1", 0),
            new("ctx2", "core2", 50),
            new("core1", "core2", 150),
        ],

        // Ein Pfad wird sichtbar dominant.
        BrainActivityType.ModelRouting =>
        [
            new("core1", "route", 0, BrainPulseKind.Dominant),
            new("route", "inf1", 130, BrainPulseKind.Dominant),
        ],

        // Kontrollierte Aktivität über mehrere verbundene Inferenz-Bereiche.
        BrainActivityType.ModelInference =>
        [
            new("route", "inf1", 0),
            new("route", "inf2", 50),
            new("inf1", "inf2", 130),
            new("inf2", "inf3", 210),
        ],

        // Signal läuft zu einem definierten äußeren Knoten innerhalb des Gehirns.
        BrainActivityType.ToolCall =>
        [
            new("inf1", "tool", 0),
        ],

        // Signal kehrt von dort in die zentralen Bereiche zurück.
        BrainActivityType.ToolResult =>
        [
            new("tool", "inf2", 0),
            new("inf2", "inf3", 130),
            new("inf3", "core2", 230),
        ],

        // Mehrere kurze rhythmische Pfade.
        BrainActivityType.ResponseGeneration =>
        [
            new("core1", "resp1", 0),
            new("core2", "resp1", 90),
            new("resp1", "resp2", 170),
            new("core1", "resp1", 280),
            new("resp1", "resp2", 360),
        ],

        // Kurzer klarer Puls mit anschließendem Ausklingen.
        BrainActivityType.MemoryWriteConfirmed =>
        [
            new("mem1", "mem2", 0),
        ],

        // Kurzer, klar unterscheidbarer Fehlerimpuls.
        BrainActivityType.ErrorEvent =>
        [
            new("core1", null, 0, BrainPulseKind.Error),
        ],

        // Zurückhaltende, reduzierte Aktivität.
        BrainActivityType.DegradedEvent =>
        [
            new("core1", "core2", 0, BrainPulseKind.Degraded),
        ],

        _ => [],
    };
}
