namespace Jarvis.ControlHub.WinUI.Domain;

/// <summary>Grobe Region eines Knotens, für Lesbarkeit und Event-Mapping (kein visuelles Cluster-Rendering).</summary>
public enum BrainRegion
{
    Input,
    Memory,
    Context,
    Routing,
    Inference,
    Tool,
    Response,
    Core,
}

/// <summary>Ein Synapsenknoten. X/Y sind normalisiert (0..1) relativ zur sichtbaren Brain-Silhouette, nicht zu Pixeln,
/// damit der Graph beim Resize mit dem Bild mitskaliert statt zu driften.</summary>
public sealed record BrainNode(string Id, double X, double Y, BrainRegion Region);

/// <summary>Eine gerichtete neuronale Verbindung zwischen zwei Knoten.</summary>
public sealed record BrainEdge(string FromId, string ToId);

/// <summary>
/// Deterministisches, festes Synapsennetz innerhalb der Brain-Silhouette (Lovable-Maske: Ellipse 62% x 64% um
/// den Mittelpunkt). Keine Zufallsgeometrie, keine Laufzeit-Generierung. Koordinaten sind bewusst konservativ
/// innerhalb der Maske gewählt, damit kein Pfad über den Randauslauf hinaus sichtbar wird.
/// </summary>
public static class BrainNeuralGraph
{
    public static readonly IReadOnlyList<BrainNode> Nodes =
    [
        new("input", 0.32, 0.24, BrainRegion.Input),
        new("mem1", 0.26, 0.42, BrainRegion.Memory),
        new("mem2", 0.36, 0.56, BrainRegion.Memory),
        new("ctx1", 0.42, 0.38, BrainRegion.Context),
        new("ctx2", 0.46, 0.53, BrainRegion.Context),
        new("route", 0.50, 0.27, BrainRegion.Routing),
        new("core1", 0.50, 0.46, BrainRegion.Core),
        new("core2", 0.54, 0.58, BrainRegion.Core),
        new("inf1", 0.60, 0.39, BrainRegion.Inference),
        new("inf2", 0.66, 0.49, BrainRegion.Inference),
        new("inf3", 0.58, 0.61, BrainRegion.Inference),
        new("tool", 0.78, 0.46, BrainRegion.Tool),
        new("resp1", 0.50, 0.69, BrainRegion.Response),
        new("resp2", 0.41, 0.74, BrainRegion.Response),
    ];

    public static readonly IReadOnlyList<BrainEdge> Edges =
    [
        new("input", "mem1"),
        new("input", "ctx1"),
        new("mem1", "mem2"),
        new("mem1", "ctx1"),
        new("mem2", "ctx2"),
        new("ctx1", "core1"),
        new("ctx2", "core1"),
        new("ctx2", "core2"),
        new("core1", "core2"),
        new("core1", "route"),
        new("route", "inf1"),
        new("route", "inf2"),
        new("inf1", "inf2"),
        new("inf2", "inf3"),
        new("inf1", "tool"),
        new("tool", "inf2"),
        new("inf3", "core2"),
        new("core2", "resp1"),
        new("core1", "resp1"),
        new("resp1", "resp2"),
    ];

    private static readonly Dictionary<string, BrainNode> ById = Nodes.ToDictionary(n => n.Id);

    public static BrainNode Node(string id) => ById[id];

    public static bool HasEdge(string fromId, string toId) =>
        Edges.Any(e => e.FromId == fromId && e.ToId == toId);
}
