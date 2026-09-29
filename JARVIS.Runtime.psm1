Set-StrictMode -Version Latest

$script:JarvisDistro = 'Ubuntu-24.04'
$script:JarvisRuntimeInvoker = $null
$script:JarvisKeepaliveEnsureInvoker = $null
$script:JarvisKeepaliveStopInvoker = $null

function Get-JarvisKeepaliveIdentity {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($RepositoryRoot.ToLowerInvariant())
    $hash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).Replace('-', '').ToLowerInvariant().Substring(0, 16)
    [pscustomobject]@{
        Marker = "jarvis_keepalive_$hash"
        StateDirectory = Join-Path (Join-Path $env:LOCALAPPDATA 'JARVIS\Runtime') $hash
    }
}

function Get-JarvisKeepaliveProcesses {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Marker)

    $wsl = (Get-Command 'wsl.exe' -ErrorAction Stop).Source
    $escapedMarker = [System.Text.RegularExpressions.Regex]::Escape($Marker)
    $allProcesses = @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'wsl.exe'" -ErrorAction Stop)
    $matches = @($allProcesses | Where-Object {
        $_.ExecutablePath -and
        [string]::Equals([System.IO.Path]::GetFullPath($_.ExecutablePath), [System.IO.Path]::GetFullPath($wsl), [System.StringComparison]::OrdinalIgnoreCase) -and
        $_.CommandLine -and
        $_.CommandLine -match "--distribution\s+$([System.Text.RegularExpressions.Regex]::Escape($script:JarvisDistro))\s+--exec\s+/usr/bin/bash\s+-c\s+`"exec\s+-a\s+$escapedMarker\s+/usr/bin/sleep\s+infinity`""
    })
    $matchedIds = @($matches | ForEach-Object { [int]$_.ProcessId })
    @($matches | Where-Object { [int]$_.ParentProcessId -notin $matchedIds })
}

function Ensure-JarvisKeepalive {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    if ($null -ne $script:JarvisKeepaliveEnsureInvoker) {
        return [bool](& $script:JarvisKeepaliveEnsureInvoker $RepositoryRoot)
    }

    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $RepositoryRoot
    $existing = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker)
    if ($existing.Count -gt 1) {
        throw 'Mehrere JARVIS-WSL-Keepalives mit derselben Runtime-Identität laufen; es wurde kein weiterer gestartet.'
    }
    if ($existing.Count -eq 1) {
        return $false
    }

    $null = New-Item -ItemType Directory -Path $identity.StateDirectory -Force
    $statePath = Join-Path $identity.StateDirectory 'keepalive.json'
    $state = [ordered]@{
        distribution = $script:JarvisDistro
        marker = $identity.Marker
        processId = $null
        startedUtc = [DateTime]::UtcNow.ToString('o')
    }
    $temporaryStatePath = "$statePath.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        $state | ConvertTo-Json | Set-Content -LiteralPath $temporaryStatePath -Encoding UTF8
        Move-Item -LiteralPath $temporaryStatePath -Destination $statePath -Force
        $wsl = Get-Command 'wsl.exe' -ErrorAction Stop
        $arguments = @('--distribution', $script:JarvisDistro, '--exec', '/usr/bin/bash', '-c', '"exec -a ' + $identity.Marker + ' /usr/bin/sleep infinity"')
        $process = Start-Process -FilePath $wsl.Source -ArgumentList $arguments -WindowStyle Hidden -PassThru -ErrorAction Stop
        Start-Sleep -Milliseconds 750
        $process.Refresh()
        if ($process.HasExited) {
            throw "Der JARVIS-WSL-Keepalive wurde unmittelbar beendet (exit $($process.ExitCode))."
        }
        $state.processId = $process.Id
        $temporaryStatePath = "$statePath.$([Guid]::NewGuid().ToString('N')).tmp"
        $state | ConvertTo-Json | Set-Content -LiteralPath $temporaryStatePath -Encoding UTF8
        Move-Item -LiteralPath $temporaryStatePath -Destination $statePath -Force
        return $true
    } catch {
        Remove-Item -LiteralPath $temporaryStatePath -Force -ErrorAction SilentlyContinue
        $owned = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker -ErrorAction SilentlyContinue)
        foreach ($candidate in $owned) {
            if ($state.processId -and [int]$candidate.ProcessId -ne [int]$state.processId) { continue }
            try {
                $null = & (Get-Command 'wsl.exe' -ErrorAction Stop).Source --distribution $script:JarvisDistro --exec /usr/bin/pkill --signal TERM --full --exact "^$($identity.Marker) infinity$" 2>$null
            } catch { }
        }
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
        throw
    }
}

function Stop-JarvisKeepalive {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    if ($null -ne $script:JarvisKeepaliveStopInvoker) {
        & $script:JarvisKeepaliveStopInvoker $RepositoryRoot
        return
    }

    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $RepositoryRoot
    $statePath = Join-Path $identity.StateDirectory 'keepalive.json'
    $owned = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker)
    if ($owned.Count -gt 1) {
        throw 'Mehrere JARVIS-WSL-Keepalives mit derselben Runtime-Identität laufen; Stop wurde aus Sicherheitsgründen abgebrochen.'
    }
    if ($owned.Count -eq 1) {
        $processId = [int]$owned[0].ProcessId
        $null = & (Get-Command 'wsl.exe' -ErrorAction Stop).Source --distribution $script:JarvisDistro --exec /usr/bin/pkill --signal TERM --full --exact "^$($identity.Marker) infinity$"
        if ($LASTEXITCODE -notin @(0, 1)) {
            throw "Das JARVIS-WSL-Keepalive konnte nicht sauber beendet werden (pkill exit $LASTEXITCODE)."
        }
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            $stillOwned = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker)
            if (-not ($stillOwned | Where-Object { [int]$_.ProcessId -eq $processId })) { break }
            Start-Sleep -Milliseconds 100
        }
        if (@(Get-JarvisKeepaliveProcesses -Marker $identity.Marker).Count -gt 0) {
            throw 'Das JARVIS-WSL-Keepalive reagiert nicht auf den sauberen Stop.'
        }
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
}

function Invoke-JarvisWsl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('start', 'stop', 'restart')][string]$Action,
        [string]$RepositoryRoot = $PSScriptRoot
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $resolvedRoot
    $mutex = [System.Threading.Mutex]::new($false, "Local\JARVIS_Runtime_$($identity.Marker)")
    $hasMutex = $false
    $startedKeepalive = $false
    try {
        try { $hasMutex = $mutex.WaitOne([TimeSpan]::FromMinutes(5)) }
        catch [System.Threading.AbandonedMutexException] { $hasMutex = $true }
        if (-not $hasMutex) { throw 'Ein anderer JARVIS-Lifecycle-Aufruf hat den Lock nicht rechtzeitig freigegeben.' }
        Set-JarvisLifecycleMarker -Identity $identity -Action $Action

        if ($null -ne $script:JarvisRuntimeInvoker) {
            if ($Action -in @('start', 'restart')) {
                $startedKeepalive = Ensure-JarvisKeepalive -RepositoryRoot $resolvedRoot
            }
            & $script:JarvisRuntimeInvoker $Action $resolvedRoot
            if ($Action -eq 'stop') { Stop-JarvisKeepalive -RepositoryRoot $resolvedRoot }
            return
        }
    $wsl = Get-Command 'wsl.exe' -ErrorAction Stop
    $null = & $wsl.Source --distribution $script:JarvisDistro --exec /usr/bin/test -x /usr/bin/bash
    if ($LASTEXITCODE -ne 0) {
        throw "WSL-Distribution '$($script:JarvisDistro)' ist nicht verfügbar oder kein Ubuntu-System."
    }

    $relativeScript = switch ($Action) {
        'start' { 'start.sh' }
        'stop' { 'stop.sh' }
        'restart' { 'restart.sh' }
    }
    $wslPathOutput = & $wsl --distribution $script:JarvisDistro --exec wslpath -u $resolvedRoot
    if ($LASTEXITCODE -ne 0 -or -not $wslPathOutput) {
        throw 'Der Repository-Pfad konnte nicht in einen WSL-Pfad übersetzt werden.'
    }
    $wslRoot = ([string]$wslPathOutput).Trim()
    $null = & $wsl --distribution $script:JarvisDistro --cd $wslRoot --exec /usr/bin/test -f "./$relativeScript"
    if ($LASTEXITCODE -ne 0) {
        throw "Das Lifecycle-Skript '$relativeScript' fehlt im WSL-Checkout."
    }
    $null = & $wsl --distribution $script:JarvisDistro --cd $wslRoot --exec systemctl --user show-environment
    if ($LASTEXITCODE -ne 0) {
        throw 'Der systemd User-Manager in WSL ist nicht erreichbar.'
    }
        if ($Action -in @('start', 'restart')) {
            $startedKeepalive = Ensure-JarvisKeepalive -RepositoryRoot $resolvedRoot
        }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell can promote native stderr to an error record. Keep
        # it non-terminating here so we can preserve the lifecycle's diagnosis.
        $ErrorActionPreference = 'Continue'
        $runtimeOutput = & $wsl.Source --distribution $script:JarvisDistro --cd $wslRoot --exec /usr/bin/bash "./$relativeScript" 2>&1
        $runtimeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    foreach ($line in @($runtimeOutput)) {
        [Console]::Out.WriteLine([string]$line)
    }
    if ($runtimeExitCode -ne 0) {
        throw "JARVIS-$Action ist fehlgeschlagen (WSL exit $runtimeExitCode)."
    }
        if ($Action -eq 'stop') { Stop-JarvisKeepalive -RepositoryRoot $resolvedRoot }
    } catch {
        if ($startedKeepalive) {
            try { Stop-JarvisKeepalive -RepositoryRoot $resolvedRoot }
            catch { Write-Warning "Der in diesem Startlauf erzeugte Keepalive konnte nicht bereinigt werden: $($_.Exception.Message)" }
        }
        throw
    } finally {
        if ($hasMutex) {
            Clear-JarvisLifecycleMarker -Identity $identity
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}

# --- Runtime supervisor (read side + lifecycle requests) ---------------------------------------
#
# Native control plane for the UI/Tauri shell. It lives on Windows, independent of the voice
# daemon, and offers exactly four operations: Get-JarvisRuntime and start/stop/restart. There is
# deliberately no way to run arbitrary commands. The runtime state is NOT decided here: it is
# read from scripts/runtime_status.py (WSL side, derived from facts). This module only adds what
# the WSL side cannot know: WSL not running (OFFLINE) and a lifecycle that is still booting WSL.
#
# Kept compatible with Windows PowerShell 5.1 (used by JARVIS-*.cmd) and ASCII-only.

$script:JarvisRuntimePython = '/home/alex/jarvis-venv/bin/python3'
$script:JarvisProbeTimeoutSeconds = 45
$script:JarvisRuntimeStates = @('STARTING', 'READY', 'DEGRADED', 'ERROR', 'STOPPED', 'OFFLINE', 'NOT_IMPLEMENTED')
$script:JarvisProbeInvoker = $null       # test seam: { param($RepositoryRoot) } -> probe JSON text
$script:JarvisWslRunningInvoker = $null  # test seam: { } -> [bool]
$script:JarvisActionSpawner = $null      # test seam: { param($Action, $RepositoryRoot) }

function Get-JarvisNowIso {
    [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
}

function Set-JarvisLifecycleMarker {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Identity, [Parameter(Mandatory)][string]$Action)

    try {
        $null = New-Item -ItemType Directory -Path $Identity.StateDirectory -Force
        $path = Join-Path $Identity.StateDirectory 'lifecycle.json'
        $temporary = "$path.$([Guid]::NewGuid().ToString('N')).tmp"
        ([ordered]@{ action = $Action; processId = $PID; startedUtc = [DateTime]::UtcNow.ToString('o') } |
            ConvertTo-Json) | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $path -Force
    } catch {
        Write-Warning "Der JARVIS-Lifecycle-Marker konnte nicht geschrieben werden: $($_.Exception.Message)"
    }
}

function Clear-JarvisLifecycleMarker {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Identity)
    Remove-Item -LiteralPath (Join-Path $Identity.StateDirectory 'lifecycle.json') -Force -ErrorAction SilentlyContinue
}

function Get-JarvisLifecycleMarker {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Identity)

    $path = Join-Path $Identity.StateDirectory 'lifecycle.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { $marker = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json } catch { return $null }
    # A marker whose owning process is gone is stale (crashed lifecycle), not an active lifecycle.
    if ($marker.action -notin @('start', 'stop', 'restart') -or -not $marker.processId) { return $null }
    $owner = Get-Process -Id ([int]$marker.processId) -ErrorAction SilentlyContinue
    if (-not $owner -or $owner.ProcessName -notin @('powershell', 'pwsh')) { return $null }
    # Lifecycles are bounded (LLM load + listener wait); an older marker is stale, not "still running".
    $started = [DateTime]::MinValue
    if ($marker.startedUtc -is [DateTime]) { $started = $marker.startedUtc }
    elseif (-not [DateTime]::TryParse([string]$marker.startedUtc, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind, [ref]$started)) { return $null }
    if (([DateTime]::UtcNow - $started.ToUniversalTime()).TotalMinutes -gt 30) { return $null }
    $marker
}

function ConvertTo-JarvisNativeArgument {
    param([Parameter(Mandatory)][string]$Value)
    # Only quote when needed: wsl.exe treats a quoted "--option" as a command, not an option.
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Invoke-JarvisNative {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [System.Text.Encoding]$Encoding = [System.Text.Encoding]::UTF8,
        [int]$TimeoutSeconds = 20
    )

    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $FilePath
    $info.Arguments = (($Arguments | ForEach-Object { ConvertTo-JarvisNativeArgument -Value $_ }) -join ' ')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = $Encoding
    $info.StandardErrorEncoding = $Encoding
    $process = [System.Diagnostics.Process]::Start($info)
    try {
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            return [pscustomobject]@{ TimedOut = $true; ExitCode = -1; Output = '' }
        }
        $process.WaitForExit()
        [pscustomobject]@{ TimedOut = $false; ExitCode = $process.ExitCode; Output = [string]$stdout.Result; ErrorOutput = [string]$stderr.Result }
    } finally {
        $process.Dispose()
    }
}

# $true / $false, or $null when wsl.exe itself is missing. Never starts the distribution.
function Test-JarvisWslRunning {
    [CmdletBinding()]
    param()

    if ($null -ne $script:JarvisWslRunningInvoker) { return [bool](& $script:JarvisWslRunningInvoker) }
    $wsl = Get-Command 'wsl.exe' -ErrorAction SilentlyContinue
    if (-not $wsl) { return $null }
    $result = Invoke-JarvisNative -FilePath $wsl.Source -Arguments @('--list', '--running', '--quiet') -Encoding ([System.Text.Encoding]::Unicode) -TimeoutSeconds 15
    if ($result.TimedOut -or $result.ExitCode -ne 0) { return $false }
    $names = @($result.Output -split "`r?`n" | ForEach-Object { $_.Trim([char]0xFEFF, [char]0, ' ', "`t") })
    $names -contains $script:JarvisDistro
}

function Read-JarvisProbe {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    if ($null -ne $script:JarvisProbeInvoker) { return [string](& $script:JarvisProbeInvoker $RepositoryRoot) }
    $wsl = (Get-Command 'wsl.exe' -ErrorAction Stop).Source
    $translated = Invoke-JarvisNative -FilePath $wsl -Arguments @('--distribution', $script:JarvisDistro, '--exec', 'wslpath', '-u', $RepositoryRoot) -TimeoutSeconds 15
    if ($translated.TimedOut -or $translated.ExitCode -ne 0 -or -not $translated.Output.Trim()) {
        throw 'Der Repository-Pfad konnte nicht in einen WSL-Pfad uebersetzt werden.'
    }
    $probe = Invoke-JarvisNative -FilePath $wsl -Arguments @(
        '--distribution', $script:JarvisDistro, '--cd', $translated.Output.Trim(), '--exec',
        $script:JarvisRuntimePython, 'scripts/runtime_status.py', '--json') -TimeoutSeconds $script:JarvisProbeTimeoutSeconds
    if ($probe.TimedOut) { throw 'Die Runtime-Probe hat das Zeitlimit ueberschritten.' }
    if ($probe.ExitCode -ne 0) { throw "Die Runtime-Probe ist fehlgeschlagen (exit $($probe.ExitCode))." }
    $probe.Output
}

# Validates the probe against the UI contract. Anything else is an ERROR, never repaired.
function ConvertFrom-JarvisProbe {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Json)

    $raw = $Json | ConvertFrom-Json -ErrorAction Stop
    $names = @($raw.PSObject.Properties | ForEach-Object { $_.Name })
    foreach ($required in 'state', 'degradedReasons', 'updatedAt', 'components', 'capabilities') {
        if ($names -notcontains $required) { throw "Feld '$required' fehlt." }
    }
    if ($script:JarvisRuntimeStates -notcontains [string]$raw.state) { throw 'Unbekannter state.' }
    $updatedAt = $raw.updatedAt
    if ($updatedAt -is [DateTime]) { $updatedAt = $updatedAt.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }
    $components = @()
    foreach ($item in @($raw.components)) {
        if ($null -eq $item) { continue }
        $component = [ordered]@{ id = [string]$item.id; name = [string]$item.name; state = [string]$item.state }
        if ($item.PSObject.Properties['detail']) { $component['detail'] = [string]$item.detail }
        $components += , $component
    }
    # [bool]"false" is $true in PowerShell: only genuine JSON booleans are accepted.
    foreach ($capability in 'start', 'stop', 'restart') {
        if ($raw.capabilities.$capability -isnot [bool]) { throw "capabilities.$capability ist kein Boolean." }
    }
    $snapshot = [ordered]@{
        state = [string]$raw.state
        degradedReasons = @($raw.degradedReasons | ForEach-Object { [string]$_ })
        updatedAt = [string]$updatedAt
        components = $components
        capabilities = [ordered]@{
            start = [bool]$raw.capabilities.start
            stop = [bool]$raw.capabilities.stop
            restart = [bool]$raw.capabilities.restart
        }
    }
    if ($names -contains 'detail' -and $raw.detail) { $snapshot['detail'] = [string]$raw.detail }
    $snapshot
}

