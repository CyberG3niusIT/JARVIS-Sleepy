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

/// <summary>Ein Synapsenknoten. X/Y sind normalisiert (0..1) relativ zum Brain-Asset (1536 x 1024), nicht zu Pixeln,
/// damit der Graph beim Resize mit dem Bild mitskaliert statt zu driften.</summary>
public sealed record BrainNode(string Id, double X, double Y, BrainRegion Region)
{
    public bool IsRelay => Region == BrainRegion.Relay;
}

/// <summary>
/// Eine gerichtete neuronale Bahn zwischen zwei Knoten. <see cref="Bend"/> krümmt die Bahn als quadratische Kurve:
/// der Kontrollpunkt liegt um Bend x Kantenlänge senkrecht zur Verbindungslinie versetzt (positiv = links der
/// Laufrichtung). Keine Zufallsgeometrie; jede Bahn ist fest definiert.
/// </summary>
public sealed record BrainEdge(string FromId, string ToId, double Bend = 0);

/// <summary>Ein kurzer Dendritenast an einem Synapsenknoten (normalisierte Start-, Knick- und Endpunkte).</summary>
public readonly record struct BrainDendrite(double X0, double Y0, double X1, double Y1, double X2, double Y2);

/// <summary>
/// Deterministisches, festes Synapsennetz innerhalb der realen Gehirnkontur des Brain-Assets
/// (<see cref="BrainSilhouette"/>). Frontallappen links, Okzipitallappen rechts, Temporallappen unten mittig,
/// Kleinhirn rechts unten. Keine Laufzeit-Generierung.
/// </summary>
public static class BrainNeuralGraph
{
    /// <summary>Stützpunkte je Bahn für Zeichnung und Signallauf. Fest, damit Rendering und Tests identisch samplen.</summary>
    public const int CurveSegments = 12;

    public static readonly IReadOnlyList<BrainNode> Nodes =
    [
        // Funktionsknoten (vom Mapper angesteuert).
        new("input", 0.285, 0.300, BrainRegion.Input),
        new("ctx1", 0.335, 0.405, BrainRegion.Context),
        new("mem1", 0.345, 0.520, BrainRegion.Memory),
        new("mem2", 0.445, 0.595, BrainRegion.Memory),
        new("ctx2", 0.430, 0.470, BrainRegion.Context),
        new("core1", 0.500, 0.375, BrainRegion.Core),
        new("core2", 0.545, 0.500, BrainRegion.Core),
        new("route", 0.530, 0.215, BrainRegion.Routing),
        new("inf1", 0.620, 0.300, BrainRegion.Inference),
        new("inf2", 0.650, 0.440, BrainRegion.Inference),
        new("inf3", 0.615, 0.545, BrainRegion.Inference),
        new("tool", 0.705, 0.385, BrainRegion.Tool),
        new("resp1", 0.600, 0.625, BrainRegion.Response),
        new("resp2", 0.655, 0.685, BrainRegion.Response),

        // Strukturknoten: tragen das feine Netz zwischen den Lappen, ohne Ereignisbedeutung.
        new("r_front", 0.245, 0.400, BrainRegion.Relay),
        new("r_top1", 0.395, 0.180, BrainRegion.Relay),
        new("r_top2", 0.450, 0.285, BrainRegion.Relay),
        new("r_par", 0.660, 0.230, BrainRegion.Relay),
        new("r_occ", 0.715, 0.500, BrainRegion.Relay),
        new("r_temp", 0.520, 0.600, BrainRegion.Relay),
        new("r_front2", 0.285, 0.490, BrainRegion.Relay),
        new("r_cb", 0.690, 0.640, BrainRegion.Relay),
    ];

