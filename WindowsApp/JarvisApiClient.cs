using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.IO;
using System.Text.Json;

namespace Jarvis.ControlHub;

/// <summary>
/// Fixed, loopback-only GET client for the read contracts that exist in Main.
/// The caller cannot supply a host, path, query, or HTTP method.
/// </summary>
public sealed class JarvisApiClient : IDisposable
{
    public const int LoopbackPort = 8091;

    private static readonly string BaseAddress = $"http://127.0.0.1:{LoopbackPort}/";
    private const int MaxResponseBytes = 2 * 1024 * 1024;

    private readonly HttpClient _httpClient;
    private readonly string? _bearerToken;

    public JarvisApiClient()
    {
        var token = Environment.GetEnvironmentVariable("JARVIS_WEB_AUTH_TOKEN");
        _bearerToken = !string.IsNullOrWhiteSpace(token) && token.Length <= 4096 ? token : null;

        var handler = new SocketsHttpHandler
        {
            AllowAutoRedirect = false,
            UseCookies = false,
            UseProxy = false,
            ConnectTimeout = TimeSpan.FromSeconds(1.5),
            PooledConnectionLifetime = TimeSpan.FromMinutes(2),
        };
        _httpClient = new HttpClient(handler, disposeHandler: true)
        {
            BaseAddress = new Uri(BaseAddress, UriKind.Absolute),
            Timeout = Timeout.InfiniteTimeSpan,
        };
    }

    public Task<JsonDocument> GetStatsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/stats", TimeSpan.FromSeconds(4), cancellationToken);

    public Task<JsonDocument> GetDesktopLiveAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/desktop/live", TimeSpan.FromMilliseconds(1800), cancellationToken);

    public Task<JsonDocument> GetDesktopSnapshotAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/desktop/snapshot", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetSttEventsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/events/stt?hours=24", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetTtsEventsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/events/tts?hours=24", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetRoutingEventsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/events/routing?hours=24", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetAgentStatusAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/agents/status", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetAutomationsStatusAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/automations/status", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetHealthHistoryAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/events/health?hours=24", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetMetricsSummaryAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/metrics/summary?hours=24", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetMetricsSkillsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/metrics/skills?hours=24", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetMetricsRoutesAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/metrics/routes?hours=24", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetMetricsTimeseriesAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/metrics/timeseries?hours=24&bucket=hour", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetMetricsToolsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/metrics/tools?hours=24", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetMetricsSearchStatsAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/metrics/search_stats?hours=24", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetEventsAggregateAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/events/aggregate?hours=24", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetEventsRecentAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/events/recent?hours=24&limit=40", TimeSpan.FromSeconds(5), cancellationToken);

    public Task<JsonDocument> GetMemorySummaryAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/memory/summary", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetSessionsPageAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/sessions?limit=1", TimeSpan.FromSeconds(6), cancellationToken);

    public Task<JsonDocument> GetWebcamStatusAsync(CancellationToken cancellationToken = default) =>
        GetJsonAsync("api/webcam/status", TimeSpan.FromSeconds(6), cancellationToken);

    private async Task<JsonDocument> GetJsonAsync(
        string allowlistedPath,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        using var requestTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        requestTimeout.CancelAfter(timeout);
        using var request = new HttpRequestMessage(HttpMethod.Get, allowlistedPath);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
        if (_bearerToken is not null)
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _bearerToken);
        }

        HttpResponseMessage response;
        try
        {
            response = await _httpClient.SendAsync(
                request,
                HttpCompletionOption.ResponseHeadersRead,
                requestTimeout.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new JarvisApiException("Zeitüberschreitung bei der lokalen JARVIS-API.", JarvisApiFailureKind.Timeout);
        }
        catch (HttpRequestException exception)
        {
            var kind = exception.InnerException switch
            {
                System.Net.Sockets.SocketException { SocketErrorCode: System.Net.Sockets.SocketError.ConnectionRefused } =>
                    JarvisApiFailureKind.ConnectionRefused,
                TimeoutException or OperationCanceledException => JarvisApiFailureKind.Timeout,
                _ => JarvisApiFailureKind.ConnectionFailed,
            };
            throw new JarvisApiException("Die JARVIS-API auf 127.0.0.1:8091 ist nicht erreichbar.", kind);
        }

        using (response)
        {
            if (!response.IsSuccessStatusCode)
            {
                var explanation = response.StatusCode switch
                {
                    HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden =>
                        "JARVIS-API lehnt die Anmeldung ab. Falls Authentifizierung aktiviert ist, JARVIS_WEB_AUTH_TOKEN in der Windows-Umgebung setzen und das Programm neu starten.",
                    HttpStatusCode.NotFound => $"JARVIS-API-Endpunkt nicht verfügbar (HTTP {(int)response.StatusCode}).",
                    _ => $"JARVIS-API meldet HTTP {(int)response.StatusCode}.",
                };
                throw new JarvisApiException(explanation, JarvisApiFailureKind.HttpStatus, response.StatusCode);
            }

            if (response.Content.Headers.ContentLength is > MaxResponseBytes)
            {
                throw new JarvisApiException("Antwort der JARVIS-API überschreitet die erlaubte Größe.", JarvisApiFailureKind.InvalidResponse);
            }

            await using var input = await response.Content.ReadAsStreamAsync(requestTimeout.Token).ConfigureAwait(false);
            using var output = new MemoryStream();
            var buffer = new byte[8192];
            while (true)
            {
                var read = await input.ReadAsync(buffer, requestTimeout.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    break;
                }

                if (output.Length + read > MaxResponseBytes)
                {
                    throw new JarvisApiException("Antwort der JARVIS-API überschreitet die erlaubte Größe.", JarvisApiFailureKind.InvalidResponse);
                }

                output.Write(buffer, 0, read);
            }

            try
            {
                return JsonDocument.Parse(output.ToArray(), new JsonDocumentOptions
                {
                    MaxDepth = 32,
                    CommentHandling = JsonCommentHandling.Disallow,
                    AllowTrailingCommas = false,
                });
            }
            catch (JsonException)
            {
                throw new JarvisApiException("JARVIS-API lieferte kein gültiges JSON.", JarvisApiFailureKind.InvalidResponse);
            }
        }
    }

    public void Dispose() => _httpClient.Dispose();
}

public enum JarvisApiFailureKind
{
    Unspecified,
    Timeout,
    ConnectionRefused,
    ConnectionFailed,
    HttpStatus,
    InvalidResponse,
}

public sealed class JarvisApiException : Exception
{
    public HttpStatusCode? StatusCode { get; }
    public JarvisApiFailureKind Kind { get; }

    public JarvisApiException(string message, HttpStatusCode? statusCode = null)
        : this(message, JarvisApiFailureKind.Unspecified, statusCode)
    {
    }

    public JarvisApiException(string message, JarvisApiFailureKind kind, HttpStatusCode? statusCode = null)
        : base(message)
    {
        Kind = kind;
        StatusCode = statusCode;
    }
}
