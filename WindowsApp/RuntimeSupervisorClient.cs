using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Jarvis.ControlHub;

public enum JarvisRuntimeAction
{
    Start,
    Stop,
    Restart,
}

public sealed record RuntimeComponent(string Id, string Name, string State, string Detail);

public sealed record RuntimeSnapshot(
    string State,
    IReadOnlyList<string> DegradedReasons,
    DateTimeOffset? UpdatedAt,
    IReadOnlyList<RuntimeComponent> Components,
    bool CanStart,
    bool CanStop,
    bool CanRestart,
    string Detail);

public sealed record RuntimeActionResult(bool Accepted, string Message);

/// <summary>
/// Narrow adapter for JARVIS-Runtime.ps1 (repository root). Refresh invokes getRuntime only;
/// lifecycle actions require an explicit call from the corresponding UI handler.
/// </summary>
public sealed class RuntimeSupervisorClient
{
    private const string EmbeddedScriptResource = "Jarvis.ControlHub.Runtime.JARVIS-Runtime.ps1";
    private const string ScriptFileName = "JARVIS-Runtime.ps1";
    private static readonly TimeSpan SupervisorTimeout = TimeSpan.FromSeconds(70);

    public async Task<RuntimeSnapshot> GetRuntimeAsync(string repositoryRoot, CancellationToken cancellationToken = default)
    {
        var validatedRoot = RepositoryRootValidator.Validate(repositoryRoot);
        var result = await InvokeSupervisorAsync("getRuntime", validatedRoot, cancellationToken).ConfigureAwait(false);
        return ParseSnapshot(result.StandardOutput);
    }

    public async Task<RuntimeActionResult> RequestActionAsync(
        JarvisRuntimeAction action,
        string repositoryRoot,
        CancellationToken cancellationToken = default)
    {
        var validatedRoot = RepositoryRootValidator.Validate(repositoryRoot);
        var actionName = action switch
        {
            JarvisRuntimeAction.Start => "start",
            JarvisRuntimeAction.Stop => "stop",
            JarvisRuntimeAction.Restart => "restart",
            _ => throw new ArgumentOutOfRangeException(nameof(action)),
        };

        var result = await InvokeSupervisorAsync(actionName, validatedRoot, cancellationToken).ConfigureAwait(false);
        using var document = ParseJson(result.StandardOutput);
        var root = document.RootElement;
        var accepted = TryGetBoolean(root, "accepted", out var value) && value;
        var message = CleanText(TryGetString(root, "message"), 500);
        if (string.IsNullOrWhiteSpace(message))
        {
            message = accepted ? "Aktion wurde vom Runtime Supervisor angenommen." : "Runtime Supervisor hat die Aktion nicht angenommen.";
        }

        return new RuntimeActionResult(accepted, message);
    }

    private static async Task<SupervisorProcessResult> InvokeSupervisorAsync(
        string action,
        string repositoryRoot,
        CancellationToken cancellationToken)
    {
        var scriptPath = EnsureEmbeddedScript();
        var powershellPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        if (!File.Exists(powershellPath))
        {
            throw new InvalidOperationException("Windows PowerShell 5.1 ist auf diesem Rechner nicht verfügbar.");
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = powershellPath,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            WorkingDirectory = repositoryRoot,
        };
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-NonInteractive");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(scriptPath);
        startInfo.ArgumentList.Add("-Action");
        startInfo.ArgumentList.Add(action);
        startInfo.Environment["JARVIS_REPOSITORY_ROOT"] = repositoryRoot;

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start())
        {
            throw new InvalidOperationException("Der Runtime Supervisor konnte nicht gestartet werden.");
        }

        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(SupervisorTimeout);
        try
        {
            await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch (InvalidOperationException)
            {
            }
            catch (System.ComponentModel.Win32Exception)
            {
            }
            if (cancellationToken.IsCancellationRequested) throw;
            throw new TimeoutException("Die Abfrage des Runtime Supervisor hat das Zeitlimit überschritten.");
        }

