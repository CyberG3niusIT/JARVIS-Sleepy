using System.Numerics;
using Jarvis.ControlHub.WinUI.Domain;
using Microsoft.UI.Composition;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Hosting;
using Windows.UI;
using Windows.UI.ViewManagement;

namespace Jarvis.ControlHub.WinUI.Views;

/// <summary>
/// Live-Aktivitätsschicht der Brain Stage. Zeichnet das feste Synapsennetz (<see cref="BrainNeuralGraph"/>: Somata auf
/// den sichtbaren Synapsenpunkten des Assets, Bahnen entlang seiner hellen Faserzüge) rein über Windows Composition,
/// ohne WebView, ohne Win2D und ohne UI-Thread-Animationsloop.
///
/// Visuelle Sprache (abgeleitet aus wissenschaftlicher Aktivitätsdarstellung):
/// - Kühles, ruhiges Grundgerüst; nur aktive Signale sind warm (Amber/Gold/Weiß).
/// - Ein Signal hat Richtung und endliche Geschwindigkeit: ein kleiner heller Kopf läuft entlang der Bahn, die Bahn
///   leuchtet segmentweise direkt hinter ihm auf und klingt vom Ende her wieder ab (Nachglühen).
/// - Knotenreaktion wie ein Kalzium-Transient: schneller Anstieg, langsamer Abfall; kurze Refraktärzeit gegen Flackern.
/// - Verzweigung mit Rate um 1: an einem Knoten setzt sich das Signal auf höchstens zwei Strukturbahnen schwächer fort
///   und endet dort (keine Kettenreaktion, keine "Explosion").
///
/// Diese Klasse interpretiert keinen Systemzustand selbst: <see cref="Raise"/> übersetzt ausschließlich das vom
/// Aufrufer übergebene <see cref="BrainActivityEvent"/> über <see cref="BrainActivityMapper"/> in einen festen
/// visuellen Ablauf. Alle Zeitpunkte werden beim Auslösen als Compositor-Verzögerungen geplant.
/// </summary>
internal sealed class BrainActivityRenderer
{
    /// <summary>Nachlaufzeit ohne neue Ereignisse, bis die Stage in Idle zurückkehrt.</summary>
    public const int ActiveHoldMs = 3600;

    private const double SpeedPxPerMs = 0.30;
    private const int MinTravelMs = 300;
    private const int MaxTravelMs = 1150;
    private const double DominantSlowdown = 1.3;
    private const double BranchSpeedFactor = 0.8;
    private const int WakeRiseMs = 70;
    private const int WakeDecayMs = 820;
    private const int NodeRiseMs = 80;
    private const int NodeDecayMs = 1050;
    private const int RefractoryMs = 320;
    private const int ReducedMotionMs = 600;
    private const int BranchPoolSize = 12;

    private const float IdleNetworkOpacity = 0.55f;
    private const float ActiveNetworkOpacity = 0.92f;

    private const float StructureStroke = 0.7f;
    private const float FunctionalStroke = 0.95f;
    private const float WakeStroke = 1.6f;
    private const float BranchWakeStroke = 1.1f;
    private const float WakeGlowStroke = 5f;
    private const float WakeGlowOpacity = 0.3f;
    private const float ActiveDim = 0.16f;
    private const float HaloSize = 38f;
    private const float HotCoreSize = 10f;
    private const float PulseSize = 15f;
    private const float BranchPulseSize = 10f;
    private const float AmbientSize = 40f;

    // Kühles Grundgerüst (Lovable memory-node / primary, stark zurückgenommen).
    private static readonly Color StructureColor = Color.FromArgb(46, 0x3A, 0x8E, 0xC0);
    private static readonly Color FunctionalColor = Color.FromArgb(72, 0x4A, 0x9C, 0xCC);
    private static readonly Color SomaColor = Color.FromArgb(255, 0x8C, 0xCF, 0xF0);
    private static readonly Color AmbientColor = Color.FromArgb(255, 0x2F, 0x9C, 0xE0);
    private static readonly Color HotWhite = Color.FromArgb(255, 0xFF, 0xF4, 0xE2);

    /// <summary>Knoten mit sehr langsamer Idle-Grundatmung (tiefe Restaktivität, keine Signalläufe).</summary>
    private static readonly string[] AmbientNodes = ["core1", "mem1", "inf2", "ctx2", "resp1"];

