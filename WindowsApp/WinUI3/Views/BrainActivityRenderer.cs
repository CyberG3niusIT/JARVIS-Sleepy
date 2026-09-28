using System.Numerics;
using Jarvis.ControlHub.WinUI.Domain;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Hosting;
using Windows.UI;
using Windows.UI.ViewManagement;

namespace Jarvis.ControlHub.WinUI.Views;

/// <summary>
/// Live-Aktivitätsschicht der Brain Stage (Layer 3+4 aus dem Auftrag: Neural Graph und Live Activity). Zeichnet
/// ein festes, deterministisches Synapsennetz (<see cref="BrainNeuralGraph"/>) rein über Windows Composition
/// (<see cref="ShapeVisual"/>/<see cref="CompositionSpriteShape"/>), ohne WebView, ohne Win2D und ohne
/// UI-Thread-Animationsloop. Verbindungen sind schmale rotierte Rechtecke (native Composition-Geometrie, kein
/// Pfad-Interop nötig); ein Signallauf ist ein kleiner, gepoolter Lichtpunkt, der linear von Start- zu Zielknoten
/// wandert. Im Idle-Zustand läuft keine Animation, es gibt nur eine sehr zurückhaltende statische Grundzeichnung.
///
/// Diese Klasse interpretiert keinen Systemzustand selbst: <see cref="Raise"/> übersetzt ausschließlich das vom
/// Aufrufer übergebene <see cref="BrainActivityEvent"/> über <see cref="BrainActivityMapper"/> in einen festen
/// visuellen Ablauf. Kein Zugriff auf Runtime, Memory, Tools oder Backend.
/// </summary>
internal sealed class BrainActivityRenderer
{
    private const int TravelMs = 260;
    private const int DominantTravelMs = 420;
    private const int NodeFlashMs = 240;
    private const int ReducedMotionMs = 500;

    private const float NodeBoxSize = 22f;
    private const float NodeRadius = 3.4f;
    private const float PulseBoxSize = 14f;
    private const float PulseRadius = 2.6f;
    private const float EdgeStrokeIdle = 0.9f;

    private static readonly Color IdleEdgeColor = Color.FromArgb(60, 0x17, 0x5F, 0x7C);
    private static readonly Color IdleNodeColor = Color.FromArgb(255, 0x17, 0x5F, 0x7C);

    private readonly FrameworkElement _sizeSource;
    private readonly Compositor _compositor;
    private readonly ContainerVisual _root;
    private readonly Dictionary<string, ShapeVisual> _edgeVisual = new();
    private readonly Dictionary<string, CompositionRoundedRectangleGeometry> _edgeGeometry = new();
    private readonly Dictionary<string, Visual> _nodeVisual = new();
    private readonly Dictionary<string, CompositionColorBrush> _nodeBrush = new();
    private readonly PulseDot[] _pulsePool = new PulseDot[BrainActivityScheduler.MaxConcurrentPulses];
    private int _activePulses;
    private Windows.Foundation.Size _lastSize;

    private sealed class PulseDot
    {
        public required Visual Visual;
        public required CompositionColorBrush Brush;
        public bool Busy;
    }

    /// <param name="sizeSource">Element, dessen tatsächliche Bildmaße (Letterbox-Rect) den Koordinatenrahmen liefert.</param>
    /// <param name="host">Element, auf das die Composition-Ebene gezeichnet wird (deckungsgleich mit <paramref name="sizeSource"/>, oberhalb des Brain-Assets in der Z-Reihenfolge).</param>
    public BrainActivityRenderer(FrameworkElement sizeSource, UIElement host)
    {
        _sizeSource = sizeSource;
        _compositor = ElementCompositionPreview.GetElementVisual(host).Compositor;
        _root = _compositor.CreateContainerVisual();
        ElementCompositionPreview.SetElementChildVisual(host, _root);

        BuildEdges();
        BuildNodes();
        BuildPulsePool();

        sizeSource.SizeChanged += (_, _) => SyncSize();
        SyncSize();
    }

