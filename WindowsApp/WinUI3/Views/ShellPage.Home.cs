using Jarvis.ControlHub.WinUI.Adapters;
using Jarvis.ControlHub.WinUI.Icons;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Shapes;
using Windows.UI;

namespace Jarvis.ControlHub.WinUI.Views;

/// <summary>
/// Home nach Lovable-Final (foundation-workspace.tsx, memory-foundation.tsx, styles.css .jx-home). Maße in DIP
/// entsprechen den im Browser gemessenen CSS-Pixeln. Zustände und Details stammen aus Supervisor und Web-API.
/// </summary>
public sealed partial class ShellPage
{
    private const double StageMaxHeight = 576;          // .jx-brain max-height 36rem
    private const double StageMaxWidth = 960;           // .jx-brain width min(100%, 60rem)
    private const double CompactGridWidth = 1172.8;     // Umbruch bei 75rem Fensterbreite abzüglich Canvas-Padding

    private UIElement BuildHome()
    {
        // Ein Raster wie .jx-home: drei Spalten, Inhalt in Zeile 0 füllt die Höhe, darunter die Command Surface.
        // Abstände zwischen Zeilen kommen über Ränder, damit leere Zeilen keinen Abstand erzeugen.
        var grid = new Grid { ColumnSpacing = 12 };
        _homeGrid = grid;
        for (var i = 0; i < 3; i++) grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < 2; i++) grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var primary = Comp(RuntimeComponents.Primary);
        var expert = Comp(RuntimeComponents.Expert);
        var voice = Comp(RuntimeComponents.VoiceDaemon);
        var stt = Comp(RuntimeComponents.Stt);
        var tts = Comp(RuntimeComponents.Chatterbox);

        var left = new StackPanel { Spacing = 12 };
        left.Children.Add(JxModule("Cpu", "RUNTIME SUMMARY", StatusChipView.Create(_snapshot?.State ?? "UNAVAILABLE").Root, JxSlots(
            JxSlot("Cpu", "PRIMARY", DetailOr(primary, "Primärmodell", "Primärmodell. Keine Runtime-Quelle."), primary.Text),
            JxSlot("Sparkles", "EXPERT", DetailOr(expert, "Expertenmodell. On-demand.", "Expertenmodell. On-demand. Keine Quelle."), expert.Text),
            JxSlot("Server", "Lokale Ausführung", _snapshot is null ? "Keine Runtime-Quelle" : "Runtime Supervisor", _snapshot?.State ?? "UNAVAILABLE", last: true))));
        left.Children.Add(JxModule("AudioLines", "VOICE & AUDIO", StatusChipView.Create(voice.Text).Root, JxSlots(
            JxSlot("Ear", "Wake Word", DetailOr(voice, "Voice-Daemon Listener", "Keine Audio-Quelle"), voice.Text),
            JxSlot("Mic", "STT", DetailOr(stt, "Spracherkennung", "Spracherkennung. Keine Quelle."), stt.Text),
            JxSlot("Volume2", "TTS", DetailOr(tts, "Sprachausgabe", "Sprachausgabe. Keine Quelle."), tts.Text, last: true))));

        var brain = JxModule("BrainCircuit", "MEMORY & THINKING", JxTag("NO LIVE DATA"), BuildBrainStage(), strong: true);
        brain.MinHeight = 480;