    private readonly FrameworkElement _sizeSource;
    private readonly Compositor _compositor;
    private readonly ContainerVisual _root;
    private readonly ContainerVisual _network;
    private readonly ContainerVisual _activityLayer;
    private readonly SpriteVisual _depthBloom;
    private readonly SpriteVisual _dimVeil;
    private readonly CompositionEasingFunction _linear;
    private readonly CompositionEasingFunction _easeOut;
    private readonly CompositionEasingFunction _decay;
    private readonly DispatcherQueueTimer? _modeTimer;

    private readonly List<(CompositionLineGeometry Line, (double X, double Y) A, (double X, double Y) B)> _lines = new();
    private readonly List<(Visual Visual, BrainNode Node, float Size)> _anchored = new();
    private readonly Dictionary<BrainEdge, Wake> _wakes = new();
    private readonly Dictionary<string, Reaction> _reactions = new();
    private readonly Dictionary<string, long> _lastFire = new();
    private readonly Dictionary<string, int> _fireCount = new();
    private readonly Pulse[] _pulses = new Pulse[BrainActivityScheduler.MaxConcurrentPulses];
    private readonly Pulse[] _branchPulses = new Pulse[BranchPoolSize];
    private readonly ShapeVisual[] _fullSize;
    private int _activePulses;
    private bool _active;
    private bool _activeIsTest;
    private Windows.Foundation.Size _lastSize;

    private sealed class Wake
    {
        public required ShapeVisual Visual;
        public required ShapeVisual Glow;
        public required CompositionColorBrush[] Segments;
    }

    private sealed class Reaction
    {
        public required SpriteVisual Halo;
        public required CompositionColorGradientStop[] HaloStops;
        public required SpriteVisual Core;
    }

    private sealed class Pulse
    {
        public required SpriteVisual Visual;
        public required CompositionColorGradientStop[] Stops;
        public bool Busy;
    }

    /// <summary>Wechsel zwischen Idle und Active (für das Status-Overlay). Argumente: aktiv, Auslöser ist Testaktivität.</summary>
    public event Action<bool, bool>? ModeChanged;

    /// <summary>Jedes zugelassene Ereignis, nachdem es visuell angestoßen wurde (für die Aktivierungskanäle).</summary>
    public event Action<BrainActivityEvent>? Raised;

    /// <param name="sizeSource">Element, dessen tatsächliche Bildmaße den Koordinatenrahmen liefern.</param>
    /// <param name="host">Element, auf das die Composition-Ebene gezeichnet wird (deckungsgleich mit <paramref name="sizeSource"/>).</param>
    public BrainActivityRenderer(FrameworkElement sizeSource, UIElement host)
    {
        _sizeSource = sizeSource;
        _compositor = ElementCompositionPreview.GetElementVisual(host).Compositor;
        _linear = _compositor.CreateLinearEasingFunction();
        _easeOut = _compositor.CreateCubicBezierEasingFunction(new Vector2(0.2f, 0.7f), new Vector2(0.3f, 1f));
        // Näherung an einen exponentiellen Abfall (Kalzium-Transient): steil zu Beginn, lang auslaufend.
        _decay = _compositor.CreateCubicBezierEasingFunction(new Vector2(0.05f, 0.7f), new Vector2(0.35f, 1f));

        _root = _compositor.CreateContainerVisual();
        ElementCompositionPreview.SetElementChildVisual(host, _root);

        // Im Active-Zustand wird das Asset leicht abgedunkelt, damit warme Signale Kontrast haben, ohne zu überstrahlen.
        _dimVeil = _compositor.CreateSpriteVisual();
        _dimVeil.Brush = _compositor.CreateColorBrush(Color.FromArgb(255, 1, 4, 8));
        _dimVeil.Opacity = 0f;
        _root.Children.InsertAtTop(_dimVeil);

        // Sehr weiche, kühle Raumtiefe hinter dem Netz im Active-Zustand. Keine Kontur, kein Ring.
        _depthBloom = _compositor.CreateSpriteVisual();
        _depthBloom.Brush = RadialBrush(Color.FromArgb(34, 0x00, 0xA2, 0xF5), false, out _);
        _depthBloom.Opacity = 0f;
        _root.Children.InsertAtTop(_depthBloom);

        _network = _compositor.CreateContainerVisual();
        _network.Opacity = IdleNetworkOpacity;
        _root.Children.InsertAtTop(_network);

        _activityLayer = _compositor.CreateContainerVisual();
        _root.Children.InsertAtTop(_activityLayer);

        _fullSize =
        [
            BuildLines(BrainNeuralGraph.Edges.Where(e => !e.Functional), StructureColor, StructureStroke),
            BuildLines(BrainNeuralGraph.Edges.Where(e => e.Functional), FunctionalColor, FunctionalStroke),
        ];
        BuildSomata();
        BuildAmbient();
        for (var i = 0; i < _pulses.Length; i++) _pulses[i] = CreatePulse(PulseSize);
        for (var i = 0; i < _branchPulses.Length; i++) _branchPulses[i] = CreatePulse(BranchPulseSize);

        var queue = DispatcherQueue.GetForCurrentThread();
        if (queue is not null)
        {
            _modeTimer = queue.CreateTimer();
            _modeTimer.Interval = TimeSpan.FromMilliseconds(ActiveHoldMs);
            _modeTimer.IsRepeating = false;
            _modeTimer.Tick += (_, _) => SetMode(false, false);
        }

        sizeSource.SizeChanged += (_, _) => SyncSize();
        SyncSize();
    }