function New-JarvisRuntimeSnapshot {
    param(
        [Parameter(Mandatory)][string]$State,
        [string[]]$Reasons = @(),
        $Components = @(),
        [string]$Detail = '',
        [bool]$Start = $false
    )
    $snapshot = [ordered]@{
        state = $State
        degradedReasons = @($Reasons)
        updatedAt = Get-JarvisNowIso
        components = @($Components)
        capabilities = [ordered]@{ start = $Start; stop = $false; restart = $false }
    }
    if ($Detail) { $snapshot['detail'] = $Detail }
    $snapshot
}

function Get-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)

    $resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $resolvedRoot
    $marker = Get-JarvisLifecycleMarker -Identity $identity

    $running = Test-JarvisWslRunning
    if ($null -eq $running) {
        return New-JarvisRuntimeSnapshot -State OFFLINE -Detail 'wsl.exe ist nicht verfuegbar.'
    }
    if (-not $running) {
        if ($marker -and $marker.action -eq 'stop') {
            return New-JarvisRuntimeSnapshot -State DEGRADED -Reasons @('Ein kontrollierter Stop laeuft.') -Detail 'Stop laeuft.'
        }
        if ($marker) {
            return New-JarvisRuntimeSnapshot -State STARTING -Detail "Kontrollierter $($marker.action) laeuft; WSL wird gestartet."
        }
        return New-JarvisRuntimeSnapshot -State OFFLINE -Start $true -Detail "WSL-Distribution '$($script:JarvisDistro)' laeuft nicht."
    }

    $snapshot = $null
    $probeError = ''
    try { $snapshot = ConvertFrom-JarvisProbe -Json (Read-JarvisProbe -RepositoryRoot $resolvedRoot) }
    catch { $probeError = $_.Exception.Message }

    if ($marker) {
        # A lifecycle owned by this supervisor is running: it wins over whatever the probe saw mid-flight.
        $components = if ($snapshot) { $snapshot.components } else { @() }
        if ($marker.action -eq 'stop') {
            return New-JarvisRuntimeSnapshot -State DEGRADED -Reasons @('Ein kontrollierter Stop laeuft.') -Components $components -Detail 'Stop laeuft.'
        }
        return New-JarvisRuntimeSnapshot -State STARTING -Components $components -Detail "Kontrollierter $($marker.action) laeuft."
    }
    if (-not $snapshot) {
        return New-JarvisRuntimeSnapshot -State ERROR -Detail "Runtime-Probe nicht auswertbar: $probeError"
    }
    $snapshot
}

