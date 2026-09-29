namespace Jarvis.ControlHub.WinUI.Domain;

public enum MobileConnectionState
{
    NotImplemented,
    Unavailable,
    Offline,
    Pairing,
    Connected,
}

public sealed record MobileConnectionStatus(
    MobileConnectionState State,
    string? DeviceName = null,
    DateTimeOffset? LastContact = null,
    IReadOnlyList<string>? Capabilities = null);
