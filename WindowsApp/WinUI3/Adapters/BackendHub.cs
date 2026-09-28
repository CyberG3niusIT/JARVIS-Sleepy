using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using Jarvis.ControlHub.WinUI.Domain;

namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>
/// Zentraler Lese-Adapter für die lokale JARVIS-Web-API. Die Oberfläche fragt pro Seite nur die
/// Endpunkte ab, die diese Seite braucht; Ergebnisse tragen einen ehrlichen Zustand statt Ausnahmen.
/// Es gibt keinen Schreibpfad und keinen Zugriff auf Kamera, Mikrofon oder Konfiguration.
/// </summary>
public sealed class BackendHub : IJarvisApiAdapter, IDisposable
{
    private static readonly TimeSpan ConnectProbeTimeout = TimeSpan.FromSeconds(4);

    private readonly Jarvis.ControlHub.JarvisApiClient _api;
    private readonly bool _ownsClient;
    private readonly Func<DateTimeOffset> _clock;
    private readonly object _gate = new();
    private IReadOnlyDictionary<WebEndpoint, WebReading> _readings = new Dictionary<WebEndpoint, WebReading>();

    public BackendHub(Jarvis.ControlHub.JarvisApiClient? api = null, Func<DateTimeOffset>? clock = null)
    {
        _api = api ?? new Jarvis.ControlHub.JarvisApiClient();
        _ownsClient = api is null;
        _clock = clock ?? (() => DateTimeOffset.Now);
    }

    public WebReading Get(WebEndpoint endpoint)
    {
        lock (_gate)
        {
            return _readings.TryGetValue(endpoint, out var reading) ? reading : WebReading.NotQueried;
        }
    }

    /// <summary>Der erste Endpunkt ist die Erreichbarkeitsprobe der Seite; die übrigen laufen nur danach.</summary>
    public static IReadOnlyList<WebEndpoint> EndpointsFor(BackendDomain domain) => domain switch
    {
        BackendDomain.Home => [WebEndpoint.EventsRecent, WebEndpoint.MemorySummary],
        BackendDomain.Chat => [WebEndpoint.Stats, WebEndpoint.Sessions],
        BackendDomain.Memory => [WebEndpoint.MemorySummary, WebEndpoint.Stats, WebEndpoint.Desktop],
        BackendDomain.Models => [WebEndpoint.Stats, WebEndpoint.Desktop],
        BackendDomain.Voice => [WebEndpoint.Desktop, WebEndpoint.EventsRecent],
        BackendDomain.Tools => [WebEndpoint.Desktop],
        BackendDomain.Automations => [WebEndpoint.Automations, WebEndpoint.Agents],
        BackendDomain.Vision => [WebEndpoint.Webcam],
        BackendDomain.Observability => [WebEndpoint.EventsRecent, WebEndpoint.EventsAggregate, WebEndpoint.MemorySummary],
        BackendDomain.Settings => [WebEndpoint.Desktop],
        _ => [],
    };

    public async Task RefreshAsync(BackendDomain domain, CancellationToken cancellationToken)
    {
        var endpoints = EndpointsFor(domain);
        if (endpoints.Count == 0) return;

        if (await ProbeRefusedAsync(cancellationToken).ConfigureAwait(false) is { } refused)
        {
            foreach (var endpoint in endpoints) Store(endpoint, refused);
            return;
        }

        var probe = await QueryAsync(endpoints[0], cancellationToken).ConfigureAwait(false);
        Store(endpoints[0], probe);
        if (endpoints.Count == 1) return;

        if (probe.State == RuntimeState.Offline)
        {
            // Nichts lauscht: die übrigen Abfragen würden nur dieselbe Antwort liefern.
            foreach (var endpoint in endpoints.Skip(1)) Store(endpoint, probe with { Data = null });
            return;
        }

        var results = await Task.WhenAll(endpoints.Skip(1).Select(endpoint => QueryAsync(endpoint, cancellationToken)))
            .ConfigureAwait(false);
        for (var index = 0; index < results.Length; index++) Store(endpoints[index + 1], results[index]);
    }

    public async Task<RuntimeStatus> GetStatusAsync(CancellationToken cancellationToken)
    {
        var reading = await ProbeRefusedAsync(cancellationToken).ConfigureAwait(false)
            ?? await QueryAsync(WebEndpoint.Stats, cancellationToken).ConfigureAwait(false);
        Store(WebEndpoint.Stats, reading);
        return new RuntimeStatus(reading.State, reading.Message, reading.ObservedAt);
    }

    public void Dispose()
    {
        if (_ownsClient) _api.Dispose();
    }