    private static bool AnimationsEnabled()
    {
        try { return new UISettings().AnimationsEnabled; }
        catch { return true; }
    }

    // ---- Aufbau (einmalig) -------------------------------------------------------------------------------------

    /// <summary>Jede Kante ist ein schmales, abgerundetes Rechteck: Shape-Offset = Startpunkt, CenterPoint links
    /// mittig, RotationAngle richtet es zum Zielpunkt aus. Trim/Pfadgeometrie wird bewusst vermieden.</summary>
    private void BuildEdges()
    {
        var idleBrush = _compositor.CreateColorBrush(IdleEdgeColor);
        foreach (var edge in BrainNeuralGraph.Edges)
        {
            var geometry = _compositor.CreateRoundedRectangleGeometry();
            geometry.CornerRadius = new Vector2(EdgeStrokeIdle / 2, EdgeStrokeIdle / 2);
            _edgeGeometry[EdgeKey(edge.FromId, edge.ToId)] = geometry;

            var shape = _compositor.CreateSpriteShape(geometry);
            shape.FillBrush = idleBrush;

            var visual = _compositor.CreateShapeVisual();
            visual.Shapes.Add(shape);
            _edgeVisual[EdgeKey(edge.FromId, edge.ToId)] = visual;
            _root.Children.InsertAtTop(visual);
        }
    }

    private void BuildNodes()
    {
        foreach (var node in BrainNeuralGraph.Nodes)
        {
            var (visual, brush) = CreateDot(NodeBoxSize, NodeRadius, IdleNodeColor);
            visual.Opacity = 0.16f;
            _nodeVisual[node.Id] = visual;
            _nodeBrush[node.Id] = brush;
            _root.Children.InsertAtTop(visual);
        }
    }

    private void BuildPulsePool()
    {
        for (var i = 0; i < _pulsePool.Length; i++)
        {
            var (visual, brush) = CreateDot(PulseBoxSize, PulseRadius, IdleNodeColor);
            visual.Opacity = 0f;
            _root.Children.InsertAtTop(visual);
            _pulsePool[i] = new PulseDot { Visual = visual, Brush = brush };
        }
    }

    private (ShapeVisual Visual, CompositionColorBrush Brush) CreateDot(float boxSize, float radius, Color color)
    {
        var visual = _compositor.CreateShapeVisual();
        visual.Size = new Vector2(boxSize, boxSize);
        visual.CenterPoint = new Vector3(boxSize / 2, boxSize / 2, 0);

        var brush = _compositor.CreateColorBrush(color);
        var ellipse = _compositor.CreateEllipseGeometry();
        ellipse.Radius = new Vector2(radius, radius);
        ellipse.Center = new Vector2(boxSize / 2, boxSize / 2);
        var shape = _compositor.CreateSpriteShape(ellipse);
        shape.FillBrush = brush;
        visual.Shapes.Add(shape);
        return (visual, brush);
    }

    // ---- Layout / Resize ----------------------------------------------------------------------------------------

    private void SyncSize()
    {
        var width = (float)_sizeSource.ActualWidth;
        var height = (float)_sizeSource.ActualHeight;
        if (width <= 0 || height <= 0) return;
        var size = new Windows.Foundation.Size(width, height);
        if (size == _lastSize) return;
        _lastSize = size;

        _root.Size = new Vector2(width, height);

        foreach (var edge in BrainNeuralGraph.Edges)
        {
            var from = PixelOf(BrainNeuralGraph.Node(edge.FromId), width, height);
            var to = PixelOf(BrainNeuralGraph.Node(edge.ToId), width, height);
            var key = EdgeKey(edge.FromId, edge.ToId);
            var delta = to - from;
            var length = delta.Length();
            var angleDegrees = (float)(Math.Atan2(delta.Y, delta.X) * 180.0 / Math.PI);

            var geometry = _edgeGeometry[key];
            geometry.Size = new Vector2(Math.Max(1, length), EdgeStrokeIdle);

            var visual = _edgeVisual[key];
            visual.Size = new Vector2(Math.Max(1, length), EdgeStrokeIdle);
            visual.CenterPoint = new Vector3(0, EdgeStrokeIdle / 2, 0);
            visual.RotationAngleInDegrees = angleDegrees;
            visual.Offset = new Vector3(from.X, from.Y - EdgeStrokeIdle / 2, 0);
        }

        foreach (var node in BrainNeuralGraph.Nodes)
        {
            var p = PixelOf(node, width, height);
            _nodeVisual[node.Id].Offset = new Vector3(p.X - NodeBoxSize / 2, p.Y - NodeBoxSize / 2, 0);
        }
    }