        var standardOutput = await stdoutTask.ConfigureAwait(false);
        _ = await stderrTask.ConfigureAwait(false); // Drain stderr; never log it (it may include local paths).
        if (standardOutput.Length > 1_000_000)
        {
            throw new InvalidOperationException("Antwort des Runtime Supervisor überschreitet die erlaubte Größe.");
        }

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"Runtime Supervisor meldet einen Fehler (Exit-Code {process.ExitCode}).");
        }

        return new SupervisorProcessResult(standardOutput);
    }

    private static string EnsureEmbeddedScript()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(EmbeddedScriptResource)
            ?? throw new InvalidOperationException("Das gebündelte JARVIS-Runtime.ps1 fehlt in der Anwendung.");
        using var buffer = new MemoryStream();
        stream.CopyTo(buffer);
        var bytes = buffer.ToArray();
        var hash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        var directory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "JARVIS",
            "ControlHub",
            "Runtime",
            hash);
        Directory.CreateDirectory(directory);
        var scriptPath = Path.Combine(directory, ScriptFileName);

        if (File.Exists(scriptPath))
        {
            using var existing = File.OpenRead(scriptPath);
            var existingHash = Convert.ToHexString(SHA256.HashData(existing)).ToLowerInvariant();
            if (!CryptographicOperations.FixedTimeEquals(
                    Convert.FromHexString(hash),
                    Convert.FromHexString(existingHash)))
            {
                throw new InvalidOperationException("Die lokale Kopie des Runtime Supervisor stimmt nicht mit der eingebetteten Version überein.");
            }

            return scriptPath;
        }

        using (var output = new FileStream(scriptPath, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        {
            output.Write(bytes);
            output.Flush(flushToDisk: true);
        }
        File.SetAttributes(scriptPath, File.GetAttributes(scriptPath) | FileAttributes.ReadOnly);
        return scriptPath;
    }

    private static RuntimeSnapshot ParseSnapshot(string json)
    {
        using var document = ParseJson(json);
        var root = document.RootElement;
        var state = CleanText(TryGetString(root, "state"), 48).ToUpperInvariant();
        var allowedStates = new HashSet<string>(StringComparer.Ordinal)
        {
            "STARTING", "READY", "DEGRADED", "ERROR", "STOPPED", "OFFLINE", "NOT_IMPLEMENTED",
        };
        if (!allowedStates.Contains(state))
        {
            throw new InvalidOperationException("Runtime Supervisor lieferte einen unbekannten Zustand.");
        }

        var reasons = new List<string>();
        if (root.TryGetProperty("degradedReasons", out var reasonArray) && reasonArray.ValueKind == JsonValueKind.Array)
        {
            foreach (var reason in reasonArray.EnumerateArray().Take(40))
            {
                if (reason.ValueKind == JsonValueKind.String)
                {
                    var text = CleanText(reason.GetString(), 300);
                    if (!string.IsNullOrWhiteSpace(text)) reasons.Add(text);
                }
            }
        }

        var components = new List<RuntimeComponent>();
        if (root.TryGetProperty("components", out var componentArray) && componentArray.ValueKind == JsonValueKind.Array)
        {
            foreach (var component in componentArray.EnumerateArray().Take(100))
            {
                if (component.ValueKind != JsonValueKind.Object) continue;
                var id = CleanText(TryGetString(component, "id"), 80);
                var name = CleanText(TryGetString(component, "name"), 160);
                var componentState = CleanText(TryGetString(component, "state"), 48).ToUpperInvariant();
                var detail = CleanText(TryGetString(component, "detail"), 400);
                if (id.Length == 0 || name.Length == 0 || componentState.Length == 0) continue;
                components.Add(new RuntimeComponent(id, name, componentState, detail));
            }
        }

        DateTimeOffset? updatedAt = DateTimeOffset.TryParse(
            TryGetString(root, "updatedAt"),
            System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.AssumeUniversal | System.Globalization.DateTimeStyles.AdjustToUniversal,
            out var parsedUpdatedAt)
            ? parsedUpdatedAt
            : null;

        var capabilities = root.TryGetProperty("capabilities", out var caps) && caps.ValueKind == JsonValueKind.Object
            ? caps
            : default;
        var detailText = CleanText(TryGetString(root, "detail"), 600);

        return new RuntimeSnapshot(
            state,
            reasons,
            updatedAt,
            components,
            TryGetBoolean(capabilities, "start", out var canStart) && canStart,
            TryGetBoolean(capabilities, "stop", out var canStop) && canStop,
            TryGetBoolean(capabilities, "restart", out var canRestart) && canRestart,
            detailText);
    }

    private static JsonDocument ParseJson(string value)
    {
        try
        {
            return JsonDocument.Parse(value, new JsonDocumentOptions { MaxDepth = 24 });
        }
        catch (JsonException)
        {
            throw new InvalidOperationException("Runtime Supervisor lieferte keine gültige JSON-Antwort.");
        }
    }

    private static string? TryGetString(JsonElement element, string propertyName) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static bool TryGetBoolean(JsonElement element, string propertyName, out bool value)
    {
        value = false;
        if (element.ValueKind != JsonValueKind.Object ||
            !element.TryGetProperty(propertyName, out var property) ||
            property.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return false;
        }

        value = property.GetBoolean();
        return true;
    }

    private static string CleanText(string? value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value)) return string.Empty;
        var cleaned = new string(value.Where(character => !char.IsControl(character)).Take(maxLength).ToArray()).Trim();
        return cleaned;
    }

    private sealed record SupervisorProcessResult(string StandardOutput);
}