function Invoke-JarvisRuntimeAction {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('start', 'stop', 'restart')][string]$Action,
        [string]$RepositoryRoot = $PSScriptRoot,
        [switch]$Wait
    )

    $snapshot = Get-JarvisRuntime -RepositoryRoot $RepositoryRoot
    if (-not $snapshot.capabilities[$Action]) {
        return [ordered]@{ accepted = $false; message = "'$Action' ist im Zustand $($snapshot.state) nicht erlaubt." }
    }
    if ($Wait) {
        try {
            switch ($Action) {
                'start' { Start-JarvisRuntime -RepositoryRoot $RepositoryRoot }
                'stop' { Stop-JarvisRuntime -RepositoryRoot $RepositoryRoot }
                'restart' { Restart-JarvisRuntime -RepositoryRoot $RepositoryRoot }
            }
        } catch {
            return [ordered]@{ accepted = $false; message = "$Action ist fehlgeschlagen: $($_.Exception.Message)" }
        }
        return [ordered]@{ accepted = $true; message = "$Action wurde abgeschlossen; der Zustand ergibt sich aus getRuntime." }
    }
    try {
        if ($null -ne $script:JarvisActionSpawner) {
            & $script:JarvisActionSpawner $Action $RepositoryRoot
        } else {
            # Detached: the lifecycle can take minutes (LLM load); the caller polls getRuntime.
            $script = Join-Path $RepositoryRoot ('JARVIS-{0}.ps1' -f (Get-Culture).TextInfo.ToTitleCase($Action))
            $hostExe = (Get-Process -Id $PID).Path
            $null = Start-Process -FilePath $hostExe -WindowStyle Hidden -ArgumentList @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (ConvertTo-JarvisNativeArgument -Value $script))
        }
    } catch {
        return [ordered]@{ accepted = $false; message = "$Action konnte nicht gestartet werden: $($_.Exception.Message)" }
    }
    [ordered]@{ accepted = $true; message = "$Action wurde angenommen; der Zustand ergibt sich aus getRuntime." }
}

function Start-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)
    Invoke-JarvisWsl -Action start -RepositoryRoot $RepositoryRoot
}

function Stop-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)
    Invoke-JarvisWsl -Action stop -RepositoryRoot $RepositoryRoot
}

function Restart-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)
    Invoke-JarvisWsl -Action restart -RepositoryRoot $RepositoryRoot
}

Export-ModuleMember -Function Start-JarvisRuntime, Stop-JarvisRuntime, Restart-JarvisRuntime, Get-JarvisRuntime, Invoke-JarvisRuntimeAction