    private static Vector2 PixelOf(BrainNode node, float width, float height) => new((float)(node.X * width), (float)(node.Y * height));

    private static string EdgeKey(string from, string to) => from + ">" + to;

    // ---- Aktivität ------------------------------------------------------------------------------------------

    /// <summary>Anzahl aktuell sichtbarer Impulse. Test-Zugriff für Determinismus-/Obergrenzen-Prüfung.</summary>
    public int ActivePulseCount => _activePulses;

    /// <summary>
    /// Übersetzt ein reales Systemereignis in einen deterministischen visuellen Impulsablauf. Ist die Stage noch
    /// nicht layoutet oder ist der Ereignistyp keinem Ablauf zugeordnet, passiert nichts (keine erfundene Aktivität).
    /// Bei einem Event-Burst wird nur bis zur Obergrenze gleichzeitig sichtbarer Impulse admittiert, der Rest
    /// dieses Bursts entfällt (Bündelung statt unbegrenzter Parallelität).
    /// </summary>
    public void Raise(BrainActivityEvent activityEvent)
    {
        if (_lastSize.Width <= 0) return;
        var steps = BrainActivityMapper.Steps(activityEvent.Type);
        if (steps.Count == 0) return;

        var admitted = BrainActivityScheduler.Admit(_activePulses, steps.Count);
        for (var i = 0; i < admitted; i++) PlayStep(steps[i]);
    }

    private void PlayStep(BrainPulseStep step)
    {
        var reduced = !AnimationsEnabled();
        var color = ColorFor(step.Kind);
        var travelMs = step.Kind == BrainPulseKind.Dominant ? DominantTravelMs : TravelMs;

        _activePulses++;
        var batch = _compositor.CreateScopedBatch(CompositionBatchTypes.Animation);
        if (step.ToNodeId is { } to)
        {
            AnimateTravel(step.FromNodeId, to, color, travelMs, step.DelayMs, reduced);
            FlashNode(to, color, step.DelayMs + (reduced ? ReducedMotionMs / 2 : travelMs), reduced);
        }
        else
        {
            FlashNode(step.FromNodeId, color, step.DelayMs, reduced);
        }

        batch.End();
        batch.Completed += (_, _) => _activePulses = Math.Max(0, _activePulses - 1);
    }

    /// <summary>Signal läuft als kleiner Lichtpunkt linear von Start- zu Zielknoten, bleibt exakt auf der Verbindung.</summary>
    private void AnimateTravel(string fromId, string toId, Color color, int travelMs, int delayMs, bool reduced)
    {
        var slot = Array.Find(_pulsePool, p => !p.Busy) ?? _pulsePool[0];
        slot.Busy = true;
        slot.Brush.Color = color;

        var width = (float)_lastSize.Width;
        var height = (float)_lastSize.Height;
        var from = PixelOf(BrainNeuralGraph.Node(fromId), width, height);
        var to = PixelOf(BrainNeuralGraph.Node(toId), width, height);
        var half = PulseBoxSize / 2;

        var duration = reduced ? ReducedMotionMs : travelMs;
        var offset = _compositor.CreateVector3KeyFrameAnimation();
        offset.InsertKeyFrame(0f, new Vector3(from.X - half, from.Y - half, 0));
        offset.InsertKeyFrame(1f, new Vector3(to.X - half, to.Y - half, 0));
        offset.Duration = TimeSpan.FromMilliseconds(duration);
        offset.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        slot.Visual.StartAnimation(nameof(Visual.Offset), offset);

        var opacity = _compositor.CreateScalarKeyFrameAnimation();
        opacity.InsertKeyFrame(0f, 0f);
        opacity.InsertKeyFrame(0.15f, 1f);
        opacity.InsertKeyFrame(0.82f, 1f);
        opacity.InsertKeyFrame(1f, 0f);
        opacity.Duration = TimeSpan.FromMilliseconds(duration);
        opacity.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        slot.Visual.StartAnimation(nameof(Visual.Opacity), opacity);

        var batch = _compositor.CreateScopedBatch(CompositionBatchTypes.Animation);
        batch.End();
        batch.Completed += (_, _) => slot.Busy = false;
    }