    private static bool AnimationsEnabled()
    {
        try { return new UISettings().AnimationsEnabled; }
        catch { return true; }
    }

    // ---- Aufbau (einmalig, statisch) --------------------------------------------------------------------------

    /// <summary>Alle Bahnen einer Klasse in einem einzigen ShapeVisual mit einem gemeinsamen Pinsel (statisch, billig).</summary>
    private ShapeVisual BuildLines(IEnumerable<BrainEdge> edges, Color color, float stroke)
    {
        var visual = _compositor.CreateShapeVisual();
        var brush = _compositor.CreateColorBrush(color);
        foreach (var edge in edges)
        {
            for (var i = 1; i < edge.Path.Count; i++)
            {
                var line = _compositor.CreateLineGeometry();
                var shape = _compositor.CreateSpriteShape(line);
                shape.StrokeBrush = brush;
                shape.StrokeThickness = stroke;
                shape.StrokeStartCap = CompositionStrokeCap.Round;
                shape.StrokeEndCap = CompositionStrokeCap.Round;
                visual.Shapes.Add(shape);
                _lines.Add((line, edge.Path[i - 1], edge.Path[i]));
            }
        }

        _network.Children.InsertAtTop(visual);
        return visual;
    }

    /// <summary>Somata als kleine kühle Punkte; Größe und Helligkeit folgen der Tiefe (vorne größer und klarer).</summary>
    private void BuildSomata()
    {
        foreach (var node in BrainNeuralGraph.Nodes)
        {
            var radius = (float)((node.IsRelay ? 0.8 : 1.3) + 1.1 * node.Depth);
            var box = radius * 4;
            var visual = _compositor.CreateShapeVisual();
            visual.Size = new Vector2(box, box);
            var ellipse = _compositor.CreateEllipseGeometry();
            ellipse.Center = new Vector2(box / 2, box / 2);
            ellipse.Radius = new Vector2(radius);
            var shape = _compositor.CreateSpriteShape(ellipse);
            var alpha = (byte)((node.IsRelay ? 70 : 150) + 90 * node.Depth);
            shape.FillBrush = _compositor.CreateColorBrush(Color.FromArgb(alpha, SomaColor.R, SomaColor.G, SomaColor.B));
            visual.Shapes.Add(shape);
            _network.Children.InsertAtTop(visual);
            _anchored.Add((visual, node, box));
        }
    }

