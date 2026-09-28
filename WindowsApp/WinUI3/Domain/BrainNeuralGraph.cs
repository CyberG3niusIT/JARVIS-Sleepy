namespace Jarvis.ControlHub.WinUI.Domain;

/// <summary>Grobe Region eines Knotens, für Lesbarkeit und Event-Mapping (kein visuelles Cluster-Rendering).
/// <see cref="Relay"/> sind reine Strukturknoten des Netzes: sie werden nie von einem Ereignis angesteuert.</summary>
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
    Relay,
}

/// <summary>Ein Synapsenknoten (Soma). X/Y sind normalisiert (0..1) relativ zum Brain-Asset (1536 x 1024), damit der
/// Graph beim Resize mit dem Bild mitskaliert. <see cref="Depth"/> (0 = hinten, 1 = vorne) steuert nur Größe und
/// Helligkeit für eine leichte räumliche Staffelung.</summary>
public sealed record BrainNode(string Id, double X, double Y, BrainRegion Region, double Depth = 0.5)
{
    public bool IsRelay => Region == BrainRegion.Relay;
}

/// <summary>
/// Eine neuronale Bahn als Polylinie (normalisiert). Funktionsbahnen sind gerichtet und werden vom Mapper
/// angesteuert; Strukturbahnen sind ungerichtet, tragen das feine Netz und die Verzweigung eines Signals.
/// </summary>
public sealed record BrainEdge(string FromId, string ToId, bool Functional, IReadOnlyList<(double X, double Y)> Path)
{
    /// <summary>Bogenlänge der Bahn in normalisierten Bildeinheiten (x mit Seitenverhältnis 1.5 gewichtet).</summary>
    public double Length { get; } = ArcLength(Path);

    private static double ArcLength(IReadOnlyList<(double X, double Y)> path)
    {
        var length = 0.0;
        for (var i = 1; i < path.Count; i++) length += Math.Sqrt(Math.Pow((path[i].X - path[i - 1].X) * 1.5, 2) + Math.Pow(path[i].Y - path[i - 1].Y, 2));
        return length;
    }
}

/// <summary>
/// Deterministisches, festes Synapsennetz auf dem Brain-Asset. Somata liegen auf den im Asset sichtbaren
/// Synapsenpunkten, Bahnen folgen den hellen Faserzügen des Assets (Offline erzeugt durch
/// Tools/generate_brain_paths.py nach <see cref="BrainPathData"/>). Keine Laufzeit-Generierung, kein Zufall.
/// </summary>
public static class BrainNeuralGraph
{
    public static readonly IReadOnlyList<BrainNode> Nodes =
        BrainPathData.Nodes.Select(n => new BrainNode(n.Id, n.X, n.Y, n.Region, n.Depth)).ToArray();

    public static readonly IReadOnlyList<BrainEdge> Edges =
        BrainPathData.Edges.Select(e => new BrainEdge(e.From, e.To, e.Functional, ToPoints(e.Path))).ToArray();

    private static readonly Dictionary<string, BrainNode> ById = Nodes.ToDictionary(n => n.Id);

    private static readonly Dictionary<string, BrainEdge[]> Structural = Nodes.ToDictionary(
        n => n.Id,
        n => Edges.Where(e => !e.Functional && (e.FromId == n.Id || e.ToId == n.Id)).ToArray());

    private static (double X, double Y)[] ToPoints(double[] flat)
    {
        var points = new (double X, double Y)[flat.Length / 2];
        for (var i = 0; i < points.Length; i++) points[i] = (flat[i * 2], flat[i * 2 + 1]);
        return points;
    }

    public static BrainNode Node(string id) => ById[id];

    /// <summary>Gerichtete Funktionsbahn From -> To (Mapper-Kante).</summary>
    public static bool HasEdge(string fromId, string toId) =>
        Edges.Any(e => e.Functional && e.FromId == fromId && e.ToId == toId);

    public static BrainEdge Edge(string fromId, string toId) =>
        Edges.First(e => e.Functional && e.FromId == fromId && e.ToId == toId);

    /// <summary>Strukturbahnen, die an einem Knoten ansetzen (für Verzweigung und Dendritenwirkung).</summary>
    public static IReadOnlyList<BrainEdge> Branches(string nodeId) =>
        Structural.TryGetValue(nodeId, out var edges) ? edges : [];

    /// <summary>Stützpunkte der Bahn in Laufrichtung ab <paramref name="fromNodeId"/> (dreht Strukturbahnen bei Bedarf um).</summary>
    public static IReadOnlyList<(double X, double Y)> PathFrom(BrainEdge edge, string fromNodeId) =>
        edge.FromId == fromNodeId ? edge.Path : edge.Path.Reverse().ToArray();

    /// <summary>Anderes Ende einer Bahn aus Sicht von <paramref name="nodeId"/>.</summary>
    public static string OtherEnd(BrainEdge edge, string nodeId) => edge.FromId == nodeId ? edge.ToId : edge.FromId;

    /// <summary>Alle Stützpunkte einer Bahn.</summary>
    public static IReadOnlyList<(double X, double Y)> Sample(BrainEdge edge) => edge.Path;
}

/// <summary>
/// Innenkontur von Großhirn und Kleinhirn im Brain-Asset (normalisiert, im Uhrzeigersinn), aus dem Asset vermessen
/// und leicht nach innen versetzt. Hirnstamm und Bodenreflex sind bewusst ausgeschlossen. Dient als harte Grenze:
/// Knoten, Bahnen und Dendriten müssen vollständig innerhalb liegen (per Test geprüft).
/// </summary>
public static class BrainSilhouette
{
    public static readonly IReadOnlyList<(double X, double Y)> Outline =
    [
        (0.215, 0.460), (0.212, 0.400), (0.220, 0.340), (0.235, 0.295), (0.258, 0.255), (0.285, 0.220),
        (0.312, 0.190), (0.340, 0.165), (0.370, 0.143), (0.400, 0.126), (0.430, 0.117), (0.460, 0.111),
        (0.490, 0.107), (0.520, 0.111), (0.552, 0.117), (0.583, 0.127), (0.610, 0.148), (0.638, 0.170),
        (0.662, 0.200), (0.683, 0.235), (0.703, 0.273), (0.719, 0.315), (0.735, 0.358), (0.745, 0.405),
        (0.752, 0.458), (0.754, 0.512), (0.747, 0.565), (0.727, 0.607), (0.700, 0.645), (0.688, 0.695),
        (0.662, 0.725), (0.632, 0.740), (0.602, 0.740), (0.575, 0.712), (0.545, 0.672), (0.500, 0.650),
        (0.455, 0.650), (0.420, 0.650), (0.390, 0.638), (0.365, 0.623), (0.340, 0.605), (0.320, 0.583),
        (0.298, 0.558), (0.265, 0.533), (0.235, 0.505),
    ];

    /// <summary>Punkt-in-Polygon (Ray Casting).</summary>
    public static bool Contains(double x, double y)
    {
        var inside = false;
        for (int i = 0, j = Outline.Count - 1; i < Outline.Count; j = i++)
        {
            var (xi, yi) = Outline[i];
            var (xj, yj) = Outline[j];
            if ((yi > y) != (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
        }

        return inside;
    }
}
