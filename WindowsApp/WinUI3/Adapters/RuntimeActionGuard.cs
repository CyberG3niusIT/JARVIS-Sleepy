namespace Jarvis.ControlHub.WinUI.Adapters;

/// <summary>
/// Freigabe von Runtime-Lifecycle-Aktionen (Start/Stop/Restart). Entscheidet allein aus Supervisor-Fakten: die
/// capabilities des Snapshots und der Checkout, für den er abgefragt wurde. Der Aufrufer fragt den Supervisor vor
/// dem Bestätigungsdialog und danach erneut ab; es gibt keinen Zeitvergleich zwischen Windows- und WSL-Uhr.
/// </summary>
public static class RuntimeActionGuard
{
    public static bool RootsMatch(string? left, string? right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right)) return false;
        try
        {
            return string.Equals(
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(left)),
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(right)),
                StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return false;
        }
    }

    public static bool IsAllowed(
        Jarvis.ControlHub.JarvisRuntimeAction action,
        Jarvis.ControlHub.RuntimeSnapshot? snapshot,
        string? snapshotRoot,
        string? selectedRoot)
    {
        if (snapshot is null || !RootsMatch(snapshotRoot, selectedRoot)) return false;
        return action switch
        {
            Jarvis.ControlHub.JarvisRuntimeAction.Start => snapshot.CanStart,
            Jarvis.ControlHub.JarvisRuntimeAction.Stop => snapshot.CanStop,
            Jarvis.ControlHub.JarvisRuntimeAction.Restart => snapshot.CanRestart,
            _ => false,
        };
    }
}
