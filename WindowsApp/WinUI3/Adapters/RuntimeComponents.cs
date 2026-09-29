using System.Net;
using Jarvis.ControlHub.WinUI.Domain;

namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>Zustand einer vom Runtime Supervisor gemeldeten Komponente.</summary>
public sealed record ComponentReading(RuntimeState State, string Name, string Detail, bool Reported)
{
    public string Text => RuntimeStateText.ToDisplayText(State);
}

/// <summary>
/// Liest Komponenten aus dem bereits verbundenen Supervisor-Snapshot. Es gibt keinen zweiten Probe:
/// was der Supervisor nicht meldet, ist UNAVAILABLE und wird nicht abgeleitet.
/// </summary>
public static class RuntimeComponents
{
    public const string VoiceDaemon = "voice-daemon";
    public const string Primary = "llm-primary";
    public const string Expert = "llm-expert";
    public const string SmallLlm = "llm-small";
    public const string Stt = "stt-model";
    public const string Chatterbox = "chatterbox";
    public const string AudioBridge = "audio-bridge";
    public const string Npu = "npu-sensor";
    public const string Vvs = "vvs";
    public const string Flux = "flux";
    public const string Web = "web";

    // "llm-main" ist ein Kompatibilitäts-Alias des Primary und wird nie doppelt gezählt.
    private const string PrimaryAlias = "llm-main";

    public static ComponentReading Find(Jarvis.ControlHub.RuntimeSnapshot? snapshot, string id)
    {
        if (snapshot is null)
        {
            return new ComponentReading(RuntimeState.Unavailable, id, "Runtime Supervisor nicht verbunden.", false);
        }

        var component = snapshot.Components.FirstOrDefault(item => string.Equals(item.Id, id, StringComparison.Ordinal));
        return component is null
            ? new ComponentReading(RuntimeState.Unavailable, id, "Vom Supervisor nicht gemeldet.", false)
            : new ComponentReading(ParseState(component.State), component.Name, component.Detail ?? string.Empty, true);
    }

    public static IReadOnlyList<Jarvis.ControlHub.RuntimeComponent> Distinct(Jarvis.ControlHub.RuntimeSnapshot? snapshot) =>
        snapshot?.Components.Where(item => item.Id != PrimaryAlias).ToList() ?? [];

    /// <summary>Unbekannte Zustandswörter werden nie als Ready/Error gedeutet.</summary>
    public static RuntimeState ParseState(string? state) => state switch
    {
        "READY" => RuntimeState.Ready,
        "STARTING" => RuntimeState.Starting,
        "DEGRADED" => RuntimeState.Degraded,
        "ERROR" => RuntimeState.Error,
        "STOPPED" => RuntimeState.Stopped,
        "OFFLINE" => RuntimeState.Offline,
        "NOT_IMPLEMENTED" => RuntimeState.NotImplemented,
        _ => RuntimeState.Unavailable,
    };

    /// <summary>Trennt Transport-, Zeitüberschreitungs-, Auth- und Backend-Fehler der Web-API.</summary>
    public static (RuntimeState State, string Message) ClassifyFailure(JarvisApiException exception) => exception.Kind switch
    {
        JarvisApiFailureKind.ConnectionRefused =>
            (RuntimeState.Offline, "Web-API nicht erreichbar (Verbindung abgelehnt, 127.0.0.1:8091). Sie wird nicht vom Supervisor verwaltet."),
        JarvisApiFailureKind.Timeout =>
            (RuntimeState.Unavailable, "Zeitüberschreitung; der Zustand der Web-API ist unbekannt."),
        JarvisApiFailureKind.ConnectionFailed =>
            (RuntimeState.Unavailable, "Verbindung zur Web-API fehlgeschlagen; der Zustand ist unbekannt."),
        JarvisApiFailureKind.HttpStatus => exception.StatusCode switch
        {
            HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden =>
                (RuntimeState.Unavailable, "Web-API lehnt die Anmeldung ab (JARVIS_WEB_AUTH_TOKEN prüfen)."),
            HttpStatusCode.NotFound => (RuntimeState.Unavailable, "Endpunkt in dieser Backend-Version nicht vorhanden."),
            HttpStatusCode.ServiceUnavailable => (RuntimeState.Unavailable, "Backend meldet: noch nicht bereit."),
            { } code when (int)code >= 500 => (RuntimeState.Error, $"Backend meldet HTTP {(int)code}."),
            _ => (RuntimeState.Unavailable, exception.Message),
        },
        JarvisApiFailureKind.InvalidResponse =>
            (RuntimeState.Unavailable, "Antwort der Web-API nicht auswertbar."),
        _ => (RuntimeState.Unavailable, exception.Message),
    };
}
