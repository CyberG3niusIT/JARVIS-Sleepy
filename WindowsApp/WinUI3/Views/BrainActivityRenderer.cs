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
/// Live-Aktivitätsschicht der Brain Stage (Neural Graph und Live Activity). Zeichnet das feste Synapsennetz
/// (<see cref="BrainNeuralGraph"/>) als gekrümmte, feine Bahnen mit Synapsenknoten und Dendritenästen rein über
/// Windows Composition, ohne WebView, ohne Win2D und ohne UI-Thread-Animationsloop.
///
/// Zustände:
/// - Idle: Netz stark zurückgenommen, nur eine sehr langsame, tiefe Grundatmung einzelner Knoten (Compositor-Thread,
///   keine Signalläufe, keine erfundenen Ereignisse).
/// - Active: Netz hebt sich an; Impulse laufen als kurze Pulsfolge (Kopf + zwei Nachläufer) exakt entlang der
///   Bahnkurve, die Bahn leuchtet beim Durchlauf nach, der Zielknoten reagiert und das Signal verzweigt sich kurz in
///   seine Dendriten. Ohne weitere Ereignisse klingt die Stage nach <see cref="ActiveHoldMs"/> in Idle zurück.
///
/// Diese Klasse interpretiert keinen Systemzustand selbst: <see cref="Raise"/> übersetzt ausschließlich das vom
/// Aufrufer übergebene <see cref="BrainActivityEvent"/> über <see cref="BrainActivityMapper"/> in einen festen
/// visuellen Ablauf. Kein Zugriff auf Runtime, Memory, Tools oder Backend.
/// </summary>
internal sealed class BrainActivityRenderer
{
    private const double PulseSpeedPxPerMs = 0.36;
    private const int MinTravelMs = 240;
    private const int MaxTravelMs = 560;
    private const double DominantSlowdown = 1.45;
    private const int TrailSpacingMs = 38;
    private const int TraceAfterglowMs = 720;
    private const int NodeReactMs = 560;
    private const int ReducedMotionMs = 500;
    private const int ModeFadeMs = 900;

    /// <summary>Nachlaufzeit ohne neue Ereignisse, bis die Stage in Idle zurückkehrt.</summary>
    public const int ActiveHoldMs = 3200;

    private const float IdleNetworkOpacity = 0.42f;
    private const float ActiveNetworkOpacity = 1f;

    private const float EdgeStroke = 0.85f;
    private const float RelayEdgeStroke = 0.6f;
    private const float TraceStroke = 1.5f;
    private const float DendriteStroke = 0.8f;
    private const float NodeCoreRadius = 2.1f;
    private const float RelayCoreRadius = 1.3f;
    private const float NodeHaloSize = 34f;
    private const float AmbientHaloSize = 46f;
    private const float PulseHeadSize = 15f;
    private const float PulseTailSize = 10f;

    // Farbwelt nach Lovable-Tokens: memory-node / signal / primary, sehr zurückhaltend eingesetzt.
    private static readonly Color EdgeIdleColor = Color.FromArgb(92, 0x2A, 0x86, 0xB4);
    private static readonly Color RelayEdgeColor = Color.FromArgb(44, 0x2A, 0x86, 0xB4);
    private static readonly Color NodeCoreColor = Color.FromArgb(200, 0x7F, 0xCB, 0xEE);
    private static readonly Color RelayCoreColor = Color.FromArgb(110, 0x5C, 0xA8, 0xD2);
    private static readonly Color SignalColor = Color.FromArgb(255, 0x00, 0xC0, 0xEE);
    private static readonly Color PrimaryColor = Color.FromArgb(255, 0x00, 0xA2, 0xF5);
    private static readonly Color HotCoreColor = Color.FromArgb(255, 0xD8, 0xF4, 0xFF);

    /// <summary>Knoten mit sehr langsamer Idle-Grundatmung (tiefe Restaktivität, keine Signalläufe).</summary>
    private static readonly string[] AmbientNodes = ["core1", "mem1", "inf2", "ctx2", "resp1"];

