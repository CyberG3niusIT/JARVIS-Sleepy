$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$modulePath = Join-Path $repoRoot 'JARVIS.Runtime.psm1'
Import-Module $modulePath -Force
$module = Get-Module JARVIS.Runtime
$global:JarvisRuntimeEvents = [System.Collections.Generic.List[string]]::new()
$global:JarvisFakeKeepalivePresent = $false
$global:JarvisFailNextRuntimeCall = $false

& $module {
    $script:JarvisRuntimeInvoker = {
        param($Action, $RepositoryRoot)
        $global:JarvisRuntimeEvents.Add("runtime:$Action")
        if ($global:JarvisFailNextRuntimeCall) {
            $global:JarvisFailNextRuntimeCall = $false
            throw 'injected lifecycle failure'
        }
    }
    $script:JarvisKeepaliveEnsureInvoker = {
        param($RepositoryRoot)
        if ($global:JarvisFakeKeepalivePresent) {
            $global:JarvisRuntimeEvents.Add('keepalive:reuse')
            return $false
        }
        $global:JarvisFakeKeepalivePresent = $true
        $global:JarvisRuntimeEvents.Add('keepalive:start')
        return $true
    }
    $script:JarvisKeepaliveStopInvoker = {
        param($RepositoryRoot)
        $global:JarvisFakeKeepalivePresent = $false
        $global:JarvisRuntimeEvents.Add('keepalive:stop')
    }
}

$repo = $repoRoot
Start-JarvisRuntime -RepositoryRoot $repo
Start-JarvisRuntime -RepositoryRoot $repo
Restart-JarvisRuntime -RepositoryRoot $repo
Stop-JarvisRuntime -RepositoryRoot $repo

$expected = @(
    'keepalive:start', 'runtime:start',
    'keepalive:reuse', 'runtime:start',
    'keepalive:reuse', 'runtime:restart',
    'runtime:stop', 'keepalive:stop'
)
if ($global:JarvisRuntimeEvents.Count -ne $expected.Count) { throw 'Runtime/keepalive event count mismatch.' }
for ($i = 0; $i -lt $expected.Count; $i++) {
    if ($global:JarvisRuntimeEvents[$i] -ne $expected[$i]) {
        throw "Unexpected runtime event at index ${i}: '$($global:JarvisRuntimeEvents[$i])'."
    }
}

$global:JarvisFailNextRuntimeCall = $true
try {
    Start-JarvisRuntime -RepositoryRoot $repo
    throw 'Expected injected start failure.'
} catch {
    if ($_.Exception.Message -ne 'injected lifecycle failure') { throw }
}
if ($global:JarvisFakeKeepalivePresent) { throw 'New keepalive survived a failed start.' }
$tail = @($global:JarvisRuntimeEvents | Select-Object -Last 3)
if (($tail -join '|') -ne 'keepalive:start|runtime:start|keepalive:stop') {
    throw 'Failed start did not clean up only the keepalive created by that start.'
}

$global:JarvisFakeKeepalivePresent = $true
$global:JarvisFailNextRuntimeCall = $true
try {
    Start-JarvisRuntime -RepositoryRoot $repo
    throw 'Expected injected warm-start failure.'
} catch {
    if ($_.Exception.Message -ne 'injected lifecycle failure') { throw }
}
if (-not $global:JarvisFakeKeepalivePresent) { throw 'Failed warm start removed a pre-existing keepalive.' }
$tail = @($global:JarvisRuntimeEvents | Select-Object -Last 2)
if (($tail -join '|') -ne 'keepalive:reuse|runtime:start') {
    throw 'Failed warm start changed ownership of the pre-existing keepalive.'
}

Write-Output 'PASS: cold/warm start, restart, stop, and owned-keepalive failure cleanup.'