internal static class RepositoryRootValidator
{
    private static readonly string[] RequiredFiles =
    {
        "JARVIS.Runtime.psm1",
        "JARVIS-Runtime.ps1",
        "jarvis_web.py",
        "config.yaml",
        "start.sh",
        "stop.sh",
        "restart.sh",
        Path.Combine("scripts", "check_runtime_dependencies.py"),
        Path.Combine("scripts", "check_chatterbox_runtime.py"),
        Path.Combine("scripts", "runtime_status.py"),
        Path.Combine("core", "runtime_state.py"),
    };

    public static string Validate(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new InvalidOperationException("Wählen Sie zuerst den JARVIS-Main-Repository-Ordner aus.");
        }

        string fullPath;
        try { fullPath = Path.GetFullPath(path); }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            throw new InvalidOperationException("Der ausgewählte Repository-Pfad ist ungültig.");
        }

        if (!Directory.Exists(fullPath) || HasReparsePointInPath(fullPath) ||
            RequiredFiles.Any(file =>
            {
                var requiredPath = Path.Combine(fullPath, file);
                return !File.Exists(requiredPath) || HasReparsePointInPath(requiredPath);
            }))
        {
            throw new InvalidOperationException("Der ausgewählte Ordner ist kein gültiger JARVIS-Main-Checkout.");
        }

        return fullPath;
    }

    public static string? DiscoverFrom(string baseDirectory)
    {
        DirectoryInfo? current;
        try
        {
            var fullPath = Path.GetFullPath(baseDirectory);
            var searchPath = Directory.Exists(fullPath) ? fullPath : Path.GetDirectoryName(fullPath);
            if (string.IsNullOrWhiteSpace(searchPath)) return null;
            current = new DirectoryInfo(searchPath);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return null;
        }

        for (var depth = 0; current is not null && depth < 32; depth++, current = current.Parent)
        {
            var candidates = new[] { current.FullName, Path.Combine(current.FullName, "Main") };
            foreach (var candidate in candidates)
            {
                if (!HasReparsePointInPath(candidate) && !HasReparsePointInRequiredFiles(candidate) &&
                    RequiredFiles.All(file => File.Exists(Path.Combine(candidate, file))))
                {
                    return Validate(candidate);
                }
            }
        }

        return null;
    }

    public static string? ResolveConfiguredRoot(IEnumerable<string?> configuredRoots, string appBaseDirectory)
    {
        var hasConfiguredRoot = false;
        foreach (var configuredRoot in configuredRoots)
        {
            if (string.IsNullOrWhiteSpace(configuredRoot)) continue;
            hasConfiguredRoot = true;
            try { return Validate(configuredRoot); }
            catch (InvalidOperationException) { }
        }

        return hasConfiguredRoot ? null : DiscoverFrom(appBaseDirectory);
    }

    private static bool HasReparsePointInPath(string path)
    {
        string? current;
        try { current = Path.GetFullPath(path); }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return true;
        }

        while (current is not null)
        {
            try
            {
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) return true;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or System.Security.SecurityException)
            {
                return true;
            }
            var parent = Path.GetDirectoryName(current);
            current = string.Equals(parent, current, StringComparison.OrdinalIgnoreCase) ? null : parent;
        }

        return false;
    }

    private static bool HasReparsePointInRequiredFiles(string root)
    {
        foreach (var file in RequiredFiles)
        {
            var path = Path.Combine(root, file);
            if (File.Exists(path) && HasReparsePointInPath(path)) return true;
        }

        return false;
    }

}
