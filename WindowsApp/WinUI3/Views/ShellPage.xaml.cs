using System.Globalization;
using Jarvis.ControlHub.WinUI.Adapters;
using Jarvis.ControlHub.WinUI.Domain;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.UI;

namespace Jarvis.ControlHub.WinUI.Views;

public sealed partial class ShellPage : Page
{
    // Titel, Untertitel und Icon je Bereich wie Page in Lovable pages.tsx; das Icon entspricht dem Navigationseintrag.
    private static readonly IReadOnlyDictionary<string, (string Title, string Description, string Icon)> Sections =
        new Dictionary<string, (string, string, string)>
        {
            ["Home"] = ("Home", "Persönliche Runtime-Übersicht", "Home"),
            ["Chat"] = ("Chat", "Lokaler Dialog. Kontextgesteuerte Verarbeitung.", "BotMessageSquare"),
            ["Memory"] = ("Memory", "Langzeitgedächtnis. Retrieval. Herkunft.", "BrainCircuit"),
            ["ModelsRuntime"] = ("Models & Runtime", "Lokale Modelle. Lifecycle. Routing.", "Cpu"),
            ["VoiceAudio"] = ("Voice & Audio", "Sprachpipeline. Geräte. Diagnose.", "AudioLines"),
            ["Tools"] = ("Tools & Integrations", "Werkzeuge. Skills. MCP. Berechtigungen.", "SlidersHorizontal"),
            ["Automations"] = ("Automations", "Trigger. Aktionen. Zeitpläne.", "Workflow"),
            ["Vision"] = ("Vision & Presence", "Kamera. Präsenz. Bewegung.", "Eye"),
            ["Mobility"] = ("Mobility / VVS", "Verkehr. Verbindungen. Fahrplankontext.", "Route"),
            ["Mobile"] = ("Mobile Connection", "Geräte- und App-Verbindung. Getrennt von Mobility / VVS.", "Smartphone"),
            ["Observability"] = ("Observability", "Zustand. Ereignisse. Logs. Diagnose.", "Activity"),
            ["Settings"] = ("Settings", "Native Desktop-Konfiguration.", "Settings"),
        };

    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(60);
    private static readonly TimeSpan WebFreshness = TimeSpan.FromSeconds(20);

    private readonly Jarvis.ControlHub.RuntimeSupervisorClient _supervisor = new();
    private readonly BackendHub _backend = new();
    private readonly Dictionary<BackendDomain, DateTimeOffset> _webLoadedAt = [];
    private readonly HashSet<BackendDomain> _webLoading = [];
    private string? _repositoryRoot;
    private Jarvis.ControlHub.RuntimeSnapshot? _snapshot;
    private string? _snapshotRoot;
    private bool _refreshing;
    private CancellationTokenSource? _lifetime;
    private DispatcherTimer? _pollTimer;
    private Border? _settingsDetailHost;
    private readonly List<Button> _settingsNavButtons = [];
    private int _selectedSettingsGroup;
    private BrainEventBridge? _brainBridge;

    public FrameworkElement TitleBarDragRegion => Wordmark;