    private readonly FrameworkElement _sizeSource;
    private readonly Compositor _compositor;
    private readonly ContainerVisual _root;
    private readonly ContainerVisual _network;
    private readonly SpriteVisual _activityBloom;
    private readonly CompositionEasingFunction _linear;
    private readonly CompositionEasingFunction _easeOut;
    private readonly DispatcherQueueTimer? _modeTimer;

    private readonly Dictionary<string, EdgeVisuals> _edges = new();
    private readonly Dictionary<string, NodeVisuals> _nodes = new();
    private readonly List<(SpriteVisual Visual, string NodeId)> _ambient = new();
    private readonly PulseTrain[] _pulsePool = new PulseTrain[BrainActivityScheduler.MaxConcurrentPulses];
    private int _activePulses;
    private bool _active;
    private bool _activeIsTest;
    private Windows.Foundation.Size _lastSize;

    private sealed class EdgeVisuals
    {
        public required BrainEdge Edge;
        public required ShapeVisual Base;
        public required ShapeVisual Trace;
        public required CompositionLineGeometry[] BaseSegments;
        public required CompositionLineGeometry[] TraceSegments;
        public required CompositionColorBrush TraceBrush;
    }

    private sealed class NodeVisuals
    {
        public required BrainNode Node;
        public required ShapeVisual Core;
        public required CompositionEllipseGeometry CoreGeometry;
        public SpriteVisual? Halo;
        public CompositionColorGradientStop[]? HaloStops;
        public ShapeVisual? Dendrites;
        public CompositionLineGeometry[]? DendriteSegments;
        public CompositionColorBrush? DendriteBrush;
    }

    private sealed class PulseTrain
    {
        public required SpriteVisual[] Sparks;
        public required CompositionColorGradientStop[][] Stops;
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

        _root = _compositor.CreateContainerVisual();
        ElementCompositionPreview.SetElementChildVisual(host, _root);

        // Weiche Aktivitätstiefe hinter dem Netz: nur im Active-Zustand sichtbar, kein Ring, keine Kontur.
        _activityBloom = _compositor.CreateSpriteVisual();
        _activityBloom.Brush = RadialBrush(Color.FromArgb(52, PrimaryColor.R, PrimaryColor.G, PrimaryColor.B), 0f, 1f, out _);
        _activityBloom.Opacity = 0f;
        _root.Children.InsertAtTop(_activityBloom);

        _network = _compositor.CreateContainerVisual();
        _network.Opacity = IdleNetworkOpacity;
        _root.Children.InsertAtTop(_network);

        BuildEdges();
        BuildNodes();
        BuildAmbient();
        BuildPulsePool();

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

    // ---- Aufbau (einmalig) -------------------------------------------------------------------------------------

    private void BuildEdges()
    {
        var baseBrush = _compositor.CreateColorBrush(EdgeIdleColor);
        var relayBrush = _compositor.CreateColorBrush(RelayEdgeColor);
        foreach (var edge in BrainNeuralGraph.Edges)
        {
            var relay = IsRelayEdge(edge);
            var (baseVisual, baseSegments) = CreatePolyline(BrainNeuralGraph.CurveSegments, relay ? relayBrush : baseBrush, relay ? RelayEdgeStroke : EdgeStroke);
            _network.Children.InsertAtTop(baseVisual);

            var traceBrush = _compositor.CreateColorBrush(SignalColor);
            var (traceVisual, traceSegments) = CreatePolyline(BrainNeuralGraph.CurveSegments, traceBrush, TraceStroke);
            traceVisual.Opacity = 0f;
            _root.Children.InsertAtTop(traceVisual);

            _edges[EdgeKey(edge.FromId, edge.ToId)] = new EdgeVisuals
            {
                Edge = edge,
                Base = baseVisual,
                Trace = traceVisual,
                BaseSegments = baseSegments,
                TraceSegments = traceSegments,
                TraceBrush = traceBrush,
            };
        }
    }