    /// <summary>Ein Knoten leuchtet beim Erreichen kurz auf und klingt kontrolliert wieder auf den Idle-Zustand aus.</summary>
    private void FlashNode(string nodeId, Color color, int delayMs, bool reduced)
    {
        if (!_nodeVisual.TryGetValue(nodeId, out var visual) || !_nodeBrush.TryGetValue(nodeId, out var brush)) return;
        brush.Color = color;

        var duration = reduced ? ReducedMotionMs : NodeFlashMs;
        var opacity = _compositor.CreateScalarKeyFrameAnimation();
        opacity.InsertKeyFrame(0f, 0.16f);
        opacity.InsertKeyFrame(reduced ? 0.5f : 0.35f, 1f);
        opacity.InsertKeyFrame(1f, 0.16f);
        opacity.Duration = TimeSpan.FromMilliseconds(duration);
        opacity.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        visual.StartAnimation(nameof(Visual.Opacity), opacity);

        if (!reduced)
        {
            var scale = _compositor.CreateVector3KeyFrameAnimation();
            scale.InsertKeyFrame(0f, new Vector3(0.75f, 0.75f, 1f));
            scale.InsertKeyFrame(0.35f, new Vector3(1.35f, 1.35f, 1f));
            scale.InsertKeyFrame(1f, new Vector3(0.75f, 0.75f, 1f));
            scale.Duration = TimeSpan.FromMilliseconds(duration);
            scale.DelayTime = TimeSpan.FromMilliseconds(delayMs);
            visual.StartAnimation(nameof(Visual.Scale), scale);
        }
    }

    private static Color ColorFor(BrainPulseKind kind) => kind switch
    {
        BrainPulseKind.Error => Color.FromArgb(255, 0xF3, 0x61, 0x64),
        BrainPulseKind.Degraded => Color.FromArgb(255, 0xDA, 0xA3, 0x41),
        BrainPulseKind.Dominant => Color.FromArgb(255, 0x00, 0xC0, 0xEE),
        _ => Color.FromArgb(255, 0x00, 0xA2, 0xF5),
    };

    // ---- TEST-ONLY -------------------------------------------------------------------------------------------

    /// <summary>
    /// TEST-ONLY: feste, klar als Test markierte Verifikationssequenz (Render, Timing, Screenshots). Wird nie
    /// automatisch im normalen Produktionsstart aufgerufen; siehe den Aufrufer in ShellPage (Umgebungsvariablen-Gate).
    /// </summary>
    public async Task RunTestSequenceAsync(CancellationToken token = default)
    {
        BrainActivityType[] sequence =
        [
            BrainActivityType.InputReceived,
            BrainActivityType.MemoryRetrieval,
            BrainActivityType.ContextBuild,
            BrainActivityType.ModelRouting,
            BrainActivityType.ModelInference,
            BrainActivityType.ToolCall,
            BrainActivityType.ToolResult,
            BrainActivityType.ResponseGeneration,
            BrainActivityType.MemoryWriteConfirmed,
        ];
        foreach (var type in sequence)
        {
            if (token.IsCancellationRequested) return;
            Raise(new BrainActivityEvent(type, IsTest: true));
            await Task.Delay(700, token);
        }
    }
}