    /// <summary>Sehr langsame, tiefe Grundatmung einzelner Somata (kühl, Compositor-Thread). Entfällt bei
    /// deaktivierten Systemanimationen. Keine Signalläufe, keine erfundenen Ereignisse.</summary>
    private void BuildAmbient()
    {
        var animate = AnimationsEnabled();
        for (var i = 0; i < AmbientNodes.Length; i++)
        {
            var sprite = _compositor.CreateSpriteVisual();
            sprite.Size = new Vector2(AmbientSize, AmbientSize);
            sprite.Brush = RadialBrush(AmbientColor, false, out _);
            sprite.Opacity = 0f;
            _network.Children.InsertAtBottom(sprite);
            _anchored.Add((sprite, BrainNeuralGraph.Node(AmbientNodes[i]), AmbientSize));
            if (!animate) continue;

            var breath = _compositor.CreateScalarKeyFrameAnimation();
            breath.InsertKeyFrame(0f, 0f);
            breath.InsertKeyFrame(0.45f, 0.28f, _easeOut);
            breath.InsertKeyFrame(1f, 0f, _easeOut);
            breath.Duration = TimeSpan.FromMilliseconds(8200 + i * 1300);
            breath.DelayTime = TimeSpan.FromMilliseconds(i * 2300);
            breath.IterationBehavior = AnimationIterationBehavior.Forever;
            sprite.StartAnimation(nameof(Visual.Opacity), breath);
        }
    }

    private Pulse CreatePulse(float size)
    {
        var sprite = _compositor.CreateSpriteVisual();
        sprite.Size = new Vector2(size, size);
        sprite.Brush = RadialBrush(HotWhite, true, out var stops);
        sprite.Opacity = 0f;
        _activityLayer.Children.InsertAtTop(sprite);
        return new Pulse { Visual = sprite, Stops = stops };
    }

    /// <summary>Radialer Verlauf: optional heller Kern, dann Farbe, dann transparent. Weiches Licht ohne Blur-Effekt.</summary>
    private CompositionRadialGradientBrush RadialBrush(Color color, bool hotCore, out CompositionColorGradientStop[] stops)
    {
        var brush = _compositor.CreateRadialGradientBrush();
        brush.MappingMode = CompositionMappingMode.Relative;
        brush.EllipseCenter = new Vector2(0.5f, 0.5f);
        brush.EllipseRadius = new Vector2(0.5f, 0.5f);
        stops =
        [
            _compositor.CreateColorGradientStop(0f, hotCore ? HotWhite : color),
            _compositor.CreateColorGradientStop(hotCore ? 0.18f : 0.05f, color),
            _compositor.CreateColorGradientStop(0.45f, WithAlpha(color, (byte)(color.A * 0.3))),
            _compositor.CreateColorGradientStop(1f, WithAlpha(color, 0)),
        ];
        foreach (var stop in stops) brush.ColorStops.Add(stop);
        return brush;
    }

    private static Color WithAlpha(Color color, byte alpha) => Color.FromArgb(alpha, color.R, color.G, color.B);

    // ---- Lazy: Nachglühen je Bahn, Reaktion je Knoten ----------------------------------------------------------

    /// <summary>Nachglüh-Spur einer Bahn: je Segment ein eigener Pinsel, damit die Spur dem Kopf segmentweise folgt.
    /// Zwei Lagen teilen sich dieselben Pinsel: ein feiner Kern und ein breiter, schwacher Lichthof.</summary>
    private Wake WakeFor(BrainEdge edge)
    {
        if (_wakes.TryGetValue(edge, out var wake)) return wake;
        var size = new Vector2((float)_lastSize.Width, (float)_lastSize.Height);
        var core = _compositor.CreateShapeVisual();
        var glow = _compositor.CreateShapeVisual();
        core.Size = glow.Size = size;
        glow.Opacity = WakeGlowOpacity;
        var brushes = new CompositionColorBrush[edge.Path.Count - 1];
        for (var i = 1; i < edge.Path.Count; i++)
        {
            var brush = _compositor.CreateColorBrush(Color.FromArgb(0, 0, 0, 0));
            brushes[i - 1] = brush;
            AddSegment(core, brush, edge.Functional ? WakeStroke : BranchWakeStroke, edge.Path[i - 1], edge.Path[i]);
            AddSegment(glow, brush, edge.Functional ? WakeGlowStroke : WakeGlowStroke * 0.7f, edge.Path[i - 1], edge.Path[i]);
        }

        _activityLayer.Children.InsertAtBottom(core);
        _activityLayer.Children.InsertAtBottom(glow);
        wake = new Wake { Visual = core, Glow = glow, Segments = brushes };
        _wakes[edge] = wake;
        return wake;
    }

