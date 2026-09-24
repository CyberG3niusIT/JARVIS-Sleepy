$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'JARVIS.Runtime.psm1') -Force

try {
    Stop-JarvisRuntime -RepositoryRoot $PSScriptRoot
} catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
