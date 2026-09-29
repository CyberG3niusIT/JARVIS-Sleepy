$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path

# Never touch the real per-user runtime state (lifecycle marker, keepalive identity).
$sandbox = Join-Path ([System.IO.Path]::GetTempPath()) ("jarvis-supervisor-test-" + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $sandbox
$env:LOCALAPPDATA = $sandbox

Import-Module (Join-Path $repoRoot 'JARVIS.Runtime.psm1') -Force
$module = Get-Module JARVIS.Runtime

function Assert-True { param($Condition, [string]$Message) if (-not $Condition) { throw "FAIL: $Message" } }
function Assert-Equal { param($Actual, $Expected, [string]$Message) if ("$Actual" -ne "$Expected") { throw "FAIL: $Message (expected '$Expected', got '$Actual')" } }

function Set-Seams {
    param($Wsl = $null, $Probe = $null)
    & $module { param($w, $p) $script:JarvisWslRunningInvoker = $w; $script:JarvisProbeInvoker = $p } $Wsl $Probe
}

function New-Probe {
    param([string]$State = 'READY', $Reasons = @(), [bool]$Start = $false, [bool]$Stop = $true, [bool]$Restart = $true)
    ([ordered]@{
        state = $State
        degradedReasons = @($Reasons)
        updatedAt = '2026-09-25T00:00:00Z'
        components = @(
            [ordered]@{ id = 'voice-daemon'; name = 'JARVIS Voice-Daemon'; state = 'READY' },
            [ordered]@{ id = 'flux'; name = 'FLUX'; state = 'STOPPED'; detail = 'on demand' }
        )
        capabilities = [ordered]@{ start = $Start; stop = $Stop; restart = $Restart }
    } | ConvertTo-Json -Depth 6)
}
$global:JarvisNewProbe = ${function:New-Probe}

function Get-MarkerPath {
    $identity = & $module { param($r) Get-JarvisKeepaliveIdentity -RepositoryRoot $r } $repoRoot
    Join-Path $identity.StateDirectory 'lifecycle.json'
}
function Set-Marker {
    param([string]$Action, [int]$ProcessId = $PID)
    $path = Get-MarkerPath
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force
    ([ordered]@{ action = $Action; processId = $ProcessId; startedUtc = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json) |
        Set-Content -LiteralPath $path -Encoding UTF8
}
function Clear-Marker { Remove-Item -LiteralPath (Get-MarkerPath) -Force -ErrorAction SilentlyContinue }

$states = @('STARTING', 'READY', 'DEGRADED', 'ERROR', 'STOPPED', 'OFFLINE', 'NOT_IMPLEMENTED')
function Assert-Contract {
    param($Snapshot)
    Assert-True ($states -contains $Snapshot.state) "state '$($Snapshot.state)' is not in the UI contract"
    Assert-True ($Snapshot.updatedAt -is [string]) 'updatedAt must be a string'
    Assert-True ($Snapshot.updatedAt -match '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$') "updatedAt '$($Snapshot.updatedAt)' is not ISO 8601"
    foreach ($key in 'start', 'stop', 'restart') { Assert-True ($Snapshot.capabilities[$key] -is [bool]) "capability $key must be boolean" }
    $json = $Snapshot | ConvertTo-Json -Depth 6
    Assert-True ($json -match '"degradedReasons":\s*\[') 'degradedReasons must serialise as an array'
    Assert-True ($json -match '"components":\s*\[') 'components must serialise as an array'
}

try {
    # 1. WSL not running, no lifecycle -> OFFLINE, only start is offered (never guessed by the UI)
    Clear-Marker
    Set-Seams -Wsl { $false }
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal $s.state 'OFFLINE' 'WSL down without lifecycle'
    Assert-True ($s.capabilities.start -and -not $s.capabilities.stop -and -not $s.capabilities.restart) 'OFFLINE capabilities'

    # 2. WSL not running but a lifecycle of ours is booting it -> STARTING, nothing allowed
    Set-Marker -Action 'start'
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal $s.state 'STARTING' 'WSL booting during controlled start'
    Assert-True (-not ($s.capabilities.start -or $s.capabilities.stop -or $s.capabilities.restart)) 'STARTING capabilities'
    Clear-Marker

    # 3. Probe passthrough: the supervisor does not re-decide the state
    Set-Seams -Wsl { $true } -Probe { param($r) & $global:JarvisNewProbe -State 'READY' }
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal $s.state 'READY' 'probe READY passes through'
    Assert-Equal $s.updatedAt '2026-09-25T00:00:00Z' 'probe updatedAt is kept as an ISO string'
    Assert-Equal @($s.components).Count 2 'components pass through'
    Assert-Equal $s.components[1].detail 'on demand' 'component detail passes through'
    Assert-True ($s.capabilities.stop -and $s.capabilities.restart -and -not $s.capabilities.start) 'probe capabilities pass through'

    foreach ($state in 'DEGRADED', 'ERROR', 'STOPPED') {
        $global:JarvisProbeState = $state
        Set-Seams -Wsl { $true } -Probe { param($r) & $global:JarvisNewProbe -State $global:JarvisProbeState -Reasons @('reason a', 'reason b') }
        $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
        Assert-Contract $s
        Assert-Equal $s.state $state "probe $state passes through"
        Assert-Equal @($s.degradedReasons).Count 2 "$state reasons pass through"
    }

    # 4. A controlled start of ours overrides what the probe saw mid-flight, but keeps its components
    Set-Seams -Wsl { $true } -Probe { param($r) & $global:JarvisNewProbe -State 'STOPPED' -Start $true -Stop $false -Restart $false }
    Set-Marker -Action 'restart'
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal $s.state 'STARTING' 'restart in progress'
    Assert-Equal @($s.components).Count 2 'components are kept while starting'
    Assert-True (-not ($s.capabilities.start -or $s.capabilities.stop -or $s.capabilities.restart)) 'no lifecycle requests while one is running'

    # 5. A controlled stop is not disguised as STARTING or STOPPED
    Set-Marker -Action 'stop'
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal $s.state 'DEGRADED' 'stop in progress'
    Assert-Equal @($s.degradedReasons).Count 1 'stop reason present'

    # 6. A marker whose process is gone is stale and must not pin the state
    Set-Marker -Action 'start' -ProcessId 2147483000
    Set-Seams -Wsl { $true } -Probe { param($r) & $global:JarvisNewProbe -State 'READY' }
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Equal $s.state 'READY' 'stale marker ignored'
    Clear-Marker

    # 7. Anything the probe gets wrong becomes a contract-valid ERROR, never a repaired state
    $bad = [ordered]@{
        'not json' = { param($r) 'this is not json' }
        'missing capabilities' = { param($r) '{"state":"READY","degradedReasons":[],"updatedAt":"2026-09-25T00:00:00Z","components":[]}' }
        'unknown state' = { param($r) '{"state":"GREAT","degradedReasons":[],"updatedAt":"2026-09-25T00:00:00Z","components":[],"capabilities":{"start":false,"stop":true,"restart":true}}' }
        'probe throws' = { param($r) throw 'Die Runtime-Probe hat das Zeitlimit ueberschritten.' }
        'capability as string' = { param($r) '{"state":"READY","degradedReasons":[],"updatedAt":"2026-09-25T00:00:00Z","components":[],"capabilities":{"start":"false","stop":true,"restart":true}}' }
    }
    foreach ($name in $bad.Keys) {
        Set-Seams -Wsl { $true } -Probe $bad[$name]
        $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
        Assert-Contract $s
        Assert-Equal $s.state 'ERROR' "invalid probe ($name)"
        Assert-True ($s.detail -like 'Runtime-Probe nicht auswertbar*') "error detail for ($name)"
        Assert-True ($s.capabilities.start -eq $false) "no capability guessed for ($name)"
    }

    # 7b. Null entries in components are skipped, one-element lists stay arrays
    Set-Seams -Wsl { $true } -Probe { param($r) '{"state":"DEGRADED","degradedReasons":["one"],"updatedAt":"2026-09-25T00:00:00Z","components":[null,{"id":"a","name":"A","state":"READY"}],"capabilities":{"start":false,"stop":true,"restart":true}}' }
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal @($s.components).Count 1 'null component skipped'
    Assert-True ((($s | ConvertTo-Json -Depth 6) -match '"degradedReasons":\s*\[\s*"one"\s*\]')) 'single reason stays an array'

    # 7c. A controlled stop while WSL is already down is a stop, not a start
    Set-Seams -Wsl { $false }
    Set-Marker -Action 'stop'
    $s = Get-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-Contract $s
    Assert-Equal $s.state 'DEGRADED' 'stop with WSL down'
    Assert-True (-not ($s.capabilities.start -or $s.capabilities.stop -or $s.capabilities.restart)) 'no requests during stop'
    Clear-Marker

    # 8. Lifecycle requests are gated by the supervisor's own capabilities
    $global:JarvisSpawned = [System.Collections.Generic.List[string]]::new()
    & $module { $script:JarvisActionSpawner = { param($Action, $Root) $global:JarvisSpawned.Add($Action) } }
    Set-Seams -Wsl { $true } -Probe { param($r) & $global:JarvisNewProbe -State 'READY' }
    $r = Invoke-JarvisRuntimeAction -Action start -RepositoryRoot $repoRoot
    Assert-True (-not $r.accepted) 'start while READY is rejected'
    Assert-Equal $global:JarvisSpawned.Count 0 'rejected start spawned nothing'
    $r = Invoke-JarvisRuntimeAction -Action restart -RepositoryRoot $repoRoot
    Assert-True $r.accepted 'restart while READY is accepted'
    Assert-Equal ($global:JarvisSpawned -join ',') 'restart' 'restart spawned exactly once'
    Set-Seams -Wsl { $false }
    $r = Invoke-JarvisRuntimeAction -Action start -RepositoryRoot $repoRoot
    Assert-True $r.accepted 'start while OFFLINE is accepted'
    $r = Invoke-JarvisRuntimeAction -Action stop -RepositoryRoot $repoRoot
    Assert-True (-not $r.accepted) 'stop while OFFLINE is rejected'
    Assert-Equal ($global:JarvisSpawned -join ',') 'restart,start' 'only accepted requests spawned'
    Set-Marker -Action 'start'
    Set-Seams -Wsl { $true } -Probe { param($r) & $global:JarvisNewProbe -State 'READY' }
    $r = Invoke-JarvisRuntimeAction -Action restart -RepositoryRoot $repoRoot
    Assert-True (-not $r.accepted) 'a second lifecycle request while one is running is rejected'
    Clear-Marker
    & $module { $script:JarvisActionSpawner = $null }

    # 9. The action set is closed: no way to pass a command through the entry point
    $entry = Join-Path $repoRoot 'JARVIS-Runtime.ps1'
    $hostExe = (Get-Process -Id $PID).Path
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 promotes the expected native stderr to an error record.
        $ErrorActionPreference = 'Continue'
        $null = & $hostExe -NoProfile -ExecutionPolicy Bypass -File $entry -Action 'whoami' 2>&1
        $rejectedExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    Assert-True ($rejectedExit -ne 0) 'entry point must reject actions outside the closed set'
    Assert-True ((Get-Content -LiteralPath $entry -Raw) -notmatch 'Invoke-Expression|\biex\b') 'entry point must not evaluate input'

    # 10. Lifecycle marker: present while the lifecycle runs (mutex held), cleared after success and failure
    $global:JarvisMarkerPath = Get-MarkerPath
    & $module {
        $script:JarvisRuntimeInvoker = {
            param($Action, $Root)
            $global:JarvisMarkerSeen = Test-Path -LiteralPath $global:JarvisMarkerPath
            if ($global:JarvisFail) { throw 'boom' }
        }
        $script:JarvisKeepaliveEnsureInvoker = { param($Root) $false }
        $script:JarvisKeepaliveStopInvoker = { param($Root) }
    }
    $global:JarvisFail = $false
    Start-JarvisRuntime -RepositoryRoot $repoRoot
    Assert-True $global:JarvisMarkerSeen 'marker exists while the lifecycle runs'
    Assert-True (-not (Test-Path -LiteralPath $global:JarvisMarkerPath)) 'marker removed after a successful lifecycle'
    $global:JarvisFail = $true
    $failed = $false
    try { Restart-JarvisRuntime -RepositoryRoot $repoRoot } catch { $failed = ($_.Exception.Message -eq 'boom') }
    Assert-True $failed 'failure propagates unchanged'
    Assert-True (-not (Test-Path -LiteralPath $global:JarvisMarkerPath)) 'marker removed after a failed lifecycle'

    # 11. -Wait runs the real lifecycle path and reports failures as not accepted
    Set-Seams -Wsl { $false }
    $global:JarvisFail = $false
    $r = Invoke-JarvisRuntimeAction -Action start -RepositoryRoot $repoRoot -Wait
    Assert-True $r.accepted 'synchronous start accepted'
    $global:JarvisFail = $true
    $r = Invoke-JarvisRuntimeAction -Action start -RepositoryRoot $repoRoot -Wait
    Assert-True (-not $r.accepted) 'failed synchronous start is reported as not accepted'
    Assert-True ($r.message -like '*boom*') 'failure message is preserved'

    Write-Output 'PASS: supervisor OFFLINE/STARTING/passthrough/ERROR contract, gated lifecycle requests, closed action set, lifecycle marker.'
} finally {
    Set-Seams
    & $module { $script:JarvisRuntimeInvoker = $null; $script:JarvisKeepaliveEnsureInvoker = $null; $script:JarvisKeepaliveStopInvoker = $null; $script:JarvisActionSpawner = $null }
    Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