    private void AddSegment(ShapeVisual visual, CompositionBrush brush, float stroke, (double X, double Y) a, (double X, double Y) b)
    {
        var line = _compositor.CreateLineGeometry();
        var shape = _compositor.CreateSpriteShape(line);
        shape.StrokeBrush = brush;
        shape.StrokeThickness = stroke;
        shape.StrokeStartCap = CompositionStrokeCap.Round;
        shape.StrokeEndCap = CompositionStrokeCap.Round;
        visual.Shapes.Add(shape);
        _lines.Add((line, a, b));
        PlaceLine(line, a, b);
    }

    private Reaction ReactionFor(BrainNode node)
    {
        if (_reactions.TryGetValue(node.Id, out var reaction)) return reaction;
        var halo = _compositor.CreateSpriteVisual();
        halo.Size = new Vector2(HaloSize, HaloSize);
        halo.CenterPoint = new Vector3(HaloSize / 2, HaloSize / 2, 0);
        halo.Brush = RadialBrush(HotWhite, false, out var stops);
        halo.Opacity = 0f;
        var core = _compositor.CreateSpriteVisual();
        core.Size = new Vector2(HotCoreSize, HotCoreSize);
        core.Brush = RadialBrush(HotWhite, true, out _);
        core.Opacity = 0f;
        _activityLayer.Children.InsertAtTop(halo);
        _activityLayer.Children.InsertAtTop(core);
        _anchored.Add((halo, node, HaloSize));
        _anchored.Add((core, node, HotCoreSize));
        PlaceAnchored(halo, node, HaloSize);
        PlaceAnchored(core, node, HotCoreSize);
        reaction = new Reaction { Halo = halo, HaloStops = stops, Core = core };
        _reactions[node.Id] = reaction;
        return reaction;
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

        var full = new Vector2(width, height);
        _root.Size = full;
        _network.Size = full;
        _activityLayer.Size = full;
        foreach (var visual in _fullSize) visual.Size = full;
        _dimVeil.Size = full;
        foreach (var wake in _wakes.Values) wake.Visual.Size = wake.Glow.Size = full;

        _depthBloom.Size = new Vector2(width * 0.62f, height * 0.78f);
        _depthBloom.Offset = new Vector3(width * 0.48f - _depthBloom.Size.X / 2, height * 0.42f - _depthBloom.Size.Y / 2, 0);

        foreach (var (line, a, b) in _lines) PlaceLine(line, a, b);
        foreach (var (visual, node, box) in _anchored) PlaceAnchored(visual, node, box);
    }

    private void PlaceLine(CompositionLineGeometry line, (double X, double Y) a, (double X, double Y) b)
    {
        line.Start = Px(a);
        line.End = Px(b);
    }

    private void PlaceAnchored(Visual visual, BrainNode node, float box)
    {
        var p = Px((node.X, node.Y));
        visual.Offset = new Vector3(p.X - box / 2, p.Y - box / 2, 0);
    }

    private Vector2 Px((double X, double Y) point) =>
        new((float)(point.X * _lastSize.Width), (float)(point.Y * _lastSize.Height));

    // ---- Zustand ----------------------------------------------------------------------------------------------

    /// <summary>Anzahl aktuell laufender Mapper-Schritte. Test-Zugriff für Obergrenzen-Prüfung.</summary>
    public int ActivePulseCount => _activePulses;

    /// <summary>True, solange die Stage im Active-Zustand ist (bis <see cref="ActiveHoldMs"/> nach dem letzten Ereignis).</summary>
    public bool IsActive => _active;

    private void SetMode(bool active, bool isTest)
    {
        if (active == _active && isTest == _activeIsTest) return;
        var changed = active != _active;
        _active = active;
        _activeIsTest = active && isTest;
        if (changed)
        {
            FadeTo(_network, active ? ActiveNetworkOpacity : IdleNetworkOpacity, active ? 420 : 1800);
            FadeTo(_depthBloom, active ? 1f : 0f, active ? 700 : 1800);
            FadeTo(_dimVeil, active ? ActiveDim : 0f, active ? 600 : 1800);
        }

        ModeChanged?.Invoke(_active, _activeIsTest);
    }

    private void FadeTo(Visual visual, float target, int durationMs)
    {
        var fade = _compositor.CreateScalarKeyFrameAnimation();
        fade.InsertExpressionKeyFrame(0f, "this.StartingValue");
        fade.InsertKeyFrame(1f, target, _easeOut);
        fade.Duration = TimeSpan.FromMilliseconds(durationMs);
        visual.StartAnimation(nameof(Visual.Opacity), fade);
    }