    public static readonly IReadOnlyList<BrainEdge> Edges =
    [
        // Funktionsbahnen.
        new("input", "mem1", 0.22),
        new("input", "ctx1", -0.12),
        new("mem1", "mem2", 0.18),
        new("mem1", "ctx1", -0.16),
        new("mem2", "ctx2", 0.14),
        new("ctx1", "core1", -0.14),
        new("ctx2", "core1", 0.12),
        new("ctx2", "core2", -0.10),
        new("core1", "core2", 0.16),
        new("core1", "route", 0.14),
        new("route", "inf1", -0.16),
        new("route", "inf2", 0.10),
        new("inf1", "inf2", -0.14),
        new("inf2", "inf3", 0.16),
        new("inf1", "tool", -0.14),
        new("tool", "inf2", -0.18),
        new("inf3", "core2", 0.14),
        new("core2", "resp1", 0.12),
        new("core1", "resp1", -0.10),
        new("resp1", "resp2", -0.18),

        // Strukturbahnen (nur Netzzeichnung, keine Signalläufe).
        new("r_front", "input", -0.16),
        new("r_front", "ctx1", 0.12),
        new("r_front", "r_front2", -0.18),
        new("r_front2", "mem1", 0.14),
        new("r_top1", "input", -0.14),
        new("r_top1", "route", 0.10),
        new("r_top2", "r_top1", 0.14),
        new("r_top2", "core1", -0.12),
        new("r_top2", "ctx1", 0.10),
        new("route", "r_par", 0.14),
        new("r_par", "inf1", -0.12),
        new("r_par", "tool", 0.16),
        new("tool", "r_occ", 0.16),
        new("r_occ", "inf3", -0.12),
        new("mem2", "r_temp", -0.14),
        new("r_temp", "core2", 0.12),
        new("r_temp", "resp1", -0.14),
        new("resp2", "r_cb", 0.18),
        new("r_cb", "r_occ", -0.14),
    ];

    private static readonly Dictionary<string, BrainNode> ById = Nodes.ToDictionary(n => n.Id);

    public static BrainNode Node(string id) => ById[id];

    public static bool HasEdge(string fromId, string toId) =>
        Edges.Any(e => e.FromId == fromId && e.ToId == toId);

    public static BrainEdge Edge(string fromId, string toId) =>
        Edges.First(e => e.FromId == fromId && e.ToId == toId);

    /// <summary>Punkt auf der gekrümmten Bahn bei Fortschritt <paramref name="t"/> (0 = Start, 1 = Ziel), normalisiert.
    /// <paramref name="aspect"/> ist Breite/Höhe des Zielrechtecks, damit die Krümmung im Bild senkrecht wirkt.</summary>
    public static (double X, double Y) PointOnEdge(BrainEdge edge, double t, double aspect = 1.5)
    {
        var a = Node(edge.FromId);
        var b = Node(edge.ToId);
        // In ein isotropes Maß umrechnen (x in Höhe-Einheiten), damit "senkrecht" auch im Bild senkrecht ist.
        var ax = a.X * aspect; var bx = b.X * aspect;
        var dx = bx - ax; var dy = b.Y - a.Y;
        var cx = (ax + bx) / 2 - dy * edge.Bend;
        var cy = (a.Y + b.Y) / 2 + dx * edge.Bend;
        var u = 1 - t;
        var x = u * u * ax + 2 * u * t * cx + t * t * bx;
        var y = u * u * a.Y + 2 * u * t * cy + t * t * b.Y;
        return (x / aspect, y);
    }

    /// <summary>Alle <see cref="CurveSegments"/>+1 Stützpunkte einer Bahn.</summary>
    public static IReadOnlyList<(double X, double Y)> Sample(BrainEdge edge, double aspect = 1.5)
    {
        var points = new (double X, double Y)[CurveSegments + 1];
        for (var i = 0; i <= CurveSegments; i++) points[i] = PointOnEdge(edge, (double)i / CurveSegments, aspect);
        return points;
    }

    /// <summary>
    /// Drei kurze, leicht geknickte Dendritenäste je Funktionsknoten. Richtungen sind aus der Knoten-ID fest
    /// abgeleitet (stabiler Hash), nicht zufällig; Länge etwa 2-3 % der Bildhöhe.
    /// </summary>
    public static IReadOnlyList<BrainDendrite> Dendrites(BrainNode node, double aspect = 1.5)
    {
        if (node.IsRelay) return [];
        var seed = 0;
        foreach (var c in node.Id) seed = (seed * 31 + c) & 0x7FFF;
        var result = new BrainDendrite[3];
        for (var i = 0; i < 3; i++)
        {
            var angle = (seed % 360 + i * 120 + (i == 1 ? 17 : 0)) * Math.PI / 180;
            var length = 0.022 + ((seed >> (i + 2)) % 5) * 0.002;
            var kink = (i % 2 == 0 ? 1 : -1) * 0.45;
            var mx = node.X + Math.Cos(angle) * length * 0.55 / aspect;
            var my = node.Y + Math.Sin(angle) * length * 0.55;
            var ex = node.X + Math.Cos(angle + kink) * length / aspect;
            var ey = node.Y + Math.Sin(angle + kink) * length;
            result[i] = new BrainDendrite(node.X, node.Y, mx, my, ex, ey);
        }

        return result;
    }
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