    private void BuildNodes()
    {
        foreach (var node in BrainNeuralGraph.Nodes)
        {
            var coreBox = NodeCoreRadius * 6;
            var core = _compositor.CreateShapeVisual();
            core.Size = new Vector2(coreBox, coreBox);
            core.CenterPoint = new Vector3(coreBox / 2, coreBox / 2, 0);
            var geometry = _compositor.CreateEllipseGeometry();
            geometry.Center = new Vector2(coreBox / 2, coreBox / 2);
            geometry.Radius = node.IsRelay ? new Vector2(RelayCoreRadius) : new Vector2(NodeCoreRadius);
            var shape = _compositor.CreateSpriteShape(geometry);
            shape.FillBrush = _compositor.CreateColorBrush(node.IsRelay ? RelayCoreColor : NodeCoreColor);
            core.Shapes.Add(shape);

            var visuals = new NodeVisuals { Node = node, Core = core, CoreGeometry = geometry };
            if (!node.IsRelay)
            {
                // Dendriten: drei kurze Äste, leuchten nur beim Durchlauf kurz nach (Signal verzweigt sich).
                var dendriteBrush = _compositor.CreateColorBrush(SignalColor);
                var (dendrites, segments) = CreatePolyline(6, dendriteBrush, DendriteStroke);
                dendrites.Opacity = 0f;
                visuals.Dendrites = dendrites;
                visuals.DendriteSegments = segments;
                visuals.DendriteBrush = dendriteBrush;
                _root.Children.InsertAtTop(dendrites);

                var halo = _compositor.CreateSpriteVisual();
                halo.Size = new Vector2(NodeHaloSize, NodeHaloSize);
                halo.CenterPoint = new Vector3(NodeHaloSize / 2, NodeHaloSize / 2, 0);
                halo.Brush = RadialBrush(SignalColor, 0f, 1f, out var stops);
                halo.Opacity = 0f;
                visuals.Halo = halo;
                visuals.HaloStops = stops;
                _root.Children.InsertAtTop(halo);
            }

            _network.Children.InsertAtTop(core);
            _nodes[node.Id] = visuals;
        }
    }

    /// <summary>Sehr langsame, tiefe Grundatmung einzelner Knoten. Läuft vollständig auf dem Compositor-Thread;
    /// bei deaktivierten Systemanimationen entfällt sie.</summary>
    private void BuildAmbient()
    {
        var animate = AnimationsEnabled();
        for (var i = 0; i < AmbientNodes.Length; i++)
        {
            var sprite = _compositor.CreateSpriteVisual();
            sprite.Size = new Vector2(AmbientHaloSize, AmbientHaloSize);
            sprite.Brush = RadialBrush(Color.FromArgb(255, PrimaryColor.R, PrimaryColor.G, PrimaryColor.B), 0f, 1f, out _);
            sprite.Opacity = 0f;
            _network.Children.InsertAtBottom(sprite);
            _ambient.Add((sprite, AmbientNodes[i]));
            if (!animate) continue;

            var breath = _compositor.CreateScalarKeyFrameAnimation();
            breath.InsertKeyFrame(0f, 0f);
            breath.InsertKeyFrame(0.5f, 0.34f, _easeOut);
            breath.InsertKeyFrame(1f, 0f);
            breath.Duration = TimeSpan.FromMilliseconds(7200 + i * 1100);
            breath.DelayTime = TimeSpan.FromMilliseconds(i * 1900);
            breath.IterationBehavior = AnimationIterationBehavior.Forever;
            sprite.StartAnimation(nameof(Visual.Opacity), breath);
        }
    }