    // ---- Aktivität ------------------------------------------------------------------------------------------

    /// <summary>
    /// Übersetzt ein reales Systemereignis in einen deterministischen visuellen Impulsablauf. Ist die Stage noch
    /// nicht layoutet oder ist der Ereignistyp keinem Ablauf zugeordnet, passiert nichts (keine erfundene Aktivität).
    /// Bei einem Event-Burst wird nur bis zur Obergrenze gleichzeitig laufender Schritte admittiert.
    /// </summary>
    public void Raise(BrainActivityEvent activityEvent)
    {
        if (_lastSize.Width <= 0) return;
        var steps = BrainActivityMapper.Steps(activityEvent.Type);
        if (steps.Count == 0) return;

        SetMode(true, activityEvent.IsTest);
        if (_modeTimer is not null)
        {
            _modeTimer.Stop();
            _modeTimer.Start();
        }

        var admitted = BrainActivityScheduler.Admit(_activePulses, steps.Count);
        for (var i = 0; i < admitted; i++) PlayStep(steps[i], activityEvent.Type);
        Raised?.Invoke(activityEvent);
    }

    private void PlayStep(BrainPulseStep step, BrainActivityType type)
    {
        var reduced = !AnimationsEnabled();
        var color = SignalColor(type, step.Kind);
        var claimed = new List<Pulse>(3);

        _activePulses++;
        var batch = _compositor.CreateScopedBatch(CompositionBatchTypes.Animation);
        if (step.ToNodeId is { } to && BrainNeuralGraph.HasEdge(step.FromNodeId, to))
        {
            var edge = BrainNeuralGraph.Edge(step.FromNodeId, to);
            var travel = TravelMs(edge, step.Kind == BrainPulseKind.Dominant ? DominantSlowdown : 1.0);
            if (reduced) travel = ReducedMotionMs;

            if (!reduced && Claim(_pulses) is { } pulse)
            {
                claimed.Add(pulse);
                RunPulse(pulse, edge.Path, color, travel, step.DelayMs, 1f);
            }

            RunWake(WakeFor(edge), color, travel, step.DelayMs, reduced ? 0.55f : 0.95f, reduced);
            var arrival = step.DelayMs + travel;
            React(BrainNeuralGraph.Node(to), color, arrival, 1f, reduced);

            // Verzweigung: nur normale Signale teilen sich, Fehler/Degradation bleiben bewusst lokal.
            if (!reduced && step.Kind is BrainPulseKind.Normal or BrainPulseKind.Dominant)
            {
                foreach (var branch in PickBranches(to, step.FromNodeId, step.Kind == BrainPulseKind.Dominant ? 1 : 2))
                {
                    if (Claim(_branchPulses) is not { } branchPulse) break;
                    claimed.Add(branchPulse);
                    var path = BrainNeuralGraph.PathFrom(branch, to);
                    var branchTravel = TravelMs(branch, 1 / BranchSpeedFactor);
                    var start = arrival + 40;
                    RunPulse(branchPulse, path, color, branchTravel, start, 0.7f);
                    RunWakeDirected(WakeFor(branch), branch.FromId == to, color, branchTravel, start, 0.55f);
                    React(BrainNeuralGraph.Node(BrainNeuralGraph.OtherEnd(branch, to)), color, start + branchTravel, 0.45f, false);
                }
            }
        }
        else
        {
            React(BrainNeuralGraph.Node(step.FromNodeId), color, step.DelayMs, 1f, reduced);
        }

        batch.End();
        batch.Completed += (_, _) =>
        {
            _activePulses = Math.Max(0, _activePulses - 1);
            foreach (var pulse in claimed) pulse.Busy = false;
        };
    }

    private static Pulse? Claim(Pulse[] pool)
    {
        var pulse = Array.Find(pool, p => !p.Busy);
        if (pulse is not null) pulse.Busy = true;
        return pulse;
    }

