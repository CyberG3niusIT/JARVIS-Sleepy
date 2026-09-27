using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Threading;
using Microsoft.Win32;

namespace Jarvis.ControlHub;

public sealed class MainWindowViewModel : INotifyPropertyChanged, IDisposable
{
    private static readonly TimeSpan LivePollInterval = TimeSpan.FromSeconds(1);
    private static readonly TimeSpan RoutingPollInterval = TimeSpan.FromSeconds(2);
    private static readonly TimeSpan StatusPollInterval = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan AgentAutomationPollInterval = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan InventoryPollInterval = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan FreshnessLimit = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan StatusSnapshotFreshnessLimit = TimeSpan.FromSeconds(15);
    private static readonly TimeSpan RuntimeFreshnessLimit = TimeSpan.FromSeconds(15);

    private readonly Dispatcher _dispatcher;
    private readonly DispatcherTimer _freshnessTimer;
    private readonly JarvisApiClient _api = new();
    private readonly RuntimeSupervisorClient _supervisor = new();
    private readonly CancellationTokenSource _lifetime = new();
    private readonly SemaphoreSlim _liveGate = new(1, 1);
    private readonly SemaphoreSlim _runtimeStatusGate = new(1, 1);
    private readonly SemaphoreSlim _apiStatusGate = new(1, 1);
    private readonly SemaphoreSlim _inventoryGate = new(1, 1);
    private readonly SemaphoreSlim _agentAutomationGate = new(1, 1);
    private readonly SemaphoreSlim _routingGate = new(1, 1);
    private readonly string _repositoryConfigPath;
    private Task? _pollingTask;
    private RuntimeSnapshot? _runtime;
    private string? _runtimeRoot;
    private bool _runtimeSnapshotMarkedStale;
    private DateTimeOffset? _liveObservedAt;
    private string? _liveSource;
    private double? _liveSampleInterval;
    private string? _repositoryRoot;
    private string _voiceRuntimeState = "Supervisor-Zustand wird geprüft.";
    private string? _voiceConfiguration;
    private string _llmConfigurationSummary = "Keine LLM-Konfiguration aus dem Runtime-Snapshot empfangen.";
    private string _voiceConfigurationSummary = "Keine Voice-Konfiguration aus dem Runtime-Snapshot empfangen.";
    private string _runtimeCapabilitiesSummary = "Keine Runtime-Capabilities aus dem Snapshot empfangen.";
    private string _memoryConfigurationSummary = "Keine Memory-Konfiguration aus dem Runtime-Snapshot empfangen.";
    private string? _sttSummary;
    private string? _ttsSummary;
    private List<JarvisListItem> _toolInventory = new();
    private List<VoiceEventEntry> _sttEvents = new();
    private List<VoiceEventEntry> _ttsEvents = new();
    private Dictionary<string, long> _toolUsage = new(StringComparer.Ordinal);
    private string _runtimeState = "Nicht verbunden";
    private string _runtimeDetail = "JARVIS-Main-Verzeichnis auswählen, um den Runtime Supervisor zu verbinden.";
    private DateTime? _runtimeUpdatedAt;
    private string _apiState = "Wird geprüft …";
    private DateTime? _apiUpdatedAt;
    private string _liveAge = "Noch keine Live-Messung empfangen.";
    private string _liveSourceDetail = "Warte auf /api/desktop/live vom JARVIS-Host.";
    private string _cpuValue = "Nicht verfügbar";
    private string _memoryValue = "Nicht verfügbar";
    private string _memoryDetail = "Wartet auf die Live-Telemetrie des JARVIS-Hosts.";
    private string _primaryModel = "Nicht verfügbar";
    private string _primaryState = "Supervisor-Zustand wird geprüft.";
    private string _expertModel = "Qwen · Expert";
    private string _expertState = "Supervisor-Zustand wird geprüft.";
    private string _voiceState = "Supervisor-Zustand wird geprüft.";
    private string _memorySummary = "Keine bestätigten Speicherdaten empfangen.";
    private string _runtimeDataSummary = "Weitere Runtime-Daten werden über /api/stats abgefragt.";
    private string _skillsStatus = "Wartet auf den Runtime-Inventar-Endpunkt.";
    private string _toolsStatus = "Wartet auf den Runtime-Inventar-Endpunkt.";
    private string _eventsStatus = "Wartet auf den Ereignis-Endpunkt.";
    private string _voiceEventsStatus = "Wartet auf datensparsame STT-/TTS-Ereignispunkte.";
    private string _routingEventsStatus = "Wartet auf datensparsame Routing-Messpunkte.";
    private DateTimeOffset? _latestRoutingAt;
    private bool? _routingSourceAvailable;
    private string _routingLiveStatus = "Warte auf aktuelle Routing-Messpunkte.";
    private string _agentSummary = "Agentenstatus wird abgefragt.";
    private string _agentDetail = "Warte auf den laufenden TaskPlanner-Status.";
    private string _automationsStatus = "Wartet auf den Scheduler-Status.";
    private string _historyStatus = "Historische Messwerte werden nicht als Live-Telemetrie angezeigt.";
    private string _runtimeComponentsStatus = "Warte auf den Runtime-Supervisor-Snapshot.";
    private string _metricsSummary = "Noch keine Metriken empfangen.";
    private string _metricsTimeseriesStatus = "Wartet auf /api/metrics/timeseries.";
    private string _skillUsageStatus = "Wartet auf /api/metrics/skills.";
    private string _routeUsageStatus = "Wartet auf /api/metrics/routes.";
    private string _searchPerformanceSummary = "Noch keine Suchmetriken empfangen.";
    private string _searchPerformanceStatus = "Wartet auf /api/metrics/search_stats.";
    private long? _routingEventsTotal;
    private long? _routingEventsHandled;
    private long? _routingEventsFallback;
    private long? _sttEventsTotal;
    private long? _sttEventsErrors;
    private long? _sttEventsEmpty;
    private long? _ttsEventsTotal;
    private long? _ttsEventsErrors;
    private bool _eventsAggregateMissing;
    private bool _isDisposed;