        var right = new StackPanel { Spacing = 12 };
        right.Children.Add(JxModule("Shield", "PRIVACY & CONTROL", JxTag("KEINE QUELLE"), JxSlots(
            JxSlot("Mic", "Mikrofon", "Keine autoritative Quelle", "UNAVAILABLE"),
            JxSlot("Camera", "Kamera", "Keine autoritative Quelle", "UNAVAILABLE"),
            JxSlot("Monitor", "Screen", "Keine autoritative Quelle", "UNAVAILABLE"),
            JxSlot("Clipboard", "Clipboard", "Keine autoritative Quelle", "UNAVAILABLE", last: true)),
            foot: "Freigaben erteilt ausschließlich das Backend. Diese Oberfläche kann keine Berechtigung setzen."));
        right.Children.Add(JxModule("Cloud", "CLOUD & NETZWERK", null, JxSlots(
            JxSlot("Cloud", "Cloud-Freigabe", "Keine Quelle. Keine implizite Freigabe.", "UNAVAILABLE"),
            JxSlot("Wrench", "Remote Tools", "Keine autoritative Quelle", "UNAVAILABLE", last: true))));
        var memory = Web(WebEndpoint.MemorySummary);
        right.Children.Add(JxModule("Network", "SYSTEMQUELLEN", null, JxSlots(
            JxSlot("Database", "Memory-Quelle", memory.IsReady ? "Memory-Zusammenfassung erreichbar" : memory.State == Domain.RuntimeState.Offline ? "Web-API nicht erreichbar" : "Nicht verbunden", memory.IsReady ? "READY" : StateText(memory)),
            JxSlot("Smartphone", "Mobile Connection", "Kein Gerätevertrag", MobileStateText(), last: true))));

        // Mitte: Brain füllt die Resthöhe, Recent Activity sitzt darunter (Lovable: Gridbereiche mem und act).
        var mid = new Grid { RowSpacing = 12 };
        mid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        mid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var activity = BuildActivity();
        Grid.SetRow(activity, 1);
        mid.Children.Add(brain);
        mid.Children.Add(activity);
        var command = BuildCommand();

        grid.Children.Add(left);
        grid.Children.Add(mid);
        grid.Children.Add(right);
        grid.Children.Add(command);