    /// <summary>Deterministische Auswahl der Folgebahnen: pro Knoten rotierend, nie zurück zum Herkunftsknoten, damit
    /// nicht jedes Mal dieselben Bahnen leuchten und nie alle gleichzeitig.</summary>
    private IEnumerable<BrainEdge> PickBranches(string nodeId, string cameFrom, int count)
    {
        var branches = BrainNeuralGraph.Branches(nodeId).Where(b => BrainNeuralGraph.OtherEnd(b, nodeId) != cameFrom).ToArray();
        if (branches.Length == 0) yield break;
        _fireCount.TryGetValue(nodeId, out var n);
        _fireCount[nodeId] = n + 1;
        for (var i = 0; i < Math.Min(count, branches.Length); i++) yield return branches[(n * 2 + i) % branches.Length];
    }

    private int TravelMs(BrainEdge edge, double slowdown)
    {
        var pxLength = edge.Length * _lastSize.Height;
        return (int)(Math.Clamp(pxLength / SpeedPxPerMs, MinTravelMs, MaxTravelMs) * slowdown);
    }

    /// <summary>Signalkopf: kleiner heller Punkt, läuft mit konstanter Geschwindigkeit exakt über die Stützpunkte.</summary>
    private void RunPulse(Pulse pulse, IReadOnlyList<(double X, double Y)> path, Color color, int travelMs, int delayMs, float strength)
    {
        pulse.Stops[1].Color = color;
        pulse.Stops[2].Color = WithAlpha(color, 70);
        pulse.Stops[3].Color = WithAlpha(color, 0);
        var half = pulse.Visual.Size.X / 2;

        var move = _compositor.CreateVector3KeyFrameAnimation();
        for (var i = 0; i < path.Count; i++)
        {
            var p = Px(path[i]);
            move.InsertKeyFrame(i / (float)(path.Count - 1), new Vector3(p.X - half, p.Y - half, 0), _linear);
        }

        move.Duration = TimeSpan.FromMilliseconds(travelMs);
        move.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        pulse.Visual.StartAnimation(nameof(Visual.Offset), move);

        var opacity = _compositor.CreateScalarKeyFrameAnimation();
        opacity.InsertKeyFrame(0f, 0f);
        opacity.InsertKeyFrame(0.06f, strength, _linear);
        opacity.InsertKeyFrame(0.9f, strength, _linear);
        opacity.InsertKeyFrame(1f, 0f, _linear);
        opacity.Duration = TimeSpan.FromMilliseconds(travelMs);
        opacity.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        pulse.Visual.StartAnimation(nameof(Visual.Opacity), opacity);
    }

    private void RunWake(Wake wake, Color color, int travelMs, int delayMs, float strength, bool reduced) =>
        RunWakeDirected(wake, true, color, travelMs, delayMs, strength, reduced);

    /// <summary>Nachglühen: jedes Segment leuchtet in dem Moment auf, in dem der Kopf es passiert, und klingt danach
    /// langsam ab. Dadurch folgt die Spur dem Signal und verblasst vom Ende her.</summary>
    private void RunWakeDirected(Wake wake, bool forward, Color color, int travelMs, int delayMs, float strength, bool reduced = false)
    {
        var count = wake.Segments.Length;
        var peak = WithAlpha(color, (byte)(255 * strength));
        var clear = WithAlpha(color, 0);
        var total = WakeRiseMs + WakeDecayMs;
        for (var i = 0; i < count; i++)
        {
            var brush = wake.Segments[forward ? i : count - 1 - i];
            var passAt = reduced ? 0 : (int)(travelMs * (i + 0.5) / count);
            var glow = _compositor.CreateColorKeyFrameAnimation();
            glow.InsertKeyFrame(0f, clear);
            glow.InsertKeyFrame(WakeRiseMs / (float)total, peak, _linear);
            glow.InsertKeyFrame(1f, clear, _decay);
            glow.Duration = TimeSpan.FromMilliseconds(reduced ? ReducedMotionMs * 2 : total);
            glow.DelayTime = TimeSpan.FromMilliseconds(delayMs + passAt);
            brush.StartAnimation(nameof(CompositionColorBrush.Color), glow);
        }
    }

