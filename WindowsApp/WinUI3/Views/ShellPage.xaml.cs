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
    private static readonly IReadOnlyDictionary<string, (string Title, string Description)> Sections =
        new Dictionary<string, (string, string)>
        {
            ["Home"] = ("Home", "Persönliche Runtime-Übersicht"),
            ["Chat"] = ("Chat", "Lokaler Dialog. Kontextgesteuerte Verarbeitung."),
            ["Memory"] = ("Memory", "Kontext, Gedächtnis und Herkunft."),
            ["ModelsRuntime"] = ("Models & Runtime", "Modelle, Runtime und Lifecycle."),
            ["VoiceAudio"] = ("Voice & Audio", "Sprachpipeline, Audio und Listener."),
            ["Tools"] = ("Tools & Integrations", "Verfügbare Fähigkeiten und Integrationen."),
            ["Automations"] = ("Automations", "Regeln, Tasks und Trigger."),
            ["Vision"] = ("Vision & Presence", "Vision, Präsenz und Sensorstatus."),
            ["Mobility"] = ("Mobility / VVS", "Mobilitätsdaten und VVS-Verbindung."),
            ["Mobile"] = ("Mobile Connection", "Native App-Verbindung und Pairing."),
            ["Observability"] = ("Observability", "Echte Runtime-Ereignisse und Diagnose."),
            ["Settings"] = ("Settings", "Native Desktop-Konfiguration."),
        };

    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(60);
    private static readonly TimeSpan WebFreshness = TimeSpan.FromSeconds(20);

    private readonly Jarvis.ControlHub.RuntimeSupervisorClient _supervisor = new();
    private readonly BackendHub _backend = new();
    private readonly Dictionary<BackendDomain, DateTimeOffset> _webLoadedAt = [];
    private readonly HashSet<BackendDomain> _webLoading = [];
    private string? _repositoryRoot;
    private Jarvis.ControlHub.RuntimeSnapshot? _snapshot;
    private bool _refreshing;
    private CancellationTokenSource? _lifetime;
    private DispatcherTimer? _pollTimer;
    private Border? _settingsDetailHost;
    private readonly List<Button> _settingsNavButtons = [];
    private int _selectedSettingsGroup;

    public FrameworkElement TitleBarDragRegion => Wordmark;

    public ShellPage()
    {
        InitializeComponent();
        Wordmark.Source = new BitmapImage(new Uri("ms-appx:///Resources/jarvis-wordmark.png"));
        BuildSystemGroups();
        SystemNavItem.Loaded += (_, _) => HideBuiltInChevron(SystemNavItem);
        PageScroll.SizeChanged += (_, _) => ApplyHomeMinHeight();
        SizeChanged += (_, args) => UpdateSystemLabels(args.NewSize.Width);
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
        await RefreshRuntimeAsync();
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
    {
        _pollTimer?.Stop();
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
        SectionHeader.Visibility = section == "Home" ? Visibility.Collapsed : Visibility.Visible;
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

        var grid = NewGrid(2, 1, 14, 0);
        grid.Height = 610;
        grid.ColumnDefinitions[0].Width = new GridLength(270);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        UIElement sessionsBody = sessions.IsReady
            ? Vertical(StateValue("Sitzungen", Field(sessions, sessions.As<SessionsInfo>()?.Total)), Caption("Nur die Anzahl aus dem Backend. Kein Verlauf geladen."))
            : StatusEmpty(sessions);
        Place(grid, Vertical(
            Panel("SESSIONS", sessions.IsReady ? "READY" : StateText(sessions), sessionsBody),
            Panel("PROCESSING CONTEXT", StateText(stats), Vertical(
                StateValue("Model", model), StateValue("Memory", memory), StateValue("Tools", tools),
                Divider(), Caption("Kontext wird nur vom Backend zusammengestellt.")))), 0, 0);

        var conversation = new Grid { RowSpacing = 0 };
        conversation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        conversation.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        conversation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        conversation.Children.Add(Panel("J.A.R.V.I.S WORKSPACE", "NOT_IMPLEMENTED", Horizontal(
            StateValue("MODEL", model), StateValue("MEMORY", memory), StateValue("TOOLS", tools))));
        var empty = new Border
        {
            Margin = new Thickness(0, 12, 0, 12),
            Background = Brush("JarvisPanelBrush"),
            BorderBrush = Brush("JarvisBorderBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Child = CenteredEmpty("CHAT NOT_IMPLEMENTED", "Kein vom Supervisor verwalteter Chat-Endpunkt. Der einzige Chat-Pfad (/ws in jarvis_web.py) gehört zu einem separaten, nicht überwachten Web-Prozess und ist von hier nicht verifiziert."),
        };
        Grid.SetRow(empty, 1);
        conversation.Children.Add(empty);
        var composer = CommandSurface("Nachricht an J.A.R.V.I.S", "Eingabe und Senden deaktiviert: Chat ist NOT_IMPLEMENTED.");
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
        stage.Children.Add(new Border { HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Bottom, Margin = new Thickness(12), Padding = new Thickness(10), MaxWidth = 260, Background = new SolidColorBrush(Color.FromArgb(232, 8, 16, 24)), BorderBrush = Brush("JarvisBorderBrush"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(4), Child = Vertical(SectionLabel("IDLE · NO LIVE DATA"), Caption("Aktivierung nur bei echten Retrieval-Ereignissen. Keine Gedanken oder Chain-of-Thought.")) });
        Place(grid, Panel("MEMORY GRAPH", "NO LIVE DATA", Vertical(stage, SearchSurface("Memory durchsuchen", false), Caption("Suche deaktiviert: kein Such-Endpunkt im Desktop-Vertrag."))), 0, 0);

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
        Place(grid, Panel("MEMORY STORE", StateText(summary), Compact(storeRows.ToArray())), 0, 1);

        UIElement categories = !summary.IsReady
            ? StatusEmpty(summary)
            : memory is { FactsByCategory.Count: > 0 }
                ? Compact(memory.FactsByCategory.Take(10).Select(item => StateValue(item.Key, item.Value.ToString(CultureInfo.CurrentCulture))).ToArray())
                : Empty("Keine Fakten in der Datenbank.");
        Place(grid, Panel("FACTS BY CATEGORY", StateText(summary), categories), 1, 0);

        Place(grid, Panel("PRIVACY & CONTROL", "BACKEND OWNED", Compact(
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
        Place(grid, Panel("PRIMARY MODEL", primary.Text, Compact(
            LargeState("PRIMARY", primary.Text), Divider(),
            StateValue("Modell", Field(stats, statsInfo?.Model)),
            StateValue("Endpoint", Field(desktop, config?.LlmEndpoint)),
            StateValue("Kontextgröße", Field(desktop, config?.LlmContextSize)),
            Caption(primary.Detail.Length > 0 ? primary.Detail : "Dauerhafte Rolle. Modellname und Endpoint nur aus dem Backend."))), 0, 0);
        Place(grid, Panel("EXPERT MODEL", expert.Text, Compact(
            LargeState("EXPERT", expert.Text), Divider(),
            StateValue("Modell", "UNAVAILABLE"),
            Caption(expert.Detail.Length > 0 ? expert.Detail : "On-demand. STOPPED ist ein gültiger Zustand."))), 1, 0);
        Place(grid, Panel("VOICE MODELS", "READ ONLY", Compact(
            StateValue("STT", stt.Text),
            StateValue("STT-Modell", Field(desktop, config?.SttModel)),
            StateValue("TTS", tts.Text),
            StateValue("Small-LLM", small.Text),
            Divider(),
            Caption(stt.Detail.Length > 0 ? stt.Detail : "Zustände vom Runtime Supervisor."))), 2, 0);
        var lifecycle = Panel("RUNTIME LIFECYCLE", "SUPERVISOR CONTROLLED", Vertical(
            RuntimeStateView(),
            FlowStrip(("01", "STARTING", "wird angefordert"), ("02", "READY", "Backend bestätigt"), ("03", "DEGRADED", "Teilfunktion fehlt"), ("04", "STOPPED", "bewusst beendet")),
            Horizontal(ActionButton("Starten", _snapshot?.CanStart == true, OnStartClick), ActionButton("Stoppen", _snapshot?.CanStop == true, OnStopClick), ActionButton("Neu starten", _snapshot?.CanRestart == true, OnRestartClick)),
            Caption("Aktionen sind nur bei freigegebener Supervisor-Capability aktiv.")));
        Grid.SetColumnSpan(lifecycle, 2);
        Place(grid, lifecycle, 0, 1);
        var sources = Compact(RuntimeComponents.Distinct(_snapshot).Select(item => StateValue(item.Name, RuntimeStateText.ToDisplayText(RuntimeComponents.ParseState(item.State)))).ToArray());
        Place(grid, Panel("RUNTIME SOURCES", _snapshot?.State ?? "UNAVAILABLE", _snapshot is null ? StatusEmpty("UNAVAILABLE", "Runtime Supervisor nicht verbunden.") : sources), 2, 1);
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
        var pipeline = Panel("VOICE PIPELINE", "NO LIVE DATA", Vertical(
            FlowStrip(("01", "Mikrofon", "Input"), ("02", "Wake Word", "oder Direct Audio"), ("03", "STT", "Transkription"), ("04", "Modell", "Antwort"), ("05", "TTS", "Sprachausgabe"), ("06", "Output", "Audio")),
            Divider(), Caption("Ablaufdarstellung. Keine Pegel, Aufnahmen oder aktiven Schritte ohne Audio-Backend.")));
        Grid.SetColumnSpan(pipeline, 3);
        Place(grid, pipeline, 0, 0);
        Place(grid, Panel("INPUT", daemon.Text, Compact(
            StateValue("Listener", daemon.Text),
            StateValue("Wake word", Field(desktop, config?.WakeKeyword)),
            StateValue("Input device", Field(desktop, config?.InputDevice)),
            StateValue("STT-Backend", Field(desktop, config?.SttBackend)),
            SearchSurface("Eingabegerät wählen", false),
            Caption(daemon.Detail.Length > 0 ? daemon.Detail : "Gerätewahl nur über die Backend-Konfiguration (lesend)."))), 0, 1);
        Place(grid, Panel("OUTPUT", tts.Text, Compact(
            StateValue("Voice", Field(desktop, config?.TtsEngine)),
            StateValue("TTS", tts.Text),
            StateValue("Output backend", Field(desktop, config?.OutputBackend)),
            StateValue("Audio-Brücke", bridge.Text),
            SearchSurface("Ausgabegerät wählen", false),
            Caption(bridge.Detail.Length > 0 ? bridge.Detail : tts.Detail.Length > 0 ? tts.Detail : "Keine lokale Geräteliste angezeigt."))), 1, 1);
        var voiceEvents = events.As<EventsInfo>()?.Items.Where(IsVoiceEvent).Take(4).ToList();
        UIElement eventBody = voiceEvents is { Count: > 0 }
            ? Compact(voiceEvents.Select(EventLine).ToArray())
            : events.IsReady ? Empty("Keine Audio-Ereignisse in den letzten 24 Stunden.") : StatusEmpty(events);
        Place(grid, Panel("PRIVACY & DIAGNOSTICS", "BACKEND OWNED", Compact(
            StateValue("Microphone gate", "UNAVAILABLE"), StateValue("Recording", "UNAVAILABLE"), Divider(),
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

            inventory = Vertical(TableHeader("TOOL", "SKILL", "HANDLER"), Divider(), Scrollable(rows, 470));
            inventoryBadge = $"{config.Tools.Count} TOOLS";
        }
        else
        {
            inventory = CenteredEmpty("NO INVENTORY", "Das Backend meldet keine registrierten Tools.");
            inventoryBadge = "NO LIVE DATA";
        }

        Place(grid, Panel("TOOL INVENTORY", inventoryBadge, inventory), 0, 0);

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
        Place(grid, Panel("CAPABILITIES", StateText(desktop), Compact(capabilityRows.ToArray())), 1, 0);
        Place(grid, Panel("INTEGRATIONS", StateText(desktop), Compact(
            StateValue("Local API", StateText(desktop)), StateValue("MCP", "UNAVAILABLE"), StateValue("Cloud", "UNAVAILABLE"),
            Caption(desktop.IsReady ? "Keine weitere Integration vom Backend gemeldet." : Note(desktop)))), 2, 0);
        var path = Panel("EXECUTION PATH", "BACKEND GATED", FlowStrip(
            ("01", "Request", "Chat oder Automation"), ("02", "Permission", "Backend policy"), ("03", "Execution", "lokal oder remote"), ("04", "Result", "authoritative event")));
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
            table = Vertical(TableHeader("NAME", "TRIGGER", "SCHEDULE", "LAST RUN", "STATE"), Divider(), StatusEmpty(automations));
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

            table = Vertical(TableHeader("NAME", "TRIGGER", "SCHEDULE", "LAST RUN", "STATE"), Divider(), rows,
                Caption("System-eigene Scheduler des Backends. Es gibt keine nutzerdefinierten Regeln. BACKEND OWNED = gehört dem Voice-Daemon, sein Zustand ist hier nicht bekannt; das ist nicht 'disabled'."));
            tableBadge = $"{info.Schedulers.Count} SCHEDULER";
        }
        else
        {
            table = CenteredEmpty("NO RULES", "Das Backend meldet keine Scheduler.");
            tableBadge = "NO LIVE DATA";
        }

        Place(grid, Panel("AUTOMATIONS", tableBadge, table), 0, 0);
        Place(grid, Panel("SELECTED RULE", "NOT_IMPLEMENTED", Vertical(
            LargeState("RULE DETAIL", "NOT_IMPLEMENTED"), StateValue("Enabled", "UNAVAILABLE"), StateValue("Trigger", "UNAVAILABLE"),
            StateValue("Action", "UNAVAILABLE"), Divider(), Caption("Keine Regel-Engine im Backend."), ActionButton("Jetzt ausführen", false, OnRefreshClick))), 1, 0);
        var plannerOwned = agents.IsReady && planner is { Available: false } && planner.State == "BACKEND OWNED";
        UIElement plannerBody = plannerOwned
            ? StatusEmpty("BACKEND OWNED", "Der Planner gehört dem Voice-Daemon. Der Desktop-Web-Prozess hat keinen Planner-Status; ein lokaler Leerlauf wird nicht als Systemzustand gezeigt.")
            : planner is { Available: true } && agents.IsReady
            ? Compact(
                StateValue("Zustand", planner.Available ? planner.State : "UNAVAILABLE"),
                StateValue("Schritte", planner.Steps.ToString(CultureInfo.CurrentCulture)),
                StateValue("Abgeschlossen", planner.Completed.ToString(CultureInfo.CurrentCulture)),
                StateValue("Laufend", planner.Running.ToString(CultureInfo.CurrentCulture)),
                StateValue("Fehlgeschlagen", planner.Failed.ToString(CultureInfo.CurrentCulture)),
                StateValue("Ausstehend", planner.Pending.ToString(CultureInfo.CurrentCulture)))
            : StatusEmpty(agents);
        Place(grid, Panel("TASK PLANNER", plannerOwned ? "BACKEND OWNED" : StateText(agents), plannerBody), 2, 0);
        var workflow = Panel("TRIGGER TO ACTION", "CONCEPTUAL FLOW", FlowStrip(
            ("01", "Trigger", "Zeit, Event, Befehl"), ("02", "Condition", "optional"), ("03", "Action", "Tool oder Antwort"), ("04", "Approval", "Backend policy")));
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
        var viewport = Panel("VISION VIEWPORT", "UNAVAILABLE", CenteredEmpty("NO CAMERA SOURCE", "Kein Kamerabild. Die Oberfläche aktiviert die Kamera nicht und zeigt keine Frames; Freigaben bleiben beim Backend."));
        viewport.Background = Brush("JarvisQuietBrush");
        viewport.BorderBrush = Brush("JarvisOfflineBrush");
        Place(grid, viewport, 0, 0);
        Place(grid, Panel("PRESENCE", "UNAVAILABLE", Vertical(
            LargeState("PRESENCE", "UNAVAILABLE"), StateValue("Occupancy", "UNAVAILABLE"), StateValue("Movement", "UNAVAILABLE"),
            StateValue("Last event", "NO LIVE DATA"), Caption("Das Backend stellt keine bestätigte Belegung bereit."))), 1, 0);
        var frameServer = webcam.IsReady && camera is { Available: true } ? "AVAILABLE" : "UNAVAILABLE";
        Place(grid, Panel("SENSOR SOURCES", npu.Text, Compact(
            StateValue("Camera frame server", frameServer),
            StateValue("NPU", npu.Text),
            StateValue("Other sensors", "UNAVAILABLE"),
            Divider(), StateValue("Privacy gate", "UNAVAILABLE"),
            Caption(npu.Detail.Length > 0 ? npu.Detail : "Geräte- und Gate-Zustand nur aus Backend."))), 2, 0);
        var flow = Panel("LOCAL DETECTION FLOW", "CONCEPTUAL", FlowStrip(
            ("01", "Camera", "permission gate"), ("02", "Detection", "local processing"), ("03", "Presence", "confirmed state"), ("04", "Event", "automation source")));
        Grid.SetColumnSpan(flow, 3);
        Place(grid, flow, 0, 1);
        return grid;
    }

    private UIElement BuildMobility()
    {
        var vvs = Comp(RuntimeComponents.Vvs);
        var stack = Vertical();
        stack.Children.Add(Panel("JOURNEY SEARCH", "NOT_IMPLEMENTED", Vertical(Horizontal(
            SearchSurface("Start", false), SearchSurface("Ziel", false), ActionButton("Verbindungen suchen", false, OnRefreshClick)),
            Caption("Keine Verbindungsabfrage über das Backend für den Desktop; nur der VVS-Dienstzustand ist angebunden."))));
        var grid = NewGrid(3, 1, 12, 0);
        grid.Height = 440;
        grid.ColumnDefinitions[0].Width = new GridLength(1.5, GridUnitType.Star);
        grid.ColumnDefinitions[1].Width = new GridLength(0.85, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = new GridLength(0.85, GridUnitType.Star);
        Place(grid, Panel("CONNECTIONS", "NO LIVE DATA", Vertical(
            TableHeader("LINE", "DEPARTURE", "ARRIVAL", "NOTICE"), Divider(),
            CenteredEmpty("NO DEPARTURES", "Keine Echtzeitdaten. Es werden keine Verbindungen oder Zeiten erfunden."))), 0, 0);
        Place(grid, Panel("ROUTE CONTEXT", "UNAVAILABLE", CenteredEmpty("NO ROUTE", "Routen- und Standortkontext werden vom Mobility-Backend geliefert.")), 1, 0);
        Place(grid, Panel("VVS SOURCE", vvs.Text, Vertical(
            StateValue("Service", vvs.Text), StateValue("Updated", TimeText(_snapshot?.UpdatedAt)), StateValue("Location", "UNAVAILABLE"),
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
        var pairing = Panel("DEVICE PAIRING", mobile, CenteredEmpty("PAIRING UNAVAILABLE", "Kein Pairing-Vertrag im Backend. Es wird kein QR-Code, Token oder Gerätezustand erzeugt."));
        pairing.BorderBrush = Brush("JarvisUnavailableBrush");
        Place(grid, pairing, 0, 0);
        Place(grid, Panel("CONNECTED DEVICES", "NO LIVE DATA", Vertical(
            TableHeader("DEVICE", "STATE", "LAST CONTACT"), Divider(), Empty("Es liegen keine Gerätedaten vor."))), 1, 0);
        Place(grid, Panel("CONNECTION", mobile, Vertical(
            LargeState("MOBILE LINK", mobile), StateValue("Pairing", mobile), StateValue("Commands", "UNAVAILABLE"),
            StateValue("Handoff", "UNAVAILABLE"),
            Caption("Backend kennt nur einen browserbasierten Kamera-Relay (jarvis_web.py), keine native App-Verbindung."))), 2, 0);
        var security = Panel("TRUST & PRIVACY", "NO PAIRING", FlowStrip(
            ("01", "Discover", "local only"), ("02", "Confirm", "on device"), ("03", "Authorize", "backend-owned"), ("04", "Connect", "after confirmation")));
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
        Place(grid, Panel("RUNTIME HEALTH", _snapshot?.State ?? "UNAVAILABLE", Compact(
            StateValue("Supervisor", _snapshot?.State ?? "UNAVAILABLE"),
            StateValue("Components", _snapshot?.Components.Count.ToString() ?? "UNAVAILABLE"),
            StateValue("Degraded-Gründe", _snapshot?.DegradedReasons.Count().ToString() ?? "UNAVAILABLE"))), 0, 0);
        Place(grid, Panel("VOICE HEALTH", daemon.Text, Compact(
            StateValue("Listener", daemon.Text), StateValue("TTS", Comp(RuntimeComponents.Chatterbox).Text), StateValue("Audio", Comp(RuntimeComponents.AudioBridge).Text))), 1, 0);
        Place(grid, Panel("MEMORY HEALTH", StateText(summary), Compact(
            StateValue("Fakten", Field(summary, memory?.FactsTotal)), StateValue("Index", Field(summary, memory?.FaissVectors)),
            StateValue("Storage", FieldBytes(summary, memory?.FaissBytes)))), 2, 0);

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
            eventBody = Vertical(TableHeader("TIME", "SOURCE", "EVENT", "STATE"), Divider(), rows,
                Caption(total is { } count ? $"{count} Ereignisse in den letzten 24 Stunden (aggregiert)." : "Datenschutz-Projektion des Backends: Kategorie, Ereignisname, Schweregrad."));
            eventBadge = $"{info.Items.Count} EVENTS";
        }
        else if (events.IsReady)
        {
            eventBody = Vertical(TableHeader("TIME", "SOURCE", "EVENT", "STATE"), Divider(), CenteredEmpty("NO EVENTS", "Keine Ereignisse in den letzten 24 Stunden."));
            eventBadge = "NO LIVE DATA";
        }
        else
        {
            UIElement hints = _snapshot is { } snapshot && snapshot.DegradedReasons.Any()
                ? Compact(snapshot.DegradedReasons.Take(4).Select(reason => Caption("Supervisor: " + reason)).ToArray())
                : Caption("Keine Supervisor-Hinweise vorhanden.");
            eventBody = Vertical(TableHeader("TIME", "SOURCE", "EVENT", "STATE"), Divider(), StatusEmpty(events), hints);
            eventBadge = StateText(events);
        }

        var eventsPanel = Panel("RUNTIME EVENTS", eventBadge, eventBody);
        Grid.SetColumnSpan(eventsPanel, 2);
        Place(grid, eventsPanel, 0, 1);
        Place(grid, Panel("LOG STREAM", "UNAVAILABLE", Vertical(
            Caption("Live-Ausgabe deaktiviert: weder Supervisor noch Web-API bieten einen strukturierten Log-Vertrag."),
            Empty("NO LIVE DATA"), ActionButton("Logs öffnen", false, OnRefreshClick))), 2, 1);
        return grid;
    }

    private UIElement BuildSettings()
    {
        var grid = NewGrid(2, 1, 12, 0);
        grid.Height = 620;
        grid.ColumnDefinitions[0].Width = new GridLength(205);
        grid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        _settingsNavButtons.Clear();
        _settingsDetailHost = new Border { Style = (Style)Application.Current.Resources["JarvisPanelStyle"], Child = BuildSettingsDetail() };
        var navContent = new StackPanel { Spacing = 2 };
        string[] groups = ["General", "Appearance", "Runtime", "Models", "Voice", "Memory", "Privacy", "Cloud", "Tools", "Mobile", "Diagnostics"];
        for (var i = 0; i < groups.Length; i++)
        {
            var index = i;
            var button = new Button { Content = groups[i], HorizontalContentAlignment = HorizontalAlignment.Left, Style = ButtonStyle(), Background = Brush(i == _selectedSettingsGroup ? "JarvisPanelRaisedBrush" : "JarvisPanelBrush"), MinHeight = 38 };
            button.Click += (_, _) => SelectSettingsGroup(index);
            _settingsNavButtons.Add(button);
            navContent.Children.Add(button);
        }

        var nav = Panel("PREFERENCES", "READ ONLY", navContent);
        Place(grid, nav, 0, 0);
        Place(grid, _settingsDetailHost, 1, 0);
        return grid;
    }

    private void SelectSettingsGroup(int index)
    {
        _selectedSettingsGroup = index;
        for (var i = 0; i < _settingsNavButtons.Count; i++)
        {
            _settingsNavButtons[i].Background = Brush(i == index ? "JarvisPanelRaisedBrush" : "JarvisPanelBrush");
            _settingsNavButtons[i].Foreground = Brush(i == index ? "JarvisTextBrush" : "JarvisMutedTextBrush");
        }
        if (_settingsDetailHost is not null) _settingsDetailHost.Child = BuildSettingsDetail();
    }

    private UIElement BuildSettingsDetail()
    {
        string[] groups = ["General", "Appearance", "Runtime", "Models", "Voice", "Memory", "Privacy", "Cloud", "Tools", "Mobile", "Diagnostics"];
        var selected = groups[Math.Clamp(_selectedSettingsGroup, 0, groups.Length - 1)];
        var desktop = Web(WebEndpoint.Desktop);
        var config = desktop.As<DesktopInfo>();
        var sttText = !desktop.IsReady
            ? "UNAVAILABLE"
            : string.Join(" / ", new[] { config?.SttBackend, config?.SttModel }.Where(part => !string.IsNullOrWhiteSpace(part))) is { Length: > 0 } stt ? stt : "UNAVAILABLE";
        var rows = selected switch
        {
            "General" => new[] { ("Start with Windows", "NOT_IMPLEMENTED"), ("Start minimized", "NOT_IMPLEMENTED"), ("Language", "System default") },
            "Appearance" => new[] { ("Theme", "System"), ("Window material", "Mica"), ("Scale", "Windows managed") },
            "Runtime" => new[] { ("Supervisor", "JARVIS-Runtime.ps1"), ("Repository", _repositoryRoot ?? "UNAVAILABLE"), ("Lifecycle actions", "Supervisor owned") },
            "Models" => new[] { ("LLM provider", Field(desktop, config?.LlmProvider)), ("LLM endpoint", Field(desktop, config?.LlmEndpoint)), ("Context size", Field(desktop, config?.LlmContextSize)), ("Routing", "Backend owned") },
            "Voice" => new[] { ("Input device", Field(desktop, config?.InputDevice)), ("Output backend", Field(desktop, config?.OutputBackend)), ("Wake word", Field(desktop, config?.WakeKeyword)), ("STT", sttText), ("TTS engine", Field(desktop, config?.TtsEngine)), ("Language", Field(desktop, config?.Language)) },
            "Memory" => new[] { ("Capture", Field(desktop, config?.MemoryEnabled)), ("Proactive surfacing", Field(desktop, config?.MemoryProactive)), ("Context window", Field(desktop, config?.ContextWindowEnabled)), ("Retention", "Backend owned") },
            "Privacy" => new[] { ("Microphone gate", "UNAVAILABLE"), ("Camera gate", "UNAVAILABLE"), ("Clipboard gate", "UNAVAILABLE") },
            "Cloud" => new[] { ("Cloud permission", "UNAVAILABLE"), ("Provider", "UNAVAILABLE") },
            "Tools" => new[] { ("Remote tools", "UNAVAILABLE"), ("Confirmation policy", "Backend owned") },
            "Mobile" => new[] { ("Pairing", "NOT_IMPLEMENTED"), ("Device list", "UNAVAILABLE") },
            _ => new[] { ("Log level", "Backend owned"), ("Diagnostics package", "NOT_IMPLEMENTED"), ("Live events", "NO LIVE DATA") },
        };
        var content = Vertical(
            TitleLine(selected.ToUpperInvariant(), "READ ONLY"),
            InfoBanner("Backend-owned values", "Nur lesend. config.yaml gehört dem Backend; es gibt keinen Schreibvertrag mit Validierung, deshalb speichert diese Ansicht nichts."),
            SectionLabel("CONFIGURATION"));
        foreach (var row in rows) content.Children.Add(SettingRow(row.Item1, row.Item2));
        if (!desktop.IsReady && selected is "Models" or "Voice" or "Memory") content.Children.Add(Caption(Note(desktop)));
        content.Children.Add(Divider());
        content.Children.Add(Caption("Änderungen werden erst angeboten, wenn ein passender lokaler Vertrag vorhanden ist."));
        content.Children.Add(Horizontal(ActionButton("Zurücksetzen", false, OnRefreshClick), ActionButton("Übernehmen", false, OnRefreshClick)));
        return content;
    }

    private UIElement RuntimeStateView() => Panel("CURRENT STATUS", _snapshot?.State ?? "UNAVAILABLE", Vertical(
        StateValue("State", _snapshot?.State ?? "UNAVAILABLE"),
        StateValue("Observed", _snapshot?.UpdatedAt?.ToLocalTime().ToString("HH:mm:ss") ?? "UNAVAILABLE"),
        StateValue("Components", _snapshot?.Components.Count.ToString() ?? "UNAVAILABLE")));

    private async void OnRefreshClick(object sender, RoutedEventArgs args) => await RefreshRuntimeAsync();
    private async void OnStartClick(object sender, RoutedEventArgs args) => await RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction.Start, _snapshot?.CanStart == true);
    private async void OnStopClick(object sender, RoutedEventArgs args) => await RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction.Stop, _snapshot?.CanStop == true);
    private async void OnRestartClick(object sender, RoutedEventArgs args) => await RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction.Restart, _snapshot?.CanRestart == true);

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
                _snapshot = await _supervisor.GetRuntimeAsync(_repositoryRoot);
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

    private async Task RequestRuntimeActionAsync(Jarvis.ControlHub.JarvisRuntimeAction action, bool capabilityAllowed)
    {
        if (!capabilityAllowed || _repositoryRoot is null) return;
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
        try
        {
            var result = await _supervisor.RequestActionAsync(action, _repositoryRoot);
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

    private static UIElement StatusEmpty(string label, string message) => new StackPanel
    {
        VerticalAlignment = VerticalAlignment.Center,
        Spacing = 6,
        Children =
        {
            new TextBlock { Text = label, FontSize = 10, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, CharacterSpacing = 40, Foreground = StateBrush(label), FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"] },
            new TextBlock { Text = message, FontSize = 12, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap, LineHeight = 18 },
        },
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
                FontSize = isState ? 10 : 11,
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

    private static Border Panel(string title, string badge, UIElement content)
    {
        var stack = new StackPanel { Spacing = 9 };
        stack.Children.Add(TitleLine(title, badge));
        stack.Children.Add(Divider());
        stack.Children.Add(content);
        return new Border { Style = (Style)Application.Current.Resources["JarvisPanelStyle"], Child = stack, MinWidth = 0, UseLayoutRounding = true };
    }

    private static UIElement TitleLine(string title, string badge) => new Grid
    {
        ColumnDefinitions =
        {
            new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) },
            new ColumnDefinition { Width = GridLength.Auto },
        },
        Children =
        {
            new TextBlock { Text = title, FontSize = 11, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, CharacterSpacing = 75, Foreground = Brush("JarvisHeaderBrush"), VerticalAlignment = VerticalAlignment.Center, FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisFontFamily"] },
            BadgeText(badge),
        },
    }.WithBadgeColumn();

    private static TextBlock BadgeText(string text) => new() { Text = text, FontSize = 9, CharacterSpacing = 25, Foreground = StateBrush(text), VerticalAlignment = VerticalAlignment.Center, FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"], TextTrimming = TextTrimming.CharacterEllipsis };

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
            new TextBlock { Text = value, FontSize = 10, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = StateBrush(value), VerticalAlignment = VerticalAlignment.Center, FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"], TextTrimming = TextTrimming.CharacterEllipsis, MaxWidth = 190 },
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

    private static UIElement Empty(string text) => new StackPanel
    {
        VerticalAlignment = VerticalAlignment.Center,
        Spacing = 6,
        Children =
        {
            new TextBlock { Text = EmptyStateLabel(text), FontSize = 10, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, CharacterSpacing = 40, Foreground = StateBrush(EmptyStateLabel(text)), FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"] },
            new TextBlock { Text = text, FontSize = 12, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap, LineHeight = 18 },
        },
    };

    private static TextBlock Caption(string text) => new() { Text = text, FontSize = 11, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap, LineHeight = 16 };
    private static Border Divider() => new() { Height = 1, Background = Brush("JarvisBorderBrush"), Margin = new Thickness(0, 1, 0, 1) };

    private static TextBlock SectionLabel(string text) => new()
    {
        Text = text,
        FontSize = 9,
        CharacterSpacing = 65,
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

    private static UIElement CenteredEmpty(string title, string detail) => new Grid
    {
        MinHeight = 105,
        Children =
        {
            new StackPanel
            {
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                MaxWidth = 430,
                Spacing = 7,
                Children = { SectionLabel(title), new TextBlock { Text = detail, FontSize = 12, Foreground = Brush("JarvisMutedTextBrush"), TextWrapping = TextWrapping.Wrap, TextAlignment = TextAlignment.Center, LineHeight = 18 } },
            },
        },
    };

    private static UIElement InfoBanner(string title, string detail) => new Border
    {
        Padding = new Thickness(10, 8, 10, 8),
        Background = Brush("JarvisQuietBrush"),
        BorderBrush = Brush("JarvisBorderBrush"),
        BorderThickness = new Thickness(1, 1, 1, 1),
        CornerRadius = new CornerRadius(4),
        Child = Vertical(SectionLabel(title.ToUpperInvariant()), Caption(detail)),
    };

    private static UIElement SettingRow(string label, string value)
    {
        var grid = new Grid { ColumnSpacing = 18, Margin = new Thickness(0, 8, 0, 8) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(210) });
        var description = Vertical(new TextBlock { Text = label, FontSize = 12, Foreground = Brush("JarvisTextBrush"), FontWeight = Microsoft.UI.Text.FontWeights.SemiBold }, Caption("Änderung nur über einen passenden Konfigurationsvertrag."));
        grid.Children.Add(description);
        var state = new TextBlock { Text = value, FontSize = 10, Foreground = StateBrush(value), FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"], TextWrapping = TextWrapping.Wrap, VerticalAlignment = VerticalAlignment.Center, HorizontalAlignment = HorizontalAlignment.Left };
        Grid.SetColumn(state, 1);
        grid.Children.Add(state);
        var stack = new StackPanel { Spacing = 0, Children = { grid, Divider() } };
        return stack;
    }

    private static UIElement TableHeader(params string[] columns)
    {
        var grid = new Grid { ColumnSpacing = 10, Margin = new Thickness(2, 4, 2, 4) };
        foreach (var _ in columns) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < columns.Length; i++)
        {
            var header = SectionLabel(columns[i]);
            header.TextTrimming = TextTrimming.CharacterEllipsis;
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

    private static UIElement CommandSurface(string placeholder, string note)
    {
        var stack = new StackPanel { Spacing = 7 };
        stack.Children.Add(TitleLine("COMMAND SURFACE", "NOT_IMPLEMENTED"));
        var composer = new Grid { ColumnSpacing = 8 };
        composer.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        composer.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        composer.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var mic = new Button { Content = "Voice", IsEnabled = false, Style = ButtonStyle(), MinWidth = 68, MinHeight = 40 };
        var input = new TextBox { PlaceholderText = placeholder, IsEnabled = false, MinHeight = 40, Style = (Style)Application.Current.Resources["JarvisTextBoxStyle"] };
        var send = new Button { Content = "Senden", IsEnabled = false, Style = ButtonStyle(), MinWidth = 82, MinHeight = 40 };
        Grid.SetColumn(input, 1);
        Grid.SetColumn(send, 2);
        composer.Children.Add(mic);
        composer.Children.Add(input);
        composer.Children.Add(send);
        stack.Children.Add(composer);
        stack.Children.Add(Caption(note));
        return new Border { Style = (Style)Application.Current.Resources["JarvisPanelStyle"], Child = stack, Padding = new Thickness(14, 10, 14, 10), VerticalAlignment = VerticalAlignment.Stretch };
    }

    private static UIElement FlowStrip(params (string Index, string Title, string Detail)[] steps)
    {
        var grid = new Grid { ColumnSpacing = 8, MinHeight = 95 };
        foreach (var _ in steps) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < steps.Length; i++)
        {
            var step = steps[i];
            var content = Vertical(SectionLabel(step.Index), new TextBlock { Text = step.Title, FontSize = 12, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Foreground = Brush("JarvisTextBrush"), TextWrapping = TextWrapping.Wrap }, Caption(step.Detail));
            var border = new Border { Padding = new Thickness(10, 8, 10, 8), Background = Brush("JarvisQuietBrush"), BorderBrush = Brush("JarvisBorderBrush"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(4), Child = content, VerticalAlignment = VerticalAlignment.Stretch };
            Grid.SetColumn(border, i);
            grid.Children.Add(border);
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

    public static Grid WithBadgeColumn(this Grid grid) => grid.WithSecondColumn();
}