    private void BuildPulsePool()
    {
        for (var i = 0; i < _pulsePool.Length; i++)
        {
            var sparks = new SpriteVisual[3];
            var stops = new CompositionColorGradientStop[3][];
            for (var s = 0; s < sparks.Length; s++)
            {
                var size = s == 0 ? PulseHeadSize : PulseTailSize - (s - 1) * 2;
                var spark = _compositor.CreateSpriteVisual();
                spark.Size = new Vector2(size, size);
                spark.Brush = RadialBrush(SignalColor, s == 0 ? 0.22f : 0.12f, 1f, out stops[s]);
                spark.Opacity = 0f;
                _root.Children.InsertAtTop(spark);
                sparks[s] = spark;
            }

            _pulsePool[i] = new PulseTrain { Sparks = sparks, Stops = stops };
        }
    }

    /// <summary>Radialer Verlauf von hellem Kern über Farbe zu transparent: weiches Leuchten ohne Blur-Effekt.</summary>
    private CompositionRadialGradientBrush RadialBrush(Color color, float hotCore, float radius, out CompositionColorGradientStop[] stops)
    {
        var brush = _compositor.CreateRadialGradientBrush();
        brush.MappingMode = CompositionMappingMode.Relative;
        brush.EllipseCenter = new Vector2(0.5f, 0.5f);
        brush.EllipseRadius = new Vector2(0.5f * radius, 0.5f * radius);
        var transparent = Color.FromArgb(0, color.R, color.G, color.B);
        stops =
        [
            _compositor.CreateColorGradientStop(0f, hotCore > 0 ? HotCoreColor : color),
            _compositor.CreateColorGradientStop(Math.Max(0.05f, hotCore), color),
            _compositor.CreateColorGradientStop(0.45f, Color.FromArgb((byte)(color.A * 0.35), color.R, color.G, color.B)),
            _compositor.CreateColorGradientStop(1f, transparent),
        ];
        foreach (var stop in stops) brush.ColorStops.Add(stop);
        return brush;
    }

    /// <summary>Kurvenzug aus kurzen Liniensegmenten mit runden Kappen (native CompositionLineGeometry).</summary>
    private (ShapeVisual Visual, CompositionLineGeometry[] Segments) CreatePolyline(int segments, CompositionBrush brush, float stroke)
    {
        var visual = _compositor.CreateShapeVisual();
        var lines = new CompositionLineGeometry[segments];
        for (var i = 0; i < segments; i++)
        {
            var line = _compositor.CreateLineGeometry();
            var shape = _compositor.CreateSpriteShape(line);
            shape.StrokeBrush = brush;
            shape.StrokeThickness = stroke;
            shape.StrokeStartCap = CompositionStrokeCap.Round;
            shape.StrokeEndCap = CompositionStrokeCap.Round;
            visual.Shapes.Add(shape);
            lines[i] = line;
        }

        return (visual, lines);
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
        var aspect = width / (double)height;

        // Aktivitätstiefe sitzt auf dem Großhirn, nicht auf dem Bildrechteck.
        _activityBloom.Size = new Vector2(width * 0.62f, height * 0.78f);
        _activityBloom.Offset = new Vector3(width * 0.48f - _activityBloom.Size.X / 2, height * 0.42f - _activityBloom.Size.Y / 2, 0);

        foreach (var visuals in _edges.Values)
        {
            var points = BrainNeuralGraph.Sample(visuals.Edge, aspect);
            visuals.Base.Size = full;
            visuals.Trace.Size = full;
            for (var i = 0; i < visuals.BaseSegments.Length; i++)
            {
                var a = Px(points[i], width, height);
                var b = Px(points[i + 1], width, height);
                visuals.BaseSegments[i].Start = a;
                visuals.BaseSegments[i].End = b;
                visuals.TraceSegments[i].Start = a;
                visuals.TraceSegments[i].End = b;
            }
        }

        foreach (var visuals in _nodes.Values)
        {
            var p = Px((visuals.Node.X, visuals.Node.Y), width, height);
            var coreBox = visuals.Core.Size.X;
            visuals.Core.Offset = new Vector3(p.X - coreBox / 2, p.Y - coreBox / 2, 0);
            if (visuals.Halo is { } halo) halo.Offset = new Vector3(p.X - NodeHaloSize / 2, p.Y - NodeHaloSize / 2, 0);
            if (visuals.Dendrites is { } dendrites && visuals.DendriteSegments is { } segments)
            {
                dendrites.Size = full;
                var branches = BrainNeuralGraph.Dendrites(visuals.Node, aspect);
                for (var i = 0; i < branches.Count; i++)
                {
                    var d = branches[i];
                    segments[i * 2].Start = Px((d.X0, d.Y0), width, height);
                    segments[i * 2].End = Px((d.X1, d.Y1), width, height);
                    segments[i * 2 + 1].Start = Px((d.X1, d.Y1), width, height);
                    segments[i * 2 + 1].End = Px((d.X2, d.Y2), width, height);
                }
            }
        }

        foreach (var (sprite, nodeId) in _ambient)
        {
            var node = BrainNeuralGraph.Node(nodeId);
            var p = Px((node.X, node.Y), width, height);
            sprite.Offset = new Vector3(p.X - AmbientHaloSize / 2, p.Y - AmbientHaloSize / 2, 0);
        }
    }

