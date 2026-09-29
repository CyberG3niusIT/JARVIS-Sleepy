using Jarvis.ControlHub.WinUI.Domain;

namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>
/// Im Backend existiert kein Pairing-, Geräte- oder Push-Vertrag für eine native App
/// (nur ein browserbasierter Kamera-Relay in jarvis_web.py). Deshalb meldet dieser Adapter
/// ausschließlich NOT_IMPLEMENTED und erfindet weder Geräte noch Verbindungszustände.
/// </summary>
public sealed class MobileConnectionAdapter : IMobileConnectionAdapter
{
    public static MobileConnectionStatus Current { get; } = new(MobileConnectionState.NotImplemented);

    public static string StateText(MobileConnectionState state) => state switch
    {
        MobileConnectionState.NotImplemented => "NOT_IMPLEMENTED",
        MobileConnectionState.Unavailable => "UNAVAILABLE",
        MobileConnectionState.Offline => "OFFLINE",
        MobileConnectionState.Pairing => "STARTING",
        MobileConnectionState.Connected => "READY",
        _ => "UNAVAILABLE",
    };

    public Task<MobileConnectionStatus> GetStatusAsync(CancellationToken cancellationToken) =>
        Task.FromResult(Current);
}