    /// <summary>
    /// Unter Windows braucht ein abgelehnter Loopback-Connect länger als das Connect-Timeout des HTTP-Clients.
    /// Diese Vorprobe wartet auf die eindeutige Antwort des Betriebssystems: nur "Verbindung abgelehnt"
    /// (nichts lauscht) ergibt OFFLINE; Erfolg, Timeout und andere Fehler führen zur normalen HTTP-Abfrage.
    /// </summary>
    private async Task<WebReading?> ProbeRefusedAsync(CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(ConnectProbeTimeout);
        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        try
        {
            await socket.ConnectAsync(new IPEndPoint(IPAddress.Loopback, Jarvis.ControlHub.JarvisApiClient.LoopbackPort), timeout.Token)
                .ConfigureAwait(false);
            return null;
        }
        catch (SocketException exception) when (exception.SocketErrorCode == SocketError.ConnectionRefused)
        {
            var (state, message) = RuntimeComponents.ClassifyFailure(new Jarvis.ControlHub.JarvisApiException(
                string.Empty, Jarvis.ControlHub.JarvisApiFailureKind.ConnectionRefused));
            return new WebReading(state, message, null, _clock());
        }
        catch (SocketException)
        {
            return null;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    private async Task<WebReading> QueryAsync(WebEndpoint endpoint, CancellationToken cancellationToken)
    {
        try
        {
            using var document = await CallAsync(endpoint, cancellationToken).ConfigureAwait(false);
            return new WebReading(RuntimeState.Ready, string.Empty, Parse(endpoint, document.RootElement), _clock());
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Jarvis.ControlHub.JarvisApiException exception)
        {
            var (state, message) = RuntimeComponents.ClassifyFailure(exception);
            return new WebReading(state, message, null, _clock());
        }
        catch (OperationCanceledException)
        {
            return Failed("Zeitüberschreitung beim Lesen der Antwort; der Zustand ist unbekannt.");
        }
        catch (Exception exception) when (exception is FormatException or JsonException or InvalidOperationException or ArgumentException)
        {
            return Failed("Antwort der Web-API nicht auswertbar.");
        }
        catch (IOException)
        {
            return Failed("Verbindung zur Web-API während des Lesens unterbrochen.");
        }
    }

    private WebReading Failed(string message) => new(RuntimeState.Unavailable, message, null, _clock());

    private Task<JsonDocument> CallAsync(WebEndpoint endpoint, CancellationToken cancellationToken) => endpoint switch
    {
        WebEndpoint.Stats => _api.GetStatsAsync(cancellationToken),
        WebEndpoint.Desktop => _api.GetDesktopSnapshotAsync(cancellationToken),
        WebEndpoint.Agents => _api.GetAgentStatusAsync(cancellationToken),
        WebEndpoint.Automations => _api.GetAutomationsStatusAsync(cancellationToken),
        WebEndpoint.MemorySummary => _api.GetMemorySummaryAsync(cancellationToken),
        WebEndpoint.EventsRecent => _api.GetEventsRecentAsync(cancellationToken),
        WebEndpoint.EventsAggregate => _api.GetEventsAggregateAsync(cancellationToken),
        WebEndpoint.Sessions => _api.GetSessionsPageAsync(cancellationToken),
        WebEndpoint.Webcam => _api.GetWebcamStatusAsync(cancellationToken),
        _ => throw new ArgumentOutOfRangeException(nameof(endpoint), endpoint, "Unbekannter Endpunkt."),
    };

    private static object Parse(WebEndpoint endpoint, JsonElement root) => endpoint switch
    {
        WebEndpoint.Stats => BackendParsers.ParseStats(root),
        WebEndpoint.Desktop => BackendParsers.ParseDesktop(root),
        WebEndpoint.Agents => BackendParsers.ParseAgents(root),
        WebEndpoint.Automations => BackendParsers.ParseAutomations(root),
        WebEndpoint.MemorySummary => BackendParsers.ParseMemory(root),
        WebEndpoint.EventsRecent => BackendParsers.ParseEventsRecent(root),
        WebEndpoint.EventsAggregate => BackendParsers.ParseEventsAggregate(root),
        WebEndpoint.Sessions => BackendParsers.ParseSessions(root),
        WebEndpoint.Webcam => BackendParsers.ParseWebcam(root),
        _ => throw new ArgumentOutOfRangeException(nameof(endpoint), endpoint, "Unbekannter Endpunkt."),
    };

    private void Store(WebEndpoint endpoint, WebReading reading)
    {
        lock (_gate)
        {
            _readings = new Dictionary<WebEndpoint, WebReading>(_readings) { [endpoint] = reading };
        }
    }
}