        void Arrange(double width)
        {
            var compact = width < CompactGridWidth;
            // Breit füllt der Inhalt die Höhe (1fr), kompakt bestimmt der Inhalt die Zeilen (grid-template-rows: auto).
            grid.RowDefinitions[0].Height = compact ? GridLength.Auto : new GridLength(1, GridUnitType.Star);
            grid.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) : new GridLength(312);
            grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
            grid.ColumnDefinitions[2].Width = compact ? new GridLength(0) : new GridLength(336);
            Put(mid, compact ? 0 : 1, 0, compact ? 2 : 1);
            Put(left, 0, compact ? 1 : 0, 1);
            Put(right, compact ? 1 : 2, compact ? 1 : 0, 1);
            Put(command, 0, compact ? 2 : 1, 3);
            var gap = new Thickness(0, 12, 0, 0);
            left.Margin = compact ? gap : new Thickness(0);
            right.Margin = compact ? gap : new Thickness(0);
            command.Margin = gap;
        }

        Arrange(double.MaxValue);
        grid.SizeChanged += (_, args) => Arrange(args.NewSize.Width);
        ApplyHomeMinHeight();
        return grid;
    }

    private static void Put(FrameworkElement element, int column, int row, int columnSpan)
    {
        Grid.SetColumn(element, column);
        Grid.SetRow(element, row);
        Grid.SetColumnSpan(element, columnSpan);
    }

    /// <summary>Backend-Detail hat Vorrang; ohne gemeldete Komponente steht der Referenztext mit "Keine Quelle".</summary>
    /// <summary>TEST-ONLY: wiederholt die Verifikationssequenz für Screenshot-Capture, bis die App endet.</summary>
    private static async Task RunBrainTestLoopAsync(BrainActivityRenderer renderer)
    {
        while (true)
        {
            await renderer.RunTestSequenceAsync();
            await Task.Delay(900);
        }
    }

    /// <summary>TEST-ONLY: wiederholt ein einzelnes Ereignis mit Pause, bis die Stage wieder Idle ist.</summary>
    private static async Task RunBrainSingleLoopAsync(BrainActivityRenderer renderer)
    {
        while (true)
        {
            renderer.RaiseTestSingle();
            await Task.Delay(BrainActivityRenderer.ActiveHoldMs + 2500);
        }
    }

    private static string DetailOr(ComponentReading reading, string described, string withoutSource) =>
        !reading.Reported ? withoutSource : reading.Detail.Length > 0 ? reading.Detail : described;

    // ---- .jx-module -------------------------------------------------------------------------------------------

    private static Border JxModule(string kind, string title, UIElement? right, UIElement body, bool strong = false, string? foot = null)
    {
        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(41.6) });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        if (foot is not null) root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var header = new Grid
        {
            Padding = new Thickness(14.4, 0, 14.4, 0),
            ColumnSpacing = 8.8,
            BorderBrush = Brush("JarvisHeadDividerBrush"),
            BorderThickness = new Thickness(0, 0, 0, 1),
        };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var icon = Lucide(kind, 16, "JarvisSignalBrush");
        icon.VerticalAlignment = VerticalAlignment.Center;
        header.Children.Add(icon);
        var heading = new TextBlock
        {
            Text = title,
            FontSize = 11.52,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            CharacterSpacing = 60,
            Foreground = Brush("JarvisHeaderBrush"),
            VerticalAlignment = VerticalAlignment.Center,
            TextTrimming = TextTrimming.CharacterEllipsis,
        };
        Grid.SetColumn(heading, 1);
        header.Children.Add(heading);
        if (right is FrameworkElement rightElement)
        {
            Grid.SetColumn(rightElement, 2);
            header.Children.Add(rightElement);
        }

        root.Children.Add(header);
        if (body is FrameworkElement bodyElement)
        {
            Grid.SetRow(bodyElement, 1);
            root.Children.Add(bodyElement);
        }

        if (foot is not null)
        {
            var note = new TextBlock
            {
                Text = foot,
                FontSize = 11.52,
                LineHeight = 16.8,
                TextWrapping = TextWrapping.Wrap,
                Foreground = Brush("JarvisMutedTextBrush"),
                Margin = new Thickness(14.4, 0, 14.4, 12),
            };
            Grid.SetRow(note, 2);
            root.Children.Add(note);
        }

        var module = new Border
        {
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush(strong ? "JarvisLineStrongBrush" : "JarvisLineBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Child = root,
            MinWidth = 0,
        };
        AutomationProperties.SetName(module, title);
        return module;
    }

    private static StackPanel JxSlots(params UIElement[] rows)
    {
        var panel = new StackPanel { Padding = new Thickness(8, 4, 8, 4) };
        foreach (var row in rows) panel.Children.Add(row);
        return panel;
    }

    /// <summary>.jx-slot: Icon-Kachel, Label mit Detailzeile, Status-Chip rechts.</summary>
    private static UIElement JxSlot(string kind, string label, string detail, string state, bool last = false)
    {
        var row = new Grid
        {
            MinHeight = 56,
            ColumnSpacing = 11.2,
            Padding = new Thickness(6.4, 9.6, 6.4, 9.6),
            BorderBrush = Brush("JarvisDividerBrush"),
            BorderThickness = new Thickness(0, 0, 0, last ? 0 : 1),
        };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(33.6) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        row.Children.Add(SlotIcon(kind));

        var text = new StackPanel { VerticalAlignment = VerticalAlignment.Center, Spacing = 1.6 };
        text.Children.Add(new TextBlock
        {
            Text = label,
            FontSize = 12.8,
            LineHeight = 18.4,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = Brush("JarvisTextBrush"),
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        text.Children.Add(new TextBlock
        {
            Text = detail,
            FontSize = 11.2,
            LineHeight = 16.8,
            TextWrapping = TextWrapping.Wrap,
            Foreground = Brush("JarvisMutedTextBrush"),
        });
        Grid.SetColumn(text, 1);
        row.Children.Add(text);

        var chip = StatusChipView.Create(state).Root;
        chip.VerticalAlignment = VerticalAlignment.Center;
        Grid.SetColumn(chip, 2);
        row.Children.Add(chip);
        return row;
    }

    /// <summary>.jx-slot-icon: 2.1rem-Kachel, Icon 18 in Sekundärfarbe (Farbe trägt Bedeutung erst bei Kopf, Aktiv und Hover).</summary>
    private static Border SlotIcon(string kind, double size = 33.6, double glyph = 18, string brushKey = "JarvisSecondaryTextBrush", string borderKey = "JarvisSlotIconBorderBrush")
    {
        var icon = Lucide(kind, glyph, brushKey);
        icon.HorizontalAlignment = HorizontalAlignment.Center;
        icon.VerticalAlignment = VerticalAlignment.Center;
        return new Border
        {
            Width = size,
            Height = size,
            VerticalAlignment = VerticalAlignment.Center,
            CornerRadius = new CornerRadius(5),
            Background = Brush("JarvisQuietBrush"),
            BorderBrush = Brush(borderKey),
            BorderThickness = new Thickness(1),
            Child = icon,
        };
    }

    // ---- Memory & Thinking ------------------------------------------------------------------------------------

    private static readonly string[] ActivationChannels =
        ["Memory-Abruf", "Kontextaufbau", "Routing", "Werkzeugauswahl", "Modellaktivität", "Antworterzeugung"];

    private BrainActivityRenderer? _brainActivity;

    private UIElement BuildBrainStage()
    {
        // Layer 1: Stage-Hintergrund (dunkle Grundfläche, radialer Tiefeneffekt kommt aus JarvisStageBrush/Fade unten).
        var stage = new Grid { Background = Brush("JarvisStageBrush"), MinHeight = 438 };

        // Layer 2: Brain-Asset. Original-Lovable-Asset (bytegleich, per Hash geprüft), Anatomie/Ausschnitt unverändert.
        var image = new Image
        {
            Source = new BitmapImage(new Uri("ms-appx:///Resources/jarvis-brain-idle.jpg")),
            Stretch = Stretch.Uniform,
            MaxWidth = StageMaxWidth,
            MaxHeight = StageMaxHeight,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetName(image, "Räumliche Gehirnstruktur im Ruhezustand, statisches Asset ohne Live-Daten");
        stage.Children.Add(image);

        // Bildrahmen: exakt deckungsgleich mit dem gerenderten Asset (Stretch=Uniform). Lässt die Bildkanten weich
        // in die Stage-Farbe auslaufen, damit auch bei Letterboxing keine Rechteckkante sichtbar wird. Das Gehirn
        // selbst (x 0.19..0.78, y 0.09..0.83 des Assets) liegt vollständig innerhalb der transparenten Zone.
        var imageFrame = new Grid
        {
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            IsHitTestVisible = false,
            Width = image.MaxWidth,
            Height = image.MaxHeight,
        };
        imageFrame.Children.Add(EdgeBand(new(0, 0), new(0, 1), 0.075, 1));      // oben
        imageFrame.Children.Add(EdgeBand(new(0, 0), new(1, 0), 0.13, 1));       // links
        imageFrame.Children.Add(EdgeBand(new(1, 0), new(0, 0), 0.13, 1));       // rechts
        // Unten: läuft ab dem Hirnstamm aus.
        imageFrame.Children.Add(EdgeBand(new(0, 1), new(0, 0), 0.18, 0.85));
        // Der eingebrannte Bodenreflex (konzentrische Ringe, y 0.77..0.95 des Assets) wird flächig in die Stage
        // zurückgenommen, damit kein HUD-/Plattform-Eindruck entsteht. Asset-Bytes bleiben unverändert.
        var floor = new RadialGradientBrush
        {
            Center = new Windows.Foundation.Point(0.5, 0.885),
            GradientOrigin = new Windows.Foundation.Point(0.5, 0.885),
            RadiusX = 0.46,
            RadiusY = 0.125,
        };
        floor.GradientStops.Add(new GradientStop { Color = Color.FromArgb(238, 1, 4, 8), Offset = 0.0 });
        floor.GradientStops.Add(new GradientStop { Color = Color.FromArgb(215, 1, 4, 8), Offset = 0.6 });
        floor.GradientStops.Add(new GradientStop { Color = Color.FromArgb(0, 1, 4, 8), Offset = 1.0 });
        imageFrame.Children.Add(new Border { Background = floor, IsHitTestVisible = false });
        stage.Children.Add(imageFrame);

        // Randauslauf wie Lovable (mask-image radial-gradient 62% 64%, opak bis 58%), bezogen auf die Bildbox
        // width min(100%, 60rem) x max-height 36rem, nicht auf die gesamte Stage.
        var fade = new RadialGradientBrush
        {
            Center = new Windows.Foundation.Point(0.5, 0.5),
            GradientOrigin = new Windows.Foundation.Point(0.5, 0.5),
            RadiusX = 0.62,
            RadiusY = 0.64,
        };
        fade.GradientStops.Add(new GradientStop { Color = Color.FromArgb(0, 1, 4, 8), Offset = 0.58 });
        fade.GradientStops.Add(new GradientStop { Color = Color.FromArgb(255, 1, 4, 8), Offset = 1.0 });
        stage.Children.Add(new Border { Background = fade, MaxWidth = StageMaxWidth, MaxHeight = StageMaxHeight, IsHitTestVisible = false });

        // Stage-Tiefe wie Lovable (.jx-brain-stage: radial-gradient ellipse 60% 55% at 50% 48%, primary 10% ->
        // transparent 70%). In Lovable scheint sie per mix-blend-mode: screen durch die dunklen Bildbereiche;
        // nativ liegt sie darum als sehr schwacher Schleier über Asset und Auslauf.
        var depth = new RadialGradientBrush
        {
            Center = new Windows.Foundation.Point(0.5, 0.48),
            GradientOrigin = new Windows.Foundation.Point(0.5, 0.48),
            RadiusX = 0.6,
            RadiusY = 0.55,
        };
        depth.GradientStops.Add(new GradientStop { Color = Color.FromArgb(26, 0x00, 0xA2, 0xF5), Offset = 0.0 });
        depth.GradientStops.Add(new GradientStop { Color = Color.FromArgb(0, 0x00, 0xA2, 0xF5), Offset = 0.7 });
        stage.Children.Add(new Border { Background = depth, IsHitTestVisible = false });

        // Layer 3+4: Neural Graph und Live Activity. Deckungsgleich mit dem Bild (gleiche Center-Ausrichtung,
        // Breite/Höhe folgen der tatsächlichen Bildgröße), damit die Koordinaten normalisiert (0..1) bleiben.
        var activityHost = new Border
        {
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            IsHitTestVisible = false,
            Width = image.MaxWidth,
            Height = image.MaxHeight,
        };
        stage.Children.Add(activityHost);
        void SyncActivityHostSize(object? _, object? __)
        {
            if (image.ActualWidth > 0) activityHost.Width = imageFrame.Width = image.ActualWidth;
            if (image.ActualHeight > 0) activityHost.Height = imageFrame.Height = image.ActualHeight;
        }
        image.SizeChanged += (s, e) => SyncActivityHostSize(s, e);

        var legend = new StackPanel { Spacing = 4 };
        legend.Children.Add(OverlayTitle("AKTIVIERUNGSKANÄLE"));
        var channelMarks = new Ellipse[ActivationChannels.Length];
        for (var i = 0; i < ActivationChannels.Length; i++)
        {
            var line = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
            var mark = new Grid { Width = 8, Height = 8, VerticalAlignment = VerticalAlignment.Center };
            mark.Children.Add(new Ellipse { Stroke = Brush("JarvisUnavailableBrush"), StrokeThickness = 1 });
            // Füllung erscheint nur kurz, wenn ein echtes (oder als TEST markiertes) Ereignis diesen Kanal anspricht.
            channelMarks[i] = new Ellipse { Fill = new SolidColorBrush(Color.FromArgb(255, 0x00, 0xC0, 0xEE)), Opacity = 0 };
            mark.Children.Add(channelMarks[i]);
            line.Children.Add(mark);
            line.Children.Add(new TextBlock { Text = ActivationChannels[i], FontSize = 11.52, Foreground = Brush("JarvisSecondaryTextBrush") });
            legend.Children.Add(line);
        }

        legend.Children.Add(OverlayNote("Nur bei echten Backend-Ereignissen. Derzeit keine."));
        stage.Children.Add(Overlay(legend, HorizontalAlignment.Left, 208));

        var idle = new StackPanel();
        var statusTitle = OverlayTitle("IDLE. UNAVAILABLE.");
        var statusNote = OverlayNote("Statischer Entwurf ohne Runtime-Events. Keine Gedanken, Memories oder Aktivität werden simuliert.");
        idle.Children.Add(statusTitle);
        idle.Children.Add(statusNote);
        stage.Children.Add(Overlay(idle, HorizontalAlignment.Right, 240));

        // Home (und damit die Brain Stage) wird beim Start mehrfach neu aufgebaut: einmal synchron, dann erneut,
        // sobald Web-Daten eintreffen (RenderSection läuft je Domain-Refresh neu). Jeder Aufbau bekommt frische
        // Elemente, darum wird der Renderer bei JEDEM Loaded dieses konkreten Hosts neu erzeugt (nicht über
        // BuildBrainStage-Aufrufe hinweg gecacht) und ein "started"-Flag verhindert nur die Doppelausführung des
        // eigenen Loaded-Events. Ältere, aus dem Baum entfernte Hosts feuern zwar noch ihr eigenes Loaded/SizeChanged,
        // ihr Renderer bleibt aber unsichtbar und ungenutzt, da niemand mehr auf ihn verweist.
        var started = false;
        activityHost.Loaded += (_, _) =>
        {
            if (started) return;
            started = true;
            SyncActivityHostSize(null, null);
            var renderer = new BrainActivityRenderer(image, activityHost);
            _brainActivity = renderer;

            // Status-Overlay folgt ausschließlich dem Renderer-Zustand. Ohne Ereignisse bleibt der Lovable-Text stehen.
            renderer.ModeChanged += (active, isTest) =>
            {
                statusTitle.Text = !active ? "IDLE. UNAVAILABLE." : isTest ? "AKTIV. TESTSEQUENZ." : "AKTIV.";
                statusNote.Text = !active
                    ? "Statischer Entwurf ohne Runtime-Events. Keine Gedanken, Memories oder Aktivität werden simuliert."
                    : isTest
                        ? "Markierte Verifikationssequenz (TEST-ONLY). Keine Runtime-Ereignisse."
                        : "Beobachtete Systemereignisse. Keine Gedanken oder Chain-of-Thought.";
            };
            renderer.Raised += activityEvent =>
            {
                if (Domain.BrainActivityMapper.Channel(activityEvent.Type) is { } channel) PulseChannel(channelMarks[(int)channel]);
            };

            // TEST-ONLY Verifikationspfad: läuft ausschließlich, wenn diese Umgebungsvariable explizit gesetzt ist.
            // Beim normalen Produktionsstart ist sie nicht gesetzt, die Stage bleibt vollständig Idle.
            // "1" spielt die Sequenz einmal ab (Idle-vorher/-nachher-Nachweis), "loop" wiederholt sie für
            // Screenshot-Capture, "single" löst wiederholt genau ein einzelnes Ereignis aus.
            var testMode = Environment.GetEnvironmentVariable("JARVIS_BRAIN_TEST_SEQUENCE");
            if (testMode == "1") _ = renderer.RunTestSequenceAsync();
            else if (testMode == "loop") _ = RunBrainTestLoopAsync(renderer);
            else if (testMode == "single") _ = RunBrainSingleLoopAsync(renderer);
        };

        return stage;
    }

    private static Border Overlay(UIElement content, HorizontalAlignment side, double width) => new()
    {
        HorizontalAlignment = side,
        VerticalAlignment = VerticalAlignment.Bottom,
        Width = width,
        Margin = new Thickness(14.4),
        Padding = new Thickness(12.8, 10.4, 12.8, 10.4),
        Background = Brush("JarvisOverlayBrush"),
        BorderBrush = Brush("JarvisLineBrush"),
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(6),
        Child = content,
    };

    /// <summary>Linearer Kantenauslauf in die Stage-Farbe: voll deckend an der Kante, transparent nach <paramref name="depth"/>.</summary>
    private static Border EdgeBand(Windows.Foundation.Point from, Windows.Foundation.Point to, double depth, double strength)
    {
        var brush = new LinearGradientBrush { StartPoint = from, EndPoint = to };
        brush.GradientStops.Add(new GradientStop { Color = Color.FromArgb((byte)(255 * strength), 1, 4, 8), Offset = 0 });
        brush.GradientStops.Add(new GradientStop { Color = Color.FromArgb(0, 1, 4, 8), Offset = depth });
        return new Border { Background = brush, IsHitTestVisible = false };
    }

    /// <summary>Kanalmarke leuchtet kurz auf und klingt aus (Compositor-Animation auf dem Element-Visual).</summary>
    private static void PulseChannel(UIElement mark)
    {
        var visual = Microsoft.UI.Xaml.Hosting.ElementCompositionPreview.GetElementVisual(mark);
        var pulse = visual.Compositor.CreateScalarKeyFrameAnimation();
        pulse.InsertKeyFrame(0f, 0f);
        pulse.InsertKeyFrame(0.15f, 0.9f);
        pulse.InsertKeyFrame(1f, 0f);
        pulse.Duration = TimeSpan.FromMilliseconds(1400);
        visual.StartAnimation("Opacity", pulse);
    }

    private static TextBlock OverlayTitle(string text) => new()
    {
        Text = text,
        FontSize = 11.52,
        FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
        Foreground = Brush("JarvisTextBrush"),
    };

    private static TextBlock OverlayNote(string text) => new()
    {
        Text = text,
        FontSize = 11.52,
        LineHeight = 16.8,
        TextWrapping = TextWrapping.Wrap,
        Foreground = Brush("JarvisMutedTextBrush"),
        Margin = new Thickness(0, 4.8, 0, 0),
    };

    // ---- Recent Activity --------------------------------------------------------------------------------------

    private Border BuildActivity()
    {
        var events = Web(WebEndpoint.EventsRecent);
        var info = events.As<EventsInfo>();
        UIElement body;
        UIElement? right;
        if (info is { Items.Count: > 0 })
        {
            var rows = new StackPanel { Padding = new Thickness(15.2, 8, 15.2, 8), Spacing = 6 };
            foreach (var item in info.Items.Take(3)) rows.Children.Add(ActivityRow(item));
            body = rows;
            right = JxTag($"{info.Items.Count} EVENTS · 24 H");
        }
        else if (events.IsReady)
        {
            body = ActivityNote("Keine Live-Aktivität verfügbar. Keine Ereignisse in den letzten 24 Stunden.");
            right = JxTag("NO LIVE DATA");
        }
        else
        {
            var reason = events.State == Domain.RuntimeState.Offline ? "Ereignisquelle OFFLINE: Web-API nicht erreichbar." : Note(events);
            body = ActivityNote("Keine Live-Aktivität verfügbar. " + reason);
            right = StatusChipView.Create(StateText(events)).Root;
        }

        return JxModule("Activity", "RECENT ACTIVITY", right, body);
    }

    private static UIElement ActivityNote(string text)
    {
        var row = new Grid { Padding = new Thickness(15.2, 12.8, 15.2, 12.8), ColumnSpacing = 9.6 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var icon = Lucide("Activity", 16, "JarvisMutedTextBrush");
        icon.VerticalAlignment = VerticalAlignment.Center;
        row.Children.Add(icon);
        var label = new TextBlock
        {
            Text = text,
            FontSize = 11.84,
            LineHeight = 17.6,
            TextWrapping = TextWrapping.Wrap,
            Foreground = Brush("JarvisMutedTextBrush"),
            VerticalAlignment = VerticalAlignment.Center,
        };
        Grid.SetColumn(label, 1);
        row.Children.Add(label);
        return row;
    }

    private static UIElement ActivityRow(EventItem item)
    {
        var row = new Grid { ColumnSpacing = 9.6 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.Children.Add(new TextBlock
        {
            Text = $"{item.Time.ToLocalTime():HH:mm:ss} · {item.Event}",
            FontSize = 11.84,
            Foreground = Brush("JarvisSecondaryTextBrush"),
            TextTrimming = TextTrimming.CharacterEllipsis,
            VerticalAlignment = VerticalAlignment.Center,
        });
        var severity = JxTag(item.Severity.ToUpperInvariant());
        Grid.SetColumn(severity, 1);
        row.Children.Add(severity);
        return row;
    }

    // ---- Command / Conversation Surface -----------------------------------------------------------------------

    private static Grid BuildCommand() =>
        BuildCommand("Nachricht an J.A.R.V.I.S …", "Chat ist NOT_IMPLEMENTED. Senden deaktiviert.", inset: true);

    /// <summary>
    /// .jx-command: Mikrofon 57.6, Feld 57.6 als Pille, Hinweis darunter. <paramref name="inset"/> = Home mit 12 %
    /// Innenabstand je Seite; sonst .jx-command-inline (Chat) über die volle Breite.
    /// </summary>
    private static Grid BuildCommand(string placeholder, string noteText, bool inset)
    {
        var outer = new Grid { MinHeight = 79.7 };
        AutomationProperties.SetName(outer, "Conversation / Command");
        outer.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(inset ? 0.12 : 0, GridUnitType.Star) });
        outer.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(inset ? 0.76 : 1, GridUnitType.Star) });
        outer.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(inset ? 0.12 : 0, GridUnitType.Star) });

        var root = new Grid { ColumnSpacing = 12 };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var mic = new Button
        {
            Content = Lucide("Mic", 20, "JarvisMutedTextBrush"),
            Width = 57.6,
            Height = 57.6,
            Padding = new Thickness(0),
            CornerRadius = new CornerRadius(28.8),
            IsEnabled = false,
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush("JarvisLineBrush"),
            BorderThickness = new Thickness(1),
        };
        AutomationProperties.SetName(mic, "Spracheingabe, deaktiviert");
        root.Children.Add(mic);

        var field = new Grid
        {
            MinHeight = 57.6,
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush("JarvisLineStrongBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(28.8),
            Padding = new Thickness(19.2, 0, 8, 0),
        };
        field.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        field.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var input = new TextBox
        {
            PlaceholderText = placeholder,
            IsEnabled = false,
            BorderThickness = new Thickness(0),
            Background = new SolidColorBrush(Color.FromArgb(0, 0, 0, 0)),
            FontSize = 14.72,
            VerticalAlignment = VerticalAlignment.Center,
            UseSystemFocusVisuals = true,
        };
        AutomationProperties.SetName(input, "Befehl oder Nachricht an J.A.R.V.I.S");
        field.Children.Add(input);
        var send = new Button
        {
            Content = Lucide("Send", 20, "JarvisMutedTextBrush"),
            Width = 43.2,
            Height = 43.2,
            Padding = new Thickness(0),
            CornerRadius = new CornerRadius(21.6),
            IsEnabled = false,
            Opacity = 0.7,
            Background = Brush("JarvisBackgroundBrush"),
            BorderBrush = Brush("JarvisBorderBrush"),
            BorderThickness = new Thickness(1),
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetName(send, "Senden, deaktiviert");
        Grid.SetColumn(send, 1);
        field.Children.Add(send);
        Grid.SetColumn(field, 1);
        root.Children.Add(field);

        var note = new TextBlock
        {
            Text = noteText,
            FontSize = 11.52,
            Foreground = Brush("JarvisMutedTextBrush"),
            Margin = new Thickness(19.2, 4.8, 0, 0),
        };
        Grid.SetColumn(note, 1);
        Grid.SetRow(note, 1);
        root.Children.Add(note);

        Grid.SetColumn(root, 1);
        outer.Children.Add(root);
        return outer;
    }
}