    public MainWindowViewModel()
    {
        _dispatcher = Application.Current?.Dispatcher ?? Dispatcher.CurrentDispatcher;
        _freshnessTimer = new DispatcherTimer(DispatcherPriority.Background, _dispatcher)
        {
            Interval = TimeSpan.FromSeconds(1),
        };
        _freshnessTimer.Tick += OnFreshnessTimerTick;
        _freshnessTimer.Start();
        var roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        _repositoryConfigPath = Path.Combine(roaming, "JARVIS", "ControlHub", "runtime-root.txt");
        _repositoryRoot = ReadConfiguredRoot();
        RepositoryRoot = _repositoryRoot ?? "Nicht verbunden — JARVIS-Main auswählen";
        if (_repositoryRoot is not null)
        {
            _runtimeDetail = "Repository verbunden; Supervisor wird abgefragt.";
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ObservableCollection<JarvisListItem> Skills { get; } = new();
    public ObservableCollection<JarvisListItem> Tools { get; } = new();
    public ObservableCollection<JarvisListItem> Events { get; } = new();
    public ObservableCollection<JarvisListItem> VoiceEvents { get; } = new();
    public ObservableCollection<JarvisListItem> RoutingEvents { get; } = new();
    public ObservableCollection<JarvisListItem> AutomationSchedulers { get; } = new();
    public ObservableCollection<JarvisListItem> RuntimeComponents { get; } = new();
    public ObservableCollection<JarvisListItem> HealthMetrics { get; } = new();

    public string RuntimeState { get => _runtimeState; private set => SetField(ref _runtimeState, value); }
    public string RuntimeDetail { get => _runtimeDetail; private set => SetField(ref _runtimeDetail, value); }
    public DateTime? RuntimeUpdatedAt { get => _runtimeUpdatedAt; private set => SetField(ref _runtimeUpdatedAt, value); }
    public string RepositoryRoot { get => _repositoryRootDisplay; private set => SetField(ref _repositoryRootDisplay, value); }
    private string _repositoryRootDisplay = "Nicht verbunden — JARVIS-Main auswählen";
    public string ApiState { get => _apiState; private set => SetField(ref _apiState, value); }
    public DateTime? ApiUpdatedAt { get => _apiUpdatedAt; private set => SetField(ref _apiUpdatedAt, value); }
    public string LiveAge { get => _liveAge; private set => SetField(ref _liveAge, value); }
    public string LiveSourceDetail { get => _liveSourceDetail; private set => SetField(ref _liveSourceDetail, value); }
    public string CpuValue { get => _cpuValue; private set => SetField(ref _cpuValue, value); }
    public string MemoryValue { get => _memoryValue; private set => SetField(ref _memoryValue, value); }
    public string MemoryDetail { get => _memoryDetail; private set => SetField(ref _memoryDetail, value); }
    public string PrimaryModel { get => _primaryModel; private set => SetField(ref _primaryModel, value); }
    public string PrimaryState { get => _primaryState; private set => SetField(ref _primaryState, value); }
    public string ExpertModel { get => _expertModel; private set => SetField(ref _expertModel, value); }
    public string ExpertState { get => _expertState; private set => SetField(ref _expertState, value); }
    public string VoiceState { get => _voiceState; private set => SetField(ref _voiceState, value); }
    public string LlmConfigurationSummary { get => _llmConfigurationSummary; private set => SetField(ref _llmConfigurationSummary, value); }
    public string VoiceConfigurationSummary { get => _voiceConfigurationSummary; private set => SetField(ref _voiceConfigurationSummary, value); }
    public string RuntimeCapabilitiesSummary { get => _runtimeCapabilitiesSummary; private set => SetField(ref _runtimeCapabilitiesSummary, value); }
    public string MemoryConfigurationSummary { get => _memoryConfigurationSummary; private set => SetField(ref _memoryConfigurationSummary, value); }
    public string MemorySummary { get => _memorySummary; private set => SetField(ref _memorySummary, value); }
    public string RuntimeDataSummary { get => _runtimeDataSummary; private set => SetField(ref _runtimeDataSummary, value); }
    public string SkillsStatus { get => _skillsStatus; private set => SetField(ref _skillsStatus, value); }
    public string ToolsStatus { get => _toolsStatus; private set => SetField(ref _toolsStatus, value); }
    public string EventsStatus { get => _eventsStatus; private set => SetField(ref _eventsStatus, value); }
    public string VoiceEventsStatus { get => _voiceEventsStatus; private set => SetField(ref _voiceEventsStatus, value); }
    public string RoutingEventsStatus { get => _routingEventsStatus; private set => SetField(ref _routingEventsStatus, value); }
    public string RoutingLiveStatus { get => _routingLiveStatus; private set => SetField(ref _routingLiveStatus, value); }
    public string AgentSummary { get => _agentSummary; private set => SetField(ref _agentSummary, value); }
    public string AgentDetail { get => _agentDetail; private set => SetField(ref _agentDetail, value); }
    public string AutomationsStatus { get => _automationsStatus; private set => SetField(ref _automationsStatus, value); }
    public string HistoryStatus { get => _historyStatus; private set => SetField(ref _historyStatus, value); }
    public string RuntimeComponentsStatus { get => _runtimeComponentsStatus; private set => SetField(ref _runtimeComponentsStatus, value); }
    public string MetricsSummary { get => _metricsSummary; private set => SetField(ref _metricsSummary, value); }
    public ObservableCollection<MetricBucket> MetricBuckets { get; } = new();
    public ObservableCollection<MetricBreakdown> SkillUsage { get; } = new();
    public ObservableCollection<MetricBreakdown> RouteUsage { get; } = new();
    public string MetricsTimeseriesStatus { get => _metricsTimeseriesStatus; private set => SetField(ref _metricsTimeseriesStatus, value); }
    public string SkillUsageStatus { get => _skillUsageStatus; private set => SetField(ref _skillUsageStatus, value); }
    public string RouteUsageStatus { get => _routeUsageStatus; private set => SetField(ref _routeUsageStatus, value); }
    public string SearchPerformanceSummary { get => _searchPerformanceSummary; private set => SetField(ref _searchPerformanceSummary, value); }
    public string SearchPerformanceStatus { get => _searchPerformanceStatus; private set => SetField(ref _searchPerformanceStatus, value); }
    public bool CanStart => IsRuntimeSnapshotFresh() && _runtime?.CanStart == true;
    public bool CanStop => IsRuntimeSnapshotFresh() && _runtime?.CanStop == true;
    public bool CanRestart => IsRuntimeSnapshotFresh() && _runtime?.CanRestart == true;

    public async Task RefreshAsync()
    {
        ThrowIfDisposed();
        var token = _lifetime.Token;
        await Task.WhenAll(
            PollLiveAsync(token),
            PollStatusAsync(token),
            PollInventoryAsync(token),
            PollAgentAutomationAsync(token),
            PollRoutingActivityAsync(token));
        if (_pollingTask is null)
        {
            _pollingTask = RunPollingLoopsAsync(token);
        }
    }

    public async Task ChooseRepositoryAsync()
    {
        ThrowIfDisposed();
        var selectedPath = await _dispatcher.InvokeAsync(() =>
        {
            var dialog = new OpenFolderDialog
            {
                Title = "JARVIS-Main-Repository auswählen",
                Multiselect = false,
                InitialDirectory = _repositoryRoot is not null && Directory.Exists(_repositoryRoot)
                    ? _repositoryRoot
                    : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            };
            return dialog.ShowDialog() == true ? dialog.FolderName : null;
        });

        if (string.IsNullOrWhiteSpace(selectedPath))
        {
            return;
        }

        var validatedRoot = RepositoryRootValidator.Validate(selectedPath);
        var parent = Path.GetDirectoryName(_repositoryConfigPath)
            ?? throw new InvalidOperationException("Der JARVIS-App-Konfigurationspfad ist ungültig.");
        Directory.CreateDirectory(parent);
        var temporaryPath = _repositoryConfigPath + ".tmp";
        try
        {
            await File.WriteAllTextAsync(temporaryPath, validatedRoot + Environment.NewLine, _lifetime.Token);
            File.Move(temporaryPath, _repositoryConfigPath, overwrite: true);
        }
        finally
        {
            try { if (File.Exists(temporaryPath)) File.Delete(temporaryPath); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }

        await SetOnUiAsync(() =>
        {
            _repositoryRoot = validatedRoot;
            _runtime = null;
            _runtimeRoot = null;
            _runtimeSnapshotMarkedStale = false;
            ReplaceCollection(RuntimeComponents, Array.Empty<JarvisListItem>());
            RuntimeComponentsStatus = "Repository gewechselt; warte auf einen passenden Supervisor-Snapshot.";
            RepositoryRoot = validatedRoot;
            RuntimeUpdatedAt = null;
            RuntimeState = "Wird geprüft …";
            RuntimeDetail = "Repository ausgewählt; Runtime Supervisor wird abgefragt.";
            RaiseCanExecuteChanged();
        });
        await PollStatusAsync(_lifetime.Token);
    }

    public Task StartRuntimeAsync() => RequestRuntimeActionAsync(JarvisRuntimeAction.Start, "Starten");
    public Task StopRuntimeAsync() => RequestRuntimeActionAsync(JarvisRuntimeAction.Stop, "Stoppen");
    public Task RestartRuntimeAsync() => RequestRuntimeActionAsync(JarvisRuntimeAction.Restart, "Neu starten");

    private async Task RequestRuntimeActionAsync(JarvisRuntimeAction action, string label)
    {
        ThrowIfDisposed();
        var root = _repositoryRoot;
        if (root is null)
        {
            throw new InvalidOperationException("Zuerst das JARVIS-Main-Repository auswählen.");
        }

        if (!IsRuntimeActionAllowed(action, root))
        {
            throw new InvalidOperationException($"Der Runtime Supervisor erlaubt die Aktion „{label}“ im aktuellen Zustand nicht.");
        }

        var confirmation = await _dispatcher.InvokeAsync(() => MessageBox.Show(
            $"Soll der JARVIS Runtime Supervisor die Aktion „{label}“ ausführen?",
            "J.A.R.V.I.S Control Hub",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning,
            MessageBoxResult.No));
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        if (!IsRuntimeActionAllowed(action, root))
        {
            throw new InvalidOperationException($"Der Runtime Supervisor-Snapshot ist nicht mehr aktuell; „{label}“ wurde nicht ausgeführt.");
        }

        var result = await _supervisor.RequestActionAsync(action, root, _lifetime.Token);
        if (!result.Accepted)
        {
            throw new InvalidOperationException(result.Message);
        }

        await SetOnUiAsync(() => RuntimeDetail = result.Message);
        await PollStatusAsync(_lifetime.Token);
    }

    private async Task RunPollingLoopsAsync(CancellationToken cancellationToken)
    {
        var liveTask = RunLoopAsync(LivePollInterval, token => PollLiveAsync(token), cancellationToken);
        var statusTask = RunLoopAsync(StatusPollInterval, token => PollStatusAsync(token), cancellationToken);
        var agentAutomationTask = RunLoopAsync(AgentAutomationPollInterval, token => PollAgentAutomationAsync(token), cancellationToken);
        var routingTask = RunLoopAsync(RoutingPollInterval, token => PollRoutingActivityAsync(token), cancellationToken);
        var inventoryTask = RunLoopAsync(InventoryPollInterval, token => PollInventoryAsync(token), cancellationToken);
        try
        {
            await Task.WhenAll(liveTask, statusTask, agentAutomationTask, inventoryTask, routingTask);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
    }

    private static async Task RunLoopAsync(
        TimeSpan interval,
        Func<CancellationToken, Task> poll,
        CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(interval);
        while (await timer.WaitForNextTickAsync(cancellationToken).ConfigureAwait(false))
        {
            try
            {
                await poll(cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception)
            {
                // Each poll owns its unavailable/error state; never surface private backend data in a log.
            }
        }
    }

    private async Task PollLiveAsync(CancellationToken cancellationToken)
    {
        if (!await _liveGate.WaitAsync(0, cancellationToken).ConfigureAwait(false)) return;
        try
        {
            using var document = await _api.GetDesktopLiveAsync(cancellationToken).ConfigureAwait(false);
            var root = document.RootElement;
            var observed = ParseTimestamp(root, "observedAt");
            var source = GetString(root, "source") ?? "Unbekannte Telemetriequelle";
            var cpu = GetDouble(root, "cpuPercent");
            var memory = GetDouble(root, "memoryPercent");
            var used = GetInt64(root, "memoryUsedBytes");
            var total = GetInt64(root, "memoryTotalBytes");
            var interval = GetDouble(root, "sampleIntervalSeconds");
            var isFresh = observed.HasValue && IsFreshLiveSample(observed.Value);

            await SetOnUiAsync(() =>
            {
                _liveObservedAt = observed;
                _liveSource = source;
                _liveSampleInterval = interval;
                CpuValue = isFresh
                    ? cpu.HasValue ? $"{cpu.Value.ToString("0.0", CultureInfo.InvariantCulture)} %" : "Wird gemessen …"
                    : "Nicht verfügbar";
                MemoryValue = isFresh && memory.HasValue ? $"{memory.Value.ToString("0.0", CultureInfo.InvariantCulture)} %" : "Nicht verfügbar";
                MemoryDetail = isFresh && used.HasValue && total is > 0
                    ? $"{FormatBytes(used.Value)} von {FormatBytes(total.Value)} · Quelle: {source}"
                    : isFresh ? $"Quelle: {source}" : "Messzeitpunkt fehlt oder Messwert ist älter als 5 Sekunden; Zahlen werden nicht als live ausgegeben.";
                LiveAge = observed.HasValue
                    ? FormatLiveAge(observed.Value, source, interval)
                    : "Nicht verfügbar — die Quelle hat keinen Messzeitpunkt geliefert.";
                LiveSourceDetail = isFresh
                    ? $"Quelle: {source} · Messzeitpunkt: {observed.GetValueOrDefault().ToLocalTime():yyyy-MM-dd HH:mm:ss zzz}"
                    : observed.HasValue
                        ? $"Quelle: {source} · Messzeitpunkt {observed.GetValueOrDefault().ToLocalTime():yyyy-MM-dd HH:mm:ss zzz} liegt außerhalb des Freshness-Fensters; Werte nicht live bestätigt."
                        : $"Quelle: {source} · Messzeitpunkt fehlt; Werte werden nicht als aktuell bestätigt.";
            });
        }
        catch (JarvisApiException exception)
        {
            await SetOnUiAsync(() =>
            {
                _liveObservedAt = null;
                _liveSource = null;
                _liveSampleInterval = null;
                CpuValue = "Nicht verfügbar";
                MemoryValue = "Nicht verfügbar";
                MemoryDetail = "Live-Telemetrie ist über den aktuellen Backend-Endpunkt nicht verfügbar.";
                LiveAge = exception.StatusCode == System.Net.HttpStatusCode.NotFound
                    ? "Nicht verfügbar — Backend meldet HTTP 404 für /api/desktop/live."
                    : exception.Message;
                LiveSourceDetail = "Live-Endpunkt nicht verfügbar; Supervisor-Status ist keine Telemetriequelle.";
            });
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
            await SetOnUiAsync(() =>
            {
                _liveObservedAt = null;
                _liveSource = null;
                _liveSampleInterval = null;
                CpuValue = "Nicht verfügbar";
                MemoryValue = "Nicht verfügbar";
                MemoryDetail = "Live-Telemetrie konnte nicht gelesen werden.";
                LiveAge = "Quelle nicht erreichbar; letzter Messwert wird nicht als live weitergeführt.";
                LiveSourceDetail = "Live-Endpunkt nicht erreichbar; Supervisor-Status ist keine Telemetriequelle.";
            });
        }
        finally
        {
            await _dispatcher.InvokeAsync(UpdateFreshnessText);
            _liveGate.Release();
        }
    }

    private async Task PollStatusAsync(CancellationToken cancellationToken)
    {
        await Task.WhenAll(PollRuntimeStatusAsync(cancellationToken), PollApiStatsAsync(cancellationToken));
    }

    private async Task PollRuntimeStatusAsync(CancellationToken cancellationToken)
    {
        if (!await _runtimeStatusGate.WaitAsync(0, cancellationToken).ConfigureAwait(false)) return;
        string? rootPath = null;
        try
        {
            rootPath = _repositoryRoot;
            if (rootPath is null)
            {
                await SetOnUiAsync(() =>
                {
                    RuntimeState = "Nicht verbunden";
                    RuntimeDetail = "JARVIS-Main-Verzeichnis auswählen, um den Runtime Supervisor zu verbinden.";
                    RuntimeUpdatedAt = null;
                    _runtime = null;
                    _runtimeRoot = null;
                    _runtimeSnapshotMarkedStale = false;
                    ReplaceCollection(RuntimeComponents, Array.Empty<JarvisListItem>());
                    RuntimeComponentsStatus = "Nicht verbunden — keine Supervisor-Komponenten verfügbar.";
                    RaiseCanExecuteChanged();
                });
                return;
            }

            var snapshot = await _supervisor.GetRuntimeAsync(rootPath, cancellationToken).ConfigureAwait(false);
            await ApplyRuntimeAsync(snapshot, rootPath);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
            await SetOnUiAsync(() =>
            {
                if (!RepositoryRootsMatch(rootPath, _repositoryRoot)) return;
                RuntimeState = "Nicht verfügbar";
                RuntimeDetail = "Runtime Supervisor konnte nicht abgefragt werden. Repository-Pfad und WSL-Status prüfen.";
                RuntimeUpdatedAt = null;
                _runtime = null;
                _runtimeRoot = null;
                _runtimeSnapshotMarkedStale = false;
                ReplaceCollection(RuntimeComponents, Array.Empty<JarvisListItem>());
                RuntimeComponentsStatus = "Nicht verfügbar — kein aktueller Supervisor-Komponenten-Snapshot.";
                RaiseCanExecuteChanged();
            });
        }
        finally
        {
            _runtimeStatusGate.Release();
        }
    }

    private async Task PollApiStatsAsync(CancellationToken cancellationToken)
    {
        if (!await _apiStatusGate.WaitAsync(0, cancellationToken).ConfigureAwait(false)) return;
        try
        {
            using var stats = await _api.GetStatsAsync(cancellationToken).ConfigureAwait(false);
            await ApplyStatsAsync(stats.RootElement);
            await SetOnUiAsync(() =>
            {
                var successfulAt = DateTimeOffset.Now;
                ApiState = "Erreichbar · /api/stats";
                ApiUpdatedAt = successfulAt.LocalDateTime;
            });
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception)
        {
            await SetOnUiAsync(() =>
            {
                ApiState = exception is JarvisApiException apiException && apiException.StatusCode == System.Net.HttpStatusCode.NotFound
                    ? "Nicht verfügbar · /api/stats HTTP 404"
                    : "API nicht erreichbar";
                ApiUpdatedAt = null;
                PrimaryModel = "Nicht verfügbar — /api/stats nicht aktuell";
                MemorySummary = "Nicht verfügbar — kein aktueller /api/stats-Messwert empfangen.";
                RuntimeDataSummary = "Nicht verfügbar — kein aktueller /api/stats-Messwert empfangen.";
            });
        }
        finally
        {
            _apiStatusGate.Release();
        }
    }

    private async Task PollInventoryAsync(CancellationToken cancellationToken)
    {
        if (!await _inventoryGate.WaitAsync(0, cancellationToken).ConfigureAwait(false)) return;
        try
        {
            var snapshotTask = _api.GetDesktopSnapshotAsync(cancellationToken);
            var sttTask = _api.GetSttEventsAsync(cancellationToken);
            var ttsTask = _api.GetTtsEventsAsync(cancellationToken);
            var eventsTask = _api.GetEventsAggregateAsync(cancellationToken);
            var healthTask = _api.GetHealthHistoryAsync(cancellationToken);
            var metricsTask = _api.GetMetricsSummaryAsync(cancellationToken);
            var metricsTimeseriesTask = _api.GetMetricsTimeseriesAsync(cancellationToken);
            var skillsUsageTask = _api.GetMetricsSkillsAsync(cancellationToken);
            var routesUsageTask = _api.GetMetricsRoutesAsync(cancellationToken);
            var toolsMetricsTask = _api.GetMetricsToolsAsync(cancellationToken);
            var searchStatsTask = _api.GetMetricsSearchStatsAsync(cancellationToken);

            await ApplyOptionalInventoryAsync(snapshotTask, ApplySnapshotAsync, message =>
            {
                ReplaceCollection(Skills, Array.Empty<JarvisListItem>());
                _toolInventory.Clear();
                _voiceConfiguration = null;
                LlmConfigurationSummary = "Nicht verfügbar — kein aktueller Konfigurations-Snapshot.";
                VoiceConfigurationSummary = "Nicht verfügbar — kein aktueller Konfigurations-Snapshot.";
                RuntimeCapabilitiesSummary = "Nicht verfügbar — keine aktuellen Capability-Daten.";
                MemoryConfigurationSummary = "Nicht verfügbar — keine aktuelle Memory-Konfiguration.";
                VoiceState = ComposeVoiceState();
                SkillsStatus = message;
                RenderTools();
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(sttTask, ApplySttAsync, message =>
            {
                _sttSummary = null;
                _sttEventsTotal = null;
                _sttEventsErrors = null;
                _sttEventsEmpty = null;
                _sttEvents.Clear();
                VoiceState = ComposeVoiceState();
                if (!string.IsNullOrWhiteSpace(message)) VoiceState += $" · {message}";
                RefreshVoiceEvents(message, null);
                RefreshFallbackEventOverview();
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(ttsTask, ApplyTtsAsync, message =>
            {
                _ttsSummary = null;
                _ttsEventsTotal = null;
                _ttsEventsErrors = null;
                _ttsEvents.Clear();
                VoiceState = ComposeVoiceState();
                if (!string.IsNullOrWhiteSpace(message)) VoiceState += $" · {message}";
                RefreshVoiceEvents(null, message);
                RefreshFallbackEventOverview();
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(eventsTask, ApplyEventsAsync, message =>
            {
                if (message.Contains("HTTP 404", StringComparison.Ordinal))
                {
                    MarkEventsAggregateMissing();
                }
                else
                {
                    _eventsAggregateMissing = false;
                    ReplaceCollection(Events, Array.Empty<JarvisListItem>());
                    EventsStatus = message;
                }
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(healthTask, ApplyHealthHistoryAsync, message => HistoryStatus = message, cancellationToken);
            await ApplyOptionalInventoryAsync(metricsTask, ApplyMetricsAsync, message => MetricsSummary = message, cancellationToken);
            await ApplyOptionalInventoryAsync(metricsTimeseriesTask, ApplyMetricsTimeseriesAsync, message =>
            {
                ReplaceMetricBuckets(Array.Empty<MetricBucket>());
                MetricsTimeseriesStatus = message;
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(skillsUsageTask, document => ApplyMetricBreakdownAsync(document, "skill", SkillUsage, value => SkillUsageStatus = value), message =>
            {
                ReplaceMetricBreakdowns(SkillUsage, Array.Empty<MetricBreakdown>());
                SkillUsageStatus = message;
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(routesUsageTask, document => ApplyMetricBreakdownAsync(document, "route_layer", RouteUsage, value => RouteUsageStatus = value), message =>
            {
                ReplaceMetricBreakdowns(RouteUsage, Array.Empty<MetricBreakdown>());
                RouteUsageStatus = message;
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(toolsMetricsTask, ApplyToolMetricsAsync, message =>
            {
                _toolUsage.Clear();
                RenderTools();
                if (_toolInventory.Count == 0) ToolsStatus = message;
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(searchStatsTask, ApplySearchStatsAsync, message =>
            {
                SearchPerformanceSummary = "Nicht verfügbar";
                SearchPerformanceStatus = message;
            }, cancellationToken);
        }
        finally
        {
            _inventoryGate.Release();
        }
    }

    private async Task PollRoutingActivityAsync(CancellationToken cancellationToken)
    {
        if (!await _routingGate.WaitAsync(0, cancellationToken).ConfigureAwait(false)) return;
        try
        {
            using var document = await _api.GetRoutingEventsAsync(cancellationToken).ConfigureAwait(false);
            await ApplyRoutingEventsAsync(document.RootElement).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception)
        {
            await SetOnUiAsync(() =>
            {
                RoutingLiveStatus = "Routing-Aktivität nicht verfügbar; die 24-h-Historie wird nicht als live gewertet.";
                RoutingEventsStatus = exception is JarvisApiException apiException && apiException.StatusCode == System.Net.HttpStatusCode.NotFound
                    ? "Nicht verfügbar · /api/events/routing HTTP 404"
                    : "Routing-Historie derzeit nicht erreichbar.";
                _latestRoutingAt = null;
                _routingSourceAvailable = false;
                _routingEventsTotal = null;
                _routingEventsHandled = null;
                _routingEventsFallback = null;
                UpdateRoutingFreshness();
                RefreshFallbackEventOverview();
            }).ConfigureAwait(false);
        }
        finally
        {
            _routingGate.Release();
        }
    }

    private async Task PollAgentAutomationAsync(CancellationToken cancellationToken)
    {
        if (!await _agentAutomationGate.WaitAsync(0, cancellationToken).ConfigureAwait(false)) return;
        try
        {
            var agentTask = _api.GetAgentStatusAsync(cancellationToken);
            var automationTask = _api.GetAutomationsStatusAsync(cancellationToken);
            await ApplyOptionalInventoryAsync(agentTask, ApplyAgentStatusAsync, message =>
            {
                AgentSummary = "Nicht verfügbar";
                AgentDetail = message;
            }, cancellationToken);
            await ApplyOptionalInventoryAsync(automationTask, ApplyAutomationsStatusAsync, message =>
            {
                ReplaceCollection(AutomationSchedulers, Array.Empty<JarvisListItem>());
                AutomationsStatus = message;
            }, cancellationToken);
        }
        finally
        {
            _agentAutomationGate.Release();
        }
    }

    private async Task ApplyOptionalInventoryAsync(
        Task<JsonDocument> documentTask,
        Func<JsonElement, Task> apply,
        Action<string> markUnavailable,
        CancellationToken cancellationToken)
    {
        try
        {
            using var document = await documentTask.ConfigureAwait(false);
            await apply(document.RootElement).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (JarvisApiException exception) when (exception.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            await SetOnUiAsync(() => markUnavailable("Nicht verfügbar — aktueller Backend-Endpunkt meldet HTTP 404."));
        }
        catch (Exception)
        {
            await SetOnUiAsync(() => markUnavailable("Nicht verfügbar — keine aktuelle Backend-Antwort."));
        }
    }

    private Task ApplyRuntimeAsync(RuntimeSnapshot snapshot, string repositoryRoot) => SetOnUiAsync(() =>
    {
        if (!RepositoryRootsMatch(repositoryRoot, _repositoryRoot)) return;
        _runtime = snapshot;
        _runtimeRoot = repositoryRoot;
        _runtimeSnapshotMarkedStale = false;
        RuntimeState = snapshot.State;
        RuntimeUpdatedAt = snapshot.UpdatedAt?.ToLocalTime().DateTime;
        var detailParts = new List<string>();
        if (!string.IsNullOrWhiteSpace(snapshot.Detail)) detailParts.Add(snapshot.Detail);
        detailParts.AddRange(snapshot.DegradedReasons.Where(reason => !string.IsNullOrWhiteSpace(reason)));
        RuntimeDetail = detailParts.Count > 0 ? string.Join(" · ", detailParts) : "Status wird direkt vom Runtime Supervisor geliefert.";

        var primary = snapshot.Components.FirstOrDefault(item => item.Id == "llm-primary")
            ?? snapshot.Components.FirstOrDefault(item => item.Id == "llm-main");
        var expert = snapshot.Components.FirstOrDefault(item => item.Id == "llm-expert");
        var voice = snapshot.Components.FirstOrDefault(item => item.Id == "voice-daemon");
        var components = snapshot.Components.Take(150)
            .Select(component => new JarvisListItem(
                string.IsNullOrWhiteSpace(component.Name) ? component.Id : component.Name,
                string.Join(" · ", new[] { component.State, component.Detail }
                    .Where(value => !string.IsNullOrWhiteSpace(value))),
                $"ID: {component.Id}"))
            .ToArray();
        ReplaceCollection(RuntimeComponents, components);
        RuntimeComponentsStatus = components.Length > 0
            ? $"{components.Length} Komponenten aus dem aktuellen Runtime-Supervisor-Snapshot."
            : "Der Supervisor-Snapshot enthält keine Komponenten.";
        PrimaryState = FormatComponent(primary, "Primary-Komponente im Snapshot nicht vorhanden.");
        ExpertState = FormatComponent(expert, "Expert-Komponente im Snapshot nicht vorhanden.");
        _voiceRuntimeState = FormatComponent(voice, "Voice-Komponente im Snapshot nicht vorhanden.");
        VoiceState = ComposeVoiceState();
        UpdateRuntimeFreshness();
        RaiseCanExecuteChanged();
    });

    private Task ApplyAgentStatusAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        if (GetBoolean(root, "available") != true)
        {
            AgentSummary = "Nicht verfügbar";
            AgentDetail = "Der Runtime-Endpunkt meldet keinen verfügbaren TaskPlanner-Status.";
            return;
        }

        var state = GetString(root, "state")?.ToLowerInvariant();
        var summary = state switch
        {
            "idle" => "Kein aktiver Agent-Plan",
            "pending" => "Plan wartet auf Ausführung",
            "running" => "Plan wird ausgeführt",
            "paused" => "Plan pausiert",
            "awaiting_confirmation" => "Bestätigung erforderlich",
            "completed" => "Plan abgeschlossen",
            "failed" => "Plan fehlgeschlagen",
            "cancelled" => "Plan abgebrochen",
            _ => null,
        };
        var stepCount = GetInt64(root, "stepCount");
        var completed = GetInt64(root, "completedSteps");
        var running = GetInt64(root, "runningSteps");
        var failed = GetInt64(root, "failedSteps");
        var pending = GetInt64(root, "pendingSteps");
        var skipped = GetInt64(root, "skippedSteps");
        var observedAt = ParseTimestamp(root, "observedAt");
        var active = GetBoolean(root, "active");
        var paused = GetBoolean(root, "paused");
        var awaitingConfirmation = GetBoolean(root, "awaitingConfirmation");
        if (observedAt.HasValue && !IsFreshStatusSnapshot(observedAt.Value))
        {
            AgentSummary = "Status veraltet";
            AgentDetail = $"Der letzte Agenten-Snapshot wird nicht als aktuell dargestellt · Zeitpunkt {FormatEventTimestamp(observedAt.Value)}";
            return;
        }

        var stateFlagsMatch = state switch
        {
            "running" => active == true && paused == false && awaitingConfirmation == false,
            "paused" => active == false && paused == true && awaitingConfirmation == false,
            "awaiting_confirmation" => active == false && paused == false && awaitingConfirmation == true,
            _ => active == false && paused == false && awaitingConfirmation == false,
        };
        var totalMatches = false;
        if (stepCount.HasValue && completed.HasValue && running.HasValue && failed.HasValue && pending.HasValue && skipped.HasValue)
        {
            try
            {
                var accounted = checked(completed.Value + running.Value + failed.Value + pending.Value + skipped.Value);
                totalMatches = accounted == stepCount.Value;
            }
            catch (OverflowException)
            {
                totalMatches = false;
            }
        }
        if (summary is null || !stepCount.HasValue || !completed.HasValue || !running.HasValue ||
            !failed.HasValue || !pending.HasValue || !skipped.HasValue || !observedAt.HasValue ||
            !active.HasValue || !paused.HasValue || !awaitingConfirmation.HasValue || !stateFlagsMatch ||
            new[] { stepCount.Value, completed.Value, running.Value, failed.Value, pending.Value, skipped.Value }.Any(value => value < 0) ||
            !totalMatches)
        {
            AgentSummary = "Nicht verfügbar";
            AgentDetail = "Der Agentenstatus ist unvollständig oder inkonsistent; es werden keine Planinhalte angezeigt.";
            return;
        }

        var detail = $"{completed.Value}/{stepCount.Value} Schritte abgeschlossen · {running.Value} aktiv · {pending.Value} ausstehend · {failed.Value} fehlgeschlagen · {skipped.Value} übersprungen";
        if (awaitingConfirmation == true) detail += " · wartet auf Bestätigung";
        if (GetBoolean(root, "canPause") == true) detail += " · pausierbar";
        AgentSummary = summary;
        AgentDetail = $"{detail} · Statuszeit {FormatEventTimestamp(observedAt.Value)}";
    });

    private Task ApplyAutomationsStatusAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        if (!TryGetArray(root, "schedulers", out var schedulers))
        {
            ReplaceCollection(AutomationSchedulers, Array.Empty<JarvisListItem>());
            AutomationsStatus = "Nicht verfügbar — der Scheduler-Endpunkt lieferte keine Liste.";
            return;
        }

        var observedAt = ParseTimestamp(root, "observedAt");
        if (!observedAt.HasValue || !IsFreshStatusSnapshot(observedAt.Value))
        {
            ReplaceCollection(AutomationSchedulers, Array.Empty<JarvisListItem>());
            AutomationsStatus = observedAt.HasValue
                ? $"Snapshot veraltet — Schedulerzustände werden nicht als aktuell angezeigt · Zeitpunkt {FormatEventTimestamp(observedAt.Value)}"
                : "Nicht verfügbar — der Scheduler-Snapshot hat keinen gültigen Messzeitpunkt.";
            return;
        }
        var items = new List<JarvisListItem>();
        foreach (var scheduler in schedulers.EnumerateArray())
        {
            var id = GetString(scheduler, "id");
            var name = id switch
            {
                "reminder_poller" => "JARVIS-Erinnerungsdienst",
                "health_snapshot" => "Health-Snapshot",
                "observation_collector" => "Beobachtungssammlung",
                _ => null,
            };
            if (name is null) continue;

            var state = GetString(scheduler, "state")?.ToLowerInvariant() switch
            {
                "running" => "läuft",
                "stopped" => "gestoppt",
                "disabled" => "deaktiviert",
                _ => "Zustand unbekannt",
            };
            var details = new List<string> { state };
            if (GetInt64(scheduler, "configuredIntervalSeconds") is long interval && interval > 0)
                details.Add($"Intervall {FormatInterval(interval)}");

            if (GetBoolean(scheduler, "lastRunAvailable") == true &&
                ParseTimestamp(scheduler, "lastRunAt") is DateTimeOffset lastRun)
                details.Add($"letzter Lauf {FormatEventTimestamp(lastRun)}");
            else
                details.Add("kein Laufzeitpunkt erfasst");

            if (id == "reminder_poller")
            {
                if (GetBoolean(scheduler, "dailyRundownEnabled") is bool dailyEnabled)
                {
                    var dailyTime = GetString(scheduler, "dailyRundownTime");
                    details.Add(dailyEnabled && IsSafeTime(dailyTime)
                        ? $"Tagesüberblick {dailyTime}"
                        : $"Tagesüberblick {(dailyEnabled ? "aktiv, Zeit nicht gemeldet" : "deaktiviert")}");
                }
                if (GetBoolean(scheduler, "weeklyRundownEnabled") is bool weeklyEnabled)
                {
                    var day = GetString(scheduler, "weeklyRundownDay")?.ToLowerInvariant() switch
                    {
                        "monday" => "Montag",
                        "tuesday" => "Dienstag",
                        "wednesday" => "Mittwoch",
                        "thursday" => "Donnerstag",
                        "friday" => "Freitag",
                        "saturday" => "Samstag",
                        "sunday" => "Sonntag",
                        _ => null,
                    };
                    details.Add(weeklyEnabled && day is not null
                        ? $"Wochenüberblick {day}"
                        : $"Wochenüberblick {(weeklyEnabled ? "aktiv, Tag nicht gemeldet" : "deaktiviert")}");
                }
            }
            else if (id == "observation_collector" && GetBoolean(scheduler, "autoConsultEnabled") is bool autoConsult)
            {
                details.Add($"Auto-Konsultation {(autoConsult ? "aktiv" : "deaktiviert")}");
            }

            var timestamp = observedAt.HasValue ? FormatEventTimestamp(observedAt.Value) : "Beobachtungszeit nicht gemeldet";
            items.Add(new JarvisListItem(name, string.Join(" · ", details), timestamp));
        }

        ReplaceCollection(AutomationSchedulers, items);
        AutomationsStatus = items.Count > 0
            ? $"{items.Count} systemeigene Scheduler · nur Status und Konfiguration, keine Reminder-Datensätze · Snapshot {(observedAt.HasValue ? FormatEventTimestamp(observedAt.Value) : "ohne Zeitstempel")}"
            : "Keine bekannten systemeigenen Scheduler gemeldet.";
    });

    private static string FormatInterval(long seconds) => seconds % 3600 == 0
        ? $"{seconds / 3600} h"
        : seconds % 60 == 0 ? $"{seconds / 60} min" : $"{seconds} s";

    private static bool IsSafeTime(string? value) =>
        value is { Length: 5 } && TimeOnly.TryParseExact(value, "HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None, out _);

    private static bool IsFreshStatusSnapshot(DateTimeOffset observedAt)
    {
        var age = DateTimeOffset.UtcNow - observedAt.ToUniversalTime();
        return age >= TimeSpan.FromSeconds(-5) && age <= StatusSnapshotFreshnessLimit;
    }

    private Task ApplyStatsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        var runtimeData = new List<string>();
        if (TryGetObject(root, "llm", out var llm))
        {
            var model = GetString(llm, "model");
            PrimaryModel = !string.IsNullOrWhiteSpace(model) ? model : "Modell nicht von /api/stats gemeldet";

            if (llm.TryGetProperty("api_fallback", out var fallback))
            {
                runtimeData.Add(fallback.ValueKind switch
                {
                    JsonValueKind.Null => "Cloud-Fallback: nicht aktiv",
                    JsonValueKind.String => $"Cloud-Fallback: {fallback.GetString()}",
                    _ => "Cloud-Fallback: Status nicht lesbar",
                });
            }
        }
        else
        {
            PrimaryModel = "LLM-Status nicht von /api/stats gemeldet";
        }

        AddBooleanStatus(root, "web_research", "Webrecherche", runtimeData);
        if (TryGetObject(root, "reminders", out var reminders) && GetInt64(reminders, "active") is long activeReminders)
        {
            runtimeData.Add($"Erinnerungen: {activeReminders.ToString(CultureInfo.InvariantCulture)} aktiv");
        }
        if (TryGetObject(root, "news", out var news) && GetInt64(news, "feeds") is long feeds)
        {
            runtimeData.Add($"News-Feeds: {feeds.ToString(CultureInfo.InvariantCulture)} gemeldet");
        }
        AddBooleanStatus(root, "calendar", "Kalender", runtimeData);
        RuntimeDataSummary = runtimeData.Count > 0
            ? string.Join(" · ", runtimeData)
            : "Die aktuelle /api/stats-Antwort enthält keine zusätzlichen Dienststatus.";

        MemorySummary = "Memory wird von der aktuellen /api/stats-Antwort nicht gemeldet.";
        if (TryGetObject(root, "memory", out var memory))
        {
            var vectors = GetInt64(memory, "vectors");
            var proactive = GetBoolean(memory, "proactive");
            MemorySummary = vectors.HasValue
                ? $"{vectors.Value.ToString(CultureInfo.InvariantCulture)} FAISS-Vektoren · proaktives Surfacing {(proactive == true ? "aktiv" : proactive == false ? "aus" : "nicht gemeldet")} · Aggregat aus /api/stats"
                : "Memory verfügbar, aber der aktuelle API-Status enthält keine Zählung.";
        }
        var loadedSkills = GetInt64(root, "skills_loaded");
        if (loadedSkills.HasValue && Skills.Count == 0)
        {
            SkillsStatus = $"/api/stats meldet {loadedSkills.Value.ToString(CultureInfo.InvariantCulture)} geladene Skills; das detaillierte Inventar ist über den aktuellen API-Endpunkt nicht verfügbar.";
        }

        if (TryGetObject(root, "context_window", out var context))
        {
            var segments = GetInt64(context, "segments");
            var tokens = GetInt64(context, "tokens");
            var percent = GetDouble(context, "usage_pct");
            var isOpen = GetBoolean(context, "open");
            if (segments.HasValue || tokens.HasValue)
            {
                MemorySummary += $" · Kontext: {segments?.ToString(CultureInfo.InvariantCulture) ?? "?"} Segmente, {tokens?.ToString(CultureInfo.InvariantCulture) ?? "?"} Tokens";
                if (percent.HasValue) MemorySummary += $", {percent.Value.ToString("0.0", CultureInfo.InvariantCulture)} %";
                if (isOpen.HasValue) MemorySummary += isOpen.Value ? " · Kontextfenster offen" : " · Kontextfenster geschlossen";
            }
        }
    });

    private static void AddBooleanStatus(JsonElement root, string propertyName, string label, ICollection<string> summary)
    {
        if (!root.TryGetProperty(propertyName, out _)) return;
        var value = GetBoolean(root, propertyName);
        summary.Add(value.HasValue ? $"{label}: {(value.Value ? "aktiv" : "aus")}" : $"{label}: Status nicht lesbar");
    }

    private Task ApplySnapshotAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        if (TryGetObject(root, "llm", out var llm))
        {
            var details = new List<string>();
            if (GetString(llm, "provider") is { Length: > 0 } provider) details.Add($"Provider {provider}");
            if (GetInt64(llm, "contextSize") is long contextSize) details.Add($"Kontext {contextSize.ToString(CultureInfo.InvariantCulture)} Tokens");
            if (GetInt64(llm, "gpuLayers") is long gpuLayers) details.Add($"GPU-Layer {gpuLayers.ToString(CultureInfo.InvariantCulture)}");
            if (GetInt64(llm, "batchSize") is long batchSize) details.Add($"Batch {batchSize.ToString(CultureInfo.InvariantCulture)}");
            if (GetInt64(llm, "ubatchSize") is long ubatchSize) details.Add($"Micro-Batch {ubatchSize.ToString(CultureInfo.InvariantCulture)}");
            if (GetDouble(llm, "temperature") is double temperature) details.Add($"Temperatur {temperature.ToString("0.00", CultureInfo.InvariantCulture)}");
            if (GetDouble(llm, "topP") is double topP) details.Add($"Top-P {topP.ToString("0.00", CultureInfo.InvariantCulture)}");
            if (GetInt64(llm, "topK") is long topK) details.Add($"Top-K {topK.ToString(CultureInfo.InvariantCulture)}");
            if (GetBoolean(llm, "toolCalling") is bool toolCalling) details.Add($"Tool Calling {(toolCalling ? "aktiv" : "aus")}");
            LlmConfigurationSummary = details.Count > 0
                ? string.Join(" · ", details) + " · Quelle: /api/desktop/snapshot"
                : "Snapshot verfügbar, aber keine LLM-Konfigurationswerte gemeldet.";
        }
        else
        {
            LlmConfigurationSummary = "Snapshot meldet keine LLM-Konfigurationswerte.";
        }

        var skills = new List<JarvisListItem>();
        if (TryGetArray(root, "skills", out var skillArray))
        {
            foreach (var skill in skillArray.EnumerateArray().Take(200))
            {
                var name = GetString(skill, "name") ?? GetString(skill, "id");
                if (string.IsNullOrWhiteSpace(name)) continue;
                var detail = GetString(skill, "description") ?? string.Empty;
                var category = GetString(skill, "category");
                var enabled = GetBoolean(skill, "enabled");
                var suffix = string.Join(" · ", new[]
                {
                    category,
                    enabled.HasValue ? enabled.Value ? "aktiv" : "deaktiviert" : null,
                    GetInt64(skill, "intents") is long intents ? $"{intents} Intents" : null,
                    GetInt64(skill, "tools") is long toolCount ? $"{toolCount} Tools" : null,
                }.Where(value => !string.IsNullOrWhiteSpace(value)));
                skills.Add(new JarvisListItem(name, string.IsNullOrWhiteSpace(suffix) ? detail : $"{suffix} · {detail}".Trim(' ', '·'), string.Empty));
            }
        }

        var tools = new List<JarvisListItem>();
        if (TryGetArray(root, "tools", out var toolArray))
        {
            foreach (var tool in toolArray.EnumerateArray().Take(300))
            {
                var name = GetString(tool, "name") ?? GetString(tool, "id");
                if (string.IsNullOrWhiteSpace(name)) continue;
                var registered = GetBoolean(tool, "registered");
                var skill = GetString(tool, "skill");
                var status = registered.HasValue ? registered.Value ? "registriert" : "nicht registriert" : "Status nicht gemeldet";
                var detail = GetString(tool, "description") ?? string.Empty;
                tools.Add(new JarvisListItem(name, string.Join(" · ", new[] { status, skill, detail }.Where(value => !string.IsNullOrWhiteSpace(value))), string.Empty));
            }
        }

        ReplaceCollection(Skills, skills);
        _toolInventory = tools;
        SkillsStatus = skills.Count > 0 ? $"{skills.Count} Skills aus /api/desktop/snapshot." : "Snapshot verfügbar, aber keine Skills gemeldet.";
        ToolsStatus = tools.Count > 0 ? $"{tools.Count} Tools aus /api/desktop/snapshot." : "Snapshot verfügbar, aber kein Tool-Inventar gemeldet.";
        RenderTools();

        if (TryGetObject(root, "voice", out var voice))
        {
            var stt = GetString(voice, "sttBackend");
            var sttModel = GetString(voice, "sttModel");
            var sttProvider = GetString(voice, "sttProvider");
            var tts = GetString(voice, "tts");
            var voiceDetails = new List<string>();
            if (!string.IsNullOrWhiteSpace(stt)) voiceDetails.Add($"STT {stt}{(sttModel is not null ? $" ({sttModel})" : string.Empty)}");
            if (!string.IsNullOrWhiteSpace(sttProvider)) voiceDetails.Add($"STT-Provider {sttProvider}");
            if (GetInt64(voice, "sttThreads") is long sttThreads) voiceDetails.Add($"STT-Threads {sttThreads.ToString(CultureInfo.InvariantCulture)}");
            if (!string.IsNullOrWhiteSpace(tts)) voiceDetails.Add($"TTS {tts}");
            if (GetInt64(voice, "sampleRate") is long sampleRate) voiceDetails.Add($"{sampleRate.ToString(CultureInfo.InvariantCulture)} Hz");
            if (GetInt64(voice, "channels") is long channels) voiceDetails.Add($"{channels.ToString(CultureInfo.InvariantCulture)} Kanal/Kanäle");
            if (GetString(voice, "outputBackend") is { Length: > 0 } outputBackend) voiceDetails.Add($"Ausgabe {outputBackend}");
            if (GetString(voice, "language") is { Length: > 0 } language) voiceDetails.Add($"Sprache {language}");
            if (GetString(voice, "wakeKeyword") is { Length: > 0 } wakeKeyword) voiceDetails.Add($"Wake-Keyword {wakeKeyword}");
            if (GetBoolean(voice, "ttsNormalization") is bool normalization) voiceDetails.Add($"TTS-Normalisierung {(normalization ? "aktiv" : "aus")}");
            var configured = string.Join(" · ", voiceDetails);
            _voiceConfiguration = string.IsNullOrWhiteSpace(configured) ? null : $"Konfiguration: {configured}";
            VoiceConfigurationSummary = voiceDetails.Count > 0
                ? string.Join(" · ", voiceDetails) + " · Quelle: /api/desktop/snapshot"
                : "Snapshot verfügbar, aber keine Voice-Konfigurationswerte gemeldet.";
        }
        else
        {
            _voiceConfiguration = null;
            VoiceConfigurationSummary = "Snapshot meldet keine Voice-Konfigurationswerte.";
        }

        if (TryGetObject(root, "capabilities", out var capabilities))
        {
            var capabilityLabels = new (string Key, string Label)[]
            {
                ("reminders", "Erinnerungen"), ("calendar", "Kalender"), ("news", "News"),
                ("weather", "Wetter"), ("memory", "Memory"), ("contextWindow", "Kontextfenster"),
                ("metrics", "Metriken"),
            };
            var available = capabilityLabels
                .Select(item => GetBoolean(capabilities, item.Key) is bool enabled
                    ? $"{item.Label}: {(enabled ? "Manager vorhanden" : "nicht vorhanden")}" : null)
                .Where(value => value is not null)
                .ToArray();
            RuntimeCapabilitiesSummary = available.Length > 0
                ? string.Join(" · ", available) + " · Quelle: /api/desktop/snapshot"
                : "Snapshot verfügbar, aber keine Capability-Werte gemeldet.";
        }
        else RuntimeCapabilitiesSummary = "Snapshot meldet keine Runtime-Capabilities.";

        if (TryGetObject(root, "memoryConfig", out var memoryConfig))
        {
            var memorySettings = new List<string>();
            if (GetBoolean(memoryConfig, "enabled") is bool enabled) memorySettings.Add($"Konversations-Memory {(enabled ? "aktiviert" : "deaktiviert")}");
            if (GetBoolean(memoryConfig, "proactiveSurfacing") is bool proactive) memorySettings.Add($"proaktives Surfacing {(proactive ? "aktiviert" : "deaktiviert")}");
            if (GetBoolean(memoryConfig, "contextWindowEnabled") is bool contextWindow) memorySettings.Add($"Kontextfenster {(contextWindow ? "aktiviert" : "deaktiviert")}");
            if (GetInt64(root, "metricsRetentionDays") is long retentionDays) memorySettings.Add($"Metrik-Aufbewahrung {retentionDays.ToString(CultureInfo.InvariantCulture)} Tage");
            MemoryConfigurationSummary = memorySettings.Count > 0
                ? string.Join(" · ", memorySettings) + " · Quelle: /api/desktop/snapshot"
                : "Snapshot vorhanden, aber keine Memory-Konfiguration gemeldet.";
        }
        else MemoryConfigurationSummary = "Snapshot meldet keine Memory-Konfiguration.";
        VoiceState = ComposeVoiceState();
    });

    private Task ApplySttAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        var total = GetInt64(root, "total");
        var errors = GetInt64(root, "errors");
        var empty = GetInt64(root, "empty");
        _sttEventsTotal = NonNegative(total);
        _sttEventsErrors = NonNegative(errors);
        _sttEventsEmpty = NonNegative(empty);
        var rate = GetDouble(root, "success_rate");
        _sttSummary = total.HasValue
            ? $"STT 24 h: {total} Transkriptionen, {errors ?? 0} Fehler, {empty ?? 0} leer" +
              (rate.HasValue ? $", {rate.Value.ToString("0.0", CultureInfo.InvariantCulture)} % erfolgreich" : string.Empty)
            : null;
        _sttEvents = ReadSttEvents(root);
        RefreshVoiceEvents("verfügbar", null);
        VoiceState = ComposeVoiceState();
        RefreshFallbackEventOverview();
    });

    private Task ApplyTtsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        var total = GetInt64(root, "total_syntheses");
        var errors = GetInt64(root, "errors");
        var cacheHits = GetInt64(root, "cache_hits");
        var average = GetDouble(root, "avg_generation_s");
        _ttsSummary = total.HasValue
            ? $"TTS 24 h: {total} Synthesen, {errors ?? 0} Fehler, {cacheHits ?? 0} Cache-Treffer" +
              (average.HasValue ? $", Ø {average.Value.ToString("0.00", CultureInfo.InvariantCulture)} s" : string.Empty)
            : null;
        _ttsEvents = ReadTtsEvents(root);
        _ttsEventsTotal = NonNegative(total);
        _ttsEventsErrors = NonNegative(errors);
        RefreshVoiceEvents(null, "verfügbar");
        VoiceState = ComposeVoiceState();
        RefreshFallbackEventOverview();
    });

    private Task ApplyRoutingEventsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        _routingSourceAvailable = true;
        _routingEventsTotal = NonNegative(GetInt64(root, "total"));
        _routingEventsHandled = NonNegative(GetInt64(root, "handled"));
        _routingEventsFallback = NonNegative(GetInt64(root, "fallback"));
        var events = new List<(DateTimeOffset At, JarvisListItem Item)>();
        if (TryGetArray(root, "data_points", out var points))
        {
            foreach (var point in points.EnumerateArray())
            {
                var timestamp = ParseTimestamp(point, "timestamp");
                if (!timestamp.HasValue) continue;
                var route = GetString(point, "intent");
                var status = GetString(point, "status")?.ToLowerInvariant() switch
                {
                    "handled" => "verarbeitet",
                    "fallback" => "Fallback",
                    _ => "Status unbekannt",
                };
                var details = new List<string>();
                AddMetric(details, point, "latency_ms", "Latenz", "0.00", " ms");
                events.Add((timestamp.Value, new JarvisListItem(
                    $"{NormalizeRouteLabel(route)} · {status}",
                    details.Count == 0 ? "Keine Latenz gemeldet." : string.Join(" · ", details),
                    FormatEventTimestamp(timestamp.Value))));
            }
        }

        var items = events.OrderByDescending(entry => entry.At).Take(10).Select(entry => entry.Item).ToArray();
        _latestRoutingAt = events.Count > 0 ? events.Max(entry => entry.At) : null;
        ReplaceCollection(RoutingEvents, items);
        RoutingEventsStatus = items.Length > 0
            ? $"{items.Length} datensparsame Routing-Messpunkte aus dem 24-h-Fenster · Abfrage {DateTime.Now:HH:mm:ss}; Routennamen sind auf feste Kategorien begrenzt."
            : "Keine Routing-Messpunkte aus dem 24-h-Fenster empfangen.";
        UpdateRoutingFreshness();
        RefreshFallbackEventOverview();
    });

    private static string NormalizeRouteLabel(string? route)
    {
        if (string.IsNullOrWhiteSpace(route)) return "Weitere Route";
        if (route.Equals("llm_direct", StringComparison.OrdinalIgnoreCase)) return "Direkter LLM-Pfad";
        if (route.Equals("llm_fallback", StringComparison.OrdinalIgnoreCase)) return "LLM-Fallback";
        if (route.Equals("keyword_direct", StringComparison.OrdinalIgnoreCase)) return "Direkte Keyword-Route";
        if (route.Equals("P4-LLM", StringComparison.OrdinalIgnoreCase)) return "P4-LLM-Tool-Aufruf";
        if (route.StartsWith("cal_l0", StringComparison.OrdinalIgnoreCase) || route.StartsWith("CAL-L0", StringComparison.OrdinalIgnoreCase))
            return "CAL-L0-Pfad";
        return "Weitere Route";
    }

    private List<VoiceEventEntry> ReadSttEvents(JsonElement root)
    {
        if (!TryGetArray(root, "data_points", out var points)) return new();
        var items = new List<VoiceEventEntry>();
        foreach (var point in points.EnumerateArray())
        {
            var timestamp = ParseTimestamp(point, "timestamp");
            if (!timestamp.HasValue) continue;
            var status = GetString(point, "status")?.ToLowerInvariant() switch
            {
                "success" => "verarbeitet",
                "empty" => "leer",
                "error" => "Fehler",
                _ => "Status unbekannt",
            };
            var details = new List<string>();
            AddDuration(details, point, "audio_duration_s", "Audio");
            if (GetInt64(point, "segments") is long segments && segments >= 0)
                details.Add($"{segments.ToString(CultureInfo.InvariantCulture)} Segmente");
            items.Add(new VoiceEventEntry(timestamp.Value, new JarvisListItem(
                $"STT · {status}",
                details.Count == 0 ? "Keine Leistungsdetails gemeldet." : string.Join(" · ", details),
                FormatEventTimestamp(timestamp.Value))));
        }
        return items.OrderByDescending(item => item.ObservedAt).Take(10).ToList();
    }

    private List<VoiceEventEntry> ReadTtsEvents(JsonElement root)
    {
        if (!TryGetArray(root, "data_points", out var points)) return new();
        var items = new List<VoiceEventEntry>();
        foreach (var point in points.EnumerateArray())
        {
            var timestamp = ParseTimestamp(point, "timestamp");
            if (!timestamp.HasValue) continue;
            var details = new List<string>();
            AddDuration(details, point, "generation_time_s", "Erzeugung");
            AddDuration(details, point, "audio_duration_s", "Audio");
            AddMetric(details, point, "rtf", "RTF", "0.00");
            AddDuration(details, point, "ttfc_s", "TTFC");
            items.Add(new VoiceEventEntry(timestamp.Value, new JarvisListItem(
                "TTS · Synthese (Ergebnis nicht ausgewiesen)",
                details.Count == 0 ? "Keine Leistungsdetails gemeldet." : string.Join(" · ", details),
                FormatEventTimestamp(timestamp.Value))));
        }
        return items.OrderByDescending(item => item.ObservedAt).Take(10).ToList();
    }

    private void RefreshVoiceEvents(string? sttState, string? ttsState)
    {
        var items = _sttEvents.Concat(_ttsEvents)
            .OrderByDescending(entry => entry.ObservedAt)
            .Take(20)
            .Select(entry => entry.Item)
            .ToArray();
        ReplaceCollection(VoiceEvents, items);
        var sourceStates = new List<string>();
        if (sttState is not null) sourceStates.Add($"STT {sttState}");
        if (ttsState is not null) sourceStates.Add($"TTS {ttsState}");
        var sourceDetail = sourceStates.Count > 0 ? $" · {string.Join(", ", sourceStates)}" : string.Empty;
        VoiceEventsStatus = items.Length > 0
            ? $"{items.Length} datensparsame Ereignispunkte aus dem 24-h-Fenster · Abfrage {DateTime.Now:HH:mm:ss}{sourceDetail} · keine Transkript- oder Sprachinhalte."
            : $"Keine datensparsamen STT-/TTS-Ereignispunkte im 24-h-Fenster empfangen{sourceDetail}.";
    }

    private static string FormatEventTimestamp(DateTimeOffset timestamp) =>
        timestamp.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss zzz", CultureInfo.InvariantCulture);

    private static void AddDuration(ICollection<string> details, JsonElement point, string propertyName, string label) =>
        AddMetric(details, point, propertyName, label, "0.00", " s");

    private static void AddMetric(ICollection<string> details, JsonElement point, string propertyName, string label, string format, string suffix = "")
    {
        if (GetDouble(point, propertyName) is double value && double.IsFinite(value) && value >= 0)
            details.Add($"{label} {value.ToString(format, CultureInfo.InvariantCulture)}{suffix}");
    }

    private sealed record VoiceEventEntry(DateTimeOffset ObservedAt, JarvisListItem Item);

    private Task ApplyEventsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        _eventsAggregateMissing = false;
        var items = new List<JarvisListItem>();
        var total = GetInt64(root, "total");
        if (TryGetObject(root, "severities", out var severities))
        {
            foreach (var property in severities.EnumerateObject().OrderByDescending(entry => entry.Value.ValueKind == JsonValueKind.Number ? entry.Value.GetInt64() : 0))
            {
                if (property.Value.ValueKind == JsonValueKind.Number)
                    items.Add(new JarvisListItem($"Schweregrad · {property.Name}", $"{property.Value.GetInt64()} aggregierte Events", "letzte 24 h"));
            }
        }
        if (items.Count == 0 && TryGetObject(root, "categories", out var categories))
        {
            foreach (var property in categories.EnumerateObject())
            {
                if (property.Value.ValueKind == JsonValueKind.Number)
                    items.Add(new JarvisListItem($"Kategorie · {property.Name}", $"{property.Value.GetInt64()} aggregierte Events", "letzte 24 h"));
            }
        }
        ReplaceCollection(Events, items);
        EventsStatus = total.HasValue ? $"{total.Value} aggregierte Events aus dem 24-h-Fenster; keine Rohereignisse." : "Der Endpunkt lieferte keine Event-Anzahl.";
    });

    private void MarkEventsAggregateMissing()
    {
        _eventsAggregateMissing = true;
        RefreshFallbackEventOverview();
    }

    private void RefreshFallbackEventOverview()
    {
        if (!_eventsAggregateMissing) return;

        var items = new List<JarvisListItem>();
        if (_routingEventsTotal is long routingTotal)
        {
            var breakdown = new List<string>();
            if (_routingEventsHandled is long handled) breakdown.Add($"{handled} verarbeitet");
            if (_routingEventsFallback is long fallback) breakdown.Add($"{fallback} Fallback");
            items.Add(new JarvisListItem(
                "Routing",
                $"{routingTotal} Entscheidungen" + (breakdown.Count > 0 ? $" · {string.Join(" · ", breakdown)}" : string.Empty),
                "letzte 24 h"));
        }

        if (_sttEventsTotal is long sttTotal)
        {
            var breakdown = new List<string>();
            if (_sttEventsErrors is long errors) breakdown.Add($"{errors} Fehler");
            if (_sttEventsEmpty is long empty) breakdown.Add($"{empty} leer");
            items.Add(new JarvisListItem(
                "STT",
                $"{sttTotal} Transkriptionen" + (breakdown.Count > 0 ? $" · {string.Join(" · ", breakdown)}" : string.Empty),
                "letzte 24 h"));
        }

        if (_ttsEventsTotal is long ttsTotal)
        {
            var detail = $"{ttsTotal} Synthesen" + (_ttsEventsErrors is long errors ? $" · {errors} Fehler" : string.Empty);
            items.Add(new JarvisListItem("TTS", detail, "letzte 24 h"));
        }

        ReplaceCollection(Events, items);
        EventsStatus = items.Count > 0
            ? $"{items.Count} verfügbare 24-h-Quellen · aus realen Routing-/STT-/TTS-Aggregaten zusammengesetzt; keine Rohereignisse."
            : "Der Aggregat-Endpunkt fehlt; die verfügbaren Einzelquellen lieferten noch keine nutzbaren Zähler.";
    }

    private static long? NonNegative(long? value) => value is >= 0 ? value : null;

    private Task ApplyHealthHistoryAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        var metrics = new List<JarvisListItem>();
        if (TryGetArray(root, "available_metrics", out var metricArray))
        {
            foreach (var metricElement in metricArray.EnumerateArray().Take(40))
            {
                if (metricElement.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(metricElement.GetString()))
                    continue;

                var name = metricElement.GetString()!;
                var detail = "Trend für diese Kennzahl wurde vom Backend in dieser Antwort nicht mitgeliefert.";
                var timestamp = "Nicht gemessen";
                if (TryGetObject(root, "trends", out var trends) && trends.TryGetProperty(name, out var trend))
                {
                    if (TryGetObject(trend, "stats", out var stats))
                    {
                        var count = GetInt64(stats, "count");
                        if (count == 0)
                        {
                            detail = "Keine Messpunkte für diese Kennzahl im ausgewählten Zeitraum.";
                        }
                        else
                        {
                            var values = new List<string>();
                            if (GetDouble(stats, "latest") is double latest)
                                values.Add($"zuletzt {latest.ToString("0.##", CultureInfo.InvariantCulture)}");
                            if (GetDouble(stats, "mean") is double mean)
                                values.Add($"Ø {mean.ToString("0.##", CultureInfo.InvariantCulture)}");
                            if (GetDouble(stats, "min") is double minimum && GetDouble(stats, "max") is double maximum)
                                values.Add($"Spanne {minimum.ToString("0.##", CultureInfo.InvariantCulture)}–{maximum.ToString("0.##", CultureInfo.InvariantCulture)}");
                            if (count is > 0)
                                values.Add($"{count.Value.ToString(CultureInfo.InvariantCulture)} Messpunkte");
                            if (values.Count > 0)
                                detail = string.Join(" · ", values) + " · historisch, nicht live";
                            else if (!count.HasValue && TryGetArray(trend, "data", out var emptyTrendData) && emptyTrendData.GetArrayLength() == 0)
                                detail = "Keine Messpunkte für diese Kennzahl im ausgewählten Zeitraum.";
                            else
                                detail = "Trendantwort vorhanden, aber ohne auswertbare Statistik.";

                            if (GetDouble(stats, "latest_ts") is double latestTimestamp && double.IsFinite(latestTimestamp))
                            {
                                var milliseconds = latestTimestamp * 1000d;
                                if (milliseconds >= long.MinValue && milliseconds <= long.MaxValue)
                                {
                                    try
                                    {
                                        timestamp = DateTimeOffset.FromUnixTimeMilliseconds(
                                            (long)Math.Round(milliseconds, MidpointRounding.AwayFromZero))
                                            .ToLocalTime().ToString("dd.MM.yyyy HH:mm:ss", CultureInfo.InvariantCulture);
                                    }
                                    catch (ArgumentOutOfRangeException)
                                    {
                                        timestamp = "Messzeitpunkt ungültig";
                                    }
                                }
                            }
                        }
                    }
                    else if (TryGetArray(trend, "data", out var trendData) && trendData.GetArrayLength() == 0)
                    {
                        detail = "Keine Messpunkte für diese Kennzahl im ausgewählten Zeitraum.";
                    }
                    else
                    {
                        detail = "Trenddaten vorhanden, aber ohne auswertbare Zusammenfassung.";
                    }
                }

                metrics.Add(new JarvisListItem(name, detail, timestamp));
            }
        }

        ReplaceCollection(HealthMetrics, metrics);
        var withSamples = metrics.Count(metric => metric.Detail.Contains("Messpunkte", StringComparison.Ordinal) &&
            !metric.Detail.StartsWith("Keine ", StringComparison.Ordinal));
        HistoryStatus = metrics.Count > 0
            ? $"{metrics.Count} Health-Kennzahlen, davon {withSamples} mit Messpunkten · /api/events/health · historische Daten, nicht live"
            : "Keine Health-Kennzahlen im aktuellen Backend-Zeitraum verfügbar; keine Live-Werte aus Historie abgeleitet.";
    });

    private Task ApplySearchStatsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        if (root.ValueKind != JsonValueKind.Array)
        {
            SearchPerformanceSummary = "Nicht verfügbar";
            SearchPerformanceStatus = "Nicht verfügbar — /api/metrics/search_stats lieferte kein Zeitreihenformat.";
            return;
        }

        long queryCount = 0;
        long pageCount = 0;
        long successfulPageCount = 0;
        long successfulPageSamples = 0;
        var hasInconsistentSuccessData = false;
        double latencyTotal = 0;
        long latencySamples = 0;
        DateTimeOffset? latestAt = null;

        foreach (var item in root.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object || GetInt64(item, "search_pages_total") is not long totalPages || totalPages < 0)
                continue;

            queryCount++;
            pageCount += totalPages;
            if (GetInt64(item, "search_pages_ok") is long successfulPages && successfulPages >= 0)
            {
                if (successfulPages <= totalPages)
                {
                    successfulPageCount += successfulPages;
                    successfulPageSamples++;
                }
                else
                {
                    hasInconsistentSuccessData = true;
                }
            }

            if (GetDouble(item, "search_latency_ms") is double latency && double.IsFinite(latency) && latency >= 0)
            {
                latencyTotal += latency;
                latencySamples++;
            }

            if (GetDouble(item, "timestamp") is double timestamp && double.IsFinite(timestamp))
            {
                var timestampMilliseconds = timestamp * 1000d;
                if (timestampMilliseconds >= long.MinValue && timestampMilliseconds <= long.MaxValue)
                {
                    try
                    {
                        var observedAt = DateTimeOffset.FromUnixTimeMilliseconds(
                            (long)Math.Round(timestampMilliseconds, MidpointRounding.AwayFromZero));
                        if (!latestAt.HasValue || observedAt > latestAt.Value) latestAt = observedAt;
                    }
                    catch (ArgumentOutOfRangeException)
                    {
                        // Ignore invalid timestamps while retaining valid aggregate values.
                    }
                }
            }
        }

        if (queryCount == 0)
        {
            SearchPerformanceSummary = "Keine Messpunkte im Zeitraum.";
            SearchPerformanceStatus = "0 Suchmessungen aus /api/metrics/search_stats · letzte 24 h · nur aggregierte Kennzahlen, keine Suchbegriffe/URLs.";
            return;
        }

        var summary = new List<string> { $"{queryCount.ToString(CultureInfo.InvariantCulture)} Suchanfragen" };
        if (successfulPageSamples == queryCount && pageCount > 0)
        {
            var successRate = successfulPageCount * 100d / pageCount;
            summary.Add($"{successfulPageCount.ToString(CultureInfo.InvariantCulture)}/{pageCount.ToString(CultureInfo.InvariantCulture)} Ergebnisseiten erfolgreich ({successRate.ToString("0.0", CultureInfo.InvariantCulture)} %)");
        }
        else if (hasInconsistentSuccessData)
        {
            summary.Add("Erfolgsquote ausgelassen (inkonsistente Seitensummen)");
        }
        if (latencySamples > 0)
        {
            var averageLatency = latencyTotal / latencySamples;
            summary.Add($"Ø {averageLatency.ToString("0", CultureInfo.InvariantCulture)} ms");
        }
        if (latestAt.HasValue)
        {
            summary.Add($"zuletzt {latestAt.Value.ToLocalTime().ToString("dd.MM.yyyy HH:mm:ss", CultureInfo.InvariantCulture)}");
        }

        SearchPerformanceSummary = string.Join(" · ", summary);
        SearchPerformanceStatus = $"{queryCount.ToString(CultureInfo.InvariantCulture)} aggregierte Datenpunkte aus /api/metrics/search_stats · letzte 24 h · keine Suchbegriffe/URLs werden angezeigt.";
    });

    private Task ApplyMetricsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        var interactions = GetInt64(root, "total_interactions");
        var tokens = GetInt64(root, "total_tokens");
        var latency = GetDouble(root, "avg_latency_ms");
        var fallbackRate = GetDouble(root, "fallback_rate");
        var errors = GetInt64(root, "error_count");
        var values = new List<string> { "24-h-Modellaggregat" };
        if (interactions.HasValue) values.Add($"{interactions.Value} Interaktionen");
        if (tokens.HasValue) values.Add($"{tokens.Value} Tokens");
        if (latency.HasValue) values.Add($"Ø {latency.Value.ToString("0", CultureInfo.InvariantCulture)} ms");
        if (fallbackRate.HasValue) values.Add($"{fallbackRate.Value.ToString("0.0", CultureInfo.InvariantCulture)} % Fallbacks");
        if (errors.HasValue) values.Add($"{errors.Value} Fehler");
        MetricsSummary = string.Join(" · ", values);
    });

    private Task ApplyMetricsTimeseriesAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        if (root.ValueKind != JsonValueKind.Array)
        {
            ReplaceMetricBuckets(Array.Empty<MetricBucket>());
            MetricsTimeseriesStatus = "Nicht verfügbar — /api/metrics/timeseries lieferte kein Zeitreihenformat.";
            return;
        }

        var rows = root.EnumerateArray().Take(48)
            .Select(item =>
            {
                var timestamp = GetInt64(item, "bucket_start");
                var interactions = GetInt64(item, "interactions");
                if (!timestamp.HasValue || !interactions.HasValue) return null;
                string label;
                try
                {
                    label = DateTimeOffset.FromUnixTimeSeconds(timestamp.Value)
                        .ToLocalTime().ToString("dd.MM HH:mm", CultureInfo.InvariantCulture);
                }
                catch (ArgumentOutOfRangeException)
                {
                    return null;
                }

                var tokens = (GetInt64(item, "prompt_tok") ?? 0) + (GetInt64(item, "completion_tok") ?? 0);
                var latency = GetDouble(item, "avg_latency") ?? 0;
                return new MetricBucket(label, interactions.Value, tokens, latency);
            })
            .Where(item => item is not null)
            .Cast<MetricBucket>()
            .ToList();

        var max = rows.Count == 0 ? 0 : rows.Max(item => item.Interactions);
        ReplaceMetricBuckets(rows.Select(item => item with
        {
            RelativeActivity = max == 0 ? 0 : item.Interactions * 100d / max,
            Detail = $"{item.Interactions.ToString(CultureInfo.InvariantCulture)} Interaktionen · {item.Tokens.ToString(CultureInfo.InvariantCulture)} Tokens · Ø {item.AverageLatencyMs.ToString("0", CultureInfo.InvariantCulture)} ms",
        }));
        MetricsTimeseriesStatus = rows.Count > 0
            ? $"{rows.Count} belegte Stunden-Buckets · Quelle /api/metrics/timeseries · letzte 24 h"
            : "Keine Interaktionen im 24-h-Zeitraum gemeldet.";
    });

    private Task ApplyMetricBreakdownAsync(JsonDocument document, string nameProperty, ObservableCollection<MetricBreakdown> target, Action<string> setStatus) =>
        ApplyMetricBreakdownAsync(document.RootElement, nameProperty, target, setStatus);

    private Task ApplyMetricBreakdownAsync(JsonElement root, string nameProperty, ObservableCollection<MetricBreakdown> target, Action<string> setStatus) => SetOnUiAsync(() =>
    {
        if (root.ValueKind != JsonValueKind.Array)
        {
            ReplaceMetricBreakdowns(target, Array.Empty<MetricBreakdown>());
            setStatus("Nicht verfügbar — der Runtime-Endpunkt lieferte kein Listenformat.");
            return;
        }

        var values = root.EnumerateArray().Take(100)
            .Select(item =>
            {
                var name = GetString(item, nameProperty);
                var interactions = GetInt64(item, "interactions");
                if (string.IsNullOrWhiteSpace(name) || !interactions.HasValue) return null;
                var tokens = GetInt64(item, "total_tokens") ?? 0;
                var latency = GetDouble(item, "avg_latency") ?? 0;
                return new MetricBreakdown(name, interactions.Value, tokens, latency);
            })
            .Where(item => item is not null)
            .Cast<MetricBreakdown>()
            .ToArray();
        ReplaceMetricBreakdowns(target, values);
        setStatus(values.Length > 0
            ? $"{values.Length} aggregierte Gruppen · Quelle /api/metrics/{(nameProperty == "skill" ? "skills" : "routes")} · letzte 24 h"
            : "Keine Gruppen im 24-h-Zeitraum gemeldet.");
    });

    private Task ApplyToolMetricsAsync(JsonElement root) => SetOnUiAsync(() =>
    {
        if (!TryGetObject(root, "tools", out var tools)) return;
        _toolUsage = tools.EnumerateObject().Take(300)
            .Where(property => property.Value.ValueKind == JsonValueKind.Number && property.Value.TryGetInt64(out _))
            .ToDictionary(property => property.Name, property => property.Value.GetInt64(), StringComparer.Ordinal);
        RenderTools();
    });

    private void UpdateFreshnessText()
    {
        if (_liveObservedAt.HasValue)
        {
            var observedAt = _liveObservedAt.Value;
            var isFresh = IsFreshLiveSample(observedAt);
            LiveAge = FormatLiveAge(observedAt, _liveSource, _liveSampleInterval);
            if (!isFresh)
            {
                CpuValue = "Nicht verfügbar";
                MemoryValue = "Nicht verfügbar";
                MemoryDetail = "Messwert älter als 5 Sekunden oder Zeitstempel außerhalb des zulässigen Fensters; nicht live bestätigt.";
                LiveSourceDetail = $"Quelle: {_liveSource ?? "Unbekannte Telemetriequelle"} · Messzeitpunkt liegt außerhalb des Freshness-Fensters; Werte nicht live bestätigt.";
            }
        }

        UpdateRuntimeFreshness();
        UpdateRoutingFreshness();
    }

    private void UpdateRoutingFreshness()
    {
        if (!_latestRoutingAt.HasValue)
        {
            RoutingLiveStatus = _routingSourceAvailable switch
            {
                true => "Keine Routing-Ereignisse mit gültigem Zeitstempel empfangen.",
                false => "Routing-Aktivität nicht verfügbar; die 24-h-Historie wird nicht als live gewertet.",
                _ => "Warte auf aktuelle Routing-Messpunkte.",
            };
            return;
        }

        var age = DateTimeOffset.UtcNow - _latestRoutingAt.Value;
        if (age >= TimeSpan.FromSeconds(-5) && age <= FreshnessLimit)
        {
            RoutingLiveStatus = $"Aktuelle Runtime-Route · vor {Math.Max(0, (int)age.TotalSeconds)} s · {FormatEventTimestamp(_latestRoutingAt.Value)}";
        }
        else
        {
            var ageText = age < TimeSpan.Zero
                ? "Zeitstempel liegt unerwartet in der Zukunft"
                : $"letzter Datenpunkt vor {FormatRoutingAge(age)}";
            RoutingLiveStatus = $"Keine Runtime-Route in den letzten 5 Sekunden belegt; {ageText}.";
        }
    }

    private static string FormatRoutingAge(TimeSpan age) => age.TotalSeconds < 60
        ? $"{age.TotalSeconds.ToString("0", CultureInfo.InvariantCulture)} s"
        : age.TotalMinutes < 60
            ? $"{age.TotalMinutes.ToString("0", CultureInfo.InvariantCulture)} min"
            : $"{age.TotalHours.ToString("0.0", CultureInfo.InvariantCulture)} h";

    private void OnFreshnessTimerTick(object? sender, EventArgs e) => UpdateFreshnessText();

    private void UpdateRuntimeFreshness()
    {
        if (_runtime is null || IsRuntimeSnapshotFresh())
        {
            _runtimeSnapshotMarkedStale = false;
            return;
        }

        if (_runtimeSnapshotMarkedStale) return;
        _runtimeSnapshotMarkedStale = true;
        RuntimeState = "Veraltet";
        RuntimeDetail = "Supervisor-Snapshot gehört nicht zum ausgewählten Repository, ist älter als 15 Sekunden oder hat keinen gültigen Messzeitpunkt; Steueraktionen bleiben bis zu einer passenden aktuellen Antwort deaktiviert.";
        RuntimeComponentsStatus = "Komponenten stammen aus einem veralteten Supervisor-Snapshot; Zustand nicht als aktuell bestätigt.";
        RaiseCanExecuteChanged();
    }

    private bool IsRuntimeSnapshotFresh()
    {
        if (!RepositoryRootsMatch(_runtimeRoot, _repositoryRoot)) return false;
        if (_runtime?.UpdatedAt is not { } updatedAt) return false;
        var age = DateTimeOffset.UtcNow - updatedAt.ToUniversalTime();
        return age >= TimeSpan.FromSeconds(-5) && age <= RuntimeFreshnessLimit;
    }

    private static bool RepositoryRootsMatch(string? left, string? right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right)) return false;
        var normalizedLeft = Path.TrimEndingDirectorySeparator(Path.GetFullPath(left));
        var normalizedRight = Path.TrimEndingDirectorySeparator(Path.GetFullPath(right));
        return string.Equals(normalizedLeft, normalizedRight, StringComparison.OrdinalIgnoreCase);
    }

    private bool IsRuntimeActionAllowed(JarvisRuntimeAction action, string? expectedRepositoryRoot = null)
    {
        if (expectedRepositoryRoot is not null && !RepositoryRootsMatch(expectedRepositoryRoot, _repositoryRoot))
        {
            return false;
        }

        return action switch
        {
            JarvisRuntimeAction.Start => CanStart,
            JarvisRuntimeAction.Stop => CanStop,
            JarvisRuntimeAction.Restart => CanRestart,
            _ => false,
        };
    }

    private static string FormatLiveAge(DateTimeOffset observedAt, string? source, double? interval)
    {
        var age = DateTimeOffset.UtcNow - observedAt.ToUniversalTime();
        if (age < TimeSpan.FromSeconds(-5))
        {
            return $"Messzeit liegt {Math.Abs(age.TotalSeconds).ToString("0", CultureInfo.InvariantCulture)} s in der Zukunft; Uhrenabweichung prüfen.";
        }
        if (age < TimeSpan.Zero) age = TimeSpan.Zero;
        var freshness = age <= FreshnessLimit ? "AKTUELL" : "VERALTET";
        var sourceText = string.IsNullOrWhiteSpace(source) ? string.Empty : $" · Quelle {source}";
        var intervalText = interval.HasValue ? $" · Messintervall {interval.Value.ToString("0.0", CultureInfo.InvariantCulture)} s" : string.Empty;
        return $"{freshness} · Messwert vor {age.TotalSeconds.ToString("0", CultureInfo.InvariantCulture)} s · {observedAt.ToLocalTime():HH:mm:ss}{sourceText}{intervalText}";
    }

    private static bool IsFreshLiveSample(DateTimeOffset observedAt)
    {
        var age = DateTimeOffset.UtcNow - observedAt.ToUniversalTime();
        return age >= TimeSpan.FromSeconds(-5) && age <= FreshnessLimit;
    }

    private string? ReadConfiguredRoot()
    {
        string? configuredRoot = null;
        try
        {
            if (File.Exists(_repositoryConfigPath)) configuredRoot = File.ReadAllText(_repositoryConfigPath).Trim();
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }

        return RepositoryRootValidator.ResolveConfiguredRoot(
            new[] { Environment.GetEnvironmentVariable("JARVIS_REPOSITORY_ROOT"), configuredRoot },
            AppContext.BaseDirectory);
    }

    private async Task SetOnUiAsync(Action update)
    {
        if (_dispatcher.CheckAccess()) update();
        else await _dispatcher.InvokeAsync(update, DispatcherPriority.DataBind);
    }

    private void ReplaceCollection(ObservableCollection<JarvisListItem> target, IEnumerable<JarvisListItem> values)
    {
        var copy = values.ToArray();
        if (!_dispatcher.CheckAccess())
        {
            _dispatcher.Invoke(() => ReplaceCollection(target, copy));
            return;
        }
        target.Clear();
        foreach (var item in copy) target.Add(item);
        OnPropertyChanged(target == Skills ? nameof(Skills) : target == Tools ? nameof(Tools) : target == VoiceEvents ? nameof(VoiceEvents) : target == RoutingEvents ? nameof(RoutingEvents) : nameof(Events));
    }

    private void ReplaceMetricBuckets(IEnumerable<MetricBucket> values)
    {
        var copy = values.ToArray();
        if (!_dispatcher.CheckAccess())
        {
            _dispatcher.Invoke(() => ReplaceMetricBuckets(copy));
            return;
        }
        MetricBuckets.Clear();
        foreach (var item in copy) MetricBuckets.Add(item);
        OnPropertyChanged(nameof(MetricBuckets));
    }

    private void ReplaceMetricBreakdowns(ObservableCollection<MetricBreakdown> target, IEnumerable<MetricBreakdown> values)
    {
        var copy = values.ToArray();
        if (!_dispatcher.CheckAccess())
        {
            _dispatcher.Invoke(() => ReplaceMetricBreakdowns(target, copy));
            return;
        }
        target.Clear();
        foreach (var item in copy) target.Add(item);
        OnPropertyChanged(target == SkillUsage ? nameof(SkillUsage) : nameof(RouteUsage));
    }

    private void RaiseCanExecuteChanged()
    {
        OnPropertyChanged(nameof(CanStart));
        OnPropertyChanged(nameof(CanStop));
        OnPropertyChanged(nameof(CanRestart));
    }

    private static string FormatComponent(RuntimeComponent? component, string missing) => component is null
        ? missing
        : string.IsNullOrWhiteSpace(component.Detail)
            ? component.State
            : $"{component.State} · {component.Detail}";

    private string ComposeVoiceState() => string.Join(" · ", new[]
    {
        _voiceRuntimeState,
        _voiceConfiguration,
        _sttSummary,
        _ttsSummary,
    }.Where(value => !string.IsNullOrWhiteSpace(value)));

    private void RenderTools()
    {
        var rendered = new List<JarvisListItem>();
        foreach (var tool in _toolInventory)
        {
            if (_toolUsage.TryGetValue(tool.Name, out var count))
                rendered.Add(tool with { Detail = $"{tool.Detail} · {count} Aufrufe, letzte 24 h".Trim(' ', '·') });
            else
                rendered.Add(tool);
        }

        if (_toolInventory.Count == 0)
        {
            rendered.AddRange(_toolUsage.OrderByDescending(pair => pair.Value).Take(100)
                .Select(pair => new JarvisListItem(
                    pair.Key,
                    $"{pair.Value} Aufrufe, letzte 24 h · Nutzungsmetrik, kein Inventarnachweis",
                    string.Empty)));
        }

        ReplaceCollection(Tools, rendered);
        if (_toolInventory.Count > 0 && _toolUsage.Count > 0)
            ToolsStatus = $"{_toolInventory.Count} Inventar-Tools; Nutzungsmetriken für {_toolUsage.Count} Namen (24 h).";
        else if (_toolInventory.Count > 0)
            ToolsStatus = $"{_toolInventory.Count} Tools aus /api/desktop/snapshot.";
        else if (_toolUsage.Count > 0)
            ToolsStatus = $"Nur aggregierte Tool-Aufrufe aus /api/metrics/tools; kein Inventar verfügbar.";
    }

    private static string FormatBytes(long bytes)
    {
        string[] units = ["B", "KB", "MB", "GB", "TB"];
        var value = (double)Math.Max(0, bytes);
        var unit = 0;
        while (value >= 1024 && unit < units.Length - 1)
        {
            value /= 1024;
            unit++;
        }
        return $"{value.ToString("0.0", CultureInfo.InvariantCulture)} {units[unit]}";
    }

    private static bool TryGetObject(JsonElement element, string propertyName, out JsonElement value)
    {
        value = default;
        return element.ValueKind == JsonValueKind.Object &&
               element.TryGetProperty(propertyName, out value) &&
               value.ValueKind == JsonValueKind.Object;
    }

    private static bool TryGetArray(JsonElement element, string propertyName, out JsonElement value)
    {
        value = default;
        return element.ValueKind == JsonValueKind.Object &&
               element.TryGetProperty(propertyName, out value) &&
               value.ValueKind == JsonValueKind.Array;
    }

    private static string? GetString(JsonElement element, string propertyName) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static double? GetDouble(JsonElement element, string propertyName) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out var result)
            ? result
            : null;

    private static long? GetInt64(JsonElement element, string propertyName) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetInt64(out var result)
            ? result
            : null;

    private static bool? GetBoolean(JsonElement element, string propertyName) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(propertyName, out var value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? value.GetBoolean()
            : null;

    private static DateTimeOffset? ParseTimestamp(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value)) return null;
        if (value.ValueKind == JsonValueKind.String)
        {
            return DateTimeOffset.TryParse(value.GetString(), CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var parsed)
                ? parsed
                : null;
        }
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetDouble(out var epoch) || !double.IsFinite(epoch)) return null;

        var epochMilliseconds = Math.Abs(epoch) >= 100_000_000_000d ? epoch : epoch * 1000d;
        if (epochMilliseconds < DateTimeOffset.MinValue.ToUnixTimeMilliseconds() ||
            epochMilliseconds > DateTimeOffset.MaxValue.ToUnixTimeMilliseconds()) return null;
        try
        {
            return DateTimeOffset.FromUnixTimeMilliseconds((long)Math.Round(epochMilliseconds, MidpointRounding.AwayFromZero));
        }
        catch (ArgumentOutOfRangeException)
        {
            return null;
        }
    }

    private bool SetField<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));

    private void ThrowIfDisposed()
    {
        ObjectDisposedException.ThrowIf(_isDisposed, this);
    }

    public void Dispose()
    {
        if (_isDisposed) return;
        _isDisposed = true;
        if (_dispatcher.CheckAccess())
        {
            _freshnessTimer.Stop();
        }
        else
        {
            _dispatcher.Invoke(_freshnessTimer.Stop);
        }
        _lifetime.Cancel();
        _api.Dispose();
    }
}