    /// <summary>Knotenreaktion wie ein Kalzium-Transient: schneller Anstieg, langsamer Abfall, warmer Halo und kurz
    /// weißlicher Kern. Innerhalb der Refraktärzeit wird eine laufende Reaktion nicht neu gestartet (kein Flackern).</summary>
    private void React(BrainNode node, Color color, int delayMs, float strength, bool reduced)
    {
        var due = Environment.TickCount64 + delayMs;
        if (_lastFire.TryGetValue(node.Id, out var last) && Math.Abs(due - last) < RefractoryMs && strength < 1f) return;
        _lastFire[node.Id] = due;

        var reaction = ReactionFor(node);
        reaction.HaloStops[1].Color = color;
        reaction.HaloStops[2].Color = WithAlpha(color, 80);
        reaction.HaloStops[3].Color = WithAlpha(color, 0);
        var duration = reduced ? ReducedMotionMs * 2 : NodeRiseMs + NodeDecayMs;
        var rise = NodeRiseMs / (float)duration;

        var halo = _compositor.CreateScalarKeyFrameAnimation();
        halo.InsertKeyFrame(0f, 0f);
        halo.InsertKeyFrame(rise, 0.9f * strength, _linear);
        halo.InsertKeyFrame(1f, 0f, _decay);
        halo.Duration = TimeSpan.FromMilliseconds(duration);
        halo.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        reaction.Halo.StartAnimation(nameof(Visual.Opacity), halo);

        if (!reduced)
        {
            var swell = _compositor.CreateVector3KeyFrameAnimation();
            swell.InsertKeyFrame(0f, new Vector3(0.6f, 0.6f, 1f));
            swell.InsertKeyFrame(rise, new Vector3(1f, 1f, 1f), _easeOut);
            swell.InsertKeyFrame(1f, new Vector3(1.12f, 1.12f, 1f), _decay);
            swell.Duration = TimeSpan.FromMilliseconds(duration);
            swell.DelayTime = TimeSpan.FromMilliseconds(delayMs);
            reaction.Halo.StartAnimation(nameof(Visual.Scale), swell);
        }

        var core = _compositor.CreateScalarKeyFrameAnimation();
        core.InsertKeyFrame(0f, 0f);
        core.InsertKeyFrame(rise, strength, _linear);
        core.InsertKeyFrame(1f, 0f, _decay);
        core.Duration = TimeSpan.FromMilliseconds((int)(duration * 0.65));
        core.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        reaction.Core.StartAnimation(nameof(Visual.Opacity), core);
    }

    /// <summary>
    /// Warme Signalfarbe je Verarbeitungsart, nur sehr subtil unterschieden (Gold, Amber, weißliches Gold).
    /// Fehler bleiben klar rot, Degradation kühl-gedämpft, damit sie nicht mit normaler Aktivität verwechselt werden.
    /// </summary>
    private static Color SignalColor(BrainActivityType type, BrainPulseKind kind) => kind switch
    {
        BrainPulseKind.Error => Color.FromArgb(255, 0xF3, 0x61, 0x64),
        BrainPulseKind.Degraded => Color.FromArgb(255, 0x8F, 0xA6, 0xBC),
        BrainPulseKind.Dominant => Color.FromArgb(255, 0xFF, 0xE2, 0xAE),
        _ => type switch
        {
            BrainActivityType.InputReceived => Color.FromArgb(255, 0xFF, 0xE6, 0xC2),
            BrainActivityType.MemoryRetrieval or BrainActivityType.MemoryWriteConfirmed => Color.FromArgb(255, 0xF2, 0xC0, 0x6B),
            BrainActivityType.ContextBuild => Color.FromArgb(255, 0xF4, 0xB2, 0x5C),
            BrainActivityType.ToolCall or BrainActivityType.ToolResult => Color.FromArgb(255, 0xF0, 0xA2, 0x55),
            BrainActivityType.ModelInference => Color.FromArgb(255, 0xF6, 0xC6, 0x78),
            BrainActivityType.ResponseGeneration => Color.FromArgb(255, 0xFF, 0xD4, 0x92),
            _ => Color.FromArgb(255, 0xF5, 0xBE, 0x6C),
        },
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
            await Task.Delay(900, token);
        }
    }

    /// <summary>TEST-ONLY: ein einzelnes, als Test markiertes Ereignis (Nachweis "einzelne Aktivität").</summary>
    public void RaiseTestSingle(BrainActivityType type = BrainActivityType.MemoryRetrieval) =>
        Raise(new BrainActivityEvent(type, IsTest: true));
}