    public ShellPage()
    {
        InitializeComponent();
        Wordmark.Source = new BitmapImage(new Uri("ms-appx:///Resources/jarvis-wordmark.png"));
        BuildSystemGroups();
        SystemNavItem.Loaded += (_, _) => HideBuiltInChevron(SystemNavItem);
        PageScroll.SizeChanged += (_, _) => ApplyHomeMinHeight();
        AttachHeaderLayout();
        Navigation.SelectedItem = Navigation.MenuItems[0];
        RenderSection("Home");
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private string CurrentSection => Navigation.SelectedItem is NavigationViewItem { Tag: string tag } ? tag : "Home";

    private static BackendDomain? DomainOf(string section) => section switch
    {
        "Home" => BackendDomain.Home,
        "Chat" => BackendDomain.Chat,
        "Memory" => BackendDomain.Memory,
        "ModelsRuntime" => BackendDomain.Models,
        "VoiceAudio" => BackendDomain.Voice,
        "Tools" => BackendDomain.Tools,
        "Automations" => BackendDomain.Automations,
        "Vision" => BackendDomain.Vision,
        "Observability" => BackendDomain.Observability,
        "Settings" => BackendDomain.Settings,
        _ => null,
    };

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        _lifetime?.Cancel();
        _lifetime?.Dispose();
        _lifetime = new CancellationTokenSource();
        if (_pollTimer is null)
        {
            _pollTimer = new DispatcherTimer { Interval = PollInterval };
            _pollTimer.Tick += OnPollTick;
        }

        _pollTimer.Start();
        StartBrainBridge(_lifetime.Token);
        await RefreshRuntimeAsync();
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
    {
        _pollTimer?.Stop();
        _brainBridge = null;
        _lifetime?.Cancel();
        _lifetime?.Dispose();
        _lifetime = null;
    }

    private async void OnPollTick(object? sender, object args)
    {
        if (!_refreshing) await RefreshRuntimeAsync();
    }

    private void OnSelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItem is NavigationViewItem item && item.Tag is string section)
        {
            UpdateNavIcons();
            ShowSection(section);
        }
    }

    private void ShowSection(string section)
    {
        RenderSection(section);
        _ = LoadWebDataAsync(section, force: false);
    }

    private async Task LoadWebDataAsync(string section, bool force)
    {
        if (DomainOf(section) is not { } domain || _lifetime is not { } lifetime) return;
        if (!force && _webLoadedAt.TryGetValue(domain, out var loadedAt) && DateTimeOffset.Now - loadedAt < WebFreshness) return;
        if (!_webLoading.Add(domain)) return;
        try
        {
            await _backend.RefreshAsync(domain, lifetime.Token);
            _webLoadedAt[domain] = DateTimeOffset.Now;
        }
        catch (OperationCanceledException)
        {
            return;
        }
        finally
        {
            _webLoading.Remove(domain);
        }

        if (CurrentSection == section) RenderSection(section);
    }

    private void RenderSection(string section)
    {
        if (!Sections.TryGetValue(section, out var page)) return;
        SectionTitle.Text = page.Title;
        SectionDescription.Text = page.Description;
        SectionIcon.Kind = page.Icon;
        // Home hat keinen Seitenkopf; Settings trägt den Kopf im Detailbereich (Lovable .jx-settings, .jx-set-head).
        SectionHeader.Visibility = section is "Home" or "Settings" ? Visibility.Collapsed : Visibility.Visible;
        PageBody.Children.Clear();
        PageBody.Children.Add(section switch
        {
            "Home" => BuildHome(),
            "Chat" => BuildChat(),
            "Memory" => BuildMemory(),
            "ModelsRuntime" => BuildModels(),
            "VoiceAudio" => BuildVoice(),
            "Tools" => BuildTools(),
            "Automations" => BuildAutomations(),
            "Vision" => BuildVision(),
            "Mobility" => BuildMobility(),
            "Mobile" => BuildMobile(),
            "Observability" => BuildObservability(),
            "Settings" => BuildSettings(),
            _ => new Grid(),
        });
    }

    // ---- Quellen: Supervisor-Komponenten und Web-API-Lesungen -------------------------------------------------

    private ComponentReading Comp(string id) => RuntimeComponents.Find(_snapshot, id);

    private WebReading Web(WebEndpoint endpoint) => _backend.Get(endpoint);

    private static string StateText(WebReading reading) =>
        ReferenceEquals(reading, WebReading.NotQueried) ? "UNAVAILABLE" : RuntimeStateText.ToDisplayText(reading.State);

    private static string Note(WebReading reading) =>
        ReferenceEquals(reading, WebReading.NotQueried) ? "Wird abgefragt …" : reading.Message;

    // Einzelfelder ohne lesbare Quelle sind UNAVAILABLE: der Zustand der Quelle steht im Panel-Badge und in der Meldung.
    private static string Field(WebReading reading, string? value) =>
        reading.IsReady && !string.IsNullOrWhiteSpace(value) ? value : "UNAVAILABLE";

    private static string Field(WebReading reading, long? value) =>
        reading.IsReady ? (value?.ToString(CultureInfo.CurrentCulture) ?? "UNAVAILABLE") : "UNAVAILABLE";

    private static string Field(WebReading reading, bool? value) =>
        reading.IsReady && value is { } flag ? (flag ? "ENABLED" : "DISABLED") : "UNAVAILABLE";

    private static string FieldPercent(WebReading reading, double? value) =>
        reading.IsReady && value is { } percent ? BackendParsers.FormatPercent(percent) : "UNAVAILABLE";

    private static string FieldBytes(WebReading reading, long? value) =>
        !reading.IsReady ? "UNAVAILABLE"
        : value is not { } bytes ? "UNAVAILABLE"
        : bytes >= 1_048_576 ? (bytes / 1_048_576d).ToString("0.#", CultureInfo.InvariantCulture) + " MB"
        : bytes >= 1024 ? (bytes / 1024d).ToString("0.#", CultureInfo.InvariantCulture) + " KB"
        : bytes.ToString(CultureInfo.InvariantCulture) + " B";

    private static string TimeText(DateTimeOffset? value) => value?.ToLocalTime().ToString("HH:mm:ss", CultureInfo.InvariantCulture) ?? "UNAVAILABLE";

    private static string MobileStateText() => MobileConnectionAdapter.StateText(MobileConnectionAdapter.Current.State);

    // ---- Seiten ----------------------------------------------------------------------------------------------

    private UIElement BuildChat()
    {
        var stats = Web(WebEndpoint.Stats);
        var sessions = Web(WebEndpoint.Sessions);
        var statsInfo = stats.As<StatsInfo>();
        var model = Field(stats, statsInfo?.Model);
        var memory = stats.IsReady && statsInfo?.MemoryVectors is { } vectors ? $"{vectors} Vektoren" : "UNAVAILABLE";
        var tools = stats.IsReady && statsInfo?.SkillsLoaded is { } skills ? $"{skills} Skills" : "UNAVAILABLE";

        var grid = NewGrid(2, 1, 12, 0);
        grid.Height = 610;
        grid.ColumnDefinitions[0].Width = new GridLength(270);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        UIElement sessionsBody = sessions.IsReady
            ? Vertical(StateValue("Sitzungen", Field(sessions, sessions.As<SessionsInfo>()?.Total)), Caption("Nur die Anzahl aus dem Backend. Kein Verlauf geladen."))
            : StatusEmpty(sessions);
        Place(grid, Vertical(
            Panel("History", "SITZUNGEN", sessions.IsReady ? "READY" : StateText(sessions), sessionsBody),
            Panel("GitBranch", "VERARBEITUNGSKONTEXT", StateText(stats), Vertical(
                StateValue("Modell", model), StateValue("Memory", memory), StateValue("Tools", tools),
                Divider(), Caption("Kontext wird nur vom Backend zusammengestellt.")))), 0, 0);

        var conversation = new Grid { RowSpacing = 0 };
        conversation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        conversation.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        conversation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        conversation.Children.Add(Panel("MessageSquare", "J.A.R.V.I.S ARBEITSFLÄCHE", "NOT_IMPLEMENTED", Horizontal(
            StateValue("Modell", model), StateValue("Memory", memory), StateValue("Tools", tools))));
        var empty = new Border
        {
            Margin = new Thickness(0, 12, 0, 12),
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush("JarvisBorderBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Child = CenteredEmpty("NOT_IMPLEMENTED", "Arbeitsfläche ohne Sitzung", "Kein vom Supervisor verwalteter Chat-Endpunkt. Der einzige Chat-Pfad (/ws in jarvis_web.py) gehört zu einem separaten, nicht überwachten Web-Prozess und ist von hier nicht verifiziert."),
        };
        Grid.SetRow(empty, 1);
        conversation.Children.Add(empty);
        var composer = BuildCommand("Nachricht an J.A.R.V.I.S …", "Eingabe und Senden deaktiviert: Chat ist NOT_IMPLEMENTED.", inset: false);
        Grid.SetRow((FrameworkElement)composer, 2);
        conversation.Children.Add(composer);
        Place(grid, conversation, 1, 0);
        return grid;
    }

    private UIElement BuildMemory()
    {
        var summary = Web(WebEndpoint.MemorySummary);
        var desktop = Web(WebEndpoint.Desktop);
        var memory = summary.As<MemoryInfo>();
        var config = desktop.As<DesktopInfo>();

        var grid = NewGrid(2, 2, 12, 12);
        grid.Height = 720;
        grid.ColumnDefinitions[0].Width = new GridLength(1.7, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(0.8, GridUnitType.Star);
        grid.RowDefinitions[0].Height = new GridLength(1, GridUnitType.Star);
        grid.RowDefinitions[1].Height = new GridLength(230);
        var stage = new Grid { Height = 385, Background = Brush("JarvisQuietBrush") };
        var memoryBrainImage = new Image { Source = new BitmapImage(new Uri("ms-appx:///Resources/jarvis-brain-idle.jpg")), Stretch = Stretch.Uniform, Opacity = 0.92, HorizontalAlignment = HorizontalAlignment.Stretch, VerticalAlignment = VerticalAlignment.Stretch };
        AutomationProperties.SetName(memoryBrainImage, "Statisches Brain-Asset im Ruhezustand");
        stage.Children.Add(memoryBrainImage);
        // Hinweisfläche wie auf Home (.jx-overlay .jx-idle): gleicher Rand, gleiche Deckung, gleiche Typografie.
        stage.Children.Add(Overlay(new StackPanel { Children = { OverlayTitle("IDLE · NO LIVE DATA"), OverlayNote("Aktivierung nur bei echten Retrieval-Ereignissen. Keine Gedanken oder Chain-of-Thought.") } }, HorizontalAlignment.Right, 240));
        Place(grid, Panel("BrainCircuit", "MEMORY GRAPH", "NO LIVE DATA", Vertical(stage, SearchSurface("Memory durchsuchen", false), Caption("Suche deaktiviert: kein Such-Endpunkt im Desktop-Vertrag."))), 0, 0);

        var storeRows = new List<UIElement>
        {
            StateValue("Fakten", Field(summary, memory?.FactsTotal)),
            StateValue("Interaktionen (7 T)", Field(summary, memory?.Interactions7d)),
            Divider(),
            StateValue("FAISS-Vektoren", Field(summary, memory?.FaissVectors)),
            StateValue("FAISS-Größe", FieldBytes(summary, memory?.FaissBytes)),
            StateValue("Kontext-Fenster", FieldPercent(summary, memory?.ContextUsagePercent)),
        };
        if (memory?.PartialError is { } partial) storeRows.Add(Caption($"Backend meldet Teilfehler in: {partial}."));
        if (!summary.IsReady) storeRows.Add(Caption(Note(summary)));
        Place(grid, Panel("HeartPulse", "MEMORY-ZUSTAND", StateText(summary), Compact(storeRows.ToArray())), 0, 1);

        UIElement categories = !summary.IsReady
            ? StatusEmpty(summary)
            : memory is { FactsByCategory.Count: > 0 }
                ? Compact(memory.FactsByCategory.Take(10).Select(item => StateValue(item.Key, item.Value.ToString(CultureInfo.CurrentCulture))).ToArray())
                : Empty("Keine Fakten in der Datenbank.");
        Place(grid, Panel("Layers", "FAKTEN NACH KATEGORIE", StateText(summary), categories), 1, 0);

        Place(grid, Panel("Shield", "PRIVACY & CONTROL", "BACKEND OWNED", Compact(
            StateValue("Aufnahme-Gate", "UNAVAILABLE"),
            StateValue("Konversations-Memory", Field(desktop, config?.MemoryEnabled)),
            StateValue("Proaktives Surfacing", Field(desktop, config?.MemoryProactive)),
            StateValue("Kontext-Fenster", Field(desktop, config?.ContextWindowEnabled)),
            Caption("Nur lesend. Änderungen werden durch das Backend gesteuert."))), 1, 1);
        return grid;
    }

    private UIElement BuildModels()
    {
        var stats = Web(WebEndpoint.Stats);
        var desktop = Web(WebEndpoint.Desktop);
        var statsInfo = stats.As<StatsInfo>();
        var config = desktop.As<DesktopInfo>();
        var primary = Comp(RuntimeComponents.Primary);
        var expert = Comp(RuntimeComponents.Expert);
        var stt = Comp(RuntimeComponents.Stt);
        var tts = Comp(RuntimeComponents.Chatterbox);
        var small = Comp(RuntimeComponents.SmallLlm);

        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 640;
        grid.RowDefinitions[0].Height = new GridLength(250);
        grid.ColumnDefinitions[0].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.85, GridUnitType.Star);
        Place(grid, Panel("Cpu", "PRIMÄRMODELL", primary.Text, Compact(
            LargeState("PRIMARY", primary.Text), Divider(),
            StateValue("Modell", Field(stats, statsInfo?.Model)),
            StateValue("Endpunkt", Field(desktop, config?.LlmEndpoint)),
            StateValue("Kontextgröße", Field(desktop, config?.LlmContextSize)),
            Caption(primary.Detail.Length > 0 ? primary.Detail : "Dauerhafte Rolle. Modellname und Endpoint nur aus dem Backend."))), 0, 0);
        Place(grid, Panel("Sparkles", "EXPERTENMODELL", expert.Text, Compact(
            LargeState("EXPERT", expert.Text), Divider(),
            StateValue("Modell", "UNAVAILABLE"),
            Caption(expert.Detail.Length > 0 ? expert.Detail : "On-demand. STOPPED ist ein gültiger Zustand."))), 1, 0);
        Place(grid, Panel("AudioLines", "SPRACHMODELLE", "READ ONLY", Compact(
            StateValue("STT", stt.Text),
            StateValue("STT-Modell", Field(desktop, config?.SttModel)),
            StateValue("TTS", tts.Text),
            StateValue("Small-LLM", small.Text),
            Divider(),
            Caption(stt.Detail.Length > 0 ? stt.Detail : "Zustände vom Runtime Supervisor."))), 2, 0);
        var lifecycle = Panel("RefreshCw", "RUNTIME LIFECYCLE", "SUPERVISOR CONTROLLED", Vertical(
            RuntimeStateView(),
            FlowStrip(("Timer", "STARTING", "Wird angefordert"), ("Gauge", "READY", "Backend bestätigt"), ("TriangleAlert", "DEGRADED", "Teilfunktion fehlt"), ("Play", "STOPPED", "Bewusst beendet")),
            Horizontal(ActionButton("Starten", _snapshot?.CanStart == true, OnStartClick), ActionButton("Stoppen", _snapshot?.CanStop == true, OnStopClick), ActionButton("Neu starten", _snapshot?.CanRestart == true, OnRestartClick)),
            Caption("Aktionen sind nur bei freigegebener Supervisor-Capability aktiv.")));
        Grid.SetColumnSpan(lifecycle, 2);
        Place(grid, lifecycle, 0, 1);
        var sources = Compact(RuntimeComponents.Distinct(_snapshot).Select(item => StateValue(item.Name, RuntimeStateText.ToDisplayText(RuntimeComponents.ParseState(item.State)))).ToArray());
        Place(grid, Panel("Server", "RUNTIME-DIENSTE", _snapshot?.State ?? "UNAVAILABLE", _snapshot is null ? StatusEmpty("UNAVAILABLE", "Runtime Supervisor nicht verbunden.") : sources), 2, 1);
        return grid;
    }

    private UIElement BuildVoice()
    {
        var desktop = Web(WebEndpoint.Desktop);
        var events = Web(WebEndpoint.EventsRecent);
        var config = desktop.As<DesktopInfo>();
        var daemon = Comp(RuntimeComponents.VoiceDaemon);
        var tts = Comp(RuntimeComponents.Chatterbox);
        var bridge = Comp(RuntimeComponents.AudioBridge);

        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 640;
        grid.RowDefinitions[0].Height = new GridLength(250);
        grid.ColumnDefinitions[0].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.9, GridUnitType.Star);
        var pipeline = Panel("Workflow", "VOICE PIPELINE", "NO LIVE DATA", Vertical(
            FlowStrip(("Mic", "Mikrofon", "Eingang"), ("Ear", "Wake Word", "Oder Direct Audio"), ("FileText", "STT", "Spracherkennung"), ("Cpu", "Modell", "Antwort"), ("Volume2", "TTS", "Sprachausgabe"), ("Speaker", "Ausgabe", "Lautsprecher")),
            Divider(), Caption("Ablaufdarstellung. Keine Pegel, Aufnahmen oder aktiven Schritte ohne Audio-Backend.")));
        Grid.SetColumnSpan(pipeline, 3);
        Place(grid, pipeline, 0, 0);
        Place(grid, Panel("Mic", "EINGABE", daemon.Text, Compact(
            StateValue("Listener", daemon.Text),
            StateValue("Wake Word", Field(desktop, config?.WakeKeyword)),
            StateValue("Eingabegerät", Field(desktop, config?.InputDevice)),
            StateValue("STT-Backend", Field(desktop, config?.SttBackend)),
            SearchSurface("Eingabegerät wählen", false),
            Caption(daemon.Detail.Length > 0 ? daemon.Detail : "Gerätewahl nur über die Backend-Konfiguration (lesend)."))), 0, 1);
        Place(grid, Panel("Speaker", "AUSGABE", tts.Text, Compact(
            StateValue("Stimme", Field(desktop, config?.TtsEngine)),
            StateValue("TTS", tts.Text),
            StateValue("Ausgabe-Backend", Field(desktop, config?.OutputBackend)),
            StateValue("Audio-Brücke", bridge.Text),
            SearchSurface("Ausgabegerät wählen", false),
            Caption(bridge.Detail.Length > 0 ? bridge.Detail : tts.Detail.Length > 0 ? tts.Detail : "Keine lokale Geräteliste angezeigt."))), 1, 1);
        var voiceEvents = events.As<EventsInfo>()?.Items.Where(IsVoiceEvent).Take(4).ToList();
        UIElement eventBody = voiceEvents is { Count: > 0 }
            ? Compact(voiceEvents.Select(EventLine).ToArray())
            : events.IsReady ? Empty("Keine Audio-Ereignisse in den letzten 24 Stunden.") : StatusEmpty(events);
        Place(grid, Panel("Shield", "PRIVACY & DIAGNOSE", "BACKEND OWNED", Compact(
            StateValue("Mikrofon-Gate", "UNAVAILABLE"), StateValue("Aufnahme", "UNAVAILABLE"), Divider(),
            eventBody, ActionButton("Pipeline testen", false, OnRefreshClick))), 2, 1);
        return grid;
    }

    private UIElement BuildTools()
    {
        var desktop = Web(WebEndpoint.Desktop);
        var config = desktop.As<DesktopInfo>();

        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 640;
        grid.RowDefinitions[0].Height = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[0].Width = new GridLength(1.5, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(0.85, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.85, GridUnitType.Star);

        UIElement inventory;
        string inventoryBadge;
        if (!desktop.IsReady)
        {
            inventory = StatusEmpty(desktop);
            inventoryBadge = StateText(desktop);
        }
        else if (config is { Tools.Count: > 0 })
        {
            var rows = new StackPanel { Spacing = 0 };
            foreach (var tool in config.Tools)
            {
                rows.Children.Add(TableRow(tool.Id, tool.Skill ?? "kein Skill", tool.Registered ? "REGISTERED" : "NO HANDLER"));
            }

            inventory = Vertical(TableHeader("Werkzeug", "Skill", "Handler"), Divider(), Scrollable(rows, 470));
            inventoryBadge = $"{config.Tools.Count} TOOLS";
        }
        else
        {
            inventory = CenteredEmpty("NO LIVE DATA", "Kein Inventar", "Das Backend meldet keine registrierten Tools.");
            inventoryBadge = "NO LIVE DATA";
        }

        Place(grid, Panel("Wrench", "WERKZEUGINVENTAR", inventoryBadge, inventory), 0, 0);

        var capabilityRows = new List<UIElement>();
        if (config is not null)
        {
            (string Key, string Label)[] labels =
            [
                ("reminders", "Erinnerungen"), ("calendar", "Kalender"), ("news", "News"), ("weather", "Wetter"),
                ("memory", "Memory"), ("contextWindow", "Kontext-Fenster"), ("metrics", "Metriken"),
            ];
            foreach (var (key, label) in labels)
            {
                capabilityRows.Add(StateValue(label, config.Capabilities.TryGetValue(key, out var loaded) ? (loaded ? "LOADED" : "NOT LOADED") : "UNAVAILABLE"));
            }

            capabilityRows.Add(Divider());
            capabilityRows.Add(StateValue("Skills aktiv", $"{config.Skills.Count(skill => skill.Enabled)} / {config.Skills.Count}"));
        }
        else
        {
            capabilityRows.Add(StatusEmpty(desktop));
        }

        capabilityRows.Add(Caption("Nur Initialisierungsstatus aus dem Backend, keine Berechtigungen angenommen."));
        Place(grid, Panel("Puzzle", "CAPABILITIES", StateText(desktop), Compact(capabilityRows.ToArray())), 1, 0);
        Place(grid, Panel("Plug", "INTEGRATIONEN", StateText(desktop), Compact(
            StateValue("Lokale API", StateText(desktop)), StateValue("MCP", "UNAVAILABLE"), StateValue("Cloud", "UNAVAILABLE"),
            Caption(desktop.IsReady ? "Keine weitere Integration vom Backend gemeldet." : Note(desktop)))), 2, 0);
        var path = Panel("GitBranch", "AUSFÜHRUNGSWEG", "BACKEND GATED", FlowStrip(
            ("MessageSquare", "Anfrage", "Aus Chat oder Automation"), ("ShieldCheck", "Berechtigung", "Gate im Backend"), ("Wrench", "Ausführung", "Lokal oder remote"), ("ListChecks", "Ergebnis", "Autoritatives Ereignis")));
        Grid.SetColumnSpan(path, 3);
        Place(grid, path, 0, 1);
        return grid;
    }

    private UIElement BuildAutomations()
    {
        var automations = Web(WebEndpoint.Automations);
        var agents = Web(WebEndpoint.Agents);
        var info = automations.As<AutomationsInfo>();
        var planner = agents.As<PlannerInfo>();

        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 590;
        grid.RowDefinitions[0].Height = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[0].Width = new GridLength(1.45, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(0.9, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.8, GridUnitType.Star);

        UIElement table;
        string tableBadge;
        if (!automations.IsReady)
        {
            table = Vertical(TableHeader("Name", "Trigger", "Zeitplan", "Letzter Lauf", "Zustand"), Divider(), StatusEmpty(automations));
            tableBadge = StateText(automations);
        }
        else if (info is { Schedulers.Count: > 0 })
        {
            var rows = new StackPanel { Spacing = 0 };
            foreach (var scheduler in info.Schedulers)
            {
                var trigger = scheduler.Owner is null ? "Scheduler" : $"Scheduler · {scheduler.Owner}";
                rows.Children.Add(TableRow(scheduler.Id, trigger, scheduler.Schedule, LastRunText(scheduler.LastRunAt), scheduler.State));
            }

            table = Vertical(TableHeader("Name", "Trigger", "Zeitplan", "Letzter Lauf", "Zustand"), Divider(), rows,
                Caption("System-eigene Scheduler des Backends. Es gibt keine nutzerdefinierten Regeln. BACKEND OWNED = gehört dem Voice-Daemon, sein Zustand ist hier nicht bekannt; das ist nicht 'disabled'."));
            tableBadge = $"{info.Schedulers.Count} SCHEDULER";
        }
        else
        {
            table = CenteredEmpty("NO LIVE DATA", "Keine Scheduler", "Das Backend meldet keine Scheduler.");
            tableBadge = "NO LIVE DATA";
        }

        Place(grid, Panel("AlarmClock", "AUTOMATIONEN", tableBadge, table), 0, 0);
        Place(grid, Panel("FileText", "DETAIL", "NOT_IMPLEMENTED", Vertical(
            LargeState("REGELDETAIL", "NOT_IMPLEMENTED"), StateValue("Aktiviert", "UNAVAILABLE"), StateValue("Trigger", "UNAVAILABLE"),
            StateValue("Aktion", "UNAVAILABLE"), Divider(), Caption("Keine Regel-Engine im Backend."), ActionButton("Jetzt ausführen", false, OnRefreshClick))), 1, 0);
        var plannerOwned = agents.IsReady && planner is { Available: false } && planner.State == "BACKEND OWNED";
        UIElement plannerBody = plannerOwned
            ? StatusEmpty("BACKEND OWNED", "Der Planner gehört dem Voice-Daemon. Der Desktop-Web-Prozess hat keinen Planner-Status; ein lokaler Leerlauf wird nicht als Systemzustand gezeigt.")
            : agents.IsReady && planner is { Implausible: true }
            ? StatusEmpty(planner.State, "Backend meldet diesen Planner-Zustand. Die Oberfläche zeigt keine Schrittzahlen, weil Flags oder Zähler der Antwort nicht zum Backend-Vertrag passen (Prüfung im Client).")
            : planner is { Available: true } && agents.IsReady
            ? Compact(
                StateValue("Zustand", planner.Available ? planner.State : "UNAVAILABLE"),
                StateValue("Schritte", planner.Steps.ToString(CultureInfo.CurrentCulture)),
                StateValue("Abgeschlossen", planner.Completed.ToString(CultureInfo.CurrentCulture)),
                StateValue("Laufend", planner.Running.ToString(CultureInfo.CurrentCulture)),
                StateValue("Fehlgeschlagen", planner.Failed.ToString(CultureInfo.CurrentCulture)),
                StateValue("Ausstehend", planner.Pending.ToString(CultureInfo.CurrentCulture)))
            : StatusEmpty(agents);
        Place(grid, Panel("ListChecks", "TASK-PLANER", plannerOwned ? "BACKEND OWNED" : StateText(agents), plannerBody), 2, 0);
        var workflow = Panel("Workflow", "ABLAUF EINER AUTOMATION", "CONCEPTUAL FLOW", FlowStrip(
            ("AlarmClock", "Trigger", "Zeit, Ereignis, Befehl"), ("Filter", "Bedingung", "Optional"), ("Play", "Aktion", "Tool oder Antwort"), ("ShieldCheck", "Bestätigung", "Richtlinie im Backend")));
        Grid.SetColumnSpan(workflow, 3);
        Place(grid, workflow, 0, 1);
        return grid;
    }

    private UIElement BuildVision()
    {
        var webcam = Web(WebEndpoint.Webcam);
        var camera = webcam.As<WebcamInfo>();
        var npu = Comp(RuntimeComponents.Npu);

        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 600;
        grid.RowDefinitions[0].Height = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[0].Width = new GridLength(1.5, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(0.9, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.8, GridUnitType.Star);
        // Viewport: ruhige Fläche mit normalem Rand. UNAVAILABLE ist kein Fehler, deshalb kein roter OFFLINE-Rand.
        var viewport = Panel("Camera", "KAMERAFLÄCHE", "UNAVAILABLE", CenteredEmpty("UNAVAILABLE", "Keine Kameraquelle", "Kein Kamerabild. Die Oberfläche aktiviert die Kamera nicht und zeigt keine Frames; Freigaben bleiben beim Backend."));
        viewport.Background = Brush("JarvisQuietBrush");
        Place(grid, viewport, 0, 0);
        Place(grid, Panel("Hand", "PRESENCE", "UNAVAILABLE", Vertical(
            LargeState("PRESENCE", "UNAVAILABLE"), StateValue("Belegung", "UNAVAILABLE"), StateValue("Bewegung", "UNAVAILABLE"),
            StateValue("Letztes Ereignis", "NO LIVE DATA"), Caption("Das Backend stellt keine bestätigte Belegung bereit."))), 1, 0);
        var frameServer = webcam.IsReady && camera is { Available: true } ? "AVAILABLE" : "UNAVAILABLE";
        Place(grid, Panel("Radar", "SENSORIK", npu.Text, Compact(
            StateValue("Kamera-Frameserver", frameServer),
            StateValue("NPU", npu.Text),
            StateValue("Weitere Sensoren", "UNAVAILABLE"),
            Divider(), StateValue("Privacy-Gate", "UNAVAILABLE"),
            Caption(npu.Detail.Length > 0 ? npu.Detail : "Geräte- und Gate-Zustand nur aus Backend."))), 2, 0);
        var flow = Panel("GitBranch", "ERKENNUNGSWEG", "CONCEPTUAL", FlowStrip(
            ("Camera", "Kamera", "Gate erforderlich"), ("Cpu", "Erkennung", "Lokal"), ("Hand", "Presence", "Anwesenheit"), ("Activity", "Ereignis", "An Automations")));
        Grid.SetColumnSpan(flow, 3);
        Place(grid, flow, 0, 1);
        return grid;
    }

    private UIElement BuildMobility()
    {
        var vvs = Comp(RuntimeComponents.Vvs);
        var stack = Vertical();
        stack.Children.Add(Panel("Search", "VERBINDUNGSSUCHE", "NOT_IMPLEMENTED", Vertical(Horizontal(
            SearchSurface("Start", false), SearchSurface("Ziel", false), ActionButton("Verbindungen suchen", false, OnRefreshClick)),
            Caption("Keine Verbindungsabfrage über das Backend für den Desktop; nur der VVS-Dienstzustand ist angebunden."))));
        var grid = NewGrid(3, 1, 12, 0);
        grid.Height = 440;
        grid.ColumnDefinitions[0].Width = new GridLength(1.5, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(0.85, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.85, GridUnitType.Star);
        Place(grid, Panel("Route", "VERBINDUNGEN", "NO LIVE DATA", Vertical(
            TableHeader("Linie", "Abfahrt", "Ankunft", "Hinweis"), Divider(),
            CenteredEmpty("NO LIVE DATA", "Keine Abfahrten", "Keine Echtzeitdaten. Es werden keine Verbindungen oder Zeiten erfunden."))), 0, 0);
        Place(grid, Panel("MapPin", "ROUTEN UND VERKEHRSKONTEXT", "UNAVAILABLE", CenteredEmpty("UNAVAILABLE", "Keine Route", "Routen- und Standortkontext werden vom Mobility-Backend geliefert.")), 1, 0);
        Place(grid, Panel("Bus", "VVS-DATENQUELLE", vvs.Text, Vertical(
            StateValue("Dienst", vvs.Text), StateValue("Aktualisiert", TimeText(_snapshot?.UpdatedAt)), StateValue("Standort", "UNAVAILABLE"),
            Divider(), Caption(vvs.Detail.Length > 0 ? vvs.Detail : vvs.Reported ? "VVS bleibt auf dieser Seite getrennt von Mobile Connection." : "Vom Supervisor nicht gemeldet (Mobility deaktiviert oder nicht konfiguriert)."))), 2, 0);
        stack.Children.Add(grid);
        return stack;
    }

    private UIElement BuildMobile()
    {
        var mobile = MobileStateText();
        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 590;
        grid.RowDefinitions[0].Height = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[0].Width = new GridLength(1.2, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.85, GridUnitType.Star);
        var pairing = Panel("Link2", "PAIRING", mobile, CenteredEmpty(mobile, "Pairing nicht verfügbar", "Kein Pairing-Vertrag im Backend. Es wird kein QR-Code, Token oder Gerätezustand erzeugt."));
        pairing.BorderBrush = Brush("JarvisUnavailableBrush");
        Place(grid, pairing, 0, 0);
        Place(grid, Panel("Smartphone", "GERÄTE", "NO LIVE DATA", Vertical(
            TableHeader("Gerät", "Zustand", "Letzter Kontakt"), Divider(), Empty("Es liegen keine Gerätedaten vor."))), 1, 0);
        Place(grid, Panel("Send", "VERBINDUNG", mobile, Vertical(
            LargeState("MOBILE LINK", mobile), StateValue("Pairing", mobile), StateValue("Befehle", "UNAVAILABLE"),
            StateValue("Handoff", "UNAVAILABLE"),
            Caption("Backend kennt nur einen browserbasierten Kamera-Relay (jarvis_web.py), keine native App-Verbindung."))), 2, 0);
        var security = Panel("GitBranch", "KOPPLUNGSABLAUF", "NO PAIRING", FlowStrip(
            ("Search", "Gerät finden", "Nur lokal"), ("Fingerprint", "Bestätigen", "Am Gerät"), ("Lock", "Autorisieren", "Backend-owned"), ("Smartphone", "Verbinden", "Nur nach Bestätigung")));
        Grid.SetColumnSpan(security, 3);
        Place(grid, security, 0, 1);
        return grid;
    }

    private UIElement BuildObservability()
    {
        var events = Web(WebEndpoint.EventsRecent);
        var aggregate = Web(WebEndpoint.EventsAggregate);
        var summary = Web(WebEndpoint.MemorySummary);
        var info = events.As<EventsInfo>();
        var memory = summary.As<MemoryInfo>();
        var daemon = Comp(RuntimeComponents.VoiceDaemon);

        var grid = NewGrid(3, 2, 12, 12);
        grid.Height = 640;
        grid.RowDefinitions[0].Height = new GridLength(160);
        grid.ColumnDefinitions[0].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(1, GridUnitType.Star);
        Place(grid, Panel("HeartPulse", "RUNTIME-ZUSTAND", _snapshot?.State ?? "UNAVAILABLE", Compact(
            StateValue("Supervisor", _snapshot?.State ?? "UNAVAILABLE"),
            StateValue("Komponenten", _snapshot?.Components.Count.ToString() ?? "UNAVAILABLE"),
            StateValue("Degraded-Gründe", _snapshot?.DegradedReasons.Count().ToString() ?? "UNAVAILABLE"))), 0, 0);
        Place(grid, Panel("AudioLines", "VOICE-ZUSTAND", daemon.Text, Compact(
            StateValue("Listener", daemon.Text), StateValue("TTS", Comp(RuntimeComponents.Chatterbox).Text), StateValue("Audio", Comp(RuntimeComponents.AudioBridge).Text))), 1, 0);
        Place(grid, Panel("Database", "MEMORY-ZUSTAND", StateText(summary), Compact(
            StateValue("Fakten", Field(summary, memory?.FactsTotal)), StateValue("Index", Field(summary, memory?.FaissVectors)),
            StateValue("Speicher", FieldBytes(summary, memory?.FaissBytes)))), 2, 0);

        UIElement eventBody;
        string eventBadge;
        if (info is { Items.Count: > 0 })
        {
            var rows = new StackPanel { Spacing = 0 };
            foreach (var item in info.Items.Take(14))
            {
                rows.Children.Add(TableRow(item.Time.ToLocalTime().ToString("HH:mm:ss", CultureInfo.InvariantCulture), item.Category, item.Event, item.Severity.ToUpperInvariant()));
            }

            var total = aggregate.As<EventsAggregateInfo>()?.Total;
            eventBody = Vertical(TableHeader("Zeit", "Quelle", "Ereignis", "Zustand"), Divider(), rows,
                Caption(total is { } count ? $"{count} Ereignisse in den letzten 24 Stunden (aggregiert)." : "Datenschutz-Projektion des Backends: Kategorie, Ereignisname, Schweregrad."));
            eventBadge = $"{info.Items.Count} EVENTS";
        }
        else if (events.IsReady)
        {
            eventBody = Vertical(TableHeader("Zeit", "Quelle", "Ereignis", "Zustand"), Divider(), CenteredEmpty("NO LIVE DATA", "Keine Ereignisse", "Keine Ereignisse in den letzten 24 Stunden."));
            eventBadge = "NO LIVE DATA";
        }
        else
        {
            UIElement hints = _snapshot is { } snapshot && snapshot.DegradedReasons.Any()
                ? Compact(snapshot.DegradedReasons.Take(4).Select(reason => Caption("Supervisor: " + reason)).ToArray())
                : Caption("Keine Supervisor-Hinweise vorhanden.");
            eventBody = Vertical(TableHeader("Zeit", "Quelle", "Ereignis", "Zustand"), Divider(), StatusEmpty(events), hints);
            eventBadge = StateText(events);
        }

        var eventsPanel = Panel("Activity", "EREIGNISSE", eventBadge, eventBody);
        Grid.SetColumnSpan(eventsPanel, 2);
        Place(grid, eventsPanel, 0, 1);
        Place(grid, Panel("ScrollText", "LOGS", "UNAVAILABLE", Vertical(
            StatusEmpty("UNAVAILABLE", "Live-Ausgabe deaktiviert: weder Supervisor noch Web-API bieten einen strukturierten Log-Vertrag."),
            ActionButton("Logs öffnen", false, OnRefreshClick))), 2, 1);
        return grid;
    }

    // Bereiche wie Lovable settingsGroups (pages.tsx): Lucide-Icon und Bezeichnung je Eintrag der Master-Liste.
    private static readonly (string Label, string Icon)[] SettingsGroups =
    [
        ("Allgemein", "Cog"), ("Darstellung", "Palette"), ("Runtime", "Server"), ("Models", "Cpu"), ("Voice", "AudioLines"),
        ("Memory", "BrainCircuit"), ("Privacy", "Shield"), ("Cloud", "Cloud"), ("Tools", "Wrench"), ("Mobile", "Smartphone"),
        ("Developer / Diagnostics", "Terminal"),
    ];

    private UIElement BuildSettings()
    {
        var grid = NewGrid(2, 1, 12, 0);
        grid.Height = 620;
        grid.ColumnDefinitions[0].Width = new GridLength(224);   // .jx-settings: 14rem Master-Liste
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        _settingsNavButtons.Clear();
        _settingsDetailHost = new Border
        {
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush("JarvisLineBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Child = BuildSettingsDetail(),
        };
        var navContent = new StackPanel { Spacing = 2, Padding = new Thickness(6.4) };
        for (var i = 0; i < SettingsGroups.Length; i++)
        {
            var button = SettingsNavButton(i);
            _settingsNavButtons.Add(button);
            navContent.Children.Add(button);
        }

        ApplySettingsNavState();
        // .jx-settings-nav: eigenes Modul, oben ausgerichtet (align-self: start), scrollt bei geringer Höhe.
        var nav = new Border
        {
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush("JarvisLineBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            VerticalAlignment = VerticalAlignment.Top,
            Child = new ScrollViewer { Content = navContent, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled },
        };
        AutomationProperties.SetName(nav, "Einstellungsbereiche");
        Place(grid, nav, 0, 0);
        Place(grid, _settingsDetailHost, 1, 0);
        return grid;
    }

    /// <summary>.jx-menu-item: Icon 16 und Label mit 0.7rem Abstand; das Icon folgt der Textfarbe (currentColor).</summary>
    private Button SettingsNavButton(int index)
    {
        var (label, icon) = SettingsGroups[index];
        var content = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 11.2 };
        content.Children.Add(new Jarvis.ControlHub.WinUI.Icons.LucideIcon { Kind = icon, Size = 16 });
        content.Children.Add(new TextBlock { Text = label, FontSize = 12.8, VerticalAlignment = VerticalAlignment.Center, TextTrimming = TextTrimming.CharacterEllipsis });
        var button = new Button
        {
            Content = content,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Left,
            Padding = new Thickness(10.4, 8.8, 10.4, 8.8),
            MinHeight = 36,
            CornerRadius = new CornerRadius(4),
            BorderThickness = new Thickness(2, 0, 0, 0),
            UseSystemFocusVisuals = true,
        };
        AutomationProperties.SetName(button, label);
        button.Click += (_, _) => SelectSettingsGroup(index);
        return button;
    }

    /// <summary>Aktiver Eintrag wie .jx-menu-item[data-active]: getönte Fläche, 2-px-Signalkante links, Vordergrundtext.</summary>
    private void ApplySettingsNavState()
    {
        for (var i = 0; i < _settingsNavButtons.Count; i++)
        {
            var active = i == _selectedSettingsGroup;
            var button = _settingsNavButtons[i];
            button.Background = active ? Brush("NavigationViewItemBackgroundSelected") : new SolidColorBrush(Color.FromArgb(0, 0, 0, 0));
            button.BorderBrush = active ? Brush("JarvisSignalBrush") : new SolidColorBrush(Color.FromArgb(0, 0, 0, 0));
            button.Foreground = Brush(active ? "JarvisTextBrush" : "JarvisSecondaryTextBrush");
            AutomationProperties.SetItemStatus(button, active ? "Ausgewählt" : string.Empty);
        }
    }

    private void SelectSettingsGroup(int index)
    {
        _selectedSettingsGroup = index;
        ApplySettingsNavState();
        if (_settingsDetailHost is not null) _settingsDetailHost.Child = BuildSettingsDetail();
    }

    private UIElement BuildSettingsDetail()
    {
        const string backendValue = "Wert nur über das Backend";
        var (group, icon) = SettingsGroups[Math.Clamp(_selectedSettingsGroup, 0, SettingsGroups.Length - 1)];
        var desktop = Web(WebEndpoint.Desktop);
        var config = desktop.As<DesktopInfo>();
        var sttText = !desktop.IsReady
            ? "UNAVAILABLE"
            : string.Join(" / ", new[] { config?.SttBackend, config?.SttModel }.Where(part => !string.IsNullOrWhiteSpace(part))) is { Length: > 0 } stt ? stt : "UNAVAILABLE";
        (string Label, string Hint, string Value)[] rows = group switch
        {
            "Allgemein" => [("Autostart mit Windows", "Startet J.A.R.V.I.S bei der Anmeldung", "NOT_IMPLEMENTED"), ("Beim Start minimiert", "Nur Infobereich", "NOT_IMPLEMENTED"), ("Anzeigesprache", "Folgt der Systemsprache", "Systemstandard")],
            "Darstellung" => [("Darstellungsmodus", "Systemeinstellung", "System"), ("Fenstermaterial", "Nativ vom System", "Mica"), ("Skalierung", "Folgt Windows", "Von Windows verwaltet")],
            "Runtime" => [("Supervisor", "Lokales Steuerskript", "JARVIS-Runtime.ps1"), ("Repository", "Erkannter Main-Checkout", _repositoryRoot ?? "UNAVAILABLE"), ("Lifecycle-Aktionen", "Nur mit Supervisor-Freigabe", "SUPERVISOR OWNED")],
            "Models" => [("LLM-Anbieter", backendValue, Field(desktop, config?.LlmProvider)), ("LLM-Endpunkt", backendValue, Field(desktop, config?.LlmEndpoint)), ("Kontextgröße", backendValue, Field(desktop, config?.LlmContextSize)), ("Routing", "Backend-Richtlinie", "BACKEND OWNED")],
            "Voice" => [("Eingabegerät", "Geräteliste aus dem Backend", Field(desktop, config?.InputDevice)), ("Ausgabe-Backend", backendValue, Field(desktop, config?.OutputBackend)), ("Wake Word", backendValue, Field(desktop, config?.WakeKeyword)), ("STT", backendValue, sttText), ("TTS-Engine", backendValue, Field(desktop, config?.TtsEngine)), ("Sprache", backendValue, Field(desktop, config?.Language))],
            "Memory" => [("Aufnahme", "Gate liegt im Backend", Field(desktop, config?.MemoryEnabled)), ("Proaktives Surfacing", backendValue, Field(desktop, config?.MemoryProactive)), ("Kontext-Fenster", backendValue, Field(desktop, config?.ContextWindowEnabled)), ("Aufbewahrung", "Backend-Richtlinie", "BACKEND OWNED")],
            "Privacy" => [("Mikrofon-Gate", "Gate liegt im Backend", "UNAVAILABLE"), ("Kamera-Gate", "Gate liegt im Backend", "UNAVAILABLE"), ("Clipboard-Gate", "Gate liegt im Backend", "UNAVAILABLE")],
            "Cloud" => [("Cloud-Freigabe", "Gate liegt im Backend", "UNAVAILABLE"), ("Anbieter", backendValue, "UNAVAILABLE")],
            "Tools" => [("Remote Tools", "Gate liegt im Backend", "UNAVAILABLE"), ("Bestätigungsrichtlinie", "Backend-Richtlinie", "BACKEND OWNED")],
            "Mobile" => [("Pairing", "Kein Gerätevertrag", "NOT_IMPLEMENTED"), ("Geräteliste", "Kein Gerätevertrag", "UNAVAILABLE")],
            _ => [("Log-Level", "Backend-Richtlinie", "BACKEND OWNED"), ("Diagnosepaket", "Kein lokaler Vertrag", "NOT_IMPLEMENTED"), ("Live-Ereignisse", "Nur Metadaten aus /api/events/recent", _brainBridge?.SourceState is { } live ? RuntimeStateText.ToDisplayText(live) : "NO LIVE DATA")],
        };

        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        // .jx-set-head: Icon-Kachel, Brotkrumen "Systemeinstellungen", Bereichstitel 1.2rem, rechts die Marke "Nur Backend".
        var head = new Grid { ColumnSpacing = 12, Padding = new Thickness(17.6, 14.4, 17.6, 14.4), BorderBrush = Brush("JarvisLineBrush"), BorderThickness = new Thickness(0, 0, 0, 1) };
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        head.Children.Add(SlotIcon(icon, glyph: 20, brushKey: "JarvisSignalBrush", borderKey: "JarvisLineBrush"));
        var titles = new StackPanel { VerticalAlignment = VerticalAlignment.Center, Spacing = 1.6 };
        titles.Children.Add(new TextBlock { Text = "Systemeinstellungen", FontSize = 12, Foreground = Brush("JarvisMutedTextBrush") });
        titles.Children.Add(new TextBlock { Text = group, FontSize = 19.2, LineHeight = 24, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = Brush("JarvisTextBrush"), TextTrimming = TextTrimming.CharacterEllipsis });
        Grid.SetColumn(titles, 1);
        head.Children.Add(titles);
        var gate = BackendGate();
        Grid.SetColumn(gate, 2);
        head.Children.Add(gate);
        root.Children.Add(head);

        var body = new StackPanel { Padding = new Thickness(17.6, 12, 17.6, 8), Spacing = 0 };
        body.Children.Add(InfoBanner("Werte gehören dem Backend", "Nur lesend. config.yaml gehört dem Backend; es gibt keinen Schreibvertrag mit Validierung, deshalb speichert diese Ansicht nichts."));
        body.Children.Add(new TextBlock
        {
            Text = "KONFIGURATION",
            FontSize = 11.52,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            CharacterSpacing = 40,
            Foreground = Brush("JarvisSecondaryTextBrush"),
            Margin = new Thickness(0, 14.4, 0, 3.2),
        });
        for (var i = 0; i < rows.Length; i++) body.Children.Add(SettingRow(rows[i].Label, rows[i].Hint, rows[i].Value, last: i == rows.Length - 1));
        if (!desktop.IsReady && group is "Models" or "Voice" or "Memory") body.Children.Add(Caption(Note(desktop)));
        var scroll = new ScrollViewer { Content = body, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        Grid.SetRow(scroll, 1);
        root.Children.Add(scroll);

        // .jx-set-foot: Hinweis links, gesperrte Aktionen rechts.
        var foot = new Grid { ColumnSpacing = 16, Padding = new Thickness(17.6, 10.4, 17.6, 10.4), BorderBrush = Brush("JarvisLineBrush"), BorderThickness = new Thickness(0, 1, 0, 0) };
        foot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        foot.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var footNote = Caption("Änderungen werden erst angeboten, wenn ein passender lokaler Vertrag vorhanden ist.");
        footNote.VerticalAlignment = VerticalAlignment.Center;
        foot.Children.Add(footNote);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(ActionButton("Zurücksetzen", false, OnRefreshClick));
        actions.Children.Add(ActionButton("Übernehmen", false, OnRefreshClick));
        Grid.SetColumn(actions, 1);
        foot.Children.Add(actions);
        Grid.SetRow(foot, 2);
        root.Children.Add(foot);
        AutomationProperties.SetName(root, group + ", Systemeinstellungen, nur lesend");
        return root;
    }

    /// <summary>.jx-gate: gesperrte Backend-Hoheit, Schloss-Icon, Cascadia Mono 0.7rem.</summary>
    private static Border BackendGate()
    {
        var content = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6.4, VerticalAlignment = VerticalAlignment.Center };
        var lockIcon = Lucide("LockKeyhole", 14, "JarvisMutedTextBrush");
        lockIcon.VerticalAlignment = VerticalAlignment.Center;
        content.Children.Add(lockIcon);
        content.Children.Add(new TextBlock
        {
            Text = "Nur Backend",
            FontSize = 11.2,
            FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"],
            Foreground = Brush("JarvisMutedTextBrush"),
            VerticalAlignment = VerticalAlignment.Center,
        });
        var gate = new Border
        {
            MinHeight = 30.4,
            Padding = new Thickness(9.6, 0, 9.6, 0),
            VerticalAlignment = VerticalAlignment.Center,
            CornerRadius = new CornerRadius(4),
            BorderBrush = Brush("JarvisBorderBrush"),
            BorderThickness = new Thickness(1),
            Background = Brush("JarvisBackgroundBrush"),
            Child = content,
        };
        AutomationProperties.SetName(gate, "Nur Backend");
        return gate;
    }

    // Aktueller Zustand als Wertegruppe innerhalb des Lifecycle-Panels (kein verschachteltes Panel, Lovable schachtelt keine Module).
    private UIElement RuntimeStateView() => Compact(
        SectionLabel("AKTUELLER ZUSTAND"),
        StateValue("Zustand", _snapshot?.State ?? "UNAVAILABLE"),
        StateValue("Beobachtet", _snapshot?.UpdatedAt?.ToLocalTime().ToString("HH:mm:ss") ?? "UNAVAILABLE"),
        StateValue("Komponenten", _snapshot?.Components.Count.ToString() ?? "UNAVAILABLE"));

    private async void OnRefreshClick(object sender, RoutedEventArgs args) => await RefreshRuntimeAsync();
    private async void OnStartClick(object sender, RoutedEventArgs args) => await RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction.Start);
    private async void OnStopClick(object sender, RoutedEventArgs args) => await RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction.Stop);
    private async void OnRestartClick(object sender, RoutedEventArgs args) => await RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction.Restart);

    private async Task RefreshRuntimeAsync()
    {
        if (_refreshing) return;
        _refreshing = true;
        RefreshButton.IsEnabled = false;
        try
        {
            _repositoryRoot ??= Jarvis.ControlHub.RepositoryRootValidator.DiscoverFrom(AppContext.BaseDirectory);
            if (_repositoryRoot is null)
            {
                SetRuntimeUnavailable("Main-Checkout nicht gefunden");
            }
            else
            {
                var root = _repositoryRoot;
                _snapshot = await _supervisor.GetRuntimeAsync(root);
                _snapshotRoot = root;
                SetRuntimeState(_snapshot.State, _snapshot.Detail.Length > 0 ? _snapshot.Detail : string.Join("; ", _snapshot.DegradedReasons));
            }
        }
        catch (Exception)
        {
            _snapshot = null;
            SetRuntimeUnavailable("Supervisor nicht erreichbar");
        }
        finally
        {
            _refreshing = false;
            RefreshButton.IsEnabled = true;
        }

        RenderSection(CurrentSection);
        await LoadWebDataAsync(CurrentSection, force: true);
    }

    /// <summary>
    /// Fragt den Supervisor für den gewählten Checkout neu ab und prüft dessen Freigabe. Wird vor dem
    /// Bestätigungsdialog und danach erneut aufgerufen, damit keine zwischenzeitlich entzogene Freigabe greift.
    /// </summary>
    private async Task<bool> IsRuntimeActionAllowedAsync(Jarvis.ControlHub.JarvisRuntimeAction action, string root)
    {
        try
        {
            var snapshot = await _supervisor.GetRuntimeAsync(root);
            _snapshot = snapshot;
            _snapshotRoot = root;
        }
        catch (Exception)
        {
            SetRuntimeUnavailable("Supervisor nicht erreichbar");
            return false;
        }

        return RuntimeActionGuard.IsAllowed(action, _snapshot, _snapshotRoot, _repositoryRoot);
    }

    private async Task RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction action)
    {
        var root = _repositoryRoot;
        if (root is null) return;
        if (!await IsRuntimeActionAllowedAsync(action, root))
        {
            RuntimeDetailLabel.Text = "Aktion nicht freigegeben: der soeben abgefragte Supervisor-Zustand dieses Checkouts erlaubt sie nicht.";
            RenderSection(CurrentSection);
            return;
        }

        var actionLabel = action switch
        {
            Jarvis.ControlHub.JarvisRuntimeAction.Start => "Runtime starten",
            Jarvis.ControlHub.JarvisRuntimeAction.Stop => "Runtime stoppen",
            _ => "Runtime neu starten",
        };
        var dialog = new ContentDialog
        {
            Title = actionLabel,
            Content = "Der Runtime Supervisor hat diese Aktion freigegeben. Fortfahren?",
            PrimaryButtonText = "Fortfahren",
            CloseButtonText = "Abbrechen",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = XamlRoot,
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary) return;
        if (!RuntimeActionGuard.RootsMatch(root, _repositoryRoot) || !await IsRuntimeActionAllowedAsync(action, root))
        {
            RuntimeDetailLabel.Text = "Aktion nicht ausgeführt: der Supervisor erlaubt sie nach der Bestätigung nicht mehr, oder der Checkout hat gewechselt.";
            RenderSection(CurrentSection);
            return;
        }

        try
        {
            var result = await _supervisor.RequestActionAsync(action, root);
            RuntimeDetailLabel.Text = result.Accepted ? "Aktion angenommen. Zustand wird neu abgefragt." : "Aktion nicht angenommen.";
            await RefreshRuntimeAsync();
        }
        catch (Exception)
        {
            SetRuntimeUnavailable("Supervisor nicht erreichbar");
        }
    }

    private void SetRuntimeUnavailable(string detail)
    {
        _snapshot = null;
        _snapshotRoot = null;
        SetRuntimeState("UNAVAILABLE", detail);
    }

    private void SetRuntimeState(string state, string detail)
    {
        var text = string.IsNullOrWhiteSpace(state) ? "UNAVAILABLE" : state;
        var message = string.IsNullOrWhiteSpace(detail) ? "Keine Detailmeldung" : detail;
        _runtimeChip?.Set(text);
        RuntimeDetailLabel.Text = message;
        if (_runtimeGroup is not null) ToolTipService.SetToolTip(_runtimeGroup, message);
    }

    // ---- Bausteine ---------------------------------------------------------------------------------------------

    private static bool IsVoiceEvent(EventItem item) =>
        item.Event is "stt_transcription" or "tts_synthesis" or "tts_cache_hit" or "turn_latency" or "speaker_identified"
        || item.Event.StartsWith("watchdog_", StringComparison.Ordinal);

    private static UIElement EventLine(EventItem item) =>
        StateValue($"{item.Time.ToLocalTime().ToString("HH:mm:ss", CultureInfo.InvariantCulture)} · {item.Event}", item.Severity.ToUpperInvariant());

    private static string LastRunText(string? iso) =>
        iso is not null && DateTimeOffset.TryParse(iso, CultureInfo.InvariantCulture, DateTimeStyles.None, out var parsed)
            ? parsed.ToLocalTime().ToString("dd.MM. HH:mm", CultureInfo.InvariantCulture)
            : "NO LIVE DATA";

    private static UIElement StatusEmpty(WebReading reading) => StatusEmpty(StateText(reading), Note(reading));

    private static UIElement StatusEmpty(string state, string message) => StateBlock(state, null, message);

    /// <summary>
    /// .jx-pstate: Lucide-Icon je Zustandsart, deutscher Titel, technischer Hinweis. Icons neutral, nur ERROR und OFFLINE
    /// in Fehlerfarbe, DEGRADED in Warnfarbe (Lovable page-kit.tsx emptyIcon, emptyTitle; styles.css .jx-pstate).
    /// </summary>
    private static UIElement StateBlock(string state, string? title, string message, bool centered = false)
    {
        var (icon, defaultTitle, brushKey) = StateKind(state);
        var row = new Grid
        {
            ColumnSpacing = 11.2,
            Padding = new Thickness(2, 6, 2, 6),
            HorizontalAlignment = centered ? HorizontalAlignment.Center : HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Center,
        };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var glyph = Lucide(icon, 20, brushKey);
        glyph.VerticalAlignment = VerticalAlignment.Center;
        row.Children.Add(glyph);
        var text = new StackPanel { Spacing = 3.2, MaxWidth = 430, VerticalAlignment = VerticalAlignment.Center };
        text.Children.Add(new TextBlock { Text = title ?? defaultTitle, FontSize = 12.48, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = Brush("JarvisSecondaryTextBrush"), TextWrapping = TextWrapping.Wrap });
        text.Children.Add(new TextBlock { Text = message, FontSize = 11.52, LineHeight = 17.6, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap });
        Grid.SetColumn(text, 1);
        row.Children.Add(text);
        AutomationProperties.SetName(row, (title ?? defaultTitle) + ". " + message);
        return row;
    }

    private static (string Icon, string Title, string BrushKey) StateKind(string state) => state switch
    {
        "NOT_IMPLEMENTED" => ("CircleSlash", "Nicht implementiert", "JarvisUnavailableBrush"),
        "OFFLINE" => ("WifiOff", "Offline", "JarvisErrorBrush"),
        "ERROR" => ("TriangleAlert", "Fehler", "JarvisErrorBrush"),
        "DEGRADED" => ("TriangleAlert", "Eingeschränkt", "JarvisDegradedBrush"),
        "STARTING" => ("LoaderCircle", "Wird gestartet", "JarvisInfoBrush"),
        "BACKEND OWNED" => ("LockKeyhole", "Gehört dem Backend", "JarvisUnavailableBrush"),
        "UNAVAILABLE" => ("CloudOff", "Quelle nicht verfügbar", "JarvisUnavailableBrush"),
        _ => ("Inbox", "Keine Einträge", "JarvisUnavailableBrush"),
    };

    private static StackPanel Compact(params UIElement[] children)
    {
        var panel = new StackPanel { Spacing = 6 };
        foreach (var child in children) panel.Children.Add(child);
        return panel;
    }

    private static UIElement Scrollable(UIElement content, double maxHeight) => new ScrollViewer
    {
        Content = content,
        MaxHeight = maxHeight,
        VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
        HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
    };

    private static UIElement TableRow(params string[] cells)
    {
        var grid = new Grid { ColumnSpacing = 10, Margin = new Thickness(2, 3, 2, 3) };
        foreach (var _ in cells) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < cells.Length; i++)
        {
            var isState = i == cells.Length - 1;
            var text = new TextBlock
            {
                Text = cells[i],
                FontSize = 11,
                Foreground = isState ? StateBrush(cells[i]) : Brush("JarvisTextBrush"),
                TextTrimming = TextTrimming.CharacterEllipsis,
                FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources[isState ? "JarvisMonoFontFamily" : "JarvisFontFamily"],
            };
            ToolTipService.SetToolTip(text, cells[i]);
            Grid.SetColumn(text, i);
            grid.Children.Add(text);
        }

        return grid;
    }

    private static Grid NewGrid(int columns, int rows, double columnGap, double rowGap)
    {
        var grid = new Grid { ColumnSpacing = columnGap, RowSpacing = rowGap };
        for (var index = 0; index < columns; index++) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var index = 0; index < rows; index++) grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        return grid;
    }

    private static void Place(Grid grid, UIElement element, int column, int row)
    {
        if (element is FrameworkElement frameworkElement)
        {
            Grid.SetColumn(frameworkElement, column);
            Grid.SetRow(frameworkElement, row);
        }
        grid.Children.Add(element);
    }

    /// <summary>
    /// Panel aller Modulseiten in derselben Sprache wie Home (.jx-module): Kopfzeile 2.6rem mit Lucide-Icon in Signalblau,
    /// Titel in Versalien, rechts Status-Chip oder neutrale Marke; Inhalt mit 0.9rem Seitenabstand wie der Kopf.
    /// </summary>
    private static Border Panel(string icon, string title, string badge, UIElement content)
    {
        var body = new Border { Padding = new Thickness(14.4, 12, 14.4, 14.4), Child = content };
        var module = JxModule(icon, title, Badge(badge), body);
        module.UseLayoutRounding = true;
        return module;
    }

    /// <summary>Runtime-Zustände als .jx-status-Chip; alles andere (NO LIVE DATA, READ ONLY, Zählwerte) als neutrale .jx-tag-Marke.</summary>
    private static UIElement Badge(string text) => IsRuntimeState(text) ? StatusChipView.Create(text).Root : JxTag(text);

    private static bool IsRuntimeState(string text) =>
        text is "READY" or "STARTING" or "DEGRADED" or "ERROR" or "STOPPED" or "OFFLINE" or "NOT_IMPLEMENTED" or "UNAVAILABLE";

    private static Button ActionButton(string label, bool enabled, RoutedEventHandler handler)
    {
        var button = new Button { Content = label, IsEnabled = enabled, Style = ButtonStyle() };
        button.Click += handler;
        return button;
    }

    private static UIElement StateValue(string label, string value) => new Grid
    {
        ColumnDefinitions =
        {
            new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) },
            new ColumnDefinition { Width = GridLength.Auto },
        },
        Children =
        {
            new TextBlock { Text = label, FontSize = 12, Foreground = Brush("JarvisMutedTextBrush"), VerticalAlignment = VerticalAlignment.Center, TextTrimming = TextTrimming.CharacterEllipsis },
            new TextBlock { Text = value, FontSize = 11, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = StateBrush(value), VerticalAlignment = VerticalAlignment.Center, FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"], TextTrimming = TextTrimming.CharacterEllipsis, MaxWidth = 190 },
        },
    }.WithSecondColumn();

    private static StackPanel Vertical(params UIElement[] children)
    {
        var panel = new StackPanel { Spacing = 12 };
        foreach (var child in children) panel.Children.Add(child);
        return panel;
    }

    private static Grid Horizontal(params UIElement[] children)
    {
        var grid = new Grid { ColumnSpacing = 12, HorizontalAlignment = HorizontalAlignment.Stretch };
        for (var index = 0; index < children.Length; index++)
        {
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            if (children[index] is FrameworkElement element)
            {
                Grid.SetColumn(element, index);
                element.HorizontalAlignment = HorizontalAlignment.Stretch;
            }
            grid.Children.Add(children[index]);
        }
        return grid;
    }

    private static UIElement Empty(string text) => StateBlock(EmptyStateLabel(text), null, text);

    private static TextBlock Caption(string text) => new() { Text = text, FontSize = 11, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap, LineHeight = 16 };
    private static Border Divider() => new() { Height = 1, Background = Brush("JarvisBorderBrush"), Margin = new Thickness(0, 1, 0, 1) };

    private static TextBlock SectionLabel(string text) => new()
    {
        Text = text,
        FontSize = 11,
        CharacterSpacing = 60,
        FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
        Foreground = Brush("JarvisMutedTextBrush"),
        FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"],
    };

    private static UIElement LargeState(string label, string state) => new StackPanel
    {
        Spacing = 4,
        Children =
        {
            SectionLabel(label),
            new TextBlock { Text = state, FontSize = 18, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = StateBrush(state), FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"], TextTrimming = TextTrimming.CharacterEllipsis },
        },
    };

    /// <summary>Zentrierter Zustand für Flächen ohne Inhalt (Viewport, Tabelle ohne Zeilen), wie .jx-module[data-variant=viewport] .jx-pstate.</summary>
    private static UIElement CenteredEmpty(string state, string title, string detail) => new Grid
    {
        MinHeight = 105,
        Children = { StateBlock(state, title, detail, centered: true) },
    };

    private static UIElement InfoBanner(string title, string detail) => new Border
    {
        Padding = new Thickness(10, 8, 10, 8),
        Background = Brush("JarvisQuietBrush"),
        BorderBrush = Brush("JarvisBorderBrush"),
        BorderThickness = new Thickness(1, 1, 1, 1),
        CornerRadius = new CornerRadius(4),
        Child = new StackPanel { Spacing = 3.2, Children = { new TextBlock { Text = title, FontSize = 12.48, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = Brush("JarvisSecondaryTextBrush") }, Caption(detail) } },
    };

    /// <summary>.jx-set-row: Label 0.8rem mit Hinweis 0.7rem links, lesender Wert rechts (15rem), Trennlinie darunter.</summary>
    private static UIElement SettingRow(string label, string hint, string value, bool last)
    {
        var grid = new Grid
        {
            ColumnSpacing = 24,
            Padding = new Thickness(0, 10.4, 0, 10.4),
            BorderBrush = Brush("JarvisDividerBrush"),
            BorderThickness = new Thickness(0, 0, 0, last ? 0 : 1),
        };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(240) });
        var description = new StackPanel { Spacing = 1.6, VerticalAlignment = VerticalAlignment.Center };
        description.Children.Add(new TextBlock { Text = label, FontSize = 12.8, LineHeight = 18.4, Foreground = Brush("JarvisTextBrush"), FontWeight = Microsoft.UI.Text.FontWeights.SemiBold });
        description.Children.Add(new TextBlock { Text = hint, FontSize = 11.2, LineHeight = 16.8, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap });
        grid.Children.Add(description);
        var state = new TextBlock { Text = value, FontSize = 11, Foreground = StateBrush(value), FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"], TextWrapping = TextWrapping.Wrap, VerticalAlignment = VerticalAlignment.Center, HorizontalAlignment = HorizontalAlignment.Left };
        Grid.SetColumn(state, 1);
        grid.Children.Add(state);
        AutomationProperties.SetName(grid, $"{label}: {value}, nur lesend");
        return grid;
    }

    private static UIElement TableHeader(params string[] columns)
    {
        var grid = new Grid { ColumnSpacing = 10, Margin = new Thickness(2, 4, 2, 4) };
        foreach (var _ in columns) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < columns.Length; i++)
        {
            // .jx-th: 0.72rem, halbfett, Sekundärtext (keine Mini-Versalien).
            var header = new TextBlock { Text = columns[i], FontSize = 11.52, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = Brush("JarvisSecondaryTextBrush"), TextTrimming = TextTrimming.CharacterEllipsis };
            Grid.SetColumn(header, i);
            grid.Children.Add(header);
        }
        return grid;
    }

    private static UIElement SearchSurface(string placeholder, bool enabled) => new TextBox
    {
        PlaceholderText = placeholder,
        IsEnabled = enabled,
        Style = (Style)Application.Current.Resources["JarvisTextBoxStyle"],
        HorizontalAlignment = HorizontalAlignment.Stretch,
        UseSystemFocusVisuals = true,
    };

    /// <summary>
    /// .jx-flow: nummerierte Schritte mit Icon-Kachel, Titel und Detail, verbunden durch eine feine Linie auf Höhe der
    /// Kachel. Konzeptuelle Abläufe tragen keinen Zustand je Schritt; der Zustand steht im Panelkopf.
    /// </summary>
    private static UIElement FlowStrip(params (string Icon, string Title, string Detail)[] steps)
    {
        var grid = new Grid { MinHeight = 95 };
        foreach (var _ in steps) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < steps.Length; i++)
        {
            var step = steps[i];
            var cell = new Grid { RowSpacing = 5.6, Padding = new Thickness(0, 0, 16, 0) };
            for (var r = 0; r < 4; r++) cell.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            cell.Children.Add(SectionLabel((i + 1).ToString("00", CultureInfo.InvariantCulture)));
            var tile = SlotIcon(step.Icon);
            tile.HorizontalAlignment = HorizontalAlignment.Left;
            Grid.SetRow(tile, 1);
            if (i < steps.Length - 1)
            {
                var connector = new Border { Height = 1, Background = Brush("JarvisLineBrush"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(41.6, 0, -6.4, 0) };
                Grid.SetRow(connector, 1);
                cell.Children.Add(connector);
            }

            cell.Children.Add(tile);
            var title = new TextBlock { Text = step.Title, FontSize = 12.8, LineHeight = 18.4, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = Brush("JarvisTextBrush"), TextWrapping = TextWrapping.Wrap };
            Grid.SetRow(title, 2);
            cell.Children.Add(title);
            var detail = new TextBlock { Text = step.Detail, FontSize = 11.2, LineHeight = 16.8, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap };
            Grid.SetRow(detail, 3);
            cell.Children.Add(detail);
            AutomationProperties.SetName(cell, $"Schritt {i + 1}: {step.Title}. {step.Detail}");
            Grid.SetColumn(cell, i);
            grid.Children.Add(cell);
        }
        return grid;
    }

    private static Brush StateBrush(string value) => value switch
    {
        "READY" or "LOADED" or "AVAILABLE" or "ENABLED" or "REGISTERED" or "RUNNING" => Brush("JarvisReadyBrush"),
        "DEGRADED" or "WARNING" or "NO HANDLER" => Brush("JarvisDegradedBrush"),
        "STARTING" => Brush("JarvisInfoBrush"),
        "ERROR" or "CRITICAL" or "OFFLINE" => Brush("JarvisErrorBrush"),
        "STOPPED" => Brush("JarvisStoppedBrush"),
        "UNAVAILABLE" or "NOT_IMPLEMENTED" or "NO LIVE DATA" or "NOT LOADED" or "DISABLED" or "BACKEND OWNED" => Brush("JarvisUnavailableBrush"),
        _ => Brush("JarvisTextBrush"),
    };

    private static string EmptyStateLabel(string detail) => detail.Contains("NOT_IMPLEMENTED", StringComparison.OrdinalIgnoreCase)
        ? "NOT_IMPLEMENTED"
        : detail.Contains("UNAVAILABLE", StringComparison.OrdinalIgnoreCase)
            ? "UNAVAILABLE"
            : "NO LIVE DATA";

    private static Brush Brush(string key) => (Brush)Application.Current.Resources[key];
    private static Style ButtonStyle() => (Style)Application.Current.Resources["JarvisButtonStyle"];
}

internal static class ShellLayoutExtensions
{
    public static Grid WithSecondColumn(this Grid grid)
    {
        if (grid.Children.Count > 1 && grid.Children[1] is FrameworkElement second) Grid.SetColumn(second, 1);
        return grid;
    }
}
