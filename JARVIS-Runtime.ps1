<#
.SYNOPSIS
  Native runtime supervisor entry point for the JARVIS desktop shell (Tauri).

.DESCRIPTION
  The closed set of operations behind the UI's RuntimeControlTransport:

    -Action getRuntime   prints the RuntimeControlSnapshot as JSON (read-only)
    -Action start|stop|restart
                         prints {"accepted": bool, "message": str}. The request is only
                         acknowledged (lifecycle runs detached); the resulting state comes
                         from the next getRuntime. Use -Wait to run it synchronously.

  ValidateSet is the whole API surface: there is no way to pass a command or a script.
  Output is pure ASCII JSON on stdout, so no console code page can corrupt it.
#>
param(
    [Parameter(Mandatory)][ValidateSet('getRuntime', 'start', 'stop', 'restart')][string]$Action,
    [switch]$Wait
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = if ($env:JARVIS_REPOSITORY_ROOT) {
    (Resolve-Path -LiteralPath $env:JARVIS_REPOSITORY_ROOT -ErrorAction Stop).Path
} else {
    $PSScriptRoot
}
$runtimeModule = Join-Path $repositoryRoot 'JARVIS.Runtime.psm1'
if (-not (Test-Path -LiteralPath $runtimeModule -PathType Leaf)) {
    throw 'JARVIS_REPOSITORY_ROOT enthaelt kein JARVIS.Runtime.psm1.'
}

function Write-JarvisJson {
    param([Parameter(Mandatory)]$Value)
    $json = $Value | ConvertTo-Json -Depth 6 -Compress
    $ascii = [regex]::Replace($json, '[^\u0000-\u007F]', { param($m) '\u{0:x4}' -f [int][char]$m.Value })
    [Console]::Out.WriteLine($ascii)
}

try {
    Import-Module $runtimeModule -Force
    if ($Action -eq 'getRuntime') {
        Write-JarvisJson (Get-JarvisRuntime -RepositoryRoot $repositoryRoot)
    } else {
        Write-JarvisJson (Invoke-JarvisRuntimeAction -Action $Action -RepositoryRoot $repositoryRoot -Wait:$Wait)
    }
} catch {
    $message = $_.Exception.Message
    if ($Action -eq 'getRuntime') {
        # Contract-valid ERROR reading instead of a crash, so the consumer never has to guess.
        Write-JarvisJson ([ordered]@{
            state = 'ERROR'
            degradedReasons = @()
            updatedAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
            components = @()
            capabilities = [ordered]@{ start = $false; stop = $false; restart = $false }
            detail = "Supervisor-Fehler: $message"
        })
        exit 0
    }
    Write-JarvisJson ([ordered]@{ accepted = $false; message = "Supervisor-Fehler: $message" })
    exit 1
}
