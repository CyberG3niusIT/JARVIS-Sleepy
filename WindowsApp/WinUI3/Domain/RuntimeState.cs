namespace Jarvis.ControlHub.WinUI.Domain;

public enum RuntimeState
{
    Ready,
    Starting,
    Degraded,
    Error,
    Stopped,
    Offline,
    NotImplemented,
    Unavailable,
    NoLiveData,
}

public sealed record RuntimeStatus(
    RuntimeState State,
    string? Message = null,
    DateTimeOffset? ObservedAt = null);

public static class RuntimeStateText
{
    public static string ToDisplayText(RuntimeState state) => state switch
    {
        RuntimeState.Ready => "READY",
        RuntimeState.Starting => "STARTING",
        RuntimeState.Degraded => "DEGRADED",
        RuntimeState.Error => "ERROR",
        RuntimeState.Stopped => "STOPPED",
        RuntimeState.Offline => "OFFLINE",
        RuntimeState.NotImplemented => "NOT_IMPLEMENTED",
        RuntimeState.Unavailable => "UNAVAILABLE",
        RuntimeState.NoLiveData => "NO LIVE DATA",
        _ => throw new ArgumentOutOfRangeException(nameof(state), state, "Unbekannter Runtime-Status."),
    };
}
