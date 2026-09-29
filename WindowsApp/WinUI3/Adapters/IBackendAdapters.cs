using Jarvis.ControlHub.WinUI.Domain;

namespace Jarvis.ControlHub.WinUI.Adapters;

public interface IRuntimeSupervisorAdapter
{
    Task<RuntimeStatus> GetStatusAsync(CancellationToken cancellationToken);
}

public interface IJarvisApiAdapter
{
    Task<RuntimeStatus> GetStatusAsync(CancellationToken cancellationToken);
}

public interface IMobilityAdapter
{
    Task<RuntimeStatus> GetStatusAsync(CancellationToken cancellationToken);
}

public interface IMobileConnectionAdapter
{
    Task<MobileConnectionStatus> GetStatusAsync(CancellationToken cancellationToken);
}

public interface IEventTelemetryAdapter
{
    Task<RuntimeStatus> GetStatusAsync(CancellationToken cancellationToken);
}

public interface IPrivacyCapabilityGate
{
    bool IsAllowed(string capability);
}