    private static Vector2 Px((double X, double Y) point, float width, float height) => new((float)(point.X * width), (float)(point.Y * height));

    private static bool IsRelayEdge(BrainEdge edge) =>
        BrainNeuralGraph.Node(edge.FromId).IsRelay || BrainNeuralGraph.Node(edge.ToId).IsRelay;

    private static string EdgeKey(string from, string to) => from + ">" + to;

    // ---- Zustand ----------------------------------------------------------------------------------------------

    /// <summary>Anzahl aktuell sichtbarer Impulse. Test-Zugriff für Determinismus-/Obergrenzen-Prüfung.</summary>
    public int ActivePulseCount => _activePulses;

    /// <summary>True, solange die Stage im Active-Zustand ist (bis <see cref="ActiveHoldMs"/> nach dem letzten Ereignis).</summary>
    public bool IsActive => _active;

    private void SetMode(bool active, bool isTest)
    {
        // Idle -> Active hebt Netz und Tiefe an; Active -> Idle blendet ruhig zurück. Reine Compositor-Animation.
        if (active == _active && isTest == _activeIsTest) return;
        var changed = active != _active;
        _active = active;
        _activeIsTest = active && isTest;
        if (changed)
        {
            FadeTo(_network, active ? ActiveNetworkOpacity : IdleNetworkOpacity, active ? 320 : ModeFadeMs * 2);
            FadeTo(_activityBloom, active ? 1f : 0f, active ? 520 : ModeFadeMs * 2);
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
    /// Bei einem Event-Burst wird nur bis zur Obergrenze gleichzeitig sichtbarer Impulse admittiert, der Rest
    /// dieses Bursts entfällt (Bündelung statt unbegrenzter Parallelität).
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
        for (var i = 0; i < admitted; i++) PlayStep(steps[i]);
        Raised?.Invoke(activityEvent);
    }

    private void PlayStep(BrainPulseStep step)
    {
        var reduced = !AnimationsEnabled();
        var color = ColorFor(step.Kind);

        _activePulses++;
        PulseTrain? train = null;
        var batch = _compositor.CreateScopedBatch(CompositionBatchTypes.Animation);
        if (step.ToNodeId is { } to && _edges.TryGetValue(EdgeKey(step.FromNodeId, to), out var edge))
        {
            var travelMs = TravelMs(edge.Edge, step.Kind);
            train = Array.Find(_pulsePool, p => !p.Busy);
            if (train is not null && !reduced)
            {
                train.Busy = true;
                AnimateTrain(train, edge.Edge, color, travelMs, step.DelayMs);
            }

            LightTrace(edge, color, step.DelayMs, reduced ? ReducedMotionMs : travelMs, reduced);
            ReactNode(to, color, step.DelayMs + (reduced ? ReducedMotionMs / 2 : travelMs), reduced);
        }
        else
        {
            ReactNode(step.FromNodeId, color, step.DelayMs, reduced);
        }

        batch.End();
        var claimed = train is { Busy: true } ? train : null;
        batch.Completed += (_, _) =>
        {
            _activePulses = Math.Max(0, _activePulses - 1);
            if (claimed is not null) claimed.Busy = false;
        };
    }

    private int TravelMs(BrainEdge edge, BrainPulseKind kind)
    {
        var width = (float)_lastSize.Width;
        var height = (float)_lastSize.Height;
        var points = BrainNeuralGraph.Sample(edge, width / (double)height);
        var length = 0.0;
        for (var i = 1; i < points.Count; i++) length += Vector2.Distance(Px(points[i - 1], width, height), Px(points[i], width, height));
        var ms = Math.Clamp(length / PulseSpeedPxPerMs, MinTravelMs, MaxTravelMs);
        return (int)(kind == BrainPulseKind.Dominant ? ms * DominantSlowdown : ms);
    }

    /// <summary>Kurze Pulsfolge: ein heller Kopf und zwei schwächere Nachläufer laufen versetzt exakt entlang der
    /// gesampelten Bahnkurve (ein Keyframe je Stützpunkt, lineare Interpolation zwischen den Stützpunkten).</summary>
    private void AnimateTrain(PulseTrain train, BrainEdge edge, Color color, int travelMs, int delayMs)
    {
        var width = (float)_lastSize.Width;
        var height = (float)_lastSize.Height;
        var points = BrainNeuralGraph.Sample(edge, width / (double)height);

        for (var s = 0; s < train.Sparks.Length; s++)
        {
            var spark = train.Sparks[s];
            var stops = train.Stops[s];
            stops[1].Color = color;
            stops[2].Color = Color.FromArgb(90, color.R, color.G, color.B);
            stops[3].Color = Color.FromArgb(0, color.R, color.G, color.B);
            var half = spark.Size.X / 2;

            var path = _compositor.CreateVector3KeyFrameAnimation();
            for (var i = 0; i < points.Count; i++)
            {
                var p = Px(points[i], width, height);
                path.InsertKeyFrame(i / (float)(points.Count - 1), new Vector3(p.X - half, p.Y - half, 0), _linear);
            }

            path.Duration = TimeSpan.FromMilliseconds(travelMs);
            path.DelayTime = TimeSpan.FromMilliseconds(delayMs + s * TrailSpacingMs);
            spark.StartAnimation(nameof(Visual.Offset), path);

            var peak = s == 0 ? 1f : s == 1 ? 0.55f : 0.3f;
            var opacity = _compositor.CreateScalarKeyFrameAnimation();
            opacity.InsertKeyFrame(0f, 0f);
            opacity.InsertKeyFrame(0.12f, peak, _linear);
            opacity.InsertKeyFrame(0.86f, peak, _linear);
            opacity.InsertKeyFrame(1f, 0f, _linear);
            opacity.Duration = TimeSpan.FromMilliseconds(travelMs);
            opacity.DelayTime = TimeSpan.FromMilliseconds(delayMs + s * TrailSpacingMs);
            spark.StartAnimation(nameof(Visual.Opacity), opacity);
        }
    }

    /// <summary>Die durchlaufene Bahn leuchtet während des Laufs auf und klingt danach ruhig nach.</summary>
    private void LightTrace(EdgeVisuals edge, Color color, int delayMs, int travelMs, bool reduced)
    {
        edge.TraceBrush.Color = color;
        var total = travelMs + TraceAfterglowMs;
        var arrive = travelMs / (float)total;
        var trace = _compositor.CreateScalarKeyFrameAnimation();
        trace.InsertKeyFrame(0f, 0f);
        trace.InsertKeyFrame(Math.Max(0.05f, arrive * 0.5f), reduced ? 0.5f : 0.32f, _linear);
        trace.InsertKeyFrame(arrive, 0.62f, _linear);
        trace.InsertKeyFrame(1f, 0f, _easeOut);
        trace.Duration = TimeSpan.FromMilliseconds(total);
        trace.DelayTime = TimeSpan.FromMilliseconds(delayMs);
        edge.Trace.StartAnimation(nameof(Visual.Opacity), trace);
    }

    /// <summary>Synapsenknoten reagiert beim Eintreffen: Kern hellt kurz auf, weicher Halo, und das Signal verzweigt
    /// sich für einen Moment in die Dendritenäste. Danach kontrolliertes Ausklingen auf den Grundzustand.</summary>
    private void ReactNode(string nodeId, Color color, int delayMs, bool reduced)
    {
        if (!_nodes.TryGetValue(nodeId, out var node)) return;
        var duration = reduced ? ReducedMotionMs : NodeReactMs;

        if (node.Halo is { } halo && node.HaloStops is { } stops)
        {
            stops[1].Color = color;
            stops[2].Color = Color.FromArgb(90, color.R, color.G, color.B);
            stops[3].Color = Color.FromArgb(0, color.R, color.G, color.B);

            var glow = _compositor.CreateScalarKeyFrameAnimation();
            glow.InsertKeyFrame(0f, 0f);
            glow.InsertKeyFrame(0.22f, 0.95f, _linear);
            glow.InsertKeyFrame(1f, 0f, _easeOut);
            glow.Duration = TimeSpan.FromMilliseconds(duration);
            glow.DelayTime = TimeSpan.FromMilliseconds(delayMs);
            halo.StartAnimation(nameof(Visual.Opacity), glow);

            if (!reduced)
            {
                var swell = _compositor.CreateVector3KeyFrameAnimation();
                swell.InsertKeyFrame(0f, new Vector3(0.55f, 0.55f, 1f));
                swell.InsertKeyFrame(0.3f, new Vector3(1.15f, 1.15f, 1f), _easeOut);
                swell.InsertKeyFrame(1f, new Vector3(1.35f, 1.35f, 1f), _easeOut);
                swell.Duration = TimeSpan.FromMilliseconds(duration);
                swell.DelayTime = TimeSpan.FromMilliseconds(delayMs);
                halo.StartAnimation(nameof(Visual.Scale), swell);
            }
        }

        if (node.Dendrites is { } dendrites && node.DendriteBrush is { } dendriteBrush)
        {
            dendriteBrush.Color = color;
            var branch = _compositor.CreateScalarKeyFrameAnimation();
            branch.InsertKeyFrame(0f, 0f);
            branch.InsertKeyFrame(0.3f, 0.7f, _linear);
            branch.InsertKeyFrame(1f, 0f, _easeOut);
            branch.Duration = TimeSpan.FromMilliseconds(duration + 180);
            branch.DelayTime = TimeSpan.FromMilliseconds(delayMs + 40);
            dendrites.StartAnimation(nameof(Visual.Opacity), branch);
        }

        if (!reduced)
        {
            var pop = _compositor.CreateVector3KeyFrameAnimation();
            pop.InsertKeyFrame(0f, Vector3.One);
            pop.InsertKeyFrame(0.25f, new Vector3(1.9f, 1.9f, 1f), _easeOut);
            pop.InsertKeyFrame(1f, Vector3.One, _easeOut);
            pop.Duration = TimeSpan.FromMilliseconds(duration);
            pop.DelayTime = TimeSpan.FromMilliseconds(delayMs);
            node.Core.StartAnimation(nameof(Visual.Scale), pop);
        }
    }

    private static Color ColorFor(BrainPulseKind kind) => kind switch
    {
        BrainPulseKind.Error => Color.FromArgb(255, 0xF3, 0x61, 0x64),
        BrainPulseKind.Degraded => Color.FromArgb(255, 0xDA, 0xA3, 0x41),
        BrainPulseKind.Dominant => SignalColor,
        _ => PrimaryColor,
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
